#!/usr/bin/env python3
"""
粮达健康 · AI 智能营销竞赛版系统架构图

目标：
1. 先讲业务闭环：多源健康输入 -> AI 决策 -> 营销输出 -> 反馈回写
2. 再讲技术可信度：前端 / 后端 / 数据层 / 外部模型能力
3. 突出项目特色：报告证据追溯、健康事实沉淀、家庭记忆、推荐理由可解释
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path


OUTPUT = Path(__file__).parent / "liangda-health-technical-architecture.excalidraw"
FONT_FAMILY = 5
UPDATED_AT = 1781699203000
elements: list[dict] = []


def uid() -> str:
    return uuid.uuid4().hex[:16]


def base() -> dict:
    return {
        "id": uid(),
        "angle": 0,
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": 1,
        "version": 1,
        "versionNonce": 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": UPDATED_AT,
        "link": None,
        "locked": False,
    }


def text(
    x: float,
    y: float,
    w: float,
    h: float,
    content: str,
    *,
    font_size: int = 14,
    color: str = "#1e1e1e",
    align: str = "left",
    vertical: str = "top",
    line_height: float = 1.25,
) -> dict:
    el = base()
    el.update(
        {
            "type": "text",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "strokeColor": color,
            "backgroundColor": "transparent",
            "text": content,
            "fontSize": font_size,
            "fontFamily": FONT_FAMILY,
            "textAlign": align,
            "verticalAlign": vertical,
            "containerId": None,
            "originalText": content,
            "lineHeight": line_height,
            "baseline": int(font_size * 0.85),
        }
    )
    elements.append(el)
    return el


def box(
    x: float,
    y: float,
    w: float,
    h: float,
    content: str,
    *,
    fill: str = "#ffffff",
    stroke: str = "#1e1e1e",
    stroke_width: float = 1,
    font_size: int = 14,
    text_color: str = "#1e1e1e",
    roundness: dict | None = None,
) -> dict:
    el = base()
    el.update(
        {
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "strokeColor": stroke,
            "backgroundColor": fill,
            "strokeWidth": stroke_width,
            "roundness": roundness or {"type": 3},
        }
    )
    elements.append(el)
    lines = content.split("\n")
    line_h = h / max(len(lines), 1)
    for i, line in enumerate(lines):
        text(
            x,
            y + i * line_h,
            w,
            line_h,
            line,
            font_size=font_size,
            color=text_color,
            align="center",
            vertical="middle",
        )
    return el


def container_box(
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    *,
    fill: str = "#f8f9fa",
    stroke: str = "#868e96",
    title_size: int = 16,
) -> dict:
    el = base()
    el.update(
        {
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "strokeColor": stroke,
            "backgroundColor": fill,
            "strokeWidth": 1,
            "strokeStyle": "dashed",
            "roundness": {"type": 3},
        }
    )
    elements.append(el)
    title_w = len(title) * title_size * 0.9 + 30
    text(x + 16, y - title_size * 0.7, title_w, title_size * 1.4, title, font_size=title_size, color="#1e1e1e")
    return el


def arrow(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = "#495057",
    style: str = "solid",
    label: str | None = None,
    label_dx: float = 0,
    label_dy: float = 0,
    stroke_width: float = 1.8,
) -> dict:
    el = base()
    dx, dy = x2 - x1, y2 - y1
    el.update(
        {
            "type": "arrow",
            "x": x1,
            "y": y1,
            "width": abs(dx) if dx != 0 else 0.0001,
            "height": abs(dy) if dy != 0 else 0.0001,
            "strokeColor": color,
            "backgroundColor": "transparent",
            "strokeWidth": stroke_width,
            "strokeStyle": style,
            "points": [[0, 0], [dx, dy]],
            "lastCommittedPoint": None,
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": None,
            "endArrowhead": "arrow",
            "elbowed": False,
        }
    )
    elements.append(el)
    if label:
        lx = (x1 + x2) / 2 + label_dx
        ly = (y1 + y2) / 2 + label_dy
        lw = max(len(label) * 9, 80)
        text(lx - lw / 2, ly - 10, lw, 20, label, font_size=12, color=color, align="center", vertical="middle")
    return el


# ===== 标题 =====
text(60, 32, 1400, 42, "粮达健康 · AI 智能营销系统架构图", font_size=28, color="#1e1e1e")
text(
    60,
    80,
    1700,
    24,
    "面向竞赛展示：以家庭健康理解为基础，打通多源数据、Agent 决策、精准推荐与营销转化闭环",
    font_size=14,
    color="#495057",
)


# ===== 1. 业务主闭环 =====
container_box(60, 130, 1880, 600, "① 业务主闭环（评委主视角）", fill="#fff9db", stroke="#f08c00")

# 输入层
container_box(90, 180, 420, 500, "多源健康输入", fill="#fff4e6", stroke="#ffa94d")
input_boxes = [
    (120, 220, 360, 90, "健康报告\nPDF 上传 + OCR 补偿 + 原文留痕", "#ffd8a8", "#d9480f"),
    (120, 330, 360, 90, "家庭档案\n成员关系 / 年龄 / 过敏 / 健康标签", "#ffd8a8", "#d9480f"),
    (120, 440, 360, 90, "手环近 7 天数据\n睡眠 / 步数 / 心率 / 血压等近期状态", "#ffd8a8", "#d9480f"),
    (120, 550, 360, 90, "互动记忆\n饮食偏好 / 排斥 / 阶段目标 / 营销反馈", "#ffd8a8", "#d9480f"),
]
for x, y, w, h, content, fill, color in input_boxes:
    box(x, y, w, h, content, fill=fill, text_color=color, font_size=15)

# 中间 AI 核心
container_box(560, 180, 860, 500, "AI 决策中枢", fill="#eef7ff", stroke="#1971c2")
box(
    720,
    220,
    540,
    105,
    "健康画像聚合器\n融合长期风险、近期状态、饮食原则、禁忌与偏好",
    fill="#a5d8ff",
    text_color="#0b3d91",
    font_size=17,
    stroke="#1971c2",
    stroke_width=1.5,
)
box(
    720,
    355,
    540,
    125,
    "Agent 工具编排\nkb_search · memory_search · meal_plan · mall_recommend · respond",
    fill="#74c0fc",
    text_color="#0b3d91",
    font_size=16,
    stroke="#1971c2",
    stroke_width=1.5,
)
box(
    640,
    520,
    700,
    120,
    "可解释决策能力\n报告证据追溯 + 健康事实沉淀 + 推荐理由生成 + 结构化卡片输出",
    fill="#d0ebff",
    text_color="#0b3d91",
    font_size=16,
    stroke="#1971c2",
    stroke_width=1.5,
)

# 输出层
container_box(1470, 180, 440, 500, "营销输出与转化", fill="#ebfbee", stroke="#2b8a3e")
output_boxes = [
    (1500, 220, 380, 88, "健康建议与报告解读\n给出结论、风险提醒与执行建议", "#b2f2bb", "#1e531b"),
    (1500, 325, 380, 88, "个性化餐单生成\n围绕家庭共餐与成员调整输出", "#b2f2bb", "#1e531b"),
    (1500, 430, 380, 88, "健康商品推荐\n把饮食原则映射到米面油、杂粮、调味等商品", "#b2f2bb", "#1e531b"),
    (1500, 535, 380, 88, "推荐依据展示\n说明来自哪份报告、哪类画像与哪条偏好", "#b2f2bb", "#1e531b"),
]
for x, y, w, h, content, fill, color in output_boxes:
    box(x, y, w, h, content, fill=fill, text_color=color, font_size=15)

# 输入 -> AI
for y in (265, 375, 485, 595):
    arrow(480, y, 720, 270 if y == 265 else 420 if y in (375, 595) else 580, color="#e67700", label="输入", label_dy=-12)

# AI 内部
arrow(990, 325, 990, 355, color="#1971c2", label="画像驱动", label_dx=70)
arrow(990, 480, 990, 520, color="#1971c2", label="编排输出", label_dx=70)

# AI -> 输出
arrow(1260, 270, 1500, 265, color="#2b8a3e", label="建议生成", label_dy=-12)
arrow(1260, 420, 1500, 370, color="#2b8a3e", label="餐单生成", label_dy=-12)
arrow(1260, 420, 1500, 475, color="#2b8a3e", label="商品推荐", label_dy=-12)
arrow(1260, 580, 1500, 580, color="#2b8a3e", label="理由可解释", label_dy=-12)

# 反馈闭环
box(
    560,
    690,
    1350,
    60,
    "用户点击、咨询、购买与反馈再次写入互动记忆，形成“理解 -> 建议 -> 推荐 -> 反馈 -> 再推荐”的持续优化闭环",
    fill="#fff0f6",
    stroke="#c2255c",
    text_color="#a61e4d",
    font_size=15,
    stroke_width=1.5,
)
arrow(1690, 623, 1690, 720, color="#c2255c", label="反馈", label_dx=50)
arrow(560, 720, 300, 640, color="#c2255c", style="dashed", label="记忆回写", label_dy=12)


# ===== 2. 技术实现支撑 =====
container_box(60, 790, 1880, 360, "② 技术实现支撑（技术可信度）", fill="#f8f9fa", stroke="#868e96")

# 前端
container_box(90, 845, 400, 255, "前端交互层", fill="#f1f3f5", stroke="#adb5bd")
box(120, 885, 340, 68, "React 19 + TypeScript + Vite", fill="#e7f5ff", text_color="#0b3d91", font_size=16)
box(120, 970, 340, 55, "ChatPage / Members / Reports / Device / Mall", fill="#e7f5ff", text_color="#0b3d91", font_size=14)
box(120, 1040, 340, 40, "结构化回复卡片 + 商品推荐卡片", fill="#e7f5ff", text_color="#0b3d91", font_size=14)

# 后端
container_box(530, 845, 560, 255, "应用与编排层", fill="#f1f3f5", stroke="#adb5bd")
box(560, 885, 500, 68, "FastAPI API\nagent / kb / members / health_analysis / device / mall / notice", fill="#d3f9d8", text_color="#1e531b", font_size=15)
box(560, 970, 500, 55, "服务层\nKbService / HealthProfileService / AgentService / MallRecommendation", fill="#d3f9d8", text_color="#1e531b", font_size=14)
box(560, 1040, 500, 40, "LangChain Agent Runner + AgentEvidenceCollector", fill="#d3f9d8", text_color="#1e531b", font_size=14)

# 数据
container_box(1130, 845, 430, 255, "数据与记忆层", fill="#f1f3f5", stroke="#adb5bd")
box(1160, 885, 370, 68, "MySQL 8.4\nmembers / kb_documents / health_facts / mall_products / agent_sessions", fill="#f3f0ff", text_color="#5f3dc4", font_size=14)
box(1160, 970, 370, 55, "Milvus 2.5.3\n报告向量检索 + 记忆向量检索", fill="#f3f0ff", text_color="#5f3dc4", font_size=14)
box(1160, 1040, 370, 40, "mem0 + history.db\n家庭级 / 成员级长期记忆", fill="#f3f0ff", text_color="#5f3dc4", font_size=14)

# 外部能力
container_box(1600, 845, 310, 255, "外部模型能力", fill="#f1f3f5", stroke="#adb5bd")
box(1630, 885, 250, 68, "DashScope\nQwen-plus", fill="#fff5f5", text_color="#c92a2a", font_size=15)
box(1630, 970, 250, 55, "text-embedding-v3\n1024 维向量", fill="#fff5f5", text_color="#c92a2a", font_size=14)
box(1630, 1040, 250, 40, "PDF 解析 + OCR 补偿", fill="#fff5f5", text_color="#c92a2a", font_size=14)

# 连接箭头
arrow(460, 918, 560, 918, color="#495057", label="HTTP / JSON")
arrow(1060, 918, 1160, 918, color="#495057", label="Repository")
arrow(1060, 995, 1160, 995, color="#495057", label="Vector Search")
arrow(1060, 1060, 1160, 1060, color="#495057", label="Memory")
arrow(1530, 920, 1630, 920, color="#fa5252", label="LLM")
arrow(1530, 995, 1630, 995, color="#fa5252", label="Embedding")
arrow(1530, 1060, 1630, 1060, color="#fa5252", label="OCR / Parse")


# ===== 3. 价值总结 =====
container_box(60, 1190, 1880, 120, "③ 项目差异化价值（比赛答辩可直接引用）", fill="#eef7ff", stroke="#4c6ef5")
box(
    90,
    1230,
    1820,
    52,
    "不是普通问答，也不是普通商城，而是把“报告理解、健康画像、Agent 编排、商品转化、反馈记忆”串成一个可持续优化的家庭健康智能营销系统",
    fill="#dbe4ff",
    stroke="#4c6ef5",
    text_color="#364fc7",
    font_size=16,
    stroke_width=1.5,
)


diagram = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {"viewBackgroundColor": "#ffffff", "gridSize": 20},
    "files": {},
}

OUTPUT.write_text(json.dumps(diagram, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✅ 已生成 {OUTPUT}")
print(f"   元素总数: {len(elements)}")
