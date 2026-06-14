# 手环设备总览页设计

日期：2026-06-14

## 1. 背景与目标

本次仅设计并实现手环相关的最简闭环，范围严格限定为：

- 设备总览页，对齐 `prd/prototype/device.html`
- 手动同步，触发最近 7 天缺失数据补齐
- 服务启动时自动检查最近 7 天数据是否完整，缺失则补齐

本次不包含：

- 真实硬件接入
- 蓝牙连接
- 多设备管理
- 实时数据流
- 异常预警闭环
- 复杂同步流水明细

目标是先把页面、接口、落库 mock 数据和启动补数机制打通，保证设备页可以稳定展示，并且服务重启后历史 7 天数据保持连续。

## 2. 约束

- 必须使用现有技术栈：
  - 前端：React + Vite + React Query
  - 后端：FastAPI + SQLAlchemy
- 设计必须贴合现有项目结构，不额外引入重型框架
- 只做可运行的最简流程，不做额外兜底设计
- mock 数据必须落库持久化
- 每次服务启动时检查最近 7 天是否完整，完整则不处理，缺失则补齐
- 手动同步只补缺失数据，不覆盖已有数据

## 3. 方案选择

- 使用一个轻量设备绑定表保存设备展示信息
- 使用一个设备每日汇总表保存最近 7 天体征数据
- 页面由后端一次性聚合返回，前端只负责渲染和触发同步

## 4. 页面范围

页面路径建议为 `/devices`。

页面内容对齐 `prd/prototype/device.html`，包含：

- 家庭成员切换
- 设备状态卡
- 今日步数卡
- 今日平均心率卡
- 今日睡眠卡
- 近 7 天图表
- 同步记录列表
- 手动同步按钮

不做绑定流程页面。首版由后端在成员存在时自动补建默认设备绑定信息。

## 5. 数据模型

### 5.1 device_bindings

用途：保存成员当前绑定的 mock 设备展示信息。

字段：

- `id`
- `member_id`
- `device_name`
- `device_status`
- `battery_level`
- `last_sync_at`
- `created_at`
- `updated_at`

约束：

- `member_id` 唯一

说明：

- 首版默认每个成员只绑定一个设备
- `device_name` 固定使用 mock 值，例如 `小米手环 8 Pro`
- `device_status` 首版固定为 `connected`

### 5.2 device_daily_metrics

用途：保存某成员某一天的手环汇总数据。

字段：

- `id`
- `member_id`
- `metric_date`
- `steps`
- `avg_heart_rate`
- `systolic_bp`
- `diastolic_bp`
- `sleep_hours`
- `blood_oxygen`
- `sync_status`
- `sync_source`
- `created_at`
- `updated_at`

约束：

- `member_id + metric_date` 唯一

说明：

- 每条记录表示 1 天的聚合数据
- `sync_source` 首版固定为 `mock`
- `sync_status` 首版默认 `success`

## 6. mock 数据生成规则

mock 数据由后端生成并落库，要求看起来稳定、连续、不夸张。

生成原则：

- 基于 `member_id + metric_date` 计算稳定随机种子
- 同一个成员同一天的数据固定
- 不同成员有差异
- 不同日期有轻微波动

建议范围：

- `steps`: 3000 ~ 12000
- `avg_heart_rate`: 62 ~ 88
- `systolic_bp`: 118 ~ 138
- `diastolic_bp`: 72 ~ 88
- `sleep_hours`: 5.8 ~ 8.6
- `blood_oxygen`: 95 ~ 99

轻量修正：

- 年龄偏大：步数略低、血压略高
- 周末：步数略高、睡眠略长

生成后数据即落库，后续不重复生成同一天已有记录。

## 7. 最近 7 天定义

最近 7 天定义为：当天往前数 6 天，共 7 个自然日。

例如在 2026-06-14 启动服务，则检查：

- 2026-06-08
- 2026-06-09
- 2026-06-10
- 2026-06-11
- 2026-06-12
- 2026-06-13
- 2026-06-14

## 8. 后端职责划分

新增模块：

- `backend/app/models/device.py`
- `backend/app/schemas/device.py`
- `backend/app/repositories/device_repository.py`
- `backend/app/services/device_service.py`
- `backend/app/api/device.py`

职责：

- repository：负责设备绑定与每日汇总表的查写
- service：负责补数、mock 生成、overview 聚合
- api：负责对外暴露设备页接口

## 9. 启动补数逻辑

服务启动后，在建表完成时执行一次设备 mock 初始化流程。

流程：

1. 查询当前所有成员
2. 对每个成员确保存在 `device_bindings`
3. 检查最近 7 天 `device_daily_metrics`
4. 缺失哪一天就补哪一天
5. 更新 `last_sync_at`

规则：

- 若最近 7 天完整，不做任何补写
- 若部分日期缺失，仅补缺失日期
- 不覆盖已有日期数据

## 10. 手动同步逻辑

接口触发后，复用与启动补数相同的逻辑。

流程：

1. 校验成员存在
2. 检查最近 7 天数据
3. 仅补齐缺失日期
4. 更新 `last_sync_at`
5. 返回最新 overview 数据

规则：

- 不生成第 8 天或更久以前的数据
- 不重算已有日期
- 前端收到返回结果后直接刷新页面

## 11. API 设计

### 11.1 获取设备总览

`GET /api/devices/{member_id}/overview`

用途：

- 返回设备总览页渲染所需的完整数据

返回结构：

```json
{
  "member": {
    "member_id": "mem_xxx",
    "name": "王建国",
    "relation": "父亲"
  },
  "device": {
    "device_name": "小米手环 8 Pro",
    "device_status": "connected",
    "battery_level": 78,
    "last_sync_at": "2026-06-14T09:30:00"
  },
  "summary": {
    "steps": 8562,
    "steps_target": 10000,
    "avg_heart_rate": 72,
    "heart_rate_range_text": "近7日均值 69-78 次/分",
    "sleep_hours": 7.2,
    "sleep_target": 8.0,
    "blood_pressure": "126/78",
    "blood_oxygen": 97
  },
  "charts": {
    "steps_7d": [
      { "date": "2026-06-08", "value": 7200 }
    ],
    "heart_rate_7d": [
      { "date": "2026-06-08", "value": 71 }
    ],
    "sleep_7d": [
      { "date": "2026-06-08", "value": 6.8 }
    ],
    "blood_oxygen_7d": [
      { "date": "2026-06-08", "value": 98 }
    ]
  },
  "sync_logs": [
    {
      "date": "2026-06-14",
      "status": "success",
      "message": "已补齐最近7天缺失数据",
      "time": "09:30"
    }
  ]
}
```

说明：

- `summary` 取最近一天数据
- 图表固定返回最近 7 天，按日期升序
- `blood_pressure` 由收缩压和舒张压拼接
- `sync_logs` 首版不单独建表，由服务端即时组装展示项

### 11.2 手动同步

`POST /api/devices/{member_id}/sync`

用途：

- 补齐最近 7 天缺失数据
- 返回最新 overview

返回结构：

- 与 `GET /overview` 保持一致

## 12. 前端设计

新增文件建议：

- `frontend/src/pages/DevicePage.tsx`
- `frontend/src/lib/device.ts`
- `frontend/src/types/device.ts`

并在 `frontend/src/main.tsx` 注册 `/devices` 路由。

页面逻辑：

1. 进入页面后请求成员列表
2. 默认选中第一个成员
3. 请求该成员 overview
4. 切换成员时重新拉取 overview
5. 点击同步时调用 sync 接口
6. 同步成功后直接使用返回数据刷新页面

空状态：

- 无成员时显示“请先创建家人档案”

说明：

- 不单独处理未绑定状态，后端自动创建默认绑定
- 页面样式按 `prd/prototype/device.html` 对齐实现

## 13. 展示口径

- 顶部步数卡：展示最近一天步数，目标固定 10000
- 顶部心率卡：展示最近一天平均心率，副文案展示近 7 天心率范围
- 顶部睡眠卡：展示最近一天睡眠时长，目标固定 8 小时
- 顶部设备卡：展示设备名称、连接状态、电量和上次同步时间
- 图表：固定最近 7 天
- 同步记录：展示最近一次同步结果和若干条最近自动同步占位记录

## 14. 错误处理

首版仅保留最基本错误处理：

- 成员不存在：返回 404
- overview 查询失败：前端显示基础错误态
- sync 失败：前端提示同步失败

不增加复杂重试、补偿逻辑或后台任务机制。

## 15. 测试方案

首版重点补后端测试。

建议新增测试：

1. `test_device_overview_returns_7_days`
   - 创建成员
   - 调 overview
   - 断言最近 7 天数据完整

2. `test_device_sync_fills_missing_days_only`
   - 构造缺失天
   - 调 sync
   - 断言只补缺失日期，无重复记录

3. `test_device_binding_auto_created`
   - 成员存在但无绑定记录
   - 调 overview
   - 断言自动创建绑定

4. `test_overview_summary_uses_latest_day`
   - 构造最近 7 天数据
   - 断言 summary 来自最近一天

## 16. 后续扩展空间

本次设计刻意不实现以下能力，但当前结构允许后续扩展：

- 替换 mock 数据源为真实硬件同步数据
- 扩展为一人多设备
- 增加同步日志表
- 增加异常预警判定
- 增加分钟级趋势数据

这些扩展不属于本次范围，不进入当前实现计划。
