# 膳食匹配私域 Agent — HTML 原型 v0.2

> 一份**可点击的网页原型**，采用**克制、留白、健康绿**的设计风格。

## 快速开始

**直接打开 `welcome.html` 开始体验**（推荐入口）。

也可以从 `home.html` 直接进入主界面，跳过引导。

## 文件结构

```
prd/prototype/
├── welcome.html          # 欢迎页
├── onboard-1.html        # 引导 1：创建家庭
├── add-member.html       # 引导 2：添加家人
├── upload.html           # 引导 3：上传报告（含识别结果）
├── home.html             # 首页（家庭总览）
├── chat.html             # 聊天主界面
├── members.html          # 家人列表
├── member-detail.html    # 家人详情（以妈妈为例）
├── report.html           # 家庭健康报表
├── mall.html             # 商场首页
├── product-detail.html   # 商品详情（含推荐理由）
├── device.html           # 手环设备绑定
├── notice.html           # 通知中心
├── css/style.css         # 样式
└── js/common.js          # 侧边栏/顶栏渲染
```

## 12 个页面清单

| 编号 | 文件 | 说明 |
| --- | --- | --- |
| P1 | welcome.html | 欢迎页：产品价值 + 3 步引导入口 |
| P2 | onboard-1.html | 创建家庭（家庭名/城市/成员数） |
| P3 | add-member.html | 添加家人（基础信息 + 慢病标签 + 忌口） |
| P4 | upload.html | 上传报告（拖拽 + 识别 + 归属） |
| P5 | home.html | 首页：家庭健康分 + 关键入口 + 今日推荐 |
| P6 | chat.html | 聊天：会话列表 + 消息流 + 卡片推荐 |
| P7 | members.html | 家人列表：4 位成员卡片 |
| P8 | member-detail.html | 家人详情：指标 + 趋势 + 报告 + 长期建议 |
| P9 | report.html | 家庭健康仪表盘 + 异常指标 Top 5 |
| P10 | mall.html | 商场：家庭推荐 + 健康专区 + 分类 |
| P11 | product-detail.html | 商品详情：含"为什么推荐" |
| P12 | device.html | 手环绑定：已绑/支持品牌/绑定流程 |
| P13 | notice.html | 通知中心：预警/系统/推荐 |

## 推荐体验路径

```
welcome.html
  → onboard-1.html（创建家庭）
    → add-member.html（添加家人）
      → upload.html（上传报告 + 识别 + 归属）
        → home.html（首页）
          ↔ chat.html（聊天咨询 / 接收推荐）
          ↔ members.html → member-detail.html（看家人详情）
          ↔ report.html（看健康报表）
          ↔ mall.html → product-detail.html（看推荐商品）
          ↔ device.html（绑定手环）
          ↔ notice.html（看通知）
```

## 核心交互演示点

打开 **chat.html** 可以看到：
- **主动推荐卡片**：基于血压偏高推送"低钠专区"
- **多轮对话**：用户问"没胃口/睡眠差"，管家给健康建议 + 商品横滑
- **报告解读卡片**：自动解读体检异常项
- **快捷指令**：底部 `/` 唤出指令面板

打开 **product-detail.html** 可以看到：
- **可解释推荐**：每个商品都有"为什么推荐"盒子，引用具体家庭成员的指标
- **推荐搭配**：基于同一健康目标推荐相关商品

打开 **member-detail.html** 可以看到：
- **多源数据融合**：报告 + 手环体征 + 用户填写的健康标签
- **趋势图**：手环数据可视化
- **报告时间轴**：历次体检对比

## 设计风格

- **背景**：`#f5f7f5`（极浅灰绿）
- **主色（健康绿）**：`#10b981`（强调按钮/链接/标签）
- **文字**：`#111827`（深灰） / `#4b5563`（次级） / `#9ca3af`（弱化）
- **边框**：`#e5e7eb`（极浅）
- **头像**：浅色背景（橘/粉/蓝/绿/紫）+ 大字姓氏，圆角 8px
- **状态标签**：浅色底 + 文字色，无填充实心
- **卡片**：无阴影、白色底、1px 极细边框、8px 圆角
- **按钮**：圆角 6px、绿色填充
- **字体**：13-14px，weight 400-500

## 角色色（头像背景）

- 爸爸 = 蓝色 (#dbeafe / #2563eb)
- 妈妈 = 粉色 (#fce7f3 / #db2777)
- 自己 = 橙色 (#fed7aa / #f97316)
- 孩子 = 绿色 (#d1fae5 / #059669)
- 其他 = 紫色 (#e9d5ff / #7c3aed)

## 注意事项

1. **静态原型**：所有数据均为 mock，无后端调用
2. **跳转为硬编码**：点击各卡片/链接会跳到对应 HTML
3. **图表为占位**：用 CSS 简单绘制柱状图原型，正式版需用 ECharts/D3
4. **响应式**：当前为 PC 端设计，未做移动端 H5 适配
5. **图标为 emoji**：占位用，正式版建议替换为 Iconify/Material Icons

## 后续建议

- v0.2：接 ECharts 真实图表
- v0.3：补 H5 移动端适配
- v0.4：补空状态/加载状态/异常状态
- v0.5：导出 PDF（家庭健康档案）
