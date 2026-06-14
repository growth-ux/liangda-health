# 健康分析功能设计

日期：2026-06-14

## 1. 背景与目标

本次设计健康分析功能，对齐 `prd/prototype/report.html`，实现一个可运行的家庭健康分析页。

第一版数据来源严格限定为：

- 成员资料
- 成员健康标签
- 成员报告数量
- 设备近 7 天数据

本次不包含：

- 从 PDF 报告中结构化抽取体检指标
- 新增健康指标明细表
- 健康分析结果历史归档
- 医疗诊断结论
- 通知闭环
- 复杂导出能力

目标是先打通健康分析页的最简闭环：后端聚合现有数据并计算分析结果，前端按原型展示家庭指标、摘要、异常 Top 5 和成员健康卡。

## 2. 约束

- 必须使用现有技术栈：
  - 前端：React + Vite + React Query
  - 后端：FastAPI + SQLAlchemy
- 页面样式和结构必须贴合 `prd/prototype/report.html`
- 不新增重型依赖
- 不做 PDF 指标抽取
- 不额外设计兜底、归档、逻辑删除等复杂机制
- 后端负责聚合与计算，前端只负责展示和交互

## 3. 方案选择

采用“后端规则聚合 + 前端纯展示”的方案。

后端新增健康分析 API，统一读取成员、报告数量、设备近 7 天数据和健康标签，计算家庭综合分、待关注数量、异常指标 Top 5、摘要和成员健康卡。

前端新增健康分析页面，通过一个接口拿到完整页面数据，按原型渲染。

不采用前端自行聚合多个接口的方案，因为分析规则会分散到页面中，后续 Agent、商城推荐、通知等模块难以复用。

不采用新增健康指标表的方案，因为第一版没有结构化体检指标，也不需要历史归档，新增表会超出当前目标。

## 4. 页面范围

页面路径：`/report`

页面内容对齐 `prd/prototype/report.html`，包含：

- 顶部标题区：家庭名、页面标题、分析周期、周期选择、导出按钮
- 核心指标：家庭综合分、待关注指标、已存报告、已绑设备
- 本周家庭健康摘要
- 异常指标 Top 5
- 各成员健康卡

首版导出按钮只保留 UI，不实现真实文件导出。

异常指标中的“看建议”首版跳转到 Agent 页面，并携带建议 prompt；如果实现成本需要压缩，也可以先作为不可跳转按钮展示。

## 5. 后端职责划分

新增模块：

- `backend/app/api/health_analysis.py`
- `backend/app/schemas/health_analysis.py`
- `backend/app/services/health_analysis_service.py`

修改模块：

- `backend/app/main.py`

职责：

- `api`：暴露健康分析接口，处理查询参数
- `schemas`：定义页面返回结构
- `service`：聚合成员、报告、设备数据并计算分析结果
- `main.py`：注册健康分析 router

复用现有模块：

- `SqlAlchemyMemberRepository`
- `SqlAlchemyDeviceRepository`
- `DeviceService`
- `KbDocument`

## 6. API 设计

### 6.1 获取家庭健康分析

`GET /api/health-analysis/overview?range=this_month`

查询参数：

- `range=this_month`
- `range=last_3_months`
- `range=last_6_months`
- `range=last_12_months`

说明：

- 第一版设备分析固定使用最近 7 天
- `range` 主要影响页面周期文案和报告数量统计区间
- 如果未传 `range`，默认 `this_month`

返回结构：

```json
{
  "family": {
    "name": "张雨微的家庭",
    "period_label": "2026-06"
  },
  "metrics": {
    "family_score": 78,
    "family_score_delta": -3,
    "attention_count": 5,
    "report_count": 5,
    "device_count": 1
  },
  "summary": [
    {
      "level": "danger",
      "text": "关注：王秀英血压偏高，近 7 天收缩压均值 152 mmHg"
    }
  ],
  "abnormal_items": [
    {
      "metric": "收缩压",
      "member_id": "mem_xxx",
      "member_name": "王秀英",
      "member_relation": "妈",
      "current_value": "152 mmHg",
      "status": "danger",
      "status_text": "偏高",
      "trend_text": "持续偏高",
      "suggestion": "建议减少高钠饮食，并在 6 月底前安排复诊"
    }
  ],
  "member_cards": [
    {
      "member_id": "mem_xxx",
      "name": "王秀英",
      "relation": "妈",
      "age": 65,
      "health_score": 68,
      "status": "warning",
      "status_text": "2项待关注",
      "avatar_text": "王"
    }
  ]
}
```

## 7. 数据计算规则

### 7.1 最近 7 天设备数据

健康分析页打开时，后端对每个成员调用 `DeviceService.ensure_recent_7_days(member_id)`，确保设备近 7 天 mock 数据存在。

随后从 `device_daily_metrics` 读取最近 7 天数据，计算：

- 平均步数
- 平均心率
- 平均收缩压
- 平均舒张压
- 平均睡眠时长
- 平均血氧

### 7.2 成员健康分

每个成员从 100 分开始扣分，最终限制在 0 到 100 之间。

扣分规则：

- 每个健康标签扣 4 分，最多扣 20 分
- 报告数量为 0 时扣 6 分
- 平均收缩压 `>= 140` 扣 12 分
- 平均收缩压 `130-139` 扣 6 分
- 平均舒张压 `>= 90` 扣 10 分
- 平均舒张压 `85-89` 扣 5 分
- 平均睡眠 `< 6` 扣 8 分
- 平均睡眠 `6-6.5` 扣 4 分
- 平均步数 `< 4000` 扣 6 分
- 平均步数 `4000-6000` 扣 3 分
- 平均血氧 `< 95` 扣 10 分
- BMI `>= 28` 扣 8 分
- BMI `24-27.9` 扣 4 分

BMI 使用成员资料中的 `height_cm` 和 `weight_kg` 计算。缺少身高或体重时不计算 BMI 风险。

### 7.3 家庭综合分

家庭综合分为所有成员健康分的平均值，四舍五入。

如果没有成员，返回 0。

### 7.4 家庭分变化

第一版没有历史分析结果，不新增归档表。

`family_score_delta` 使用轻量规则生成：

- 待关注项大于等于 4 时返回 `-3`
- 待关注项为 1 到 3 时返回 `0`
- 待关注项为 0 时返回 `2`

### 7.5 待关注指标

待关注指标来自三类数据：

1. 健康标签
   - 高血压
   - 糖尿病
   - 高血脂
   - 骨质疏松
   - 超重
   - 痛风
   - 心血管
   - 胃肠
2. 设备指标
   - 血压
   - 睡眠
   - 步数
   - 血氧
   - 心率
3. 成员资料
   - BMI

异常项分级：

- `danger`：血压明显偏高、血氧偏低、睡眠严重不足、BMI 肥胖
- `warning`：轻度偏高、轻度不足、健康标签提示风险

异常 Top 5 排序：

1. `danger` 优先
2. 同级按扣分值从高到低
3. 最多返回 5 条

`attention_count` 为所有异常项数量，不只是 Top 5 数量。

## 8. 摘要生成规则

第一版不调用大模型，使用规则模板生成类似 Agent 摘要的文案。

最多返回 4 条：

- 关注：选择风险最高的异常项
- 改善或稳定：选择健康分最高的成员
- 提醒：选择睡眠、步数、报告不足或健康标签风险中的一个
- 建议：根据最高风险项生成行动建议

示例：

- `关注：王秀英血压偏高，近 7 天收缩压均值 152 mmHg`
- `稳定：张雨微近期设备指标整体平稳，健康分 92`
- `提醒：张小溪暂无近期体检报告，建议补充儿童生长发育记录`
- `建议：为王秀英减少高钠食品摄入，并在 6 月底前安排血压复查`

## 9. 前端职责划分

新增模块：

- `frontend/src/api/healthAnalysis.ts`
- `frontend/src/pages/HealthAnalysisPage.tsx`

修改模块：

- `frontend/src/main.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/styles.css`

职责：

- `healthAnalysis.ts`：封装 `/api/health-analysis/overview`
- `HealthAnalysisPage.tsx`：渲染健康分析页
- `main.tsx`：注册 `/report` 路由
- `AppShell.tsx`：健康分析导航跳转到 `/report`
- `styles.css`：补充页面样式，复用现有卡片、按钮、标签风格

## 10. 前端页面行为

### 10.1 数据请求

页面使用 React Query：

```ts
useQuery({
  queryKey: ['health-analysis', range],
  queryFn: () => getHealthAnalysisOverview(range)
})
```

### 10.2 周期切换

周期下拉选项：

- 本月：`this_month`
- 近 3 月：`last_3_months`
- 近 6 月：`last_6_months`
- 近 1 年：`last_12_months`

切换后重新请求接口。

### 10.3 页面状态

- 加载中：显示 `正在加载健康分析...`
- 加载失败：显示 `健康分析加载失败`
- 无成员：显示空状态，引导去 `/members`

### 10.4 看建议

点击异常项的“看建议”时跳转到：

`/chat?prompt=请根据{成员名}的{指标}问题给出家庭健康建议`

如果现有 Chat 页暂不消费 `prompt` 参数，第一版可以先完成跳转，后续再接入自动填充。

### 10.5 成员卡跳转

点击成员健康卡跳转：

`/members/{member_id}`

## 11. 测试设计

### 11.1 后端测试

新增测试文件：

- `backend/tests/test_api_health_analysis.py`

测试场景：

- 有成员、有报告、有设备数据时返回完整 overview
- 高血压标签和高血压设备均值会进入异常 Top 5
- 无成员时返回空指标，不报错
- 成员无报告时健康分扣分，摘要出现报告提醒
- 有设备绑定的成员计入 `device_count`

### 11.2 前端验证

当前前端项目没有测试框架，第一版不新增测试框架。

验证方式：

- `npm run build`
- 本地打开 `/report` 页面检查：
  - 页面布局贴合原型
  - 周期切换可重新加载
  - 指标卡、摘要、异常表格、成员卡正常展示
  - 成员卡可跳转详情页

## 12. 实现顺序

1. 定义后端 schema
2. 实现 `HealthAnalysisService`
3. 实现 `/api/health-analysis/overview`
4. 注册 router
5. 添加后端测试
6. 新增前端 API 类型和请求函数
7. 新增 `HealthAnalysisPage`
8. 注册 `/report` 路由
9. 修改导航链接
10. 补充页面样式
11. 运行后端测试和前端构建

## 13. 后续可扩展方向

以下内容不进入第一版：

- PDF 体检指标结构化抽取
- 健康分析结果按月归档
- 趋势图和历史对比
- Agent 自动生成长摘要
- 商城推荐联动
- 异常通知闭环
- 导出 PDF 或 Excel
