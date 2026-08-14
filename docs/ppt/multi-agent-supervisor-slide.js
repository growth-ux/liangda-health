const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = 'Supervisor 多 Agent 协作';
pptx.title = '多 Agent 协作 · Supervisor 架构';
pptx.company = '粮达健康';

const S = pptx.ShapeType;
const C = {
  bg: 'F6F9FD', ink: '14274A', muted: '657A99', line: 'C9D8EC',
  blue: '155EEF', blue2: 'E8F0FF', cyan: '00A6C7', cyan2: 'E7F8FB',
  green: '16A085', green2: 'E7F7F2', orange: 'F59E0B', orange2: 'FFF4DD',
  navy: '1237B8', white: 'FFFFFF'
};
const slide = pptx.addSlide();
slide.background = { color: C.bg };

function txt(t, o = {}) {
  slide.addText(t, { fontFace: 'Aptos', color: C.ink, margin: 0, fit: 'shrink', ...o });
}
function box(x, y, w, h, fill, lineColor = C.line, radius = 0.05) {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: radius, fill: { color: fill }, line: { color: lineColor, width: 0.9 } });
}
function arrow(x, y, w, h, color = C.line, dash = 'solid') {
  slide.addShape(S.line, { x, y, w, h, line: { color, width: 1.25, dashType: dash, beginArrowType: 'none', endArrowType: 'triangle' } });
}

// Header
txt('04 / 核心功能展示', { x: 0.62, y: 0.35, w: 3.4, h: 0.24, fontSize: 14, bold: true, color: C.blue, charSpacing: 1.1 });
txt('多 Agent 协作', { x: 0.62, y: 0.72, w: 4.5, h: 0.48, fontFace: 'Aptos Display', fontSize: 30, bold: true });
txt('Supervisor 持续理解上下文、调度专业 Agent，并对最终家庭健康方案负责。', { x: 0.64, y: 1.28, w: 7.3, h: 0.24, fontSize: 10.5, color: C.muted });
txt('SUPERVISOR ARCHITECTURE', { x: 10.35, y: 0.47, w: 2.15, h: 0.14, fontSize: 7.4, bold: true, color: C.blue, align: 'right', charSpacing: 0.8 });

// Left architecture panel
box(0.62, 1.82, 7.7, 4.72, C.white, C.line);
txt('协作编排图', { x: 0.92, y: 2.08, w: 1.2, h: 0.2, fontSize: 12, bold: true });
txt('不是一次路由，而是持续监督与动态再规划', { x: 2.0, y: 2.11, w: 3.6, h: 0.14, fontSize: 8.3, color: C.muted });

// User question node
box(2.96, 2.45, 2.02, 0.62, C.blue2, 'A9C5FA');
txt('用户问题', { x: 3.18, y: 2.58, w: 1.58, h: 0.16, fontSize: 13, bold: true, color: C.blue, align: 'center' });
txt('家庭健康诉求', { x: 3.18, y: 2.82, w: 1.58, h: 0.1, fontSize: 7.4, color: C.muted, align: 'center' });

// Supervisor node
box(2.55, 3.38, 2.84, 0.92, C.navy, C.navy);
txt('Agent 管家', { x: 2.79, y: 3.55, w: 2.36, h: 0.22, fontSize: 16, bold: true, color: C.white, align: 'center' });
txt('Supervisor · 任务规划与动态决策', { x: 2.78, y: 3.89, w: 2.38, h: 0.12, fontSize: 8.0, color: 'D6E5FF', align: 'center' });

// Agent nodes
const agents = [
  { x: 0.95, title: '健康分析 Agent', sub: '报告 / 指标 / 趋势', fill: C.cyan2, accent: C.cyan },
  { x: 2.72, title: '膳食规划 Agent', sub: '家庭饮食方案', fill: C.green2, accent: C.green },
  { x: 4.49, title: '家庭档案 Agent', sub: '成员 / 记忆 / 上下文', fill: C.orange2, accent: C.orange },
  { x: 6.26, title: '商品推荐 Agent', sub: '需求 / 偏好 / 匹配', fill: C.blue2, accent: C.blue }
];
agents.forEach(a => {
  box(a.x, 4.98, 1.56, 0.72, a.fill, a.accent);
  txt(a.title, { x: a.x + 0.08, y: 5.15, w: 1.4, h: 0.14, fontSize: 9.2, bold: true, color: C.ink, align: 'center' });
  txt(a.sub, { x: a.x + 0.08, y: 5.42, w: 1.4, h: 0.1, fontSize: 6.8, color: C.muted, align: 'center' });
});

// Arrows and labels
arrow(3.97, 3.07, 0, 0.3, C.blue);
txt('理解上下文', { x: 4.1, y: 3.15, w: 0.75, h: 0.1, fontSize: 7.2, color: C.blue });
agents.forEach((a, i) => {
  const center = a.x + 0.78;
  arrow(3.97, 4.31, center - 3.97, 0.62, a.accent, 'dash');
  txt('委派任务', { x: (center + 3.97) / 2 - 0.29, y: 4.58, w: 0.58, h: 0.1, fontSize: 6.4, color: a.accent, align: 'center' });
});

// Feedback / replan loop as editable curved-ish path made from lines
arrow(6.9, 5.34, -0.7, -0.82, C.navy);
txt('结果观察', { x: 6.02, y: 4.46, w: 0.66, h: 0.1, fontSize: 7.1, color: C.navy, align: 'center' });
arrow(2.55, 4.72, -0.42, -0.55, C.navy);
txt('动态再规划', { x: 1.08, y: 4.23, w: 0.72, h: 0.1, fontSize: 7.1, color: C.navy });

// Output strip within left panel
slide.addShape(S.roundRect, { x: 1.76, y: 5.98, w: 5.04, h: 0.35, rectRadius: 0.04, fill: { color: C.blue }, line: { color: C.blue } });
txt('结果汇总与校验  →  家庭健康方案', { x: 1.9, y: 6.09, w: 4.75, h: 0.1, fontSize: 8.8, bold: true, color: C.white, align: 'center' });

// Right evidence window
box(8.66, 1.82, 4.05, 4.72, C.white, C.line);
txt('真实运行证据', { x: 8.96, y: 2.08, w: 1.45, h: 0.2, fontSize: 12, bold: true });
txt('Web 端 Supervisor 协作状态', { x: 10.48, y: 2.11, w: 1.8, h: 0.14, fontSize: 8, color: C.muted, align: 'right' });
// browser frame
slide.addShape(S.roundRect, { x: 8.94, y: 2.48, w: 3.48, h: 3.42, rectRadius: 0.04, fill: { color: 'F8FBFF' }, line: { color: 'BFD2EB', width: 0.8 } });
slide.addShape(S.rect, { x: 8.94, y: 2.48, w: 3.48, h: 0.29, fill: { color: 'EAF1FB' }, line: { color: 'EAF1FB' } });
['E85D6A', 'F5B942', '16A085'].forEach((col, i) => slide.addShape(S.ellipse, { x: 9.12 + i * 0.16, y: 2.58, w: 0.07, h: 0.07, fill: { color: col }, line: { color: col } }));
txt('agent-chat / orchestration', { x: 9.65, y: 2.57, w: 1.9, h: 0.1, fontSize: 6.8, color: C.muted });
slide.addShape(S.roundRect, { x: 9.16, y: 3.05, w: 3.04, h: 2.54, rectRadius: 0.02, fill: { color: C.white }, line: { color: C.line, width: 0.65 } });
txt('此处替换为多 Agent 协作截图', { x: 9.42, y: 4.02, w: 2.52, h: 0.22, fontSize: 14, bold: true, color: '7890B2', align: 'center' });
txt('保留：调度中心 · 膳食规划师 · 已完成状态 · 最终回复', { x: 9.37, y: 4.42, w: 2.62, h: 0.3, fontSize: 7.5, color: C.muted, align: 'center' });
// callout chips
[['调度中心', C.blue], ['专业 Agent', C.green], ['协作结果', C.orange]].forEach((c, i) => {
  const x = 9.18 + i * 1.0;
  slide.addShape(S.roundRect, { x, y: 5.74, w: 0.92, h: 0.25, rectRadius: 0.03, fill: { color: i === 0 ? C.blue2 : i === 1 ? C.green2 : C.orange2 }, line: { color: 'FFFFFF', transparency: 100 } });
  txt(c[0], { x, y: 5.83, w: 0.92, h: 0.08, fontSize: 6.7, bold: true, color: c[1], align: 'center' });
});

// Footer architecture statement
slide.addShape(S.roundRect, { x: 0.62, y: 6.86, w: 12.09, h: 0.35, rectRadius: 0.04, fill: { color: C.navy }, line: { color: C.navy } });
txt('用户提问  →  Supervisor 规划  →  专业 Agent 执行  →  结果观察  →  动态再调度  →  统一回复', { x: 0.95, y: 6.97, w: 8.8, h: 0.1, fontSize: 8.8, bold: true, color: C.white });
txt('对整个任务负责到底', { x: 10.45, y: 6.97, w: 1.86, h: 0.1, fontSize: 8.5, bold: true, color: '9FE7DB', align: 'right' });

pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-supervisor-multi-agent.pptx' });
