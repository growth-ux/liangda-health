"""集团运营 Agent 工具集：封装 DashboardService 查询能力供 Agent 调用。"""
import logging

from app.db.session import SessionLocal
from app.services.common.dashboard_service import DashboardService

logger = logging.getLogger(__name__)


class OpsAgentTools:
    """将 DashboardService 的查询结果包装成 Agent 可调用的工具函数。

    每次工具调用创建独立的 db session，避免与 FastAPI 请求 session 共享 MySQL 连接
    （LangChain Agent 在 StreamingResponse generator 内调用工具时会导致包序列号错乱）。
    """

    def _dashboard(self) -> DashboardService:
        """返回一个使用独立 session 的 DashboardService。"""
        return DashboardService(SessionLocal())

    def get_overview(self) -> str:
        """获取集团经营概览：成员数、报告数、健康事实数、会话数、消息数、推荐数、购物车数量和金额。"""
        logger.info("ops_agent tool call name=get_overview")
        svc = self._dashboard()
        data = svc.summary()
        overview = data.overview
        return (
            f"成员数：{overview.member_count}\n"
            f"报告数：{overview.report_count}\n"
            f"健康事实数：{overview.health_fact_count}\n"
            f"会话数：{overview.session_count}\n"
            f"消息数：{overview.message_count}\n"
            f"推荐消息数：{overview.recommendation_count}\n"
            f"购物车数量：{overview.cart_item_count}\n"
            f"购物车金额：{overview.cart_amount_yuan} 元"
        )

    def get_brand_ranks(self) -> str:
        """获取品牌转化排行榜：推荐次数、加购数、转化金额。"""
        logger.info("ops_agent tool call name=get_brand_ranks")
        svc = self._dashboard()
        data = svc.summary()
        ranks = data.brand_ranks
        if not ranks:
            return "暂无品牌推荐数据"
        lines = ["品牌转化排行榜："]
        for idx, item in enumerate(ranks, 1):
            lines.append(
                f"{idx}. {item.brand}（{item.category_name or '未分类'}）：推荐 {item.recommend_count} 次，加购 {item.cart_count} 件，转化 ¥{item.amount_yuan}"
            )
        return "\n".join(lines)

    def get_category_penetration(self) -> str:
        """获取品类推荐渗透率：各品类被推荐的次数。"""
        logger.info("ops_agent tool call name=get_category_penetration")
        svc = self._dashboard()
        data = svc.summary()
        items = data.category_penetration
        if not items:
            return "暂无品类推荐数据"
        lines = ["品类推荐渗透："]
        for item in items:
            lines.append(f"- {item.category_name}：推荐 {item.recommend_count} 次")
        return "\n".join(lines)

    def get_funnel(self) -> str:
        """获取推荐转化漏斗：用户主动咨询 → AI 推荐消息 → 推荐商品曝光 → 加入购物车 → 下单/支付。"""
        logger.info("ops_agent tool call name=get_funnel")
        svc = self._dashboard()
        data = svc.summary()
        funnel = data.funnel
        if not funnel:
            return "暂无漏斗数据"
        lines = ["推荐转化漏斗："]
        for step in funnel:
            lines.append(f"- {step.name}：{step.value}")
        if len(funnel) >= 2 and funnel[0].value > 0:
            rate = round((funnel[-1].value / funnel[0].value) * 100, 2)
            lines.append(f"转化率：{rate}%")
        return "\n".join(lines)

    def get_hot_products(self) -> str:
        """获取热门商品：推荐次数、加购数、转化金额。"""
        logger.info("ops_agent tool call name=get_hot_products")
        svc = self._dashboard()
        data = svc.summary()
        products = data.hot_products
        if not products:
            return "暂无热门商品数据"
        lines = ["热门商品 Top 榜："]
        for idx, item in enumerate(products, 1):
            lines.append(
                f"{idx}. {item.name}（{item.brand or '无品牌'}，{item.category_name or '未分类'}）：¥{item.price_yuan}，推荐 {item.recommend_count} 次，加购 {item.cart_count} 件，转化 ¥{item.amount_yuan}"
            )
        return "\n".join(lines)

    def get_fact_status(self) -> str:
        """获取健康事实状态分布：正常、预警、危险。"""
        logger.info("ops_agent tool call name=get_fact_status")
        svc = self._dashboard()
        data = svc.summary()
        fact = data.fact_status
        return f"健康事实状态：正常 {fact.normal} 条，预警 {fact.warning} 条，危险 {fact.danger} 条"

    def get_risk_members(self) -> str:
        """获取高风险成员：危险和预警健康事实数量。"""
        logger.info("ops_agent tool call name=get_risk_members")
        svc = self._dashboard()
        data = svc.summary()
        members = data.risk_members
        if not members:
            return "暂无高风险成员"
        lines = ["高风险成员："]
        for item in members:
            lines.append(
                f"- {item.member_name}（{item.relation or '未标注'}）：危险 {item.danger_count} 项，预警 {item.warning_count} 项"
            )
        return "\n".join(lines)

    def get_member_profile(self) -> str:
        """获取成员画像：性别分布、关系分布、年龄段、健康标签。"""
        logger.info("ops_agent tool call name=get_member_profile")
        svc = self._dashboard()
        data = svc.summary()
        profile = data.member_profile
        parts = ["成员画像："]
        if profile.gender_distribution:
            parts.append("性别：" + "、".join(f"{item.name} {item.count} 人" for item in profile.gender_distribution))
        if profile.relation_distribution:
            parts.append("关系：" + "、".join(f"{item.name} {item.count} 人" for item in profile.relation_distribution))
        if profile.age_bands:
            parts.append("年龄段：" + "、".join(f"{item.name} {item.count} 人" for item in profile.age_bands if item.count > 0))
        if profile.health_tag_cloud:
            tags = [f"{item.name}({item.count})" for item in profile.health_tag_cloud[:8]]
            parts.append("健康标签：" + "、".join(tags))
        return "\n".join(parts) if len(parts) > 1 else "暂无成员画像数据"

    def get_ai_usage(self) -> str:
        """获取 AI 使用统计：模型名称、token 用量、预估成本。"""
        logger.info("ops_agent tool call name=get_ai_usage")
        svc = self._dashboard()
        data = svc.summary()
        usage = data.ai_usage
        return (
            f"AI 使用统计：模型 {usage.model_name or '未知'}，"
            f"输入 token {usage.token_prompt_total}，输出 token {usage.token_completion_total}，"
            f"预估成本 ¥{usage.estimated_cost_yuan}"
        )

    def get_daily_trend(self) -> str:
        """获取近 14 天每日消息和推荐趋势。"""
        logger.info("ops_agent tool call name=get_daily_trend")
        svc = self._dashboard()
        data = svc.summary()
        trend = data.daily_trend
        if not trend:
            return "暂无趋势数据"
        lines = ["近 14 天趋势："]
        for point in trend[-7:]:  # 只展示最近 7 天
            lines.append(f"{point.date}：消息 {point.message_count}，推荐 {point.recommendation_count}")
        return "\n".join(lines)

    def get_session_depth(self) -> str:
        """获取会话深度统计：会话数、平均提问轮次、最深轮次。"""
        logger.info("ops_agent tool call name=get_session_depth")
        svc = self._dashboard()
        data = svc.summary()
        depth = data.session_depth
        return (
            f"会话深度：共 {depth.session_count} 个会话，"
            f"平均提问 {depth.avg_user_turns} 轮，最深 {depth.max_user_turns} 轮"
        )
