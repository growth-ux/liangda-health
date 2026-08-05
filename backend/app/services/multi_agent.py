import json
import logging
import queue
import threading

from app.core.config import settings
from app.services.langchain_agent import (
    BaseAgentRunner,
    _build_members_block,
    _content_to_text,
)
from app.services.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


AGENT_LABELS = {
    "supervisor": "调度中心",
    "meal_planner": "餐单规划师",
    "shopping_guide": "商品导购师",
    "report_reader": "报告解读师",
}


SUPERVISOR_PROMPT_TEMPLATE = """你是粮达健康的家庭健康管家「总调度 Agent」。你不直接干活，而是把任务分派给手下三位专家 Agent，再汇总他们的结果回复用户。

专家工具：
- ask_meal_planner(task)：餐单规划师，处理"吃什么/三餐/今晚做什么"类问题，他会自己查记忆和生成餐单。
- ask_shopping_guide(task)：商品导购师，处理商品/类目推荐。任务里带餐单文本时按餐单推荐；用户只问某类商品（油/米/调料/坚果/牛奶/零食等）时把用户原问题写进任务，不要先找餐单规划师。
- ask_report_reader(task)：报告解读师，只有用户明确问报告/体检结果时才调用，任务里写清家人和问题。

调度规则：
1. 三餐/吃什么问题：先调 ask_meal_planner；拿到餐单后，把餐单文本原样写进 ask_shopping_guide 的任务里继续推荐商品。
2. 纯商品/类目问题：直接调 ask_shopping_guide。
3. 专家返回以 "Error:" 开头的结果时，温和降级说明（如"暂时无法推荐商品"），同一专家最多重试 1 次。
4. 简单寒暄、普通健康问答不需要调度专家，直接调用 respond。
{members_block}
回复风格：
1. 用简体中文回答，不做诊断，不替代医生。
2. 语气像日常健康顾问，回复短一点、口语一点，优先说用户马上能理解和执行的做法。
3. 商品推荐结果会由系统自动附加商品卡片，不要把商品名、价格、推荐理由写进你的文本回复。
4. 餐单/报告解读这类信息密集回复，summary_text 只写"结论 + 关键安排 + 注意点"。
5. 餐单份量默认用日常说法（一小碗、一盘、一杯、一掌心），不要展开克数；只有用户明确要求精确克数或热量时才给。
6. 【硬性禁止】面向用户的文本中绝不能出现 member_id、session_id 等内部标识符，称呼家人用姓名或家庭称呼。

【硬性要求】完成一次用户回复必须调用 respond 工具，不能直接用普通文本对用户说话。respond 参数：
- kind：5 选 1——meal_plan / qa / greeting / kb_interpretation / general_advice
- summary_text：Markdown 摘要（≤400字），易扫读，可用少量加粗、emoji、短列表
- payload：按 kind 决定的结构化字段：
  * meal_plan.payload：scope / target_member_name / meal_items[] (slot/title/summary) / member_adjustments[] (member_name/note/tags) / avoid_tags[] / extra_note
  * qa.payload：question_topic / answer / tips[]
  * greeting.payload：message / suggested_topics[]
  * kb_interpretation.payload：topic / evidence[] (source/excerpt) / suggestions[] (text/priority) / red_flags[]
  * general_advice.payload：topic / advice / cautions[]
完成专家调度后立即调用 respond，调完不要再追加任何普通文本。
"""


MEAL_PLANNER_PROMPT_TEMPLATE = """你是粮达健康的「餐单规划师」专家 Agent，只对总调度负责，不直接面对用户。
工作流程：
1. 先用 memory_search 查询任务涉及家人（或全家）的饮食偏好和排斥；明确指向某位家人时传 member_id，全家不传。
2. 再调用 meal_plan 生成餐单：scope/member_id 按任务判断，全家用 family。
3. 把 meal_plan 返回的餐单文本作为最终回复原样返回，不要加评论、不要改写。
4. 任何工具返回 "Error:" 开头时，直接把该 Error 文本作为最终回复返回。
5. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌和健康安全约束。
6. 最终回复中不得出现 member_id 等内部标识符。
{members_block}
"""


SHOPPING_GUIDE_PROMPT_TEMPLATE = """你是粮达健康的「商品导购师」专家 Agent，只对总调度负责。
工作流程：
1. 任务里带餐单文本时：调用 mall_recommend，把餐单文本原样作为 meal_plan_text；scope/member_id 与任务描述一致，全家用 family。
2. 任务只问某类商品时：meal_plan_text 留空，把用户原问题放进 query_text。
3. 把 mall_recommend 返回的原始结果字符串作为最终回复原样返回，不要改写或总结。
4. 工具返回 "Error:" 开头时，直接原样返回该 Error 文本。
{members_block}
"""


REPORT_READER_PROMPT_TEMPLATE = """你是粮达健康的「报告解读师」专家 Agent，只对总调度负责。
工作流程：
1. 按任务中的 member_id 调用 kb_search 检索报告片段；跨家人对比时对每位家人分别检索再合成。
2. 基于检索结果给出简洁解读：说明来自哪份报告或页码，不做诊断，不替代医生。
3. 检索无结果或工具返回 "Error:" 时如实说明。
4. 最终回复中不得出现 member_id 等内部标识符，称呼家人用姓名或家庭称呼。
{members_block}
"""


class MultiAgentRunner(BaseAgentRunner):
    """Supervisor + 3 专家 Agent 的多 Agent runner，接口与 BaseAgentRunner 一致。"""

    SYSTEM_PROMPT_TEMPLATE = SUPERVISOR_PROMPT_TEMPLATE

    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, mall_recommend_tool=None, member_provider=None):
        super().__init__(
            kb_tool=kb_tool,
            meal_plan_tool=meal_plan_tool,
            memory_tool=memory_tool,
            mall_recommend_tool=mall_recommend_tool,
            member_provider=member_provider,
        )
        self._activity_queue = None
        self._product_payloads = []
        self._experts_cache = None

    # ---- 提示词 ----

    def _expert_prompt(self, template: str) -> str:
        return template.format(members_block=_build_members_block(self.member_provider()))

    # ---- 工具注册 ----

    def _tools(self):
        def ask_meal_planner(task: str) -> str:
            """把三餐/吃什么类任务交给餐单规划师。task 里写清用户诉求、scope（family/member）和 member_id。"""
            return self._run_expert("meal_planner", task)

        def ask_shopping_guide(task: str) -> str:
            """把商品推荐任务交给商品导购师。带餐单时 task 原样附餐单文本；只问商品类目时写用户原问题。"""
            return self._run_expert("shopping_guide", task)

        def ask_report_reader(task: str) -> str:
            """把报告检索和解读任务交给报告解读师。task 里写清 member_id 和用户问题。"""
            return self._run_expert("report_reader", task)

        from app.services.langchain_agent import _RESPOND_TOOL

        return [ask_meal_planner, ask_shopping_guide, ask_report_reader, _RESPOND_TOOL]

    def _meal_planner_tools(self):
        tools = []
        if self.meal_plan_tool is not None:
            def meal_plan(scope: str, member_id: str | None = None, goal: str | None = None, meal_type: str = "day") -> str:
                """根据单人或全家健康状态生成一日三餐或指定餐次建议。"""
                logger.info("expert tool call name=meal_plan scope=%s member_id=%s meal_type=%s", scope, member_id, meal_type)
                return self.meal_plan_tool.build(scope=scope, member_id=member_id, goal=goal, meal_type=meal_type)

            tools.append(meal_plan)
        if self.memory_tool is not None:
            def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
                """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标。"""
                logger.info("expert tool call name=memory_search member_id=%s limit=%s", member_id, limit)
                return self.memory_tool.search(query=query, member_id=member_id, limit=limit)

            tools.append(memory_search)
        return tools

    def _shopping_guide_tools(self):
        tools = []
        if self.mall_recommend_tool is not None:
            def mall_recommend(scope: str, member_id: str | None = None, meal_plan_text: str = "", query_text: str = "", limit: int = 5) -> str:
                """根据餐单文本或商品类目问题推荐商城商品。"""
                logger.info("expert tool call name=mall_recommend scope=%s member_id=%s limit=%s", scope, member_id, limit)
                raw = self.mall_recommend_tool.recommend(
                    scope=scope,
                    member_id=member_id,
                    meal_plan_text=meal_plan_text,
                    query_text=query_text,
                    limit=limit,
                )
                self._capture_product_payload(raw)
                return raw

            tools.append(mall_recommend)
        return tools

    def _report_reader_tools(self):
        tools = []
        if self.kb_tool is not None:
            def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
                """检索指定家人的健康报告片段。"""
                logger.info("expert tool call name=kb_search member_id=%s top_k=%s", member_id, top_k)
                return self.kb_tool.search(query=query, member_id=member_id, top_k=top_k)

            tools.append(kb_search)
        return tools

    # ---- 专家执行 ----

    def _run_expert(self, agent_key: str, task: str) -> str:
        logger.info("multi_agent expert start agent=%s task_chars=%s", agent_key, len(task))
        self._emit_activity(agent_key, "start", f"{AGENT_LABELS[agent_key]}正在处理…")
        try:
            result = self._expert_invoke(agent_key, task)
        except Exception:
            logger.exception("multi_agent expert failed agent=%s", agent_key)
            result = "Error: 专家处理失败"
        self._emit_activity(agent_key, "done", f"{AGENT_LABELS[agent_key]}完成")
        logger.info("multi_agent expert done agent=%s output_chars=%s", agent_key, len(result))
        return result

    def _expert_invoke(self, agent_key: str, task: str) -> str:
        from langchain_core.messages import HumanMessage

        expert = self._expert_agents()[agent_key]
        response = expert.invoke({"messages": [HumanMessage(content=task)]})
        return _content_to_text(response["messages"][-1].content)

    def _expert_agents(self) -> dict:
        if self._experts_cache is None:
            from langchain.agents import create_agent

            model = self._model()
            self._experts_cache = {
                "meal_planner": create_agent(
                    model=model,
                    tools=self._meal_planner_tools(),
                    system_prompt=self._expert_prompt(MEAL_PLANNER_PROMPT_TEMPLATE),
                ),
                "shopping_guide": create_agent(
                    model=model,
                    tools=self._shopping_guide_tools(),
                    system_prompt=self._expert_prompt(SHOPPING_GUIDE_PROMPT_TEMPLATE),
                ),
                "report_reader": create_agent(
                    model=model,
                    tools=self._report_reader_tools(),
                    system_prompt=self._expert_prompt(REPORT_READER_PROMPT_TEMPLATE),
                ),
            }
        return self._experts_cache

    def _emit_activity(self, agent: str, action: str, detail: str = "") -> None:
        if self._activity_queue is not None:
            self._activity_queue.put(("activity", {"agent": agent, "action": action, "detail": detail}))
