# 通知模块设计文档

日期：2026-06-14

## 1. 背景与目标

本次设计系统内通知中心，对齐 `prd/prototype/notice.html`。

范围严格限定为系统内消息中心，不做短信、微信、App 推送、邮件或第三方触达。

目标：

- 通知页支持分类筛选、按时间分组、未读状态和操作按钮
- 通知数据由后端根据现有业务数据按固定规则生成
- 用户操作能够持久化，包括单条已读、全部已读、稍后和收到
- 顶部通知角标展示未读数量
- 前后端使用项目现有技术栈最小实现

## 2. 本次范围

### 2.1 包含

- 通知列表页 `/notice`
- 通知分类筛选：全部、健康预警、系统、推荐
- 通知分组：今天、本周、更早
- 通知未读数统计
- 单条操作：查看、稍后、收到
- 全部已读
- 后端通知表、通知 API、规则生成服务
- 与现有成员、报告、手环、商城数据的轻量关联

### 2.2 不包含

- 站外推送
- 多用户收件箱
- 通知模板管理后台
- 定时任务调度系统
- 消息队列
- 发送失败重试
- 通知删除、逻辑删除、回收站
- 复杂通知偏好设置

## 3. 关键决策

### 3.1 通知产生方式

采用“落库通知 + 规则补齐”的方式。

每次读取通知列表或 summary 前，后端调用规则生成服务，根据当前业务数据补齐缺失通知。补齐依赖 `dedupe_key` 去重，避免重复生成。

选择原因：

- 能持久化已读、稍后、收到状态
- 不需要改造所有业务入口
- 不引入事件队列和调度系统
- 与当前项目“最简流程”要求一致

### 3.2 分类方式

通知内部分类保留 4 类：

- `health_alert`：健康预警
- `system`：系统
- `recommendation`：推荐
- `reminder`：提醒

前端筛选按钮只展示：

- 全部
- 健康预警
- 系统
- 推荐

`reminder` 不单独放筛选按钮，只在“全部”中展示。这样和原型一致，也避免增加界面复杂度。

### 3.3 操作方式

通知操作只改变通知自身状态，不反向改业务数据。

- 查看：标记为已读，然后跳转目标页
- 稍后：标记为 `snoozed`
- 收到：标记为 `done`
- 全部已读：把所有 `unread` 改为 `read`

## 4. 后端设计

### 4.1 模块结构

新增：

- `backend/app/models/notice.py`
- `backend/app/schemas/notice.py`
- `backend/app/repositories/notice_repository.py`
- `backend/app/services/notice_service.py`
- `backend/app/api/notice.py`

改造：

- `backend/app/main.py`
  - import notice model
  - include notice router
- `frontend/src/components/AppShell.tsx`
  - 顶部角标读取未读数
  - 侧边栏通知入口跳转 `/notice`

### 4.2 数据模型

新增表 `notices`。

字段：

```text
id                  int primary key auto increment
notice_id           varchar(64) unique not null
category            varchar(30) not null
level               varchar(20) not null
title               varchar(120) not null
description         text not null
source              varchar(30) not null
member_id           varchar(64) null
target_type         varchar(30) null
target_id           varchar(64) null
action_text         varchar(20) null
secondary_action    varchar(20) null
status              varchar(20) not null
dedupe_key          varchar(160) unique not null
created_at          datetime not null
updated_at          datetime not null
```

字段说明：

- `notice_id`：业务 ID，格式 `not_<uuid>`
- `category`：`health_alert`、`system`、`recommendation`、`reminder`
- `level`：`danger`、`warning`、`info`、`success`
- `source`：`housekeeper` 或 `system`
- `member_id`：关联家人，可为空
- `target_type`：前端跳转类型，例如 `chat`、`report`、`upload`、`mall`、`member`、`devices`
- `target_id`：跳转所需业务 ID，例如 `document_id`、`member_id`
- `status`：`unread`、`read`、`snoozed`、`done`
- `dedupe_key`：规则去重键

首版不加外键约束，保持当前项目风格简单一致。

### 4.3 Schema 设计

新增响应结构：

```text
NoticeItem
NoticeGroup
NoticeCounts
NoticeListResponse
NoticeSummaryResponse
```

`NoticeItem` 字段：

- `notice_id`
- `category`
- `level`
- `title`
- `description`
- `source`
- `source_text`
- `status`
- `created_at`
- `meta_text`
- `target_url`
- `action_text`
- `secondary_action`

`NoticeListResponse` 字段：

- `counts`
- `groups`

`NoticeSummaryResponse` 字段：

- `unread`

### 4.4 Repository 职责

`SqlAlchemyNoticeRepository` 负责：

- 按 `dedupe_key` 判断通知是否存在
- 创建通知
- 查询通知列表
- 查询未读数
- 更新单条状态
- 批量全部已读

查询排序：

- `created_at desc`
- 同时间按 `id desc`

### 4.5 Service 职责

`NoticeService` 负责：

- 调用规则生成流程
- 组装通知列表响应
- 组装 summary 响应
- 根据 `target_type` 和 `target_id` 生成前端跳转 URL
- 生成中文时间描述和分组标签
- 执行单条操作和全部已读

时间分组规则：

- 今天：`created_at.date() == date.today()`
- 本周：最近 7 天内但不是今天
- 更早：其他

`meta_text` 规则：

- 今天内：`30 分钟前 · 来自管家`
- 昨天：`昨天 HH:mm · 来自系统`
- 更早：`YYYY-MM-DD · 来自管家`

## 5. 规则生成设计

规则生成在读取列表和 summary 前执行一次。

### 5.1 欢迎通知

条件：

- 当前没有任何通知

生成：

- category: `system`
- level: `info`
- title: `欢迎使用粮达健康`
- description: `您的家庭健康档案已创建，添加家人并上传第一份报告开始吧！`
- source: `system`
- target_type: `upload`
- action_text: `上传`
- dedupe_key: `welcome`

### 5.2 报告识别完成

条件：

- `kb_documents.status = ready`

每份报告生成一条。

生成：

- category: `system`
- level: `info`
- title: `新报告已识别`
- description: `{成员名} 的体检报告已识别完成，报告内容已归档。`
- source: `system`
- member_id: 文档所属成员
- target_type: `report`
- target_id: `document_id`
- action_text: `查看`
- dedupe_key: `report_ready:{document_id}`

### 5.3 健康预警

条件：

- 读取成员最近一天 `device_daily_metrics`
- `systolic_bp >= 140` 或 `diastolic_bp >= 90`

每个成员每天最多生成一条。

生成：

- category: `health_alert`
- level: `danger`
- title: `{关系}血压偏高`
- description: `最近一次血压为 {systolic}/{diastolic} mmHg，已超过建议关注阈值。已为您推荐相关健康专区。`
- source: `housekeeper`
- member_id: 当前成员
- target_type: `chat`
- action_text: `查看`
- secondary_action: `稍后`
- dedupe_key: `bp_high:{member_id}:{metric_date}`

### 5.4 改善通知

条件：

- 同一成员最近两天都有手环数据
- 最近一天收缩压和舒张压均低于前一天
- 最近一天未达到血压预警阈值

生成：

- category: `health_alert`
- level: `success`
- title: `{关系}血压改善`
- description: `最近一次血压较前一天下降，继续保持。`
- source: `housekeeper`
- member_id: 当前成员
- target_type: `devices`
- action_text: `收到`
- dedupe_key: `bp_improved:{member_id}:{metric_date}`

### 5.5 补充报告提醒

条件：

- 成员没有任何报告，或最近报告日期距离当前日期超过 6 个月

每个成员每天最多生成一条。

生成：

- category: `reminder`
- level: `info`
- title: `建议补充报告`
- description: `{姓名}（{关系}）的最新体检报告已超过 6 个月，建议上传新报告。`
- source: `housekeeper`
- member_id: 当前成员
- target_type: `upload`
- action_text: `上传`
- dedupe_key: `report_reminder:{member_id}:{today}`

说明：

- 如果成员没有任何报告，描述改为 `{姓名}（{关系}）还没有体检报告，建议上传第一份报告。`

### 5.6 推荐通知

条件：

- 成员健康标签包含高血压、高血脂、糖尿病、控糖、低钠、补钙等关键词
- 商城存在匹配专区或商品

每个成员每天最多生成一条。

生成：

- category: `recommendation`
- level: `info`
- title: `3 个新推荐商品`
- description: `根据家庭最新健康数据，管家为您推荐了适合 {关系} 的健康商品。`
- source: `housekeeper`
- member_id: 当前成员
- target_type: `mall`
- action_text: `查看`
- dedupe_key: `mall_recommendation:{member_id}:{today}`

健康标签映射：

- 高血压、低钠 -> 低钠专区
- 糖尿病、控糖、高血糖 -> 控糖专区
- 高血脂、低脂 -> 低脂专区
- 缺钙、骨质疏松 -> 高钙专区
- 蛋白、营养不良 -> 高蛋白专区

## 6. API 设计

### 6.1 获取通知列表

```text
GET /api/notices?category=all|health_alert|system|recommendation
```

说明：

- 默认 `category=all`
- 请求前先执行规则补齐
- `all` 包含 `reminder`
- 其他分类只返回对应 category

返回示例：

```json
{
  "counts": {
    "all": 12,
    "health_alert": 3,
    "system": 4,
    "recommendation": 5,
    "unread": 3
  },
  "groups": [
    {
      "label": "今天",
      "items": [
        {
          "notice_id": "not_xxx",
          "category": "health_alert",
          "level": "danger",
          "title": "妈妈血压偏高",
          "description": "最近一次血压为 152/92 mmHg，已超过建议关注阈值。",
          "source": "housekeeper",
          "source_text": "来自管家",
          "status": "unread",
          "created_at": "2026-06-14T10:20:00",
          "meta_text": "30 分钟前 · 来自管家",
          "target_url": "/chat",
          "action_text": "查看",
          "secondary_action": "稍后"
        }
      ]
    }
  ]
}
```

### 6.2 获取未读数

```text
GET /api/notices/summary
```

返回：

```json
{
  "unread": 3
}
```

### 6.3 单条已读

```text
POST /api/notices/{notice_id}/read
```

返回更新后的通知。

### 6.4 全部已读

```text
POST /api/notices/read-all
```

返回：

```json
{
  "updated": 3
}
```

### 6.5 稍后

```text
POST /api/notices/{notice_id}/snooze
```

把状态改为 `snoozed`。

### 6.6 收到

```text
POST /api/notices/{notice_id}/done
```

把状态改为 `done`。

## 7. 前端设计

### 7.1 新增文件

- `frontend/src/api/notices.ts`
- `frontend/src/pages/NoticePage.tsx`

改造：

- `frontend/src/main.tsx`
  - 增加 `/notice` 路由
- `frontend/src/components/AppShell.tsx`
  - 通知导航 href 改为 `/notice`
  - 顶部 Bell badge 使用 `/api/notices/summary`
- `frontend/src/styles.css`
  - 增加通知页样式

### 7.2 页面布局

页面标题使用 `通知中心`。

顶部工具栏：

- 左侧筛选按钮：
  - 全部 `{counts.all}`
  - 健康预警 `{counts.health_alert}`
  - 系统 `{counts.system}`
  - 推荐 `{counts.recommendation}`
- 右侧按钮：全部已读

内容区：

- 以 card 分组展示
- 分组标题：今天、本周、更早
- 每条通知包含：
  - 左侧状态图标
  - 标题
  - 描述
  - meta 文案
  - 右侧操作按钮

### 7.3 交互规则

- 切换分类：更新本地 category state，并重新请求列表
- 点击查看：
  1. 调用 `/read`
  2. 更新列表缓存
  3. 跳转 `target_url`
- 点击稍后：
  1. 调用 `/snooze`
  2. 更新列表缓存
- 点击收到：
  1. 调用 `/done`
  2. 更新列表缓存
- 点击全部已读：
  1. 调用 `/read-all`
  2. 刷新列表和 summary

### 7.4 图标映射

使用 lucide-react 图标，不使用 emoji 作为主要 UI 图标。

- `danger`：`TriangleAlert`
- `warning`：`Clock`
- `info`：`FileText` 或 `ShoppingBag`
- `success`：`Check`

## 8. 跳转 URL 规则

`NoticeService` 根据 `target_type` 生成 URL：

```text
chat      -> /chat
report    -> /reports/{target_id}
upload    -> /reports
mall      -> /mall
member    -> /members/{target_id}
devices   -> /devices
```

如果 `target_type` 为空，则不展示主操作按钮。

## 9. 状态与样式

状态含义：

- `unread`：未读，正常展示
- `read`：已读，透明度降低
- `snoozed`：稍后，透明度降低
- `done`：已处理，透明度降低

前端不隐藏已读通知，保持和原型“更早”已读项一致。

## 10. 测试设计

新增 `backend/tests/test_api_notice.py`。

覆盖：

- 首次读取通知会生成欢迎通知
- 报告 ready 时生成系统通知
- 高血压手环数据生成健康预警
- 分类筛选只返回对应分类
- `category=all` 包含 reminder
- 单条已读会减少 summary 未读数
- 全部已读会清空未读数
- 稍后和收到会更新状态
- 重复读取不会生成重复通知

前端验证：

- 执行 `npm run build`
- 如项目已有稳定 lint/test 命令，则同步执行

## 11. 实施顺序

1. 新增后端 notice model/schema/repository/service/api
2. 在 `main.py` 注册模型和 router
3. 编写后端测试覆盖 API 和规则生成
4. 新增前端 notices API
5. 新增 NoticePage
6. 改造路由和 AppShell 通知入口
7. 添加通知页 CSS
8. 执行后端测试和前端 build

## 12. 验收标准

- `/notice` 页面视觉和 `prd/prototype/notice.html` 保持一致
- 筛选按钮数量正确
- 通知按今天、本周、更早分组
- 未读角标来自真实 API
- 全部已读后角标变为 0
- 单条查看会标记已读并跳转
- 稍后和收到能持久化状态
- 重复刷新不会重复生成同一条规则通知
- 后端通知测试通过
- 前端能正常构建
