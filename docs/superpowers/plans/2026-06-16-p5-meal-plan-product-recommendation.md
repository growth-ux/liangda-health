# P5 餐单接商品推荐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户问餐单时，Agent 在生成餐单后追加“可选商品”推荐，推荐来源于健康画像、餐单食材方向和现有商城商品标签。

**Architecture:** 新增一个后端服务 `MealProductRecommendationService`，负责复用 `HealthProfileService` 和 `SqlAlchemyMallRepository` 读取画像与商品，再用轻量规则把餐单文本、饮食原则、近期状态和商品 `recommend_tags` 匹配起来。Agent 增加 `mall_recommend` 工具，并在餐单意图中先调用 `meal_plan`，再调用 `mall_recommend`，最后把餐单和商品推荐合成自然语言回复。

**Tech Stack:** FastAPI + SQLAlchemy + LangChain tools + pytest；不新增数据库表，不新增前端页面，不引入新依赖。

---

## Scope

包含：

- `MealPlanService` 输出餐单后，可按单人或全家推荐商城商品。
- 推荐商品复用现有商城种子商品、`recommend_tags`、`health_tags`、`warning_tags` 和过敏过滤。
- Agent 注册 `mall_recommend` 工具，并在系统提示词中要求餐单回复追加可选商品。
- 增加服务层、工具层和 Agent 工具注册测试。

不包含：

- 不做 P6 推荐证据链 UI。
- 不改商品详情页。
- 不新增购物车自动加购逻辑。
- 不把推荐结果持久化。
- 不做 embedding 商品召回或 LLM 自检。

## Files

- Create: `backend/app/services/meal_product_recommendation_service.py`
  - 负责从画像、餐单文本和商品标签生成推荐商品 Markdown。
- Modify: `backend/app/services/agent_tools.py`
  - 新增 `MallRecommendTool`。
- Modify: `backend/app/services/langchain_agent.py`
  - 注册 `mall_recommend` LangChain tool，更新系统提示词。
- Modify: `backend/app/api/agent.py`
  - 注入 `SqlAlchemyMallRepository` 和 `MallRecommendTool`。
- Create: `backend/tests/test_meal_product_recommendation_service.py`
  - 覆盖单人、全家、过敏过滤、餐单关键词映射。
- Modify: `backend/tests/test_agent_tools.py`
  - 覆盖 `MallRecommendTool` 参数校验和调用。
- Modify: `backend/tests/test_langchain_agent.py`
  - 覆盖 `mall_recommend` 工具注册和系统提示词。

## Data Mapping

第一版规则只做可解释的标签映射：

| 输入来源 | 命中关键词 | 商品标签 |
| --- | --- | --- |
| 饮食原则/餐单/近期状态 | 低钠、清淡、血压 | `low_sodium`, `hypertension` |
| 饮食原则/餐单/目标 | 控糖、低GI、血糖、主食定量、杂粮、燕麦、糙米 | `sugar_control`, `low_gi` |
| 饮食原则/餐单 | 少油、低脂、轻负担、晚餐减轻 | `low_fat` |
| 饮食原则/餐单 | 高纤维、高纤、杂粮、蔬菜、燕麦、黑米、藜麦 | `high_fiber` |
| 饮食原则/餐单 | 优质蛋白、高蛋白、鸡胸肉、豆腐、豆浆、牛奶、蛋 | `high_protein` |
| 饮食原则/餐单 | 高钙、骨密度、骨质、牛奶、芝麻 | `high_calcium`, `nutrients` |
| 饮食原则/餐单 | 低嘌呤、尿酸、痛风 | `low_purine` |

排序规则：

```text
过敏冲突过滤
> 餐单关键词命中
> 健康画像原则/近期状态/目标命中
> 商品原有会员推荐分
> 商品 id 稳定排序
```

输出格式：

```text
可选商品：
- 商品名：推荐原因
- 商品名：推荐原因
- 商品名：推荐原因

说明：以上是根据本次餐单方向和健康画像匹配的商城商品，不构成医疗建议。
```

## Task 1: 新增餐单商品推荐服务

**Files:**
- Create: `backend/app/services/meal_product_recommendation_service.py`
- Test: `backend/tests/test_meal_product_recommendation_service.py`

- [ ] **Step 1: 写单人推荐失败测试**

在 `backend/tests/test_meal_product_recommendation_service.py` 新增：

```python
import json
from datetime import datetime

from app.models.mall import MallProduct
from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.meal_product_recommendation_service import MealProductRecommendationService


def _add_member(db_session, *, member_id="mem_dad", allergies=None):
    member = Member(
        member_id=member_id,
        name="李建国",
        relation="爸爸",
        gender="男",
        birth_year=1958,
        health_tags=json.dumps(["高血压", "高血脂"], ensure_ascii=False),
        allergies=allergies,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(member)
    db_session.commit()
    return member


def test_recommend_member_products_from_meal_plan_and_profile(db_session):
    _add_member(db_session)
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    result = service.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="晚餐：杂粮饭 + 鸡胸肉 + 豆腐青菜。建议低钠、少油。",
        limit=4,
    )

    assert "可选商品：" in result
    assert "低钠" in result
    assert any(word in result for word in ["杂粮", "燕麦", "糙米", "黑米", "藜麦"])
    assert "本推荐不构成医疗建议" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/test_meal_product_recommendation_service.py::test_recommend_member_products_from_meal_plan_and_profile -q
```

Expected: FAIL，原因是 `app.services.meal_product_recommendation_service` 不存在。

- [ ] **Step 3: 实现最小服务**

创建 `backend/app/services/meal_product_recommendation_service.py`：

```python
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.mall import MallProduct
from app.models.member import Member
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.health_profile_service import FamilyHealthProfile, HealthProfile, HealthProfileService
from app.services.mall_recommendation import score_product_for_member


@dataclass(frozen=True)
class MealProductRecommendation:
    product: MallProduct
    score: int
    reason: str


TAG_RULES: list[tuple[tuple[str, ...], tuple[str, ...], str]] = [
    (("低钠", "清淡", "血压"), ("low_sodium", "hypertension"), "契合本次低钠清淡方向"),
    (("控糖", "低GI", "血糖", "主食定量", "杂粮", "燕麦", "糙米"), ("sugar_control", "low_gi"), "适合作为控糖或低 GI 主食选择"),
    (("少油", "低脂", "轻负担", "晚餐减轻"), ("low_fat",), "更适合少油轻负担饮食"),
    (("高纤维", "高纤", "杂粮", "蔬菜", "黑米", "藜麦"), ("high_fiber",), "补充膳食纤维，适合餐单中的杂粮方向"),
    (("优质蛋白", "高蛋白", "鸡胸肉", "豆腐", "豆浆", "牛奶", "蛋"), ("high_protein",), "补充优质蛋白，适合餐单搭配"),
    (("高钙", "骨密度", "骨质", "牛奶", "芝麻"), ("high_calcium", "nutrients"), "匹配高钙和营养补充方向"),
    (("低嘌呤", "尿酸", "痛风"), ("low_purine",), "更适合关注尿酸和嘌呤摄入的人群"),
]


class MealProductRecommendationService:
    def __init__(
        self,
        db: Session,
        *,
        mall_repository: SqlAlchemyMallRepository | None = None,
        profile_service: HealthProfileService | None = None,
    ):
        self.db = db
        self.mall_repository = mall_repository or SqlAlchemyMallRepository(db)
        self.profile_service = profile_service or HealthProfileService(db)

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 3,
    ) -> str:
        if scope == "member":
            if not member_id:
                return "Error: 单人商品推荐必须传入 member_id"
            profile = self.profile_service.get_member_profile(member_id)
            member = self.db.query(Member).filter(Member.member_id == member_id).one_or_none()
            if member is None:
                return "Error: 家人不存在"
            recs = self._recommend_for_member(profile, member, meal_plan_text, limit)
        elif scope == "family":
            profile = self.profile_service.get_family_profile()
            members = self.db.query(Member).all()
            recs = self._recommend_for_family(profile, members, meal_plan_text, limit)
        else:
            return "Error: scope 只能是 member 或 family"
        return self._format(recs)

    def _recommend_for_member(
        self,
        profile: HealthProfile,
        member: Member,
        meal_plan_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self.mall_repository.list_all_products()
        context = " ".join([
            meal_plan_text,
            " ".join(profile.diet_principles),
            " ".join(profile.recent_states),
            " ".join(profile.goals),
        ])
        return self._rank(products, context, [member], limit)

    def _recommend_for_family(
        self,
        profile: FamilyHealthProfile,
        members: list[Member],
        meal_plan_text: str,
        limit: int,
    ) -> list[MealProductRecommendation]:
        products = self.mall_repository.list_all_products()
        context = " ".join([
            meal_plan_text,
            " ".join(profile.shared_principles),
            " ".join(profile.family_modifiers),
            " ".join(profile.family_goals),
        ])
        return self._rank(products, context, members, limit)

    def _rank(
        self,
        products: list[MallProduct],
        context: str,
        members: list[Member],
        limit: int,
    ) -> list[MealProductRecommendation]:
        scored: list[MealProductRecommendation] = []
        for product in products:
            if any(_has_allergy_conflict(member, product) for member in members):
                continue
            tags = set(_json_list(product.recommend_tags))
            tag_score, reason = _score_tags(context, tags)
            member_score = sum(max(0, score_product_for_member(member, product)) for member in members)
            score = tag_score + member_score
            if score > 0:
                scored.append(MealProductRecommendation(product=product, score=score, reason=reason))
        scored.sort(key=lambda item: (-item.score, item.product.product_id))
        return scored[: max(1, limit)]

    def _format(self, recs: list[MealProductRecommendation]) -> str:
        if not recs:
            return "可选商品：暂无匹配商品。\n\n说明：以上是根据本次餐单方向和健康画像匹配的商城商品，本推荐不构成医疗建议。"
        lines = ["可选商品："]
        for item in recs:
            lines.append(f"- {item.product.name}：{item.reason}")
        lines.append("")
        lines.append("说明：以上是根据本次餐单方向和健康画像匹配的商城商品，本推荐不构成医疗建议。")
        return "\n".join(lines)


def _score_tags(context: str, tags: set[str]) -> tuple[int, str]:
    for keywords, recommend_tags, reason in TAG_RULES:
        if any(keyword in context for keyword in keywords) and tags & set(recommend_tags):
            return 80, reason
    return 0, "适合本次健康餐单搭配"


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _has_allergy_conflict(member: Member, product: MallProduct) -> bool:
    allergies = _csv(member.allergies)
    warning_tags = [item.lower() for item in _json_list(product.warning_tags)]
    return any(a in w or w in a for a in allergies for w in warning_tags)
```

- [ ] **Step 4: 运行单人测试确认通过**

Run:

```bash
cd backend && pytest tests/test_meal_product_recommendation_service.py::test_recommend_member_products_from_meal_plan_and_profile -q
```

Expected: PASS。

- [ ] **Step 5: 增加全家和过敏过滤测试**

追加到 `backend/tests/test_meal_product_recommendation_service.py`：

```python
def test_recommend_family_products_filters_any_member_allergy(db_session):
    _add_member(db_session, member_id="mem_dad", allergies="soy")
    _add_member(db_session, member_id="mem_mom", allergies=None)
    repo = SqlAlchemyMallRepository(db_session)
    repo.seed_default_data()
    service = MealProductRecommendationService(db_session, mall_repository=repo)

    result = service.recommend(
        scope="family",
        meal_plan_text="全家晚餐：低钠调味 + 杂粮饭 + 豆腐青菜。",
        limit=5,
    )

    assert "可选商品：" in result
    assert "酱油" not in result
    assert "生抽" not in result
    assert "说明：" in result


def test_recommend_rejects_missing_member_id(db_session):
    service = MealProductRecommendationService(db_session)

    result = service.recommend(scope="member", meal_plan_text="晚餐：杂粮饭")

    assert result == "Error: 单人商品推荐必须传入 member_id"
```

- [ ] **Step 6: 运行服务测试**

Run:

```bash
cd backend && pytest tests/test_meal_product_recommendation_service.py -q
```

Expected: PASS。

## Task 2: Agent Tools 接入 mall_recommend

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: 写工具层失败测试**

追加到 `backend/tests/test_agent_tools.py`：

```python
class FakeMallRecommendService:
    def __init__(self):
        self.calls = []

    def recommend(self, *, scope, meal_plan_text, member_id=None, limit=3):
        self.calls.append((scope, meal_plan_text, member_id, limit))
        return "可选商品：\n- 低钠盐：契合低钠方向"


def test_mall_recommend_tool_returns_products():
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(
        scope="member",
        member_id="mem_dad",
        meal_plan_text="晚餐：低钠杂粮饭",
        limit=2,
    )

    assert service.calls == [("member", "晚餐：低钠杂粮饭", "mem_dad", 2)]
    assert "低钠盐" in result


def test_mall_recommend_tool_rejects_unknown_member():
    from app.services.agent_tools import MallRecommendTool

    service = FakeMallRecommendService()
    tool = MallRecommendTool(service, allowed_member_ids=["mem_dad"])

    result = tool.recommend(scope="member", member_id="mem_unknown", meal_plan_text="晚餐：低钠杂粮饭")

    assert "Error" in result
    assert service.calls == []
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/test_agent_tools.py::test_mall_recommend_tool_returns_products tests/test_agent_tools.py::test_mall_recommend_tool_rejects_unknown_member -q
```

Expected: FAIL，原因是 `MallRecommendTool` 不存在。

- [ ] **Step 3: 实现 MallRecommendTool**

在 `backend/app/services/agent_tools.py` 末尾新增：

```python
class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str]):
        self.service = service
        self.allowed_member_ids = set(allowed_member_ids)

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 3,
    ) -> str:
        if scope not in {"member", "family"}:
            logger.info("mall_recommend rejected reason=invalid_scope scope=%s", scope)
            return "Error: scope 只能是 member 或 family"
        if not meal_plan_text.strip():
            logger.info("mall_recommend rejected reason=blank_meal_plan")
            return "Error: meal_plan_text 不能为空"
        if scope == "member":
            if not member_id:
                logger.info("mall_recommend rejected reason=missing_member_id")
                return "Error: 单人商品推荐必须传入 member_id"
            if member_id not in self.allowed_member_ids:
                logger.info("mall_recommend rejected reason=member_not_allowed member_id=%s", member_id)
                return f"Error: member_id={member_id} 不在可用家人列表中，可用：{sorted(self.allowed_member_ids)}"
        result = self.service.recommend(
            scope=scope,
            member_id=member_id,
            meal_plan_text=meal_plan_text,
            limit=limit,
        )
        logger.info(
            "mall_recommend done scope=%s member_id=%s output_chars=%s",
            scope,
            member_id,
            len(result),
        )
        return result
```

- [ ] **Step 4: 运行工具层测试**

Run:

```bash
cd backend && pytest tests/test_agent_tools.py -q
```

Expected: PASS。

## Task 3: LangChain Agent 注册 mall_recommend

**Files:**
- Modify: `backend/app/services/langchain_agent.py`
- Modify: `backend/tests/test_langchain_agent.py`

- [ ] **Step 1: 写 Agent 注册失败测试**

修改 `backend/tests/test_langchain_agent.py`：

```python
class FakeMallRecommendTool:
    def __init__(self):
        self.calls = []

    def recommend(self, scope, meal_plan_text, member_id=None, limit=3):
        self.calls.append((scope, meal_plan_text, member_id, limit))
        return "可选商品：\n- 低钠盐：契合低钠方向"
```

追加测试：

```python
def test_langchain_agent_registers_mall_recommend_tool(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    mall_tool = FakeMallRecommendTool()
    runner = LangChainAgentRunner(mall_recommend_tool=mall_tool)

    tools = runner._tools()
    result = tools[0](scope="member", member_id="mem_dad", meal_plan_text="晚餐：低钠杂粮饭", limit=2)

    assert mall_tool.calls == [("member", "晚餐：低钠杂粮饭", "mem_dad", 2)]
    assert "可选商品" in result


def test_runner_system_prompt_requires_mall_recommend_after_meal_plan():
    runner = LangChainAgentRunner()

    prompt = runner._system_prompt()

    assert "mall_recommend" in prompt
    assert "meal_plan 工具返回的餐单文本" in prompt
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
cd backend && pytest tests/test_langchain_agent.py::test_langchain_agent_registers_mall_recommend_tool tests/test_langchain_agent.py::test_runner_system_prompt_requires_mall_recommend_after_meal_plan -q
```

Expected: FAIL，原因是 `LangChainAgentRunner.__init__` 不接受 `mall_recommend_tool`，系统提示词也未包含规则。

- [ ] **Step 3: 修改 Agent Runner 构造函数和工具注册**

在 `backend/app/services/langchain_agent.py` 中把构造函数改为：

```python
class LangChainAgentRunner:
    def __init__(self, kb_tool=None, meal_plan_tool=None, memory_tool=None, mall_recommend_tool=None, member_provider=None):
        self.kb_tool = kb_tool
        self.meal_plan_tool = meal_plan_tool
        self.memory_tool = memory_tool
        self.mall_recommend_tool = mall_recommend_tool
        self.member_provider = member_provider or (lambda: [])
```

在 `_tools()` 的 `meal_plan` 注册之后新增：

```python
        if self.mall_recommend_tool is not None:
            def mall_recommend(
                scope: str,
                meal_plan_text: str,
                member_id: str | None = None,
                limit: int = 3,
            ) -> str:
                """根据 meal_plan 工具返回的餐单文本和健康画像推荐商城商品。"""
                logger.info(
                    "agent tool call name=mall_recommend scope=%s member_id=%s limit=%s meal_plan_chars=%s",
                    scope,
                    member_id,
                    limit,
                    len(meal_plan_text.strip()),
                )
                return self.mall_recommend_tool.recommend(
                    scope=scope,
                    member_id=member_id,
                    meal_plan_text=meal_plan_text,
                    limit=limit,
                )

            tools.append(mall_recommend)
```

- [ ] **Step 4: 更新系统提示词**

在 `SYSTEM_PROMPT_TEMPLATE` 中追加规则：

```text
14. 当用户询问吃什么、早餐、午餐、晚餐、一日三餐或全家共餐时，必须先调用 meal_plan 工具生成餐单。
15. meal_plan 工具返回餐单后，必须把 meal_plan 工具返回的餐单文本原样作为 meal_plan_text 参数继续调用 mall_recommend 工具。
16. 最终回复先给餐单，再追加 mall_recommend 返回的“可选商品”段落；如果 mall_recommend 返回 Error，只输出餐单并简短说明暂时无法推荐商品。
17. mall_recommend 的 scope 和 member_id 必须与 meal_plan 保持一致；全家餐单使用 scope="family"，不传 member_id。
```

- [ ] **Step 5: 运行 Agent 测试**

Run:

```bash
cd backend && pytest tests/test_langchain_agent.py -q
```

Expected: PASS。

## Task 4: API 依赖注入

**Files:**
- Modify: `backend/app/api/agent.py`

- [ ] **Step 1: 修改 import**

在 `backend/app/api/agent.py` 增加：

```python
from app.repositories.mall_repository import SqlAlchemyMallRepository
from app.services.agent_tools import KbSearchTool, MealPlanTool, MemorySearchTool, MallRecommendTool
from app.services.meal_product_recommendation_service import MealProductRecommendationService
```

并删除原来的单行：

```python
from app.services.agent_tools import KbSearchTool, MealPlanTool, MemorySearchTool
```

- [ ] **Step 2: 在 get_agent_runner 中创建 allowed_member_ids**

把重复的 `[m.member_id for m in member_provider()]` 提成局部变量：

```python
    allowed_member_ids = [m.member_id for m in member_provider()]
```

- [ ] **Step 3: 注入 MallRecommendTool**

在 `LangChainAgentRunner(...)` 参数中新增：

```python
        mall_recommend_tool=MallRecommendTool(
            service=MealProductRecommendationService(
                db,
                mall_repository=SqlAlchemyMallRepository(db),
            ),
            allowed_member_ids=allowed_member_ids,
        ),
```

同时把 `KbSearchTool` 和 `MealPlanTool` 的 `allowed_member_ids` 改为复用局部变量。

- [ ] **Step 4: 跑已有 API/Agent 测试**

Run:

```bash
cd backend && pytest tests/test_agent_api.py tests/test_langchain_agent.py tests/test_agent_tools.py -q
```

Expected: PASS。

## Task 5: 回归商城和餐单

**Files:**
- Test only

- [ ] **Step 1: 跑 P5 相关测试集合**

Run:

```bash
cd backend && pytest \
  tests/test_meal_plan_service.py \
  tests/test_meal_product_recommendation_service.py \
  tests/test_api_mall.py \
  tests/test_agent_tools.py \
  tests/test_langchain_agent.py \
  -q
```

Expected: PASS。

- [ ] **Step 2: 手动检查 Agent 提示词顺序**

Run:

```bash
cd backend && python - <<'PY'
from app.services.langchain_agent import LangChainAgentRunner
print(LangChainAgentRunner()._system_prompt())
PY
```

Expected:

```text
提示词中同时包含 meal_plan、mall_recommend，并明确最终回复先给餐单再追加“可选商品”。
```

- [ ] **Step 3: 最终全量后端测试**

Run:

```bash
cd backend && pytest -q
```

Expected: PASS。

## Implementation Notes

- 现有工作区有未跟踪的 `__pycache__` 和 `prd/prototype/.DS_Store`，执行本计划时不要清理或提交这些文件，除非用户另行要求。
- `MealPlanService` 当前由 LLM 生成自然语言餐单；P5 不要求把餐单改成 JSON。商品推荐服务直接消费餐单文本，保持最小改动。
- `MallProductRecommendationService` 内部使用 `_json_list` 和 `_has_allergy_conflict`，避免依赖 `mall_recommendation.py` 的私有函数。
- P6 再扩展推荐依据结构化字段；P5 只输出可读推荐原因。

## Self-Review

- Spec coverage: P5 的三个目标均已覆盖：餐单后提取健康原则和食材方向、复用商城标签和推荐规则、Agent 回复追加可选商品。
- Placeholder scan: 本计划没有保留未定义的待办占位。
- Type consistency: `scope/member_id/meal_plan_text/limit` 在 service、tool 和 LangChain tool 中保持一致。
