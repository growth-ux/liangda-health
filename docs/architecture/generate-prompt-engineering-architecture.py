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
    parts = [
        _text_cell("title", "Prompt Engineering 架构图",
                   x=40, y=20, w=600, h=36,
                   font_size=28, bold=True, color=PALETTE["title"]),
        _text_cell("subtitle",
                   "聚焦 LLM 调用链路的提示词工程：Agent 循环 + 策略池 + 工具调用 + 输出解析 + 横切观测",
                   x=40, y=60, w=1320, h=24,
                   font_size=14, color=PALETTE["subtitle"]),
        # Agent Loop 容器
        _swimlane(
            "agent_loop_container",
            "Agent Loop（核心循环）",
            x=40, y=120, w=1320, h=200,
            fill=PALETTE["container"], stroke=PALETTE["container_b"],
        ),
        _rounded_box(
            "step_think", "① Think\n选策略 + 生成 plan",
            x=80, y=180, w=240, h=80,
            fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
        ),
        _rounded_box(
            "step_act", "② Act\n调用工具 / 给出回答",
            x=380, y=180, w=240, h=80,
            fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
        ),
        _rounded_box(
            "step_observe", "③ Observe\n解析工具结果 + 校验",
            x=680, y=180, w=240, h=80,
            fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
        ),
        _rounded_box(
            "step_decide", "④ Decide\n证据齐 / Safety / 最大步数",
            x=980, y=180, w=240, h=80,
            fill=PALETTE["agent_loop"], stroke=PALETTE["agent_loop_b"],
        ),
        _arrow("step_think", "step_act"),
        _arrow("step_act", "step_observe"),
        _arrow("step_observe", "step_decide"),
        _arrow("step_decide", "step_think", label="Re-Think",
               style_extra="dashed=1;strokeColor=#dc2626;"),
        # ① Prompt Assembly
        _swimlane(
            "assembly_container",
            "① Prompt Assembly（提示词装配层）",
            x=40, y=360, w=1320, h=240,
            fill=PALETTE["container"], stroke=PALETTE["container_b"],
        ),
    ]
    slot_y = 420
    slot_h = 140
    slot_w = 200
    slot_gap = 8
    slot_x_start = 56
    slots_assembly = [
        ("slot_system",       "System Prompt\n角色 / 能力 / 边界"),
        ("slot_context",      "Context 注入\n来自 Context Eng Layer\n(硬约束置顶)"),
        ("slot_strategy_dir", "Strategy Directive\n当前步用啥策略"),
        ("slot_fewshot",      "Few-shot Examples\n按 intent 选"),
        ("slot_tool_schema",  "Tool Schema\n当前可用工具描述"),
        ("slot_output_fmt",   "Output Format Spec\n约束输出 schema"),
    ]
    for i, (rid, label) in enumerate(slots_assembly):
        x = slot_x_start + i * (slot_w + slot_gap)
        parts.append(_rounded_box(
            rid, label, x=x, y=slot_y, w=slot_w, h=slot_h,
            parent="assembly_container",
            fill=PALETTE["assembly"], stroke=PALETTE["assembly_b"],
            font_size=12, bold=False,
        ))
    parts.append(_arrow("slot_system", "step_think",
                        style_extra="dashed=1;strokeColor=#2563eb;"))
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
    parts.append(_rounded_box(
        "strat_selector",
        "Strategy Selector\n输入: intent + 上下文 + 上轮结果 → 输出: 策略名 + 参数",
        x=56, y=strat_y + 2 * (strat_h + 12),
        w=4 * strat_w + 3 * strat_gap,
        h=70,
        parent="strategy_container",
        fill="#e0e7ff", stroke="#4f46e5",
        font_size=13,
    ))
    parts.append(_arrow("strat_selector", "step_think",
                        style_extra="dashed=1;strokeColor=#16a34a;"))
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
    parts.append(_arrow("tool_registry", "tool_schema_gen"))
    parts.append(_arrow("tool_schema_gen", "step_act",
                        style_extra="dashed=1;strokeColor=#9333ea;"))
    parts.append(_arrow("step_act", "tool_executor"))
    parts.append(_arrow("tool_executor", "tool_normalizer"))
    parts.append(_arrow("tool_normalizer", "step_observe",
                        style_extra="dashed=1;strokeColor=#9333ea;"))
    parts.append(_arrow("tool_router", "tool_safe_alt",
                        style_extra="dashed=1;strokeColor=#dc2626;"))
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
    parts.append(_arrow("step_observe", "parse_format"))
    parts.append(_arrow("parse_format", "parse_schema"))
    parts.append(_arrow("parse_schema", "parse_evidence"))
    parts.append(_arrow("parse_evidence", "parse_safety"))
    parts.append(_arrow("parse_safety", "step_decide",
                        style_extra="dashed=1;strokeColor=#f97316;"))
    return "\n".join(parts)


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


if __name__ == "__main__":
    main()
