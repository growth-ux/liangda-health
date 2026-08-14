const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = '数据源层核心功能展示';
pptx.title = '从多源数据到家庭健康底座';
pptx.company = '粮达健康';
pptx.lang = 'zh-CN';
pptx.theme = {
  headFontFace: 'Aptos Display',
  bodyFontFace: 'Aptos',
  lang: 'zh-CN'
};

const slide = pptx.addSlide();
slide.background = { color: 'F7F9FC' };

const C = {
  navy: '1237B8',
  ink: '17233D',
  muted: '667085',
  line: 'D9E2F2',
  paleBlue: 'EAF1FF',
  blue: '2D6BFF',
  teal: '00A99A',
  paleTeal: 'E8F8F5',
  orange: 'F59E0B',
  paleOrange: 'FFF4DD',
  purple: '7657D8',
  palePurple: 'F0EDFF',
  white: 'FFFFFF'
};

function addText(text, opts = {}) {
  slide.addText(text, {
    fontFace: 'Aptos', color: C.ink, margin: 0,
    breakLine: false, fit: 'shrink', ...opts
  });
}

// 顶部标题区
addText('04 / 核心功能展示', { x: 0.62, y: 0.38, w: 4.6, h: 0.34, fontFace: 'Aptos Display', fontSize: 24, bold: true, color: C.navy });
addText('从多源数据，到家庭健康底座', { x: 0.62, y: 0.84, w: 7.0, h: 0.48, fontFace: 'Aptos Display', fontSize: 29, bold: true, color: C.ink });
addText('粮达健康把分散在报告、设备与家庭交互中的信息，统一沉淀为可检索、可关联、可持续更新的家庭健康数据。', {
  x: 0.64, y: 1.32, w: 6.2, h: 0.38, fontSize: 10.5, color: C.muted, breakLine: true
});
addText('LIANGDA HEALTH', { x: 11.35, y: 0.52, w: 1.25, h: 0.18, fontSize: 7.5, bold: true, color: C.navy, charSpacing: 1.4, align: 'right' });

// 左侧图片占位区（用户后续替换为产品截图）
slide.addShape(pptx.ShapeType.roundRect, {
  x: 0.62, y: 1.93, w: 6.15, h: 4.52,
  rectRadius: 0.08,
  fill: { color: C.white },
  line: { color: C.line, width: 1.1, dash: 'dash' },
  shadow: { type: 'outer', color: '9AA8C4', blur: 3, offset: 1, angle: 135, opacity: 0.12 }
});
addText('此处替换为产品截图', { x: 2.2, y: 3.82, w: 3.0, h: 0.34, fontSize: 20, bold: true, color: '9AA8C4', align: 'center' });
addText('建议放置：健康体检报告详情页\n突出“成员归属 / 解析状态 / 报告分块”', {
  x: 1.6, y: 4.3, w: 4.15, h: 0.55, fontSize: 11, color: '98A2B3', align: 'center', breakLine: true
});
// 图片区小标签
slide.addShape(pptx.ShapeType.roundRect, { x: 0.86, y: 2.18, w: 1.05, h: 0.28, rectRadius: 0.04, fill: { color: C.paleBlue }, line: { color: C.paleBlue } });
addText('DATA INPUT', { x: 0.86, y: 2.25, w: 1.05, h: 0.12, fontSize: 7.5, bold: true, color: C.blue, align: 'center', charSpacing: 0.7 });

// 右侧解读区标题
addText('数据源层 · 五类输入', { x: 7.15, y: 1.9, w: 3.25, h: 0.26, fontSize: 14, bold: true, color: C.ink });
addText('先让数据“有归属、可理解、能关联”，再进入后续分析。', { x: 7.15, y: 2.23, w: 5.45, h: 0.22, fontSize: 9.5, color: C.muted });

const cards = [
  { y: 2.62, n: '01', title: '体检报告数据', desc: '接入 PDF、扫描件和图片；保留指标、结论、日期与原始页码。', tags: '报告原文  ·  检查指标', fill: C.paleBlue, accent: C.blue },
  { y: 3.38, n: '02', title: '多模态文档解析', desc: '同时理解文字、表格、图片和版式，将非结构化医疗文档转成机器可读数据。', tags: 'OCR  ·  表格  ·  版式', fill: C.paleTeal, accent: C.teal },
  { y: 4.14, n: '03', title: '智能分块与向量化', desc: '按检查结论、指标明细和医生建议进行语义切分，建立家庭健康知识索引。', tags: '语义分块  ·  向量检索', fill: C.palePurple, accent: C.purple },
  { y: 4.90, n: '04', title: '穿戴设备数据', desc: '接入心率、睡眠、步数等连续数据，补充报告之外的日常健康状态。', tags: '心率  ·  睡眠  ·  活动', fill: C.paleOrange, accent: C.orange },
  { y: 5.66, n: '05', title: '家庭档案与互动', desc: '关联成员关系、历史报告和健康对话，形成每位家人的连续健康上下文。', tags: '成员归属  ·  对话记忆', fill: 'EEF2F7', accent: '526581' }
];

cards.forEach(c => {
  slide.addShape(pptx.ShapeType.roundRect, { x: 7.12, y: c.y, w: 5.55, h: 0.64, rectRadius: 0.04, fill: { color: C.white }, line: { color: C.line, width: 0.75 } });
  slide.addShape(pptx.ShapeType.roundRect, { x: 7.27, y: c.y + 0.12, w: 0.42, h: 0.39, rectRadius: 0.08, fill: { color: c.fill }, line: { color: c.fill } });
  addText(c.n, { x: 7.27, y: c.y + 0.235, w: 0.42, h: 0.12, fontSize: 8.5, bold: true, color: c.accent, align: 'center' });
  addText(c.title, { x: 7.86, y: c.y + 0.105, w: 1.75, h: 0.18, fontSize: 11.5, bold: true, color: C.ink });
  addText(c.desc, { x: 7.86, y: c.y + 0.31, w: 3.35, h: 0.18, fontSize: 9.2, color: C.muted });
  addText(c.tags, { x: 11.27, y: c.y + 0.22, w: 1.17, h: 0.22, fontSize: 8.2, color: c.accent, align: 'right', breakLine: true });
});

// 底部统一底座与闭环
slide.addShape(pptx.ShapeType.roundRect, { x: 0.62, y: 6.77, w: 12.05, h: 0.43, rectRadius: 0.05, fill: { color: C.navy }, line: { color: C.navy } });
addText('统一健康数据底座', { x: 0.9, y: 6.9, w: 1.55, h: 0.12, fontSize: 9.5, bold: true, color: C.white });
addText('成员身份归属  →  多模态解析  →  语义分块  →  向量化索引  →  家庭健康画像', { x: 2.65, y: 6.88, w: 7.35, h: 0.14, fontSize: 9.3, color: 'DCE7FF', align: 'center' });
addText('可检索 · 可关联 · 可追溯', { x: 10.55, y: 6.89, w: 1.85, h: 0.12, fontSize: 8.4, bold: true, color: '9FE7DB', align: 'right' });

pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-data-source-layer.pptx' });
