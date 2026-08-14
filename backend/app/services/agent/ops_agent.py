"""集团运营 Agent：面向集团运营人员的智能数据助手，支持流式对话。"""
import logging
from collections.abc import Iterable

from app.core.config import settings
from app.services.agent.langchain_agent import LlmConfigError, _content_to_text
from app.services.agent.llm_logging import log_llm_request

logger = logging.getLogger(__name__)


OPS_AGENT_SYSTEM_PROMPT = """你是粮达健康的「集团运营 AI 助手」，服务于集团运营管理团队。
你的职责是帮助运营人员快速了解平台经营状况、分析数据趋势、发现运营洞察。

你可以调用以下数据查询工具获取实时经营数据：
- get_overview：集团经营概览（成员数、报告数、消息数、购物车等）
- get_brand_ranks：品牌转化排行榜
- get_category_penetration：品类推荐渗透率
- get_funnel：推荐转化漏斗
- get_hot_products：热门商品排行
- get_fact_status：健康事实状态分布
- get_risk_members：高风险成员列表
- get_member_profile：成员画像分析
- get_ai_usage：AI 使用统计和成本
- get_daily_trend：近 14 天消息和推荐趋势
- get_session_depth：会话深度统计

工作规则：
1. 回答必须基于工具返回的真实数据，不要编造数字。
2. 分析要有洞察，不只罗列数据，要指出趋势、异常和建议。
3. 用简体中文回答，语气专业但易懂，像一位资深数据分析师在做汇报。
4. 【重要】使用简洁的 Markdown 格式让回复结构清晰：
   - 用 **加粗** 做段落标题和突出关键数字、结论
   - 排行榜、对比数据使用标准 Markdown 表格（| 列 | 列 | + 分隔行）
   - 要点使用无序列表（- 开头）
   - 不同主题之间用空行分隔
   - 不要用 | 符号做纯文本分隔
   - 禁止使用 # / ## / ### / #### 等标题语法，一律用 **加粗文字** 代替
5. 当运营人员问“最近经营怎么样”等开放问题时，主动调用多个工具汇总关键指标。
6. 发现异常数据（如转化率下降、某品牌突然掉量）时主动提示并给出可能原因。
7. 回复控制在 400 字以内，先给结论再给数据支撑。
"""


class OpsAgentRunner:
    """集团运营 Agent Runner —— 单 Agent + 多工具，支持 run() 和 stream()。"""

    def __init__(self, ops_tools):
        self.ops_tools = ops_tools

    def _ensure_api_key(self) -> None:
        if not settings.llm_api_key:
            raise LlmConfigError("未配置模型 API Key")

    def _model(self):
        from langchain.chat_models import init_chat_model

        return init_chat_model(
            model=settings.llm_model,
            model_provider="openai",
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
        )

    def _build_tools(self):
        tools = []
        tool_map = {
            "get_overview": self.ops_tools.get_overview,
            "get_brand_ranks": self.ops_tools.get_brand_ranks,
            "get_category_penetration": self.ops_tools.get_category_penetration,
            "get_funnel": self.ops_tools.get_funnel,
            "get_hot_products": self.ops_tools.get_hot_products,
            "get_fact_status": self.ops_tools.get_fact_status,
            "get_risk_members": self.ops_tools.get_risk_members,
            "get_member_profile": self.ops_tools.get_member_profile,
            "get_ai_usage": self.ops_tools.get_ai_usage,
            "get_daily_trend": self.ops_tools.get_daily_trend,
            "get_session_depth": self.ops_tools.get_session_depth,
        }
        for name, func in tool_map.items():
            from langchain_core.tools import StructuredTool
            tools.append(
                StructuredTool.from_function(
                    func=func,
                    name=name,
                    description=func.__doc__ or name,
                )
            )
        return tools

    def _agent(self):
        from langchain.agents import create_agent

        return create_agent(
            model=self._model(),
            tools=self._build_tools(),
            system_prompt=OPS_AGENT_SYSTEM_PROMPT,
        )

    def _to_langchain_messages(self, messages: list[dict[str, str]]):
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        result = []
        for message in messages:
            if message["role"] == "assistant":
                result.append(AIMessage(content=message["content"]))
            elif message["role"] == "system":
                result.append(SystemMessage(content=message["content"]))
            else:
                result.append(HumanMessage(content=message["content"]))
        return result

    def run(self, messages: list[dict[str, str]]) -> dict[str, object]:
        """同步调用：返回 {"content": str, "token_prompt": int, ...}。"""
        self._ensure_api_key()
        logger.info("ops_agent run start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        log_llm_request(
            logger,
            service="ops_agent.run",
            payload={
                "model": settings.llm_model,
                "system_prompt": OPS_AGENT_SYSTEM_PROMPT,
                "messages": messages,
            },
        )
        response = agent.invoke({"messages": self._to_langchain_messages(messages)})
        response_message = response["messages"][-1]
        content = _content_to_text(response_message.content)
        token_usage = (
            response_message.response_metadata.get("token_usage", {})
            if response_message.response_metadata
            else {}
        )
        logger.info("ops_agent run done output_chars=%s", len(content))
        return {
            "content": content,
            "token_prompt": token_usage.get("prompt_tokens"),
            "token_completion": token_usage.get("completion_tokens"),
            "model_name": response_message.response_metadata.get("model_name") if response_message.response_metadata else None,
        }

    def stream(self, messages: list[dict[str, str]]) -> Iterable[tuple[str, object]]:
        """流式调用：yield ("delta", text) 事件。"""
        self._ensure_api_key()
        logger.info("ops_agent stream start message_count=%s model=%s", len(messages), settings.llm_model)
        agent = self._agent()
        log_llm_request(
            logger,
            service="ops_agent.stream",
            payload={
                "model": settings.llm_model,
                "system_prompt": OPS_AGENT_SYSTEM_PROMPT,
                "messages": messages,
            },
        )

        for chunk, _metadata in agent.stream(
            {"messages": self._to_langchain_messages(messages)},
            stream_mode="messages",
        ):
            if chunk.__class__.__name__ == "AIMessageChunk":
                text = _content_to_text(getattr(chunk, "content", ""))
                if text:
                    yield ("delta", text)

        logger.info("ops_agent stream done")
