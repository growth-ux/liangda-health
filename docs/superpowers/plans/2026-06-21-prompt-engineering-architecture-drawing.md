# Prompt Engineering 架构图画图计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 `docs/superpowers/specs/2026-06-21-prompt-engineering-architecture-design.md` 生成一张可交付的 Prompt Engineering 架构图（drawio 格式），用于 AI 竞赛方案展示。

**Architecture:** 用 Python 脚本按 spec 定义结构化数据，生成 drawio XML 文件（mxGraphModel）。脚本风格对齐项目已有的 `docs/architecture/generate-architecture-diagram.py`，但输出格式是 drawio（与 `context_engineering_arch.drawio` 一致）。

**Tech Stack:** Python 3（标准库）、drawio XML（mxGraphModel 格式）

---

## 背景信息

- spec：`docs/superpowers/specs/2026-06-21-prompt-engineering-architecture-design.md`
- 目标产物：`docs/architecture/prompt-engineering-architecture.drawio`
- 工具脚本：`docs/architecture/generate-prompt-engineering-architecture.py`
- 参考风格：`docs/architecture/context_engineering_arch.drawio`（同款 swimlane + 圆角矩形 + 颜色编码风格）

## 颜色与样式约定

为了让生成的图与 `context_engineering_arch.drawio` 视觉风格一致，使用以下色板（写死在脚本里）：

```python
PALETTE = {
    "title":       "#0f172a",   # 标题文字
    "subtitle":    "#475569",   # 副标题文字
    "container":   "#f8fafc",   # 外层 swimlane
    "container_b": "#cbd5e1",   # 外层 swimlane 边框
    "agent_loop":  "#fee2e2",   # Agent Loop 中心（强调色：红）
    "agent_loop_b":"#dc2626",
    "assembly":    "#dbeafe",   # ① Prompt Assembly（蓝）
    "assembly_b":  "#2563eb",
    "strategy":    "#dcfce7",   # ② Strategy Pool（绿）
    "strategy_b":  "#16a34a",
    "tool":        "#f3e8ff",   # ③ Tool Calling（紫）
    "tool_b":      "#9333ea",
    "parse":       "#ffedd5",   # ④ Output Parsing（橙）
    "parse_b":     "#f97316",
    "observe":     "#fef9c3",   # ⑤ Observe / Eval / Safety（黄）
    "observe_b":   "#ca8a04",
    "edge":        "#94a3b8",   # 普通箭头
    "safety":      "#fecaca",   # Safety 相关（红警示）
    "safety_b":    "#dc2626",
}
```

## 文件结构

- **Create** `docs/architecture/generate-prompt-engineering-architecture.py`
  - 单一脚本：定义结构化数据 → 输出 drawio XML
  - 入口函数 `main()` 写文件
  - 不引入第三方依赖（仅用 `xml.sax.saxutils.escape`、`pathlib`）

- **Create** `docs/architecture/prompt-engineering-architecture.drawio`
  - 由脚本生成，commit 到 git

---

## Task 1：搭建脚本骨架

**Files:**
- Create: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 1.1：创建脚本文件并写入头部**

```python
#!/usr/bin/env python3
"""
粮达健康 · Prompt Engineering 架构图生成器

目标：
基于 docs/superpowers/specs/2026-06-21-prompt-engineering-architecture-design.md
生成可交付的 drawio 架构图。

输出：docs/architecture/prompt-engineering-architecture.drawio
"""

from __future__ import annotations

import uuid
from pathlib import Path
from xml.sax.saxutils import escape

OUTPUT = Path(__file__).parent / "prompt-engineering-architecture.drawio"

PALETTE = {
    "title":       "#0f172a",
    "subtitle":    "#475569",
    "container":   "#f8fafc",
    "container_b": "#cbd5e1",
    "agent_loop":  "#fee2e2",
    "agent_loop_b":"#dc2626",
    "assembly":    "#dbeafe",
    "assembly_b":  "#2563eb",
    "strategy":    "#dcfce7",
    "strategy_b":  "#16a34a",
    "tool":        "#f3e8ff",
    "tool_b":      "#9333ea",
    "parse":       "#ffedd5",
    "parse_b":     "#f97316",
    "observe":     "#fef9c3",
    "observe_b":   "#ca8a04",
    "edge":        "#94a3b8",
    "safety":      "#fecaca",
    "safety_b":    "#dc2626",
}


def uid() -> str:
    return uuid.uuid4().hex[:12]


def main() -> None:
    # 后续 Task 会在此拼装 diagram
    cells: list[str] = []
    cells.append(_root_cells())
    diagram = _wrap_diagram("\n".join(cells))
    OUTPUT.write_text(diagram, encoding="utf-8")
    print(f"wrote {OUTPUT}")


def _wrap_diagram(body: str) -> str:
    return (
        '<mxfile host="app.diagrams.net">\n'
        '  <diagram name="Prompt Engineering 架构图" id="prompt-engineering">\n'
        '    <mxGraphModel dx="1620" dy="137" grid="0" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" '
        'pageWidth="1400" pageHeight="1950" math="0" shadow="0">\n'
        '      <root>\n'
        '        <mxCell id="0" />\n'
        '        <mxCell id="1" parent="0" />\n'
        f'{body}\n'
        '      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
        '</mxfile>\n'
    )


def _root_cells() -> str:
    return ""  # 占位，后续 Task 填充


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.2：运行脚本确认能生成空 drawio 文件**

Run: `cd /Users/tiger/PycharmProjects/liangda-health && python3 docs/architecture/generate-prompt-engineering-architecture.py`
Expected: `wrote docs/architecture/prompt-engineering-architecture.drawio` 且文件存在

- [ ] **Step 1.3：检查输出文件首行**

Run: `head -3 /Users/tiger/PycharmProjects/liangda-health/docs/architecture/prompt-engineering-architecture.drawio`
Expected: 第一行是 `<mxfile host="app.diagrams.net">`

- [ ] **Step 1.4：commit 骨架**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "chore(diagram): Prompt Engineering 架构图生成器骨架"
```

---

## Task 2：标题与外层容器

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 2.1：在脚本中加 helper：`_text_cell` 和 `_swimlane`**

在 `_root_cells` 函数上方添加：

```python
def _text_cell(rid: str, text: str, x: int, y: int, w: int, h: int,
               font_size: int = 14, bold: bool = False,
               color: str = "#0f172a", align: str = "left") -> str:
    style = (
        f"text;html=1;strokeColor=none;fillColor=none;align={align};"
        f"verticalAlign=middle;fontSize={font_size};"
        f"fontStyle={'1' if bold else '0'};fontColor={color};"
    )
    safe = escape(text).replace("\n", "&#xa;")
    return (
        f'        <mxCell id="{rid}" parent="1" style="{style}" '
        f'value="{safe}" vertex="1">\n'
        f'          <mxGeometry height="{h}" width="{w}" x="{x}" y="{y}" as="geometry" />\n'
        f'        </mxCell>'
    )


def _swimlane(rid: str, label: str, x: int, y: int, w: int, h: int,
              parent: str = "1", font_size: int = 16,
              fill: str = "#f8fafc", stroke: str = "#cbd5e1") -> str:
    style = (
        f"swimlane;html=1;rounded=1;whiteSpace=wrap;startSize=36;"
        f"container=1;collapsible=0;horizontal=1;"
        f"fillColor={fill};strokeColor={stroke};"
        f"fontSize={font_size};fontStyle=1;fontColor=#0f172a;"
    )
    safe = escape(label)
    return (
        f'        <mxCell id="{rid}" parent="{parent}" style="{style}" '
        f'value="{safe}" vertex="1">\n'
        f'          <mxGeometry height="{h}" width="{w}" x="{x}" y="{y}" as="geometry" />\n'
        f'        </mxCell>'
    )
```

- [ ] **Step 2.2：在 `_root_cells` 里加标题和副标题**

替换 `_root_cells` 为：

```python
def _root_cells() -> str:
    parts = [
        _text_cell("title", "Prompt Engineering 架构图",
                   x=40, y=20, w=600, h=36,
                   font_size=28, bold=True, color=PALETTE["title"]),
        _text_cell("subtitle",
                   "聚焦 LLM 调用链路的提示词工程：Agent 循环 + 策略池 + 工具调用 + 输出解析 + 横切观测",
                   x=40, y=60, w=1320, h=24,
                   font_size=14, color=PALETTE["subtitle"]),
    ]
    return "\n".join(parts)
```

- [ ] **Step 2.3：运行脚本并检查标题**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "Prompt Engineering 架构图" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 `1`（标题被写入文件）

- [ ] **Step 2.4：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "chore(diagram): 加标题与副标题"
```

---

## Task 3：Agent Loop 中心循环

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 3.1：加 helper：`_rounded_box`**

在 `_swimlane` 下方添加：

```python
def _rounded_box(rid: str, label: str, x: int, y: int, w: int, h: int,
                 parent: str = "1",
                 fill: str = "#ffffff", stroke: str = "#64748b",
                 font_size: int = 13, bold: bool = True,
                 font_color: str = "#0f172a") -> str:
    style = (
        f"rounded=1;html=1;whiteSpace=wrap;"
        f"fillColor={fill};strokeColor={stroke};"
        f"fontSize={font_size};fontStyle={'1' if bold else '0'};"
        f"fontColor={font_color};"
    )
    safe = escape(label).replace("\n", "&#xa;")
    return (
        f'        <mxCell id="{rid}" parent="{parent}" style="{style}" '
        f'value="{safe}" vertex="1">\n'
        f'          <mxGeometry height="{h}" width="{w}" x="{x}" y="{y}" as="geometry" />\n'
        f'        </mxCell>'
    )


def _arrow(src: str, dst: str, label: str = "",
           style_extra: str = "") -> str:
    style = (
        f"endArrow=classic;html=1;rounded=0;strokeColor={PALETTE['edge']};"
        f"strokeWidth=2;{style_extra}"
    )
    safe = escape(label).replace("\n", "&#xa;")
    return (
        f'        <mxCell id="{uid()}" parent="1" style="{style}" '
        f'value="{safe}" edge="1" source="{src}" target="{dst}">\n'
        f'          <mxGeometry relative="1" as="geometry" />\n'
        f'        </mxCell>'
    )
```

- [ ] **Step 3.2：在 `_root_cells` 中追加 Agent Loop 容器**

修改 `_root_cells`，在 parts 列表里 append：

```python
    # Agent Loop 容器
    parts.append(_swimlane(
        "agent_loop_container",
        "Agent Loop（核心循环）",
        x=40, y=120, w=1320, h=200,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    # 四个步骤
    parts.append(_rounded_box(
        "step_think", "① Think\n选策略 + 生成 plan",
        x=80, y=180, w=240, h=80,
        fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
    ))
    parts.append(_rounded_box(
        "step_act", "② Act\n调用工具 / 给出回答",
        x=380, y=180, w=240, h=80,
        fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
    ))
    parts.append(_rounded_box(
        "step_observe", "③ Observe\n解析工具结果 + 校验",
        x=680, y=180, w=240, h=80,
        fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
    ))
    parts.append(_rounded_box(
        "step_decide", "④ Decide\n证据齐 / Safety / 最大步数",
        x=980, y=180, w=240, h=80,
        fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
    ))
    # 循环箭头
    parts.append(_arrow("step_think", "step_act"))
    parts.append(_arrow("step_act", "step_observe"))
    parts.append(_arrow("step_observe", "step_decide"))
    # Re-Think 回环
    parts.append(_arrow("step_decide", "step_think", label="Re-Think",
                        style_extra="dashed=1;strokeColor=#dc2626;"))
    # 终止（输出）虚线
    parts.append(_arrow("step_decide", "step_decide", label="终止 → 输出",
                        style_extra="dashed=1;exitX=1;exitY=1;entryX=0;entryY=1;"))
```

- [ ] **Step 3.3：运行脚本验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "Agent Loop" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 1（Agent Loop 容器被写入）

- [ ] **Step 3.4：用 drawio 校验 XML 合法性**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('/Users/tiger/PycharmProjects/liangda-health/docs/architecture/prompt-engineering-architecture.drawio'); print('valid XML')"`
Expected: `valid XML`

- [ ] **Step 3.5：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): Agent Loop 中心循环与 4 步流程"
```

---

## Task 4：① Prompt Assembly 层

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 4.1：在 `_root_cells` 追加 Prompt Assembly swimlane 和 6 个槽位**

在现有 parts 列表 append：

```python
    # ① Prompt Assembly
    parts.append(_swimlane(
        "assembly_container",
        "① Prompt Assembly（提示词装配层）",
        x=40, y=360, w=1320, h=240,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    slot_y = 420
    slot_h = 140
    slot_w = 200
    slot_gap = 8
    slot_x_start = 56
    slots_assembly = [
        ("slot_system", "System Prompt\n角色 / 能力 / 边界"),
        ("slot_context", "Context 注入\n来自 Context Eng Layer\n(硬约束置顶)"),
        ("slot_strategy_dir", "Strategy Directive\n当前步用啥策略"),
        ("slot_fewshot", "Few-shot Examples\n按 intent 选"),
        ("slot_tool_schema", "Tool Schema\n当前可用工具描述"),
        ("slot_output_fmt", "Output Format Spec\n约束输出 schema"),
    ]
    for i, (rid, label) in enumerate(slots_assembly):
        x = slot_x_start + i * (slot_w + slot_gap)
        parts.append(_rounded_box(
            rid, label, x=x, y=slot_y, w=slot_w, h=slot_h,
            parent="assembly_container",
            fill=PALETTE["assembly"], stroke=PALETTE["assembly_b"],
            font_size=12, bold=False,
        ))
    # Prompt Assembly → Agent Loop 输入
    parts.append(_arrow("slot_system", "step_think",
                        style_extra="dashed=1;strokeColor=#2563eb;"))
```

- [ ] **Step 4.2：运行并验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "System Prompt\|Few-shot\|Output Format" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 3（6 个槽位中的多个被找到）

- [ ] **Step 4.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): Prompt Assembly 六槽位"
```

---

## Task 5：② Strategy Pool 层

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 5.1：在 `_root_cells` 追加 Strategy Pool**

```python
    # ② Strategy Pool
    parts.append(_swimlane(
        "strategy_container",
        "② Strategy Pool（策略池）",
        x=40, y=640, w=1320, h=320,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    strategies = [
        ("strat_zero",  "Zero-shot\n直接回答\n简单问答/查事实"),
        ("strat_few",   "Few-shot\n样例驱动\n格式化输出"),
        ("strat_cot",   "CoT\n链式思考\n多步推理"),
        ("strat_react", "ReAct\n思考+行动\n需调工具的复杂任务"),
        ("strat_selfc", "Self-Consistency\n多路径投票\n事实性强/答案唯一"),
        ("strat_refl",  "Reflection\n自我反思\nRe-Think 步骤"),
        ("strat_tot",   "ToT\n思维树\n多方案探索/对比"),
        ("strat_safe",  "Safety-Guard\n硬约束 prompt\n触犯禁忌立即终止"),
    ]
    strat_w = 152
    strat_h = 130
    strat_gap = 8
    strat_y = 700
    for i, (rid, label) in enumerate(strategies):
        col = i % 4
        row = i // 4
        x = 56 + col * (strat_w + strat_gap)
        y = strat_y + row * (strat_h + 12)
        is_safety = rid == "strat_safe"
        parts.append(_rounded_box(
            rid, label, x=x, y=y, w=strat_w, h=strat_h,
            parent="strategy_container",
            fill=PALETTE["safety"] if is_safety else PALETTE["strategy"],
            stroke=PALETTE["safety_b"] if is_safety else PALETTE["strategy_b"],
            font_size=11, bold=False,
        ))
    # Strategy Selector
    parts.append(_rounded_box(
        "strat_selector",
        "Strategy Selector\n输入: intent + 上下文 + 上轮结果\n输出: 策略名 + 参数",
        x=56, y=strat_y + 2 * (strat_h + 12),
        w=4 * strat_w + 3 * strat_gap,
        h=70,
        parent="strategy_container",
        fill="#e0e7ff", stroke="#4f46e5",
        font_size=13,
    ))
    # Strategy Pool → Agent Loop Think
    parts.append(_arrow("strat_selector", "step_think",
                        style_extra="dashed=1;strokeColor=#16a34a;"))
```

- [ ] **Step 5.2：运行验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "CoT\|ReAct\|Self-Consistency\|ToT" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 4（多个策略被找到）

- [ ] **Step 5.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): Strategy Pool 8 策略 + Selector"
```

---

## Task 6：③ Tool Calling 层

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 6.1：追加 Tool Calling 层**

```python
    # ③ Tool Calling
    parts.append(_swimlane(
        "tool_container",
        "③ Tool Calling（工具调用层）",
        x=40, y=1000, w=1320, h=260,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    parts.append(_rounded_box(
        "tool_registry", "Tool Registry\n工具元数据 / 参数 schema\n输入输出样例 / 风险等级 / 耗时成本",
        x=56, y=1060, w=300, h=160,
        parent="tool_container",
        fill=PALETTE["tool"], stroke=PALETTE["tool_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_schema_gen", "Tool Schema Generator\n把 Registry 转成 JSON Schema\n注入 Prompt",
        x=376, y=1060, w=240, h=70,
        parent="tool_container",
        fill=PALETTE["tool"], stroke=PALETTE["tool_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_router", "Tool Router\n- 串行: 报告检索 → 画像 → 推荐\n- 并行: RAG + Memory + Product\n- 条件: 触发禁忌时改调 Safe-Alt",
        x=376, y=1140, w=300, h=80,
        parent="tool_container",
        fill=PALETTE["tool"], stroke=PALETTE["tool_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_executor", "Tool Executor\n执行工具调用",
        x=696, y=1060, w=200, h=70,
        parent="tool_container",
        fill=PALETTE["tool"], stroke=PALETTE["tool_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_normalizer", "Tool Result Normalizer\n统一格式: 证据 / 状态 / 错误",
        x=696, y=1140, w=200, h=80,
        parent="tool_container",
        fill=PALETTE["tool"], stroke=PALETTE["tool_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_safe_alt", "Safe-Alt-Generator\n触发禁忌时调\n生成安全替代方案",
        x=916, y=1060, w=300, h=80,
        parent="tool_container",
        fill=PALETTE["safety"], stroke=PALETTE["safety_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "tool_loop_back", "→ 返回 Agent Loop Observe 步",
        x=916, y=1150, w=300, h=70,
        parent="tool_container",
        fill="#f1f5f9", stroke="#475569",
        font_size=12, bold=False,
    ))
    # Tool Calling → Agent Loop Act
    parts.append(_arrow("tool_registry", "tool_schema_gen"))
    parts.append(_arrow("tool_schema_gen", "step_act",
                        style_extra="dashed=1;strokeColor=#9333ea;"))
    parts.append(_arrow("step_act", "tool_executor"))
    parts.append(_arrow("tool_executor", "tool_normalizer"))
    parts.append(_arrow("tool_normalizer", "step_observe",
                        style_extra="dashed=1;strokeColor=#9333ea;"))
    parts.append(_arrow("tool_router", "tool_safe_alt",
                        style_extra="dashed=1;strokeColor=#dc2626;"))
```

- [ ] **Step 6.2：运行验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "Tool Registry\|Tool Router\|Tool Executor\|Normalizer\|Safe-Alt" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 5

- [ ] **Step 6.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): Tool Calling 工具三件套"
```

---

## Task 7：④ Output Parsing & Validation 层

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 7.1：追加 Output Parsing 层**

```python
    # ④ Output Parsing & Validation
    parts.append(_swimlane(
        "parse_container",
        "④ Output Parsing & Validation（输出解析与校验）",
        x=40, y=1300, w=1320, h=200,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    parts.append(_rounded_box(
        "parse_format", "Format Parser\nJSON / 结构化字段提取",
        x=56, y=1360, w=300, h=80,
        parent="parse_container",
        fill=PALETTE["parse"], stroke=PALETTE["parse_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "parse_schema", "Schema Validator\n必填字段 / 类型 / 范围",
        x=376, y=1360, w=300, h=80,
        parent="parse_container",
        fill=PALETTE["parse"], stroke=PALETTE["parse_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "parse_evidence", "Evidence Link Checker\n检查证据链是否完整",
        x=696, y=1360, w=300, h=80,
        parent="parse_container",
        fill=PALETTE["parse"], stroke=PALETTE["parse_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "parse_safety", "Safety Filter\n输出后再次过 Safety Context",
        x=1016, y=1360, w=300, h=80,
        parent="parse_container",
        fill=PALETTE["safety"], stroke=PALETTE["safety_b"],
        font_size=12, bold=False,
    ))
    # 解析层 → Agent Loop Decide
    parts.append(_arrow("step_observe", "parse_format"))
    parts.append(_arrow("parse_format", "parse_schema"))
    parts.append(_arrow("parse_schema", "parse_evidence"))
    parts.append(_arrow("parse_evidence", "parse_safety"))
    parts.append(_arrow("parse_safety", "step_decide",
                        style_extra="dashed=1;strokeColor=#f97316;"))
```

- [ ] **Step 7.2：运行验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "Format Parser\|Schema Validator\|Evidence Link\|Safety Filter" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 4

- [ ] **Step 7.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): Output Parsing 三层 + Safety Filter"
```

---

## Task 8：⑤ Observe / Eval / Safety 横切层

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 8.1：追加横切关注点层**

```python
    # ⑤ Observe / Eval / Safety（横切）
    parts.append(_swimlane(
        "observe_container",
        "⑤ Observe / Eval / Safety（横切关注点）",
        x=40, y=1540, w=1320, h=220,
        fill=PALETTE["container"], stroke=PALETTE["container_b"],
    ))
    parts.append(_rounded_box(
        "obs_trace", "Prompt Trace Logger\n- 每次调用的 prompt+输出\n- 证据链快照\n- Context 用/弃记录",
        x=56, y=1600, w=300, h=130,
        parent="observe_container",
        fill=PALETTE["observe"], stroke=PALETTE["observe_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "obs_eval", "Eval Harness\n固定用例集:\n报告问答 / 成员识别 /\n证据引用 / 健康禁忌 /\n餐单生成 / 商品推荐",
        x=376, y=1600, w=300, h=130,
        parent="observe_container",
        fill=PALETTE["observe"], stroke=PALETTE["observe_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "obs_watchdog", "Safety Watchdog\n- 实时检测触犯禁忌的中间步骤\n- 立即终止并回退",
        x=696, y=1600, w=300, h=130,
        parent="observe_container",
        fill=PALETTE["safety"], stroke=PALETTE["safety_b"],
        font_size=12, bold=False,
    ))
    parts.append(_rounded_box(
        "obs_feedback", "反馈闭环\n用户行为 → 记忆沉淀\n→ 下次 Strategy Selector 输入",
        x=1016, y=1600, w=300, h=130,
        parent="observe_container",
        fill=PALETTE["observe"], stroke=PALETTE["observe_b"],
        font_size=12, bold=False,
    ))
    # 反馈闭环 → Strategy Selector
    parts.append(_arrow("obs_feedback", "strat_selector",
                        style_extra="dashed=1;strokeColor=#ca8a04;"))
```

- [ ] **Step 8.2：运行验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py && grep -c "Prompt Trace\|Eval Harness\|Safety Watchdog\|反馈闭环" docs/architecture/prompt-engineering-architecture.drawio`
Expected: 输出 ≥ 4

- [ ] **Step 8.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): 横切关注点四件套"
```

---

## Task 9：图例与底部说明

**Files:**
- Modify: `docs/architecture/generate-prompt-engineering-architecture.py`

- [ ] **Step 9.1：追加图例**

```python
    # 图例
    parts.append(_text_cell(
        "legend_title", "图例",
        x=40, y=1800, w=80, h=24,
        font_size=14, bold=True,
    ))
    legend_items = [
        ("legend_agent", "Agent Loop", PALETTE["agent_loop"], PALETTE["agent_loop_b"]),
        ("legend_assembly", "Prompt Assembly", PALETTE["assembly"], PALETTE["assembly_b"]),
        ("legend_strategy", "Strategy Pool", PALETTE["strategy"], PALETTE["strategy_b"]),
        ("legend_tool", "Tool Calling", PALETTE["tool"], PALETTE["tool_b"]),
        ("legend_parse", "Output Parsing", PALETTE["parse"], PALETTE["parse_b"]),
        ("legend_observe", "Observe/Eval", PALETTE["observe"], PALETTE["observe_b"]),
        ("legend_safety", "Safety", PALETTE["safety"], PALETTE["safety_b"]),
    ]
    for i, (rid, label, fill, stroke) in enumerate(legend_items):
        x = 40 + i * 180
        parts.append(_rounded_box(
            rid, label, x=x, y=1830, w=160, h=40,
            fill=fill, stroke=stroke,
            font_size=12,
        ))
```

- [ ] **Step 9.2：运行并最终验证**

Run: `python3 docs/architecture/generate-prompt-engineering-architecture.py`
Expected: `wrote docs/architecture/prompt-engineering-architecture.drawio`

- [ ] **Step 9.3：commit**

```bash
cd /Users/tiger/PycharmProjects/liangda-health
git add docs/architecture/generate-prompt-engineering-architecture.py docs/architecture/prompt-engineering-architecture.drawio
git commit -m "feat(diagram): 图例"
```

---

## Task 10：最终自检

**Files:**
- 不修改文件，只运行验证命令

- [ ] **Step 10.1：XML 合法性检查**

Run: `python3 -c "import xml.etree.ElementTree as ET; ET.parse('/Users/tiger/PycharmProjects/liangda-health/docs/architecture/prompt-engineering-architecture.drawio'); print('valid XML')"`
Expected: `valid XML`

- [ ] **Step 10.2：spec 覆盖检查 —— 关键术语都在图里**

Run:
```bash
cd /Users/tiger/PycharmProjects/liangda-health
for term in "Agent Loop" "Prompt Assembly" "Strategy Pool" "Tool Calling" "Output Parsing" "Prompt Trace" "Eval Harness" "Safety Watchdog" "Strategy Selector" "Context Eng" "Zero-shot" "Few-shot" "CoT" "ReAct" "Self-Consistency" "Reflection" "ToT" "Safety-Guard" "Format Parser" "Schema Validator" "Evidence Link" "Safety Filter" "Tool Registry" "Tool Router" "Tool Executor" "Normalizer" "Safe-Alt"; do
  if grep -q "$term" docs/architecture/prompt-engineering-architecture.drawio; then
    echo "OK  $term"
  else
    echo "MISSING  $term"
  fi
done
```
Expected: 全部 `OK`，无 `MISSING`

- [ ] **Step 10.3：人工在 drawio 中打开验证视觉**

Run: 用浏览器打开 https://app.diagrams.net → File → Open from Device → 选 `docs/architecture/prompt-engineering-architecture.drawio`
Expected: 图能正常显示，5 个 swimlane 排列整齐，Agent Loop 居中，箭头方向正确

- [ ] **Step 10.4：把 drawio 文件加入 git（确保是最新版本）**

Run:
```bash
cd /Users/tiger/PycharmProjects/liangda-health
git status --short docs/architecture/prompt-engineering-architecture.drawio
```
Expected: 无输出（说明已 commit）

- [ ] **Step 10.5：最终 commit 记录**

Run: `git log --oneline -10`
Expected: 看到一系列 "feat(diagram):" 和 "chore(diagram):" 的 commit，对应 8 个图块

---

## 验收口径

1. ✅ `docs/architecture/prompt-engineering-architecture.drawio` 文件存在且是合法 XML
2. ✅ spec 12 段中每个关键模块都在图里可见（Step 10.2 全部 OK）
3. ✅ 图能在 https://app.diagrams.net 打开
4. ✅ 与 `context_engineering_arch.drawio` 视觉风格一致（相同色板 / swimlane / 圆角矩形）
5. ✅ git log 中能看出"分块提交"的过程（每加一个模块一个 commit）

## 不在本计划范围

- 把 drawio 进一步转成 PNG/PDF 导出（可用 drawio 自行导出）
- 在 README/技术方案文档中嵌入该图（属于"集成到方案"的下游任务）
- 实装 Prompt Engineering 涉及的代码改动（spec 是架构设计图，不是代码任务）
