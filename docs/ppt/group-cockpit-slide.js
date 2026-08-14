const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = '集团经营驾驶舱核心功能展示';
pptx.title = '集团经营驾驶舱';
pptx.company = '粮达健康';

const S = pptx.ShapeType;
const C = {
  bg: 'F5F8FC', panel: 'FFFFFF', panel2: 'EEF5FF', line: 'D5E2F3',
  ink: '14274A', white: 'FFFFFF', muted: '667A98', blue: '155EEF', cyan: '00A6C7',
  green: '16A085', orange: 'F59E0B', red: 'E85D6A'
};
const slide = pptx.addSlide();
slide.background = { color: C.bg };

function txt(t, o) {
  slide.addText(t, { fontFace: 'Aptos', color: C.ink, margin: 0, fit: 'shrink', ...o });
}
function line(x, y, w, color = C.line, width = 1) {
  slide.addShape(S.line, { x, y, w, h: 0, line: { color, width } });
}

// Header: premium dark cockpit style
txt('04 / 核心功能展示', { x: 0.62, y: 0.38, w: 3.2, h: 0.25, fontSize: 14, bold: true, color: C.blue, charSpacing: 1.1 });
txt('集团经营驾驶舱', { x: 0.62, y: 0.76, w: 4.6, h: 0.52, fontFace: 'Aptos Display', fontSize: 30, bold: true });
txt('把分散的家庭健康数据，转化为可衡量、可分析、可运营的健康资产。', { x: 0.64, y: 1.34, w: 6.35, h: 0.24, fontSize: 10.5, color: C.muted });
txt('集团健康资产 · 实时经营视角', { x: 10.48, y: 0.48, w: 2.18, h: 0.18, fontSize: 8.5, color: C.muted, align: 'right', charSpacing: 0.7 });
slide.addShape(S.ellipse, { x: 12.78, y: 0.45, w: 0.16, h: 0.16, fill: { color: C.green }, line: { color: C.green } });

// Left: website screenshot placeholder in browser chrome
slide.addShape(S.roundRect, { x: 0.62, y: 1.88, w: 8.18, h: 4.68, rectRadius: 0.05, fill: { color: C.panel }, line: { color: C.line, width: 0.9 }, shadow: { type: 'outer', color: '9AA8C4', blur: 4, offset: 2, angle: 135, opacity: 0.18 } });
slide.addShape(S.rect, { x: 0.62, y: 1.88, w: 8.18, h: 0.38, fill: { color: 'EAF1FB' }, line: { color: 'EAF1FB' } });
['E85D6A', 'F5B942', '16A085'].forEach((col, i) => slide.addShape(S.ellipse, { x: 0.82 + i * 0.18, y: 2.02, w: 0.09, h: 0.09, fill: { color: col }, line: { color: col } }));
txt('dashboard / group-health-assets', { x: 1.42, y: 2.005, w: 3.2, h: 0.12, fontSize: 7.6, color: C.muted });
slide.addShape(S.roundRect, { x: 0.88, y: 2.56, w: 7.65, h: 3.65, rectRadius: 0.03, fill: { color: 'F8FBFF' }, line: { color: 'BFD2EB', width: 0.8, dash: 'dash' } });
txt('此处替换为集团经营驾驶舱 Web 截图', { x: 2.22, y: 4.0, w: 4.95, h: 0.3, fontSize: 19, bold: true, color: '7890B2', align: 'center' });
txt('建议画面包含：核心指标卡 · 资产趋势 · 人群分布 · 风险排行 · AI经营洞察', { x: 1.62, y: 4.48, w: 6.1, h: 0.26, fontSize: 9.5, color: C.muted, align: 'center' });
// screenshot annotation markers
[['01', 1.22, 2.84, C.blue], ['02', 6.92, 3.26, C.cyan], ['03', 2.02, 5.72, C.orange]].forEach(([n, x, y, col]) => {
  slide.addShape(S.ellipse, { x, y, w: 0.28, h: 0.28, fill: { color: col }, line: { color: col } });
  txt(n, { x, y: y + 0.085, w: 0.28, h: 0.08, fontSize: 7.3, bold: true, color: C.bg, align: 'center' });
});

// Right rail: KPI / insight panels, intentionally unlike previous cards
txt('经营总览', { x: 9.18, y: 1.88, w: 1.8, h: 0.22, fontSize: 14, bold: true });
txt('集团健康资产的实时切面', { x: 9.18, y: 2.17, w: 2.9, h: 0.16, fontSize: 8.5, color: C.muted });

const kpis = [
  ['覆盖家庭', '—', '家庭健康服务规模', C.blue],
  ['健康档案', '—', '已沉淀成员资产', C.cyan],
  ['报告解析', '—', '多模态数据入库', C.green],
  ['重点人群', '—', '需要持续运营', C.orange]
];
kpis.forEach((k, i) => {
  const x = 9.18 + (i % 2) * 1.73, y = 2.56 + Math.floor(i / 2) * 0.94;
  slide.addShape(S.roundRect, { x, y, w: 1.56, h: 0.77, rectRadius: 0.04, fill: { color: C.panel }, line: { color: C.line, width: 0.75 } });
  slide.addShape(S.rect, { x, y, w: 0.06, h: 0.77, fill: { color: k[3] }, line: { color: k[3] } });
  txt(k[0], { x: x + 0.17, y: y + 0.12, w: 1.18, h: 0.14, fontSize: 8.5, color: C.muted });
  txt(k[1], { x: x + 0.17, y: y + 0.31, w: 0.65, h: 0.24, fontSize: 18, bold: true, color: k[3] });
  txt(k[2], { x: x + 0.17, y: y + 0.59, w: 1.2, h: 0.1, fontSize: 6.9, color: C.muted });
});

slide.addShape(S.roundRect, { x: 9.18, y: 4.6, w: 3.29, h: 1.7, rectRadius: 0.04, fill: { color: C.panel2 }, line: { color: C.line, width: 0.75 } });
txt('经营洞察', { x: 9.4, y: 4.83, w: 1.3, h: 0.2, fontSize: 12, bold: true, color: C.ink });
txt('数据沉淀之后，回答三个经营问题', { x: 9.4, y: 5.12, w: 2.8, h: 0.15, fontSize: 8.3, color: C.muted });
const insights = [
  ['01', '哪里有持续健康需求？', C.cyan],
  ['02', '哪些人群需要重点关注？', C.orange],
  ['03', '下一步资源应该投向哪里？', C.green]
];
insights.forEach((it, i) => {
  const y = 5.43 + i * 0.25;
  txt(it[0], { x: 9.4, y, w: 0.24, h: 0.12, fontSize: 7.2, bold: true, color: it[2] });
  txt(it[1], { x: 9.76, y, w: 2.4, h: 0.12, fontSize: 8.7, color: C.ink });
});

// Bottom decision pathway
slide.addShape(S.roundRect, { x: 0.62, y: 6.83, w: 11.85, h: 0.38, rectRadius: 0.04, fill: { color: C.blue }, line: { color: C.blue } });
txt('数据接入', { x: 0.92, y: 6.95, w: 0.7, h: 0.1, fontSize: 8.6, bold: true, color: C.white });
txt('→', { x: 1.78, y: 6.92, w: 0.28, h: 0.13, fontSize: 12, color: 'BFD3FF', align: 'center' });
txt('健康资产', { x: 2.15, y: 6.95, w: 0.7, h: 0.1, fontSize: 8.6, bold: true, color: C.white });
txt('→', { x: 3.03, y: 6.92, w: 0.28, h: 0.13, fontSize: 12, color: 'BFD3FF', align: 'center' });
txt('人群洞察', { x: 3.4, y: 6.95, w: 0.7, h: 0.1, fontSize: 8.6, bold: true, color: C.white });
txt('→', { x: 4.28, y: 6.92, w: 0.28, h: 0.13, fontSize: 12, color: 'BFD3FF', align: 'center' });
txt('经营决策', { x: 4.65, y: 6.95, w: 0.7, h: 0.1, fontSize: 8.6, bold: true, color: C.white });
txt('集团看见健康资产，运营找到真实需求', { x: 7.15, y: 6.94, w: 4.75, h: 0.12, fontSize: 9, color: 'D7E4FF', align: 'right' });

pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-group-cockpit.pptx' });
