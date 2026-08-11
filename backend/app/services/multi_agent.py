import json
import logging
import queue
import threading
import time

from app.core.config import settings
from app.services.langchain_agent import (
    BaseAgentRunner,
    _build_members_block,
    _content_to_text,
)
from app.services.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


def _strip_heading_prefix(text: str) -> str:
    """清除 LLM 输出中每行开头的 Markdown 标题标记（### / ## / #）。

    报告解读师有时会自作主张用 ### 给每个指标加标题，
    渲染出来会变成大块标题，影响阅读体验。这里统一替换为加粗。
    """
    import re
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = re.sub(r"^#{1,6}\s+", "", line)
        cleaned.append(stripped)
    return "\n".join(cleaned)


AGENT_LABELS = {
    "supervisor": "调度中心",
    "meal_planner": "餐单规划师",
    "shopping_guide": "商品导购师",
    "report_reader": "报告解读师",
}


SUPERVISOR_PROMPT_TEMPLATE = """你是粮达健康的家庭健康管家「总调度 Agent」。你不直接干活，而是把任务分派给手下三位专家 Agent，再汇总他们的结果回复用户。

专家工具：
- ask_meal_planner(task)：餐单规划师，处理“吃什么/三餐/今晚做什么”类问题，他会自己查记忆和生成餐单。
- ask_shopping_guide(task)：商品导购师，处理商品/类目推荐。任务里带餐单文本时按餐单推荐；用户只问某类商品（油/米/调料/坚果/牛奶/零食等）时把用户原问题写进任务，不要先找餐单规划师。
- ask_report_reader(task)：报告解读师，只有用户明确问报告/体检结果时才调用，任务里写清家人和问题。

调度规则：
1. 三餐/吃什么问题：先调 ask_meal_planner；拿到餐单后，把餐单文本原样写进 ask_shopping_guide 的任务里继续推荐商品。
   - 【重要】task 文本必须明确写出 scope 和 member_id：用户提到特定家人（如"爸爸/妈妈/儿子"）时写 scope=member + 对应 member_id；用户说"全家/我们家"时写 scope=family。
   - task 里也要写清 meal_type：用户说"今晚/晚餐"写 dinner，"早餐"写 breakfast，"午餐"写 lunch，"今天/一日三餐"写 day。
   - 拿到餐单后传给 ask_shopping_guide 时，同样要带上与餐单一致的 scope 和 member_id。
2. 纯商品/类目问题：用户明确要"推荐/买/选"某类商品时才调 ask_shopping_guide。
3. 专家返回以 "Error:" 开头的结果时，温和降级说明（如"暂时无法推荐商品"），同一专家最多重试 1 次。
4. 【禁止调 ask_shopping_guide 的场景——违反会货不对板】只要用户的核心意图是"问偏好/习惯/口味"而非"要买/推荐商品"，就绝对不要调 ask_shopping_guide，一律走 memory_search + respond(kind=qa)：
   - 询问偏好："爸爸喜欢吃鱼吗""妈妈爱喝什么茶""儿子爱吃辣吗"
   - 声明偏好/排斥："爸爸不喜欢吃鱼""妈妈不吃辣的""儿子不要海鲜"
   - 问胃口/状态："儿子最近胃口怎么样""爸爸吃得还好吗"
   - 判断方法：句子主语是家人 + 谓语是"喜欢/不喜欢/爱吃/不吃/排斥/胃口"等 → 一定是偏好类，不是商品推荐。
   - 即使问题中出现了食品名（鱼/肉/菜/水果等），只要不是在"推荐/买/选"商品，就不要调商品导购师。
5. 不需要调度专家、直接调用 respond 的其他场景（用 kind=qa 或 kind=greeting）：
   - 简单寒暄："你好""谢谢""晚安"等。
   - 普通健康常识问答："感冒了吃什么好""高血压能喝酒吗"——不涉及具体家人的报告数据。
   - 判断标准：如果回复不需要生成餐单、不需要推荐商品、也不需要查体检报告，就不要调度专家，直接 respond。
{members_block}
反馈重排规则：
- 如果商品导购师返回中包含 replaced_items 列表，说明用户之前对某些商品做了反馈（不喜欢/太贵），系统已自动替换。
- 此时在 summary_text 开头加一句“因您之前的反馈，已调整了部分推荐商品”。不要列出具体被替换的商品名。

卡片类型硬约束：
- 只要本轮调用了 ask_meal_planner，最终 respond.kind 必须是 meal_plan，绝不能使用 general_advice、qa 或其他类型替代。
- 此时 payload 必须按 meal_plan 结构填写：把餐单拆成 meal_items；本轮只有晚餐/午餐/早餐时，也只填对应 slot；同时填写可得出的 member_adjustments、avoid_tags 和 extra_note。

回复风格：
1. 用简体中文回答，不做诊断，不替代医生。
2. 语气像日常健康顾问，口语化，优先说用户马上能理解和执行的做法。
3. 商品推荐结果会由系统自动附加商品卡片，不要把商品名、价格、推荐理由写进你的文本回复。
   - 报告解读回复中禁止出现任何药品名称、处方药/非处方药名称、药物剂量或具体用药方案；如确有用药疑问，只能建议咨询医生或药师。
4. 不同 kind 的 summary_text 长度要求不同，严格遵守：
   - 餐单类（meal_plan）：只写"结论 + 关键安排 + 注意点"，简洁为主。
   - 报告解读（kb_interpretation）：【必须详尽，禁止摘要化】把报告解读师返回的每一条异常指标完整写入 summary_text，不得只保留结论或合并成一句话。每个指标必须包含：指标名称、实测值、参考范围、通俗解读、生活建议、报告来源页码。报告解读师返回了多少异常就写多少，宁可多列也不能遗漏，允许写到 1200 字。这是用户最关心的内容，不要简化、不要改写成“重点有几项”式短摘要。
   - 当报告解读师已返回完整条目时，优先原样保留其条目内容，仅删除内部 member_id 等标识；不要再次概括。
   - 其他类型：一般控制在 400 字以内。
5. 餐单份量默认用日常说法（一小碗、一盘、一杯、一掌心），不要展开克数；只有用户明确要求精确克数或热量时才给。
6. 【硬性禁止】面向用户的文本中绝不能出现 member_id、session_id 等内部标识符，称呼家人用姓名或家庭称呼。

【硬性要求】完成一次用户回复必须调用 respond 工具，不能直接用普通文本对用户说话。respond 参数：
- kind：5 选 1——meal_plan / qa / greeting / kb_interpretation / general_advice
   - summary_text：Markdown 摘要，易扫读，可用少量加粗、emoji、短列表。餐单/一般回复≤400字；报告解读（kind=kb_interpretation）≤1200字，必须把所有异常指标完整列出，且不得省略专家返回的指标详情
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
2. 再调用 meal_plan 生成餐单：
   - 【重要】只要 task 里提到了特定家人和 member_id，就必须用 scope="member" + 对应 member_id，不要用 family。只有 task 明确写 scope=family 时才用 family。
   - meal_type 按 task 描述判断：dinner=晚餐，breakfast=早餐，lunch=午餐，day=一日三餐。
3. 把 meal_plan 返回的餐单文本作为最终回复原样返回，不要加评论、不要改写。
4. 任何工具返回 "Error:" 开头时，直接把该 Error 文本作为最终回复返回。
5. 记忆只能用于个性化表达，不能覆盖过敏、健康禁忌和健康安全约束。
6. 最终回复中不得出现 member_id 等内部标识符。
{members_block}
"""


SHOPPING_GUIDE_PROMPT_TEMPLATE = """你是粮达健康的「商品导购师」专家 Agent，只对总调度负责。
工作流程：
1. 任务里带餐单文本时：调用 mall_recommend，把餐单文本原样作为 meal_plan_text；scope/member_id 严格按任务描述传递（任务写 scope=member 就用 member，写 scope=family 就用 family），不要默认用 family。
2. 任务只问某类商品时：meal_plan_text 留空，把用户原问题放进 query_text。
3. 把 mall_recommend 返回的原始结果字符串作为最终回复原样返回，不要改写或总结。如果返回的 JSON 中包含 replaced_items 列表（用户反馈替换记录），也原样保留。
4. 工具返回 "Error:" 开头时，直接原样返回该 Error 文本。
{members_block}
"""


REPORT_READER_PROMPT_TEMPLATE = """你是粮达健康的「报告解读师」专家 Agent，只对总调度负责。

【核心原则】你必须全面检索、完整输出——绝不允许只报告一个异常就结束。

工作流程：
1. 【一次查询拿到全部指标】调用 report_facts(member_id=xxx) 工具，该工具直接从数据库返回该家人所有已提取的结构化健康事实（无需多次查询）。
   - 每条事实已包含：指标名称、实测值、参考范围、状态（正常/偏高/偏低/异常）、来源报告名称和页码、证据说明。
   - 这是报告上传时由 LLM 提取并入库的结构化数据，比 RAG 检索更全更准。

2. 【完整输出所有异常】从 report_facts 返回的全部事实中，找出所有异常指标（status 为"偏高/偏低"或"异常"的），列出每一个，格式如下：
   对每个异常指标（使用加粗编号列表，不要用 ### 或 # 标题）：
   **1. 指标名称**：实测值（参考范围）——通俗解读 + 生活建议（来源：报告名 页码）
   **2. 指标名称**：实测值（参考范围）——通俗解读 + 生活建议（来源：报告名 页码）
   禁止使用 ### 标题标记，禁止只说一个异常就停下——有几个就说几个，宁可多列也不能遗漏。

3. 如果所有事实均正常，明确告诉总调度"该家人报告指标均在正常范围内"。
4. 工具返回 "Error:" 开头时如实说明。
5. 最终回复中不得出现 member_id 等内部标识符，称呼家人用姓名或家庭称呼。
6. 不做诊断，不替代医生。
7. 【用药禁令】最终回复绝不输出任何药品名称（包括品牌名、通用名、中药名）、剂量、疗程或自行用药建议。只能提供饮食、运动、复查和就医提醒；用户追问用药时，回复“请携带报告咨询医生或药师”，不要举例任何药名。
{members_block}
"""


class MultiAgentRunner(BaseAgentRunner):
    """Supervisor + 3 专家 Agent 的多 Agent runner，接口与 BaseAgentRunner 一致。"""

    SYSTEM_PROMPT_TEMPLATE = SUPERVISOR_PROMPT_TEMPLATE

    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, mall_recommend_tool=None, report_fact_tool=None, member_provider=None):
        super().__init__(
            kb_tool=kb_tool,
            meal_plan_tool=meal_plan_tool,
            memory_tool=memory_tool,
            mall_recommend_tool=mall_recommend_tool,
            member_provider=member_provider,
        )
        self.report_fact_tool = report_fact_tool
        self._activity_queue = None
        self._product_payloads = []
        self._experts_cache = None
        self._last_report_reader_output = ""

    # ---- 提示词 ----

    def _attach_evidence_collector(self):
        collector = super()._attach_evidence_collector()
        if self.report_fact_tool is not None:
            self.report_fact_tool.evidence_collector = collector
        return collector

    def _expert_prompt(self, template: str) -> str:
        return template.format(members_block=_build_members_block(self.member_provider()))

    # ---- 工具注册 ----

    def _tools(self):
        def ask_meal_planner(task: str) -> str:
            """把三餐/吃什么类任务交给餐单规划师。task 里必须写清：scope=member/family、member_id（单人时）、meal_type=dinner/breakfast/lunch/day。示例："为爸爸(member_id=xxx, scope=member)规划今晚晚餐(meal_type=dinner)"。"""
            return self._run_expert("meal_planner", task)

        def ask_shopping_guide(task: str) -> str:
            """把商品推荐任务交给商品导购师。仅当用户明确要求"推荐/买/选"商品时使用。带餐单时 task 原样附餐单文本，同时写清 scope=member/family 和 member_id（与餐单一致）；只问商品类目时写用户原问题。注意：询问家人偏好（"爸爸喜欢吃鱼吗"）、声明排斥（"妈妈不吃辣的"）、问胃口状态等绝对不要调用本工具，应走 memory_search + respond。"""
            return self._run_expert("shopping_guide", task)

        def ask_report_reader(task: str) -> str:
            """把报告检索和解读任务交给报告解读师。task 里写清 member_id 和用户问题。"""
            return self._run_expert("report_reader", task)

        from app.services.langchain_agent import _RESPOND_TOOL

        tools = [ask_meal_planner, ask_shopping_guide, ask_report_reader]

        # 总调度自己也能查记忆，用于回答家人偏好/闲聊类问题时提供依据
        if self.memory_tool is not None:
            def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
                """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标。在直接回答用户闲聊/偏好问题时使用。"""
                logger.info("supervisor tool call name=memory_search member_id=%s limit=%s", member_id, limit)
                return self.memory_tool.search(query=query, member_id=member_id, limit=limit)

            tools.append(memory_search)

        tools.append(_RESPOND_TOOL)
        return tools

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
        if self.report_fact_tool is not None:
            def report_facts(member_id: str) -> str:
                """查询指定家人的所有已提取健康事实（结构化数据，无需向量搜索）。一次返回全部指标。"""
                logger.info("expert tool call name=report_facts member_id=%s", member_id)
                return self.report_fact_tool.get_facts(member_id=member_id)

            tools.append(report_facts)
        # 保留 kb_search 作为兑底：用户追问报告细节原文时使用
        if self.kb_tool is not None:
            def kb_search(query: str, member_id: str, top_k: int = 5) -> str:
                """检索指定家人的健康报告片段（仅在需要查看报告原文细节时使用）。"""
                logger.info("expert tool call name=kb_search member_id=%s top_k=%s", member_id, top_k)
                return self.kb_tool.search(query=query, member_id=member_id, top_k=top_k)

            tools.append(kb_search)
        return tools

    # ---- 专家执行 ----

    def _run_expert(self, agent_key: str, task: str) -> str:
        logger.info("multi_agent expert start agent=%s task_chars=%s", agent_key, len(task))
        self._emit_activity(agent_key, "start", f"{AGENT_LABELS[agent_key]}正在处理…",
                            task=task[:300])
        start_time = time.time()
        try:
            result = self._expert_invoke(agent_key, task)
        except Exception:
            logger.exception("multi_agent expert failed agent=%s", agent_key)
            result = "Error: 专家处理失败"
        elapsed = round(time.time() - start_time, 1)
        self._emit_activity(agent_key, "done", f"{AGENT_LABELS[agent_key]}完成",
                            result_summary=result[:200] if not result.startswith("Error:") else result,
                            elapsed_seconds=elapsed)
        # 临时诊断日志：查看专家返回给总调度的完整原始文本，定位内容是否在专家侧已被压缩。
        logger.info("multi_agent expert done agent=%s output_chars=%s output=%s", agent_key, len(result), result)
        if agent_key == "report_reader":
            self._last_report_reader_output = result
        return result

    def _preserve_report_reader_text(self, card: dict) -> dict:
        """报告解读不经过总调度二次摘要，直接使用专家原始文本。"""
        if (
            card.get("kind") == "kb_interpretation"
            and self._last_report_reader_output.strip()
            and not self._last_report_reader_output.startswith("Error:")
        ):
            card["summary_text"] = _strip_heading_prefix(self._last_report_reader_output.strip())
        return card

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

    def _emit_activity(self, agent: str, action: str, detail: str = "", **extra) -> None:
        if self._activity_queue is not None:
            payload = {"agent": agent, "action": action, "detail": detail}
            payload.update(extra)
            self._activity_queue.put(("activity", payload))

    # ---- 流式输出过滤 ----

    def _process_stream_chunk(self, chunk, respond_args_state):
        """重写父类：supervisor 的推理文本不输出给用户，但直接回复要保留。

        规则：
        1. mall_recommend 工具结果 → product_recommendations
        2. respond 工具的 ToolMessage → card
        3. respond 工具的 summary_text 增量 → delta
        4. AIMessageChunk 有 tool_call_chunks 时：只保留 respond 的 summary_text 增量，静默普通文本（推理过程）
        5. AIMessageChunk 没有 tool_call_chunks 时：输出普通文本（LLM 直接回复，不是推理）
        """
        from app.services.langchain_agent import (
            _try_parse_mall_recommend_payload,
            _parse_respond_payload,
            _parse_respond_payload_from_args_state,
            _extract_respond_summary_text_delta,
            _content_to_text,
            ResponseSchemaError,
        )

        events = []

        # 1) mall_recommend → product_recommendations
        payload = _try_parse_mall_recommend_payload(chunk)
        if payload is not None and payload.get("items"):
            logger.info("multi_agent stream emit product_recommendations item_count=%s", len(payload["items"]))
            events.append(("product_recommendations", payload))
            return events, False

        # 2) respond ToolMessage → card
        if chunk.__class__.__name__ == "ToolMessage" and getattr(chunk, "name", None) == "respond":
            card = _parse_respond_payload(chunk) or _parse_respond_payload_from_args_state(
                respond_args_state,
                tool_call_id=getattr(chunk, "tool_call_id", None),
            )
            if card is None:
                raw_content = getattr(chunk, "content", "")
                logger.warning(
                    "multi_agent stream respond payload invalid tool_call_id=%s raw=%r",
                    getattr(chunk, "tool_call_id", None),
                    raw_content[:500] if isinstance(raw_content, str) else str(raw_content)[:500],
                )
                raise ResponseSchemaError("respond 工具参数不符合 StructuredResponse schema")
            card = self._apply_evidence_to_card(card)
            logger.info(
                "multi_agent stream emit card kind=%s summary_chars=%s",
                card.get("kind"),
                len(card.get("summary_text", "")),
            )
            events.append(("card", card))
            return events, True

        # 3) AIMessageChunk
        if chunk.__class__.__name__ == "AIMessageChunk":
            tool_call_chunks = getattr(chunk, "tool_call_chunks", None) or []
            if tool_call_chunks:
                # 有 tool_call：只保留 respond 的 summary_text 增量，静默普通文本（推理过程）
                respond_chunk_text = _extract_respond_summary_text_delta(tool_call_chunks, respond_args_state)
                if respond_chunk_text:
                    events.append(("delta", respond_chunk_text))
                else:
                    text = _content_to_text(getattr(chunk, "content", ""))
                    if text:
                        logger.debug("multi_agent suppress supervisor reasoning text chars=%s", len(text))
            else:
                # 没有 tool_call：LLM 直接回复，输出普通文本
                text = _content_to_text(getattr(chunk, "content", ""))
                if text:
                    logger.info("multi_agent stream emit direct reply text chars=%s", len(text))
                    events.append(("delta", text))
            return events, False

        return events, False

    # ---- 商品结构捕获 ----

    def _capture_product_payload(self, raw: str) -> None:
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(parsed, dict) or not isinstance(parsed.get("items"), list) or not parsed["items"]:
            return
        self._product_payloads.append(parsed)
        if self._activity_queue is not None:
            self._activity_queue.put(("product", parsed))

    # ---- run()：商品改从专家捕获结果取 ----

    def run(self, messages):
        self._product_payloads = []
        self._last_report_reader_output = ""
        result = super().run(messages)
        if isinstance(result.get("card"), dict):
            result["card"] = self._preserve_report_reader_text(result["card"])
            result["content"] = result["card"].get("summary_text", "")
        return result

    def _extract_products(self, messages) -> dict | None:
        return self._product_payloads[-1] if self._product_payloads else None

    # ---- stream()：工作线程 + 事件队列 ----

    def stream(self, messages):
        self._ensure_api_key()
        logger.info("multi_agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        self._product_payloads = []
        self._last_report_reader_output = ""
        self._activity_queue = queue.Queue()
        self._attach_evidence_collector()
        agent = self._agent()
        prepared_messages = self._append_kb_context(messages)
        log_llm_request(
            logger,
            service="multi_agent.stream",
            payload={
                "model": settings.llm_model,
                "base_url": settings.llm_base_url,
                "temperature": settings.llm_temperature,
                "timeout": settings.llm_timeout_seconds,
                "system_prompt": self._system_prompt(),
                "messages": prepared_messages,
            },
        )

        stop_event = threading.Event()

        def worker(event_queue, stop):
            try:
                for chunk, _metadata in agent.stream(
                    {"messages": self._to_langchain_messages(prepared_messages)},
                    stream_mode="messages",
                ):
                    if stop.is_set():
                        logger.info("multi_agent stream worker stopped by signal")
                        break
                    event_queue.put(("chunk", chunk))
            except Exception as exc:
                if not stop.is_set():
                    logger.exception("multi_agent stream worker failed")
                    event_queue.put(("error", exc))
            finally:
                event_queue.put(("sentinel", None))

        worker_thread = threading.Thread(target=worker, args=(self._activity_queue, stop_event), daemon=True)
        worker_thread.start()

        user_query = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        supervisor_start = time.time()
        yield ("agent_activity", {"agent": "supervisor", "action": "start", "detail": "调度中心解析意图中", "user_query": user_query})

        respond_args_state: dict[str, str] = {}
        finished_by_card = False
        final_card_summary = ""
        # 延迟商品推荐：等 card（respond）完成后再一起推送，避免商品图片先于文字出现
        deferred_product_events: list[dict] = []
        while True:
            kind, payload = self._activity_queue.get()
            if kind == "sentinel":
                break
            if kind == "error":
                self._activity_queue = None
                raise payload
            if kind == "activity":
                logger.info("multi_agent stream emit agent_activity agent=%s action=%s", payload.get("agent"), payload.get("action"))
                yield ("agent_activity", payload)
                continue
            if kind == "product":
                logger.info("multi_agent stream deferred product_recommendations item_count=%s", len(payload.get("items") or []))
                deferred_product_events.append(payload)
                continue
            events, done = self._process_stream_chunk(payload, respond_args_state)
            if events:
                events = [
                    (event_type, self._preserve_report_reader_text(event_payload)
                     if event_type == "card" and isinstance(event_payload, dict)
                     else event_payload)
                    for event_type, event_payload in events
                ]
            for event in events:
                if event[0] == "card" and isinstance(event[1], dict):
                    final_card_summary = event[1].get("summary_text", "")[:200]
                yield event
            if done:
                finished_by_card = True
                break

        # card 已产出（或流结束），现在才推送延迟的商品推荐事件
        for product_payload in deferred_product_events:
            logger.info("multi_agent stream emit deferred product_recommendations item_count=%s", len(product_payload.get("items") or []))
            yield ("product_recommendations", product_payload)

        if finished_by_card:
            # respond 卡片已产出，通知工作线程停止，避免 supervisor 继续无意义的 LLM 调用
            stop_event.set()
            worker_thread.join(timeout=5)
            if worker_thread.is_alive():
                logger.warning("multi_agent stream worker did not stop within 5s, leaving as daemon")
            self._activity_queue = None
            elapsed = round(time.time() - supervisor_start, 1)
            yield ("agent_activity", {"agent": "supervisor", "action": "done", "detail": "调度中心完成", "output_summary": final_card_summary, "elapsed_seconds": elapsed})
            return

        logger.warning("multi_agent stream finished without card")
        fallback_card = self._fallback_evidence_card()
        if fallback_card is not None:
            logger.info("multi_agent stream emit fallback evidence card")
            yield ("card", fallback_card)
        self._activity_queue = None
        elapsed = round(time.time() - supervisor_start, 1)
        yield ("agent_activity", {"agent": "supervisor", "action": "done", "detail": "调度中心完成", "output_summary": final_card_summary, "elapsed_seconds": elapsed})
