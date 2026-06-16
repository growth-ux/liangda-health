# P3 记忆系统接入设计

日期：2026-06-15

## 1. 背景和目标

根据 `docs/liangda-health-iteration-roadmap.md`，P3 需要新增 mem0 记忆框架，支持偏好、排斥、阶段目标和营销反馈，并让 Agent 推荐前读取相关记忆。

本阶段目标是完成一个最小闭环：

```text
用户表达偏好或反馈
→ 写入 mem0 记忆
→ 后续餐单或推荐前检索记忆
→ Agent 输出体现个性化
```

典型 demo：

```text
用户：爸爸不喜欢鱼
系统：写入记忆
用户：爸爸今晚吃什么
系统：生成低钠、少油餐单，并用鸡胸肉或豆腐替代鱼
```

## 2. 范围

本次只做 P3 记忆系统，不提前实现 P4-P6 的完整工具路由、餐单到商品转化和推荐证据链展示。

包含：

- 接入 `mem0ai` 依赖。
- 新增 `MemoryService`，薄封装 mem0。
- 新增 `MemorySearchTool`。
- Agent 暴露 `memory_search` 工具。
- 用户消息保存后写入记忆。
- 餐单生成前读取相关记忆。
- 记忆影响明确饮食偏好，例如“不喜欢鱼”。
- 增加后端单元测试。

不包含：

- 不新增前端记忆管理页面。
- 不做复杂记忆审核流。
- 不做本地 `agent_memories` 业务表。
- 不做逻辑删除。
- 不做多后端存储抽象。
- 不做推荐证据链 UI。
- 不让记忆覆盖健康禁忌、过敏、报告健康事实或手环状态。

## 3. 推荐方案

采用方案 A：

```text
mem0 薄封装
+ Agent memory_search 工具
+ 餐单服务读取记忆
```

原因：

- 符合路线图明确的 mem0 方向。
- 当前 Agent 已经通过 `LangChainAgentRunner` 暴露 `meal_plan` 和 `kb_search` 工具，新增 `memory_search` 边界清晰。
- 当前对话历史只取最近 8 条，mem0 正好承担跨会话偏好和反馈。
- 餐单服务本身必须被调用，仅在 prompt 注入记忆无法保证工具输出避开用户排斥项。
- 第一版只做一个薄服务，不引入额外基础设施。

## 4. 记忆边界

记忆系统只负责：

```text
这个人最近怎么想、怎么选、怎么买
```

个人档案、健康事实和手环数据仍负责：

```text
这个人是谁、身体有什么硬约束、报告有什么证据、近期状态如何
```

记忆类型只保留四类：

| 类型 | 说明 | 示例 |
| --- | --- | --- |
| `preference` | 喜欢或偏好 | 爸爸喜欢鸡肉 |
| `avoidance` | 不喜欢或排斥 | 爸爸不喜欢鱼 |
| `goal` | 阶段目标 | 妈妈最近想控糖 |
| `marketing_feedback` | 营销反馈 | 用户连续跳过高价商品 |

健康安全优先级不变：

```text
过敏/禁忌
> 报告健康事实
> 个人健康标签
> 手环近期状态
> 当前问题
> 记忆偏好
> 营销转化
```

示例：

```text
档案：爸爸高血压
记忆：爸爸喜欢咸口
```

系统不能推荐重盐食品，只能推荐低钠调味替代方案。

## 5. 后端文件设计

### 5.1 `backend/app/services/memory_service.py`

新增 `MemoryService`。

职责：

- 延迟初始化 mem0 client。
- 根据当前对话和家庭成员列表推断记忆归属。
- 写入用户消息中的可记忆内容，并带上推断出的记忆归属。
- 按 query 检索记忆。
- 把 mem0 返回值格式化成 Agent 和餐单服务容易消费的文本。
- 在测试中允许传入 fake client。

建议接口：

```python
class MemoryService:
    def __init__(self, client=None, family_user_id: str | None = None, enabled: bool | None = None):
        ...

    def add_from_user_message(self, content: str, *, member_id: str | None = None) -> None:
        ...

    def search(self, query: str, *, member_id: str | None = None, limit: int = 5) -> list[MemoryItem]:
        ...

    def search_text(self, query: str, *, member_id: str | None = None, limit: int = 5) -> str:
        ...
```

`MemoryItem` 使用 dataclass：

```python
@dataclass(frozen=True)
class MemoryItem:
    content: str
    memory_type: str | None = None
    member_id: str | None = None
```

mem0 的 `user_id` 不固定写死为 `default_family`。本项目第一版用下面的最简归属规则：

- 如果用户话语能指向某个家庭成员，例如“爸爸不喜欢吃鱼”，先根据家庭成员的 `relation/name/member_id` 推断出 `member_id`，写入 mem0 时使用该 `member_id` 作为 `user_id`。
- 如果用户明确说“全家/我们家/家里人都...”，写入家庭级记忆，mem0 的 `user_id` 使用 `default_family`。
- 如果无法明确指向单个成员，也没有明确的全家表达，不写入记忆，避免把个人偏好混入家庭级记忆。

写入单人记忆时，metadata 中也保留 `member_id`，方便后续格式化和排查；写入家庭级记忆时，metadata 中可标记 `scope=family`。

写入时给 mem0 的文本需要带项目约束：

```text
只沉淀 preference、avoidance、goal、marketing_feedback。
不要记录健康禁忌、诊断结论、报告事实或手环数据。
记忆归属：{member_id 或 default_family}
用户原话：{content}
```

第一版不做额外本地分类器，避免把规则做复杂。需要分类展示时，先从 mem0 metadata 或文本中取；没有类型时显示 `memory`。

### 5.2 `backend/app/services/agent_tools.py`

新增 `MemorySearchTool`。

职责：

- 校验 query 非空。
- 调用 `MemoryService.search_text(...)`。
- 返回纯文本，供 LangChain tool 使用。

建议接口：

```python
class MemorySearchTool:
    def __init__(self, service: MemoryService):
        self.service = service

    def search(self, query: str, member_id: str | None = None, limit: int = 5) -> str:
        ...
```

### 5.3 `backend/app/services/langchain_agent.py`

`LangChainAgentRunner` 构造函数新增：

```python
memory_tool=None
```

`_tools()` 新增：

```python
def memory_search(query: str, member_id: str | None = None, limit: int = 5) -> str:
    """检索家庭或指定家人的长期互动记忆，包括偏好、排斥、阶段目标和营销反馈。"""
    return self.memory_tool.search(query=query, member_id=member_id, limit=limit)
```

system prompt 增加规则：

```text
涉及餐单、商品推荐、饮食偏好、排斥、阶段目标或购买反馈时，先调用 memory_search。
涉及某位家人时，memory_search 传入该家人的 member_id；涉及全家时不传 member_id，检索家庭级记忆。
记忆只能用于个性化表达，不能覆盖过敏、健康禁忌、报告事实和健康安全约束。
```

### 5.4 `backend/app/services/meal_plan_service.py`

`MealPlanService` 构造函数新增：

```python
def __init__(self, db: Session, memory_service: MemoryService | None = None):
    ...
```

单人餐单：

```text
HealthProfileService 获取健康画像
→ MemoryService 搜索成员偏好/排斥
→ 生成默认餐单
→ 应用明确排斥记忆
→ 格式化输出
```

第一版只处理一个 demo 必需规则：

```text
如果记忆包含“不喜欢鱼”或“不吃鱼”，餐单里的“鱼”替换为“鸡胸肉/豆腐”。
```

全家餐单先搜索家庭级记忆。若存在全家偏好或排斥，应用同样的鱼替换规则。后续 P5 再扩展到商品推荐。

输出中可以增加一行：

```text
个性化记忆：已避开爸爸不喜欢的鱼。
```

这行只在确实命中记忆时出现。

### 5.5 `backend/app/services/agent_service.py`

`AgentService` 构造函数新增：

```python
memory_service=None
```

发送消息流程：

```text
保存用户消息
→ 写入记忆
→ 调用 runner
→ 保存 assistant 消息
```

流式消息流程同样在保存用户消息后写入。

写入记忆失败不应中断聊天主流程，但需要记录日志，避免第三方记忆服务异常导致基础聊天不可用。

### 5.6 `backend/app/api/agent.py`

新增依赖组装：

```text
MemoryService
MemorySearchTool
MealPlanService(db, memory_service)
LangChainAgentRunner(memory_tool=...)
AgentService(memory_service=...)
```

`MemoryService` 需要拿到家庭成员列表或成员解析能力。第一版不新增复杂实体识别模块，可复用 `SqlAlchemyMemberRepository.list_members()` 的结果做轻量匹配：

- 命中成员 `relation` 或 `name` 时，写入和检索使用该成员 `member_id`。
- 命中“全家/我们家/家里人”等家庭表达时，使用 `default_family`。
- 无法明确命中成员且没有家庭表达时，跳过记忆写入。

## 6. 配置设计

新增配置项：

```python
memory_enabled: bool = True
memory_family_user_id: str = "default_family"
memory_provider: str = "mem0"
```

mem0 使用现有模型配置：

```text
llm_base_url
llm_api_key
llm_model
```

依赖新增：

```text
mem0ai
```

写入：

- `backend/requirements.txt`
- `pyproject.toml`

`MemoryService` 中延迟 import mem0，避免未启用记忆时影响基础服务启动。

## 7. 数据流

### 7.1 写入记忆

```text
POST /api/agent/sessions/{session_id}/messages:send
→ AgentService._save_user_message
→ 根据当前用户消息推断 member_id 或明确家庭级 default_family
→ 若无法判断归属，跳过记忆写入
→ 否则 MemoryService.add_from_user_message
→ mem0.add(..., user_id=member_id 或 default_family)
→ runner.run(...)
→ 保存 assistant message
```

流式接口：

```text
POST /api/agent/sessions/{session_id}/messages:stream
→ AgentService._save_user_message
→ 根据当前用户消息推断 member_id 或明确家庭级 default_family
→ 若无法判断归属，跳过记忆写入
→ 否则 MemoryService.add_from_user_message
→ runner.stream(...)
→ 保存 assistant message
```

### 7.2 餐单读取记忆

```text
用户：爸爸今晚吃什么
→ Agent 调用 meal_plan(scope="member", member_id="...")
→ MealPlanService.get_member_profile
→ MemoryService.search("饮食 偏好 排斥", member_id=...)
→ mem0.search(..., filters={"user_id": member_id})
→ 生成餐单
→ 应用明确排斥
→ 返回餐单
```

全家餐单：

```text
用户：全家今晚吃什么
→ Agent 调用 meal_plan(scope="family")
→ MemoryService.search("全家 饮食 偏好 排斥")
→ mem0.search(..., filters={"user_id": "default_family"})
→ 生成全家餐单
→ 应用全家明确排斥
→ 返回餐单
```

### 7.3 Agent 主动检索记忆

```text
用户：为什么不推荐鱼？
→ Agent 调用 memory_search(query="爸爸 饮食 排斥", member_id="...")
→ mem0.search(..., filters={"user_id": member_id})
→ 返回：爸爸不喜欢鱼
→ Agent 解释个性化依据
```

## 8. 错误处理

记忆系统第一版只做必要处理：

- `memory_enabled=False` 时，写入 no-op，检索返回空。
- `llm_api_key` 缺失时，mem0 初始化失败应在写入或检索时记录日志，并返回空记忆。
- `memory_search` query 为空时返回 `Error: query 不能为空`。
- mem0 调用异常时，聊天主流程继续，检索结果为空。

不新增复杂重试、队列、死信、后台补偿或一致性机制。

## 9. 测试计划

新增或修改测试：

### 9.1 `backend/tests/test_memory_service.py`

覆盖：

- `add_from_user_message` 调用 fake client，并在单人记忆中把推断出的 `member_id` 作为 mem0 `user_id`。
- “全家都不喜欢吃鱼”这类输入写入家庭级记忆，mem0 `user_id` 为 `default_family`。
- 无法明确归属到成员或全家的输入不写入记忆。
- 写入文本包含四类记忆约束。
- `search` 调用 fake client，并传入 query、user_id、limit。
- `search_text` 能把结果格式化为多行文本。
- disabled 状态写入 no-op，检索为空。

### 9.2 `backend/tests/test_agent_tools.py`

新增：

- `MemorySearchTool.search` 正常返回记忆文本。
- query 为空时返回错误。

### 9.3 `backend/tests/test_meal_plan_service.py`

新增：

- 记忆包含“爸爸不喜欢鱼”时，单人餐单不出现“鱼”。
- 没有记忆时，保持现有餐单输出。
- 记忆包含“喜欢咸口”时，高血压成员仍输出低钠原则，不推荐重盐。

### 9.4 `backend/tests/test_agent_service.py`

新增：

- `send_message` 保存用户消息后调用记忆写入。
- `stream_message` 保存用户消息后调用记忆写入。
- 记忆写入异常不阻断 runner。

### 9.5 `backend/tests/test_langchain_agent.py`

新增：

- runner 有 `memory_tool` 时，工具列表包含 `memory_search`。
- system prompt 包含记忆边界说明。

## 10. 验收标准

后端验收：

- 安装依赖后服务能启动。
- Agent runner 暴露 `memory_search` 工具。
- 用户发送“爸爸不喜欢鱼”后会调用记忆写入。
- 后续生成爸爸餐单时，输出不包含鱼，并说明已避开该偏好。
- 没有记忆时，现有餐单能力不退化。
- 记忆不覆盖低钠、控糖、过敏等健康安全约束。
- 相关 pytest 通过。

demo 验收：

```text
1. 用户：爸爸不喜欢鱼
2. 用户：爸爸今晚吃什么
3. Agent：返回适合爸爸健康状态的晚餐，且用鸡胸肉/豆腐替代鱼
```

## 11. 后续阶段

P4 可基于本次结果继续做更明确的意图识别和工具路由。

P5 可让餐单结果进一步转商品推荐，并读取 `marketing_feedback` 调整商品选择。

P6 可把记忆作为推荐证据链的一部分展示：

```text
互动记忆：爸爸不喜欢鱼
```
