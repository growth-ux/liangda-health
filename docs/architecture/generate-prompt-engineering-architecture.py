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
    return ""  # 占位，后续 Task 填充


if __name__ == "__main__":
    main()
