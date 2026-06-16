# P5 餐单接商品推荐设计

日期：2026-06-16

## 1. 背景和目标

根据 `docs/liangda-health-iteration-roadmap.md`，P5 需要把餐单推荐继续转化为商品推荐，这是“AI 智能营销”主 demo 的关键链路。

当前项目已经具备基础能力：

- `MealPlanService`：基于健康画像生成单人或全家餐单。
- `HealthProfileService`：聚合成员档案、健康事实、手环近期状态和互动记忆。
- 商城模块：已有商品、标签、健康专区、商品详情、购物车和基础推荐规则。
- Agent 工具路由：已有 `meal_plan`、`memory_search`、`kb_search` 工具。

本阶段目标是完成一个最小闭环：

```text
用户问吃什么
→ Agent 调用 meal_plan 生成餐单
→ 系统从餐单和画像中提取健康原则、食材方向
→ 复用商城商品标签推荐商品
→ Agent 回复中追加“可选商品”
```

典型 demo：

```text
用户：爸爸今晚吃什么？

Agent：
爸爸今晚建议低钠、少油，主食减量。
可以用鸡胸肉或豆腐替代鱼。

可选商品：
- 低钠盐：契合低钠清淡方向
- 杂粮组合：适合作为晚餐轻负担主食
- 无糖豆浆：补充优质蛋白，避免高糖饮品
```

## 2. 范围

包含：

- 新增餐单商品推荐服务。
- 从餐单文本、健康画像饮食原则、近期状态和目标中提取推荐方向。
- 复用现有商城商品 `recommend_tags`、`health_tags` 和 `warning_tags`。
- 商品推荐遵守过敏和健康禁忌优先级。
- Agent 新增 `mall_recommend` 工具。
- Agent 在餐单回复后追加“可选商品”段落。
- 增加后端单元测试。

不包含：

- 不做 P6 推荐证据链 UI。
- 不改商品详情页。
- 不新增商品表字段。
- 不新增餐单或推荐结果持久化表。
- 不做自动加入购物车。
- 不做真实支付或订单。
- 不引入商品 embedding、用户画像 embedding 或 rerank。
- 不让 LLM 自由决定商品匹配规则。

## 3. 推荐方案

采用方案 A：

```text
新增 MealProductRecommendationService
+ 读取 HealthProfileService
+ 读取 SqlAlchemyMallRepository 商品列表
+ 规则匹配餐单方向和商品标签
+ Agent 暴露 mall_recommend 工具
```

原因：

- 符合路线图 P5 的“复用商城商品标签和推荐规则”目标。
- 不改现有商城数据结构，不影响商城首页和商品详情。
- `MealPlanService` 当前输出自然语言餐单，直接消费餐单文本是最小改动。
- 推荐逻辑留在服务层，可测试、可解释，避免把业务规则写进 prompt。
- 后续 P6 可以在该服务基础上扩展结构化证据链。

不采用把商品推荐直接写入 `MealPlanService` 的方案。餐单服务负责“吃什么”，商品推荐负责“买什么”，职责混在一起会让后续购物车、证据链和商品详情扩展变复杂。

不采用新增推荐表的方案。当前阶段只需要即时推荐，不需要保存推荐历史，新增表会引入刷新和一致性问题。

## 4. 数据优先级

P5 商品推荐必须继承路线图中的推荐决策优先级：

```text
过敏/禁忌
> 报告健康事实
> 个人健康标签
> 手环近期状态
> 当前问题和餐单方向
> 记忆偏好
> 营销转化
```

具体原则：

- 如果商品 `warning_tags` 命中成员过敏信息，直接过滤。
- 健康画像中的 `avoid_tags` 不直接当作商品标签匹配，但不能推荐明显冲突方向。
- 记忆偏好只能影响推荐排序和文案，不能覆盖过敏、报告事实或健康约束。
- 全家推荐按最严格家庭限制处理，任一成员过敏都过滤相关商品。

## 5. 后端设计

### 5.1 新增 `MealProductRecommendationService`

新增文件：

- `backend/app/services/meal_product_recommendation_service.py`

职责：

- 根据 `scope` 区分单人推荐和全家推荐。
- 单人推荐读取 `HealthProfileService.get_member_profile(member_id)`。
- 全家推荐读取 `HealthProfileService.get_family_profile()`。
- 通过 `SqlAlchemyMallRepository.list_all_products()` 获取商品。
- 根据餐单文本和画像字段生成商品推荐排序。
- 输出稳定 Markdown 文本，供 Agent 直接拼接到最终回复。

建议接口：

```python
class MealProductRecommendationService:
    def __init__(
        self,
        db: Session,
        *,
        mall_repository: SqlAlchemyMallRepository | None = None,
        profile_service: HealthProfileService | None = None,
    ):
        ...

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 3,
    ) -> str:
        ...
```

输出格式：

```text
可选商品：
- 商品名：推荐原因
- 商品名：推荐原因
- 商品名：推荐原因

说明：以上是根据本次餐单方向和健康画像匹配的商城商品，本推荐不构成医疗建议。
```

如果没有匹配商品：

```text
可选商品：暂无匹配商品。

说明：以上是根据本次餐单方向和健康画像匹配的商城商品，本推荐不构成医疗建议。
```

### 5.2 新增 `MallRecommendTool`

修改文件：

- `backend/app/services/agent_tools.py`

新增工具：

```python
class MallRecommendTool:
    def __init__(self, service, allowed_member_ids: list[str]):
        ...

    def recommend(
        self,
        *,
        scope: str,
        meal_plan_text: str,
        member_id: str | None = None,
        limit: int = 3,
    ) -> str:
        ...
```

校验规则：

- `scope` 只能是 `member` 或 `family`。
- `meal_plan_text` 不能为空。
- `scope == "member"` 时必须传 `member_id`。
- `member_id` 必须在当前可用家人列表中。

### 5.3 Agent 注册 `mall_recommend`

修改文件：

- `backend/app/services/langchain_agent.py`
- `backend/app/api/agent.py`

`LangChainAgentRunner` 构造函数新增：

```python
mall_recommend_tool=None
```

`_tools()` 新增：

```python
def mall_recommend(
    scope: str,
    meal_plan_text: str,
    member_id: str | None = None,
    limit: int = 3,
) -> str:
    """根据 meal_plan 工具返回的餐单文本和健康画像推荐商城商品。"""
    return self.mall_recommend_tool.recommend(
        scope=scope,
        member_id=member_id,
        meal_plan_text=meal_plan_text,
        limit=limit,
    )
```

`get_agent_runner()` 中注入：

```python
mall_recommend_tool=MallRecommendTool(
    service=MealProductRecommendationService(
        db,
        mall_repository=SqlAlchemyMallRepository(db),
    ),
    allowed_member_ids=allowed_member_ids,
)
```

## 6. 商品标签匹配规则

第一版只做常见健康饮食方向，避免复杂规则引擎。

| 输入关键词 | 商品推荐标签 |
| --- | --- |
| 低钠、清淡、血压 | `low_sodium`, `hypertension` |
| 控糖、低GI、血糖、主食定量、杂粮、燕麦、糙米 | `sugar_control`, `low_gi` |
| 少油、低脂、轻负担、晚餐减轻 | `low_fat` |
| 高纤维、高纤、杂粮、蔬菜、黑米、藜麦 | `high_fiber` |
| 优质蛋白、高蛋白、鸡胸肉、豆腐、豆浆、牛奶、蛋 | `high_protein` |
| 高钙、骨密度、骨质、牛奶、芝麻 | `high_calcium`, `nutrients` |
| 低嘌呤、尿酸、痛风 | `low_purine` |

参与匹配的上下文：

```text
meal_plan_text
+ HealthProfile.diet_principles
+ HealthProfile.recent_states
+ HealthProfile.goals
+ FamilyHealthProfile.shared_principles
+ FamilyHealthProfile.family_modifiers
+ FamilyHealthProfile.family_goals
```

排序规则：

```text
过敏冲突过滤
> 餐单关键词命中
> 健康画像原则/近期状态/目标命中
> 现有会员商品推荐分
> 商品 product_id 稳定排序
```

推荐原因第一版用固定文案：

| 命中方向 | 推荐原因 |
| --- | --- |
| 低钠 | 契合本次低钠清淡方向 |
| 控糖/低 GI | 适合作为控糖或低 GI 主食选择 |
| 低脂 | 更适合少油轻负担饮食 |
| 高纤维 | 补充膳食纤维，适合餐单中的杂粮方向 |
| 高蛋白 | 补充优质蛋白，适合餐单搭配 |
| 高钙/营养素 | 匹配高钙和营养补充方向 |
| 低嘌呤 | 更适合关注尿酸和嘌呤摄入的人群 |

## 7. Agent 行为规则

系统提示词增加：

```text
当用户询问吃什么、早餐、午餐、晚餐、一日三餐或全家共餐时，必须先调用 meal_plan 工具生成餐单。
meal_plan 工具返回餐单后，必须把 meal_plan 工具返回的餐单文本作为 meal_plan_text 参数继续调用 mall_recommend 工具。
最终回复先给餐单，再追加 mall_recommend 返回的“可选商品”段落。
mall_recommend 的 scope 和 member_id 必须与 meal_plan 保持一致；全家餐单使用 scope="family"，不传 member_id。
如果 mall_recommend 返回 Error，只输出餐单并简短说明暂时无法推荐商品。
```

这保证 P5 的商品推荐发生在餐单之后，而不是让 LLM 自己编商品。

## 8. 测试设计

新增测试文件：

- `backend/tests/test_meal_product_recommendation_service.py`

覆盖：

- 单人餐单包含“低钠、杂粮、鸡胸肉”时，推荐低钠、杂粮或高蛋白方向商品。
- 全家推荐中过敏冲突商品被过滤。
- 单人推荐缺少 `member_id` 时返回明确 Error。

修改测试：

- `backend/tests/test_agent_tools.py`
  - 覆盖 `MallRecommendTool` 正常调用。
  - 覆盖未知 `member_id` 拒绝。

- `backend/tests/test_langchain_agent.py`
  - 覆盖 `mall_recommend` tool 注册。
  - 覆盖 system prompt 包含餐单后调用商品推荐的规则。

建议回归命令：

```bash
cd backend && pytest \
  tests/test_meal_plan_service.py \
  tests/test_meal_product_recommendation_service.py \
  tests/test_api_mall.py \
  tests/test_agent_tools.py \
  tests/test_langchain_agent.py \
  -q
```

最终全量：

```bash
cd backend && pytest -q
```

## 9. 后续扩展边界

P6 再做：

- 推荐证据链结构化输出。
- 商品详情展示健康事实、手环状态、互动记忆和商品标签依据。
- Agent 回复中展示可追溯依据。

P7 再考虑：

- 商品 embedding。
- 用户画像 embedding。
- Hybrid Search + rerank。
- LLM 推荐结果自检。

这些不进入 P5，避免把当前最小闭环做复杂。
