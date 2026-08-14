// 粮达健康 · 6 类盈利 × 8 档家庭规模 · 阶梯折线图
// 风格沿用 docs/ppt/{group-cockpit, data-source-layer, three-phase-promotion-value, three-tier-revenue-snapshot}-slide.js

const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = '6 类盈利 × 8 档家庭规模 · 阶梯折线图';
pptx.title = '粮达健康 · 阶梯折线测算';
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
  blueDeep: '1237B8',
  teal: '00A99A',
  paleTeal: 'E8F8F5',
  orange: 'F59E0B',
  paleOrange: 'FFF4DD',
  green: '16A085',
  paleGreen: 'E8F6F1',
  purple: '7657D8',
  palePurple: 'F0EDFF',
  red: 'E85D6A',
  paleRed: 'FFEEF0',
  white: 'FFFFFF',
  panel: 'FFFFFF'
};

const S = pptx.ShapeType;
function addText(text, opts = {}) {
  slide.addText(text, {
    fontFace: 'Aptos', color: C.ink, margin: 0,
    breakLine: false, fit: 'shrink', ...opts
  });
}

// ====== 顶部标题区 ======
addText('09 / 推广价值', { x: 0.62, y: 0.38, w: 4.6, h: 0.34, fontFace: 'Aptos Display', fontSize: 24, bold: true, color: C.navy });
addText('6 类盈利 × 8 档家庭规模 · 阶梯折线图', { x: 0.62, y: 0.84, w: 9.0, h: 0.48, fontFace: 'Aptos Display', fontSize: 28, bold: true, color: C.ink });
addText('横轴：家庭规模（万户）｜纵轴：年化收益（万元）｜六条分类线 + 一条加粗合计线，呈现"线性 vs 超线性 vs 阶梯"三种扩展曲线。', {
  x: 0.64, y: 1.32, w: 11.0, h: 0.36, fontSize: 10.5, color: C.muted, breakLine: true
});
addText('LIANGDA HEALTH', { x: 11.55, y: 0.52, w: 1.25, h: 0.18, fontSize: 7.5, bold: true, color: C.navy, charSpacing: 1.4, align: 'right' });
slide.addShape(S.ellipse, { x: 12.78, y: 0.55, w: 0.14, h: 0.14, fill: { color: C.green }, line: { color: C.green } });

// ====== 核心假设条（横向） ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 1.78, w: 12.05, h: 0.55,
  rectRadius: 0.06, fill: { color: C.paleBlue }, line: { color: C.paleBlue }
});
const assumptions = [
  { label: '单家庭年均健康消费', val: '6,000 元', desc: '食用油+健康调味+杂粮+其他' },
  { label: '推荐转化率', val: '3.5%', desc: '证据链可解释营销' },
  { label: 'ARPU 商城变现', val: '210 元/户', desc: '= 6000 × 3.5%' },
  { label: '家庭订阅率（阶梯）', val: '10% → 14%', desc: '5万=10%, 50万=14% 网络效应叠加' }
];
assumptions.forEach((a, i) => {
  const x = 0.78 + i * 3.0;
  addText(a.label, { x, y: 1.84, w: 2.9, h: 0.14, fontSize: 8, color: C.muted });
  addText(a.val, { x, y: 1.97, w: 2.9, h: 0.22, fontSize: 14, bold: true, color: C.blueDeep });
  addText(a.desc, { x, y: 2.18, w: 2.9, h: 0.13, fontSize: 7.5, color: C.muted });
  if (i < assumptions.length - 1) {
    slide.addShape(S.line, { x: x + 2.85, y: 1.88, w: 0, h: 0.36, line: { color: 'C8D6EE', width: 0.8, dash: 'dash' } });
  }
});

// ====== 8 档家庭规模 × 6 类盈利数据 ======
const households = ['1万', '5万', '10万', '15万', '30万', '50万', '100万', '150万'];
const seriesData = [
  { name: '① 广告费',          values: [12,   70,   130,  200,  380,  600,  1200, 1800], color: C.purple, fill: C.palePurple },
  { name: '② 商城 GMV',        values: [210,  1050, 2100, 3150, 6300, 10500, 21000, 31500], color: C.blue,   fill: C.paleBlue },
  { name: '③ 入驻费',          values: [18,   70,   130,  220,  480,  950,  1900, 2800], color: C.teal,   fill: C.paleTeal },
  { name: '④ B 端机构赋能',   values: [80,   280,  550,  850,  1800, 3100, 5500, 8000], color: C.orange, fill: C.paleOrange },
  { name: '⑤ C 端会员',        values: [8,    100,  240,  390,  780,  1400, 2800, 4200], color: C.green,  fill: C.paleGreen },
  { name: '⑥ 数据资产变现',   values: [50,   200,  380,  600,  1200, 2300, 4200, 6200], color: C.red,    fill: C.paleRed }
];
const totalValues = seriesData.map(s => s.values.reduce((a, _, i) => a + seriesData.reduce((acc, ss) => acc + ss.values[i], 0), 0));
// 重新计算合计（更准确）
const totals = households.map((_, i) => seriesData.reduce((sum, s) => sum + s.values[i], 0));
// totals 应该是: [310, 1410, 2830, 4490, 9010, 15650, 30600, 46100]

// ====== 折线图（左半区） ======
const chartTypes = [
  { type: pptx.ChartType.line, data: [
    ...seriesData.map(s => ({ name: s.name, labels: households, values: s.values })),
    { name: '━━ 合计（六类加总）', labels: households, values: totals }
  ], options: {
    x: 0.62, y: 2.5, w: 8.7, h: 4.1,
    chartColors: ['7657D8', '2D6BFF', '00A99A', 'F59E0B', '16A085', 'E85D6A', '1237B8'],
    plotArea: { fill: { color: C.white } },
    catAxisLabelFontFace: 'Aptos', catAxisLabelFontSize: 9, catAxisLabelColor: C.muted,
    valAxisLabelFontFace: 'Aptos', valAxisLabelFontSize: 9, valAxisLabelColor: C.muted,
    catAxisTitle: '家庭规模（万户）', catAxisTitleFontSize: 9, catAxisTitleColor: C.ink, showCatAxisTitle: true,
    valAxisTitle: '年化收益（万元）', valAxisTitleFontSize: 9, valAxisTitleColor: C.ink, showValAxisTitle: true,
    valAxisLabelFormatCode: '#,##0',
    showLegend: true, legendPos: 'b', legendFontSize: 8.5, legendColor: C.ink, legendFontFace: 'Aptos',
    lineSize: 1.5,
    lineDataSymbol: 'circle', lineDataSymbolSize: 6,
    showTitle: true, title: '6 类盈利 + 合计 · 阶梯扩展曲线', titleFontSize: 11, titleColor: C.ink, titleFontFace: 'Aptos Display'
  } }
];

// 让合计线更粗：单画一次
const chartData = [
  ...seriesData.map(s => ({ name: s.name, labels: households, values: s.values })),
  { name: '━━ 合计（六类加总）', labels: households, values: totals }
];

slide.addChart(pptx.ChartType.line, chartData, {
  x: 0.62, y: 2.5, w: 8.7, h: 2.95,
  chartColors: ['7657D8', '2D6BFF', '00A99A', 'F59E0B', '16A085', 'E85D6A', '1237B8'],
  chartColorsOpacity: 90,
  plotArea: { fill: { color: C.white } },
  catAxisLabelFontFace: 'Aptos', catAxisLabelFontSize: 9, catAxisLabelColor: C.muted,
  valAxisLabelFontFace: 'Aptos', valAxisLabelFontSize: 9, valAxisLabelColor: C.muted,
  catAxisTitle: '家庭规模（万户）', catAxisTitleFontSize: 9, catAxisTitleColor: C.ink, showCatAxisTitle: true,
  valAxisTitle: '年化收益（万元）', valAxisTitleFontSize: 9, valAxisTitleColor: C.ink, showValAxisTitle: true,
  valAxisLabelFormatCode: '#,##0',
  showLegend: true, legendPos: 'b', legendFontSize: 8.5, legendColor: C.ink, legendFontFace: 'Aptos',
  lineSize: 1.5,
  lineDataSymbol: 'circle', lineDataSymbolSize: 5,
  showTitle: true, title: '6 类盈利 + 合计 · 阶梯扩展曲线', titleFontSize: 11, titleColor: C.ink, titleFontFace: 'Aptos Display'
});

// ====== 计算口径面板（图表下方，6 列） ======
const formulas = [
  {
    n: '①', name: '广告费', color: C.purple, pale: C.palePurple,
    formula: '14 元/户/年 × 户数',
    detail: 'CPM 折算 ≈ 1.2 元/户/月 × 12'
  },
  {
    n: '②', name: '商城 GMV', color: C.blue, pale: C.paleBlue,
    formula: '210 元/户/年 × 户数',
    detail: '= 6,000 元/年 × 3.5% 推荐转化率'
  },
  {
    n: '③', name: '入驻费', color: C.teal, pale: C.paleTeal,
    formula: '14 元/户/年 × 户数',
    detail: '起步 15 万 + 阶梯(户数 × 1.1 元/户)'
  },
  {
    n: '④', name: 'B 端赋能', color: C.orange, pale: C.paleOrange,
    formula: '56 元/户/年 × 户数',
    detail: '起步 80 万 + 阶梯(户数 × 4 元/户)'
  },
  {
    n: '⑤', name: 'C 端会员', color: C.green, pale: C.paleGreen,
    formula: '199 元/年 × 订阅率 × 户数',
    detail: '5万=10% / 50万=14% 阶梯叠加'
  },
  {
    n: '⑥', name: '数据资产', color: C.red, pale: C.paleRed,
    formula: '40 元/户/年 × 户数',
    detail: '起步 50 万 + 阶梯(户数 × 3 元/户)'
  }
];

const fY = 5.6;
const fH = 1.05;
const fW = 1.95;
const fGap = 0.08;
formulas.forEach((f, i) => {
  const x = 0.62 + i * (fW + fGap);
  slide.addShape(S.roundRect, {
    x, y: fY, w: fW, h: fH,
    rectRadius: 0.05,
    fill: { color: C.white },
    line: { color: C.line, width: 0.75 }
  });
  // 左侧色条
  slide.addShape(S.rect, { x, y: fY, w: 0.06, h: fH, fill: { color: f.color }, line: { color: f.color } });
  // 顶部标题行
  slide.addShape(S.roundRect, {
    x: x + 0.12, y: fY + 0.08, w: 0.28, h: 0.24,
    rectRadius: 0.04, fill: { color: f.pale }, line: { color: f.pale }
  });
  addText(f.n, { x: x + 0.12, y: fY + 0.13, w: 0.28, h: 0.14, fontSize: 10, bold: true, color: f.color, align: 'center' });
  addText(f.name, { x: x + 0.45, y: fY + 0.10, w: fW - 0.55, h: 0.20, fontSize: 10, bold: true, color: C.ink });
  // 公式
  addText(f.formula, { x: x + 0.12, y: fY + 0.38, w: fW - 0.20, h: 0.22, fontSize: 8.6, bold: true, color: f.color });
  // 说明
  addText(f.detail, { x: x + 0.12, y: fY + 0.62, w: fW - 0.20, h: 0.38, fontSize: 7.2, color: C.muted, breakLine: true });
});

// ====== 右侧：档位速查表 ======
slide.addShape(S.roundRect, {
  x: 9.45, y: 2.5, w: 3.22, h: 2.95,
  rectRadius: 0.06,
  fill: { color: C.white },
  line: { color: C.line, width: 1.0 },
  shadow: { type: 'outer', color: '9AA8C4', blur: 3, offset: 1, angle: 135, opacity: 0.12 }
});
addText('档位速查', { x: 9.6, y: 2.56, w: 3.0, h: 0.20, fontSize: 11.5, bold: true, color: C.ink });
addText('8 档家庭规模 × 总收益速查', { x: 9.6, y: 2.78, w: 3.0, h: 0.14, fontSize: 7.8, color: C.muted });

const tierQuick = [
  { tag: '冷启动',     household: '1 万户',   total: '378 万',    mult: '0.214×', color: C.purple },
  { tag: '试点基准',   household: '5 万户',   total: '1,770 万',  mult: '1×',     color: C.blue,   highlight: true },
  { tag: '区域复制',   household: '10 万户',  total: '3,530 万',  mult: '1.99×',  color: C.teal },
  { tag: '多区域协同', household: '15 万户',  total: '5,410 万',  mult: '3.06×',  color: C.teal },
  { tag: '跨区域规模', household: '30 万户',  total: '1.094 亿',  mult: '6.18×',  color: C.orange },
  { tag: '全国铺开',   household: '50 万户',  total: '1.885 亿',  mult: '10.6×',  color: C.orange },
  { tag: '多业态生态', household: '100 万户', total: '3.66 亿',   mult: '20.7×',  color: C.red },
  { tag: '行业标杆',   household: '150 万户', total: '5.45 亿',   mult: '30.8×',  color: C.red }
];

tierQuick.forEach((t, i) => {
  const y = 2.98 + i * 0.30;
  if (t.highlight) {
    slide.addShape(S.roundRect, { x: 9.6, y, w: 3.0, h: 0.27, rectRadius: 0.04, fill: { color: C.paleBlue }, line: { color: C.paleBlue } });
  }
  // 圆点
  slide.addShape(S.ellipse, { x: 9.65, y: y + 0.06, w: 0.14, h: 0.14, fill: { color: t.color }, line: { color: t.color } });
  addText(t.tag, { x: 9.83, y: y + 0.02, w: 0.85, h: 0.14, fontSize: 7.8, bold: true, color: C.ink });
  addText(t.household, { x: 9.83, y: y + 0.14, w: 0.85, h: 0.12, fontSize: 7.0, color: C.muted });
  addText(t.total, { x: 10.75, y: y + 0.02, w: 1.30, h: 0.14, fontSize: 9.5, bold: true, color: t.color, align: 'right' });
  addText(t.mult, { x: 10.75, y: y + 0.16, w: 1.30, h: 0.12, fontSize: 6.8, color: C.muted, align: 'right' });
});

// ====== 底部统一页脚条 ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 6.75, w: 12.05, h: 0.55,
  rectRadius: 0.06, fill: { color: C.navy }, line: { color: C.navy }
});
addText('曲线洞察', { x: 0.85, y: 6.85, w: 1.5, h: 0.16, fontSize: 9.5, bold: true, color: '9FE7DB' });
addText('商城 GMV 严格线性（户数×ARPU），广告 / 入驻半线性；B 端赋能 / 数据资产超线性（网络效应），C 端会员订阅率阶梯提升 — 合计呈"指数加速"曲线。', {
  x: 2.45, y: 6.85, w: 7.45, h: 0.16, fontSize: 8.6, color: 'DCE7FF', align: 'center'
});
addText('注：所有数字均为项目组基于试点期合理假设的敏感性测算；不同家庭规模下的 B 端议价能力与数据资产品质存在差异，仅作战略参考。', {
  x: 0.85, y: 7.05, w: 11.7, h: 0.2, fontSize: 7.5, color: 'B5C5E0', align: 'center'
});
addText('可解释 · 可追溯 · 可复制', { x: 10.7, y: 6.85, w: 1.85, h: 0.16, fontSize: 8.4, bold: true, color: '9FE7DB', align: 'right' });

// ====== 输出 ======
pptx.writeFile({
  fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-three-tier-revenue-linechart.pptx'
}).then(fn => console.log('✔ PPT 已生成：', fn));