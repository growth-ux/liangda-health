// 粮达健康 · 6 类盈利 × 3 档家庭规模 · 阶梯式测算
// 风格沿用 docs/ppt/{group-cockpit, data-source-layer, three-phase-promotion-value}-slide.js

const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = '6 类盈利 × 3 档家庭规模 · 阶梯式测算';
pptx.title = '粮达健康 · 阶梯式盈利测算';
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
addText('6 类盈利 × 3 档家庭规模 · 阶梯式测算', { x: 0.62, y: 0.84, w: 9.0, h: 0.48, fontFace: 'Aptos Display', fontSize: 28, bold: true, color: C.ink });
addText('基于"单家庭年均健康消费 6,000 元 × 推荐转化率 3.5%"的核心假设，敏感性测算 5 万 / 15 万 / 50 万三档家庭规模下的年化收益。', {
  x: 0.64, y: 1.32, w: 9.4, h: 0.36, fontSize: 10.5, color: C.muted, breakLine: true
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
  { label: '家庭订阅率（随规模）', val: '10% → 13% → 14%', desc: '5万=10% / 15万=13% / 50万=14%' }
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

// ====== 3 档阶梯列 ======
const tiers = [
  {
    name: 'Tier 1', tag: 'Y1 基准', households: '5 万户', color: C.blue, pale: C.paleBlue,
    items: [
      { n: '①', label: '广告费',         amount: '70 万',    note: '原生 + 品牌冠名' },
      { n: '②', label: '商城 GMV',      amount: '1,050 万', note: '210×5万' },
      { n: '③', label: '入驻费',         amount: '70 万',    note: '集团子品牌 + 区域' },
      { n: '④', label: 'B 端机构赋能',  amount: '280 万',   note: '体检+保险+健康管理' },
      { n: '⑤', label: 'C 端会员',      amount: '100 万',   note: '10% 订阅率' },
      { n: '⑥', label: '数据资产变现',  amount: '200 万',   note: '白皮书+洞察+咨询' }
    ],
    total: '1,770 万',
    highlight: '单户 354 元/年 · 试点基准'
  },
  {
    name: 'Tier 2', tag: 'Y1.5 / Y2 中期', households: '15 万户', color: C.teal, pale: C.paleTeal,
    items: [
      { n: '①', label: '广告费',         amount: '200 万',   note: '规模化广告位' },
      { n: '②', label: '商城 GMV',      amount: '3,150 万', note: '210×15万' },
      { n: '③', label: '入驻费',         amount: '220 万',   note: '区域品牌扩列' },
      { n: '④', label: 'B 端机构赋能',  amount: '850 万',   note: '网络效应放大' },
      { n: '⑤', label: 'C 端会员',      amount: '390 万',   note: '13% 订阅率' },
      { n: '⑥', label: '数据资产变现',  amount: '600 万',   note: '区域洞察×4期' }
    ],
    total: '5,410 万',
    highlight: '约为 Tier 1 的 3 倍'
  },
  {
    name: 'Tier 3', tag: 'Y3 远景', households: '50 万户', color: C.orange, pale: C.paleOrange,
    items: [
      { n: '①', label: '广告费',         amount: '600 万',   note: '程序化广告' },
      { n: '②', label: '商城 GMV',      amount: '10,500 万', note: '210×50万' },
      { n: '③', label: '入驻费',         amount: '950 万',   note: '全国铺开' },
      { n: '④', label: 'B 端机构赋能',  amount: '3,100 万', note: 'B 端生态成熟' },
      { n: '⑤', label: 'C 端会员',      amount: '1,400 万', note: '14% 订阅率' },
      { n: '⑥', label: '数据资产变现',  amount: '2,300 万', note: '国标提案+品牌咨询' }
    ],
    total: '1.885 亿',
    highlight: '约为 Tier 1 的 10.7 倍'
  }
];

const colW = 3.92;
const startX = 0.62;
const gap = 0.155;
const colY = 2.5;
const colH = 4.05;

tiers.forEach((t, idx) => {
  const x = startX + idx * (colW + gap);

  // 主面板
  slide.addShape(S.roundRect, {
    x, y: colY, w: colW, h: colH,
    rectRadius: 0.07,
    fill: { color: C.white },
    line: { color: C.line, width: 1.0 },
    shadow: { type: 'outer', color: '9AA8C4', blur: 3, offset: 1, angle: 135, opacity: 0.12 }
  });

  // 顶部渐变色带
  slide.addShape(S.roundRect, {
    x, y: colY, w: colW, h: 0.78,
    rectRadius: 0.07, fill: { color: t.color }, line: { color: t.color }
  });
  // 盖住下半圆角使其贴合
  slide.addShape(S.rect, {
    x, y: colY + 0.4, w: colW, h: 0.38,
    fill: { color: t.color }, line: { color: t.color }
  });

  // Tier 标签
  addText(`${t.name}  ${t.tag}`, {
    x: x + 0.18, y: colY + 0.07, w: colW - 0.36, h: 0.18, fontSize: 8.5, bold: true, color: C.white, charSpacing: 1.0
  });
  addText(t.households, {
    x: x + 0.18, y: colY + 0.28, w: colW - 0.36, h: 0.36, fontSize: 22, bold: true, color: C.white
  });
  // 右上角 small chip
  addText('假设', {
    x: x + colW - 0.7, y: colY + 0.08, w: 0.55, h: 0.18, fontSize: 7.5, bold: true, color: t.color, align: 'center',
    fill: { color: 'FFFFFF' }
  });

  // 6 类盈利行
  const itemY = colY + 0.88;
  t.items.forEach((it, j) => {
    const y = itemY + j * 0.42;
    // 编号色块
    slide.addShape(S.roundRect, {
      x: x + 0.15, y: y + 0.05, w: 0.26, h: 0.26,
      rectRadius: 0.04, fill: { color: t.pale }, line: { color: t.pale }
    });
    addText(it.n, { x: x + 0.15, y: y + 0.10, w: 0.26, h: 0.16, fontSize: 10, bold: true, color: t.color, align: 'center' });
    // 标签 + note
    addText(it.label, { x: x + 0.46, y: y + 0.02, w: 1.65, h: 0.18, fontSize: 9.5, bold: true, color: C.ink });
    addText(it.note, { x: x + 0.46, y: y + 0.19, w: 1.65, h: 0.15, fontSize: 7.5, color: C.muted });
    // 金额
    addText(it.amount, {
      x: x + 2.0, y: y + 0.04, w: colW - 2.15, h: 0.30,
      fontSize: 13, bold: true, color: t.color, align: 'right'
    });
    // 分隔线
    if (j < t.items.length - 1) {
      slide.addShape(S.line, {
        x: x + 0.15, y: y + 0.40, w: colW - 0.3, h: 0,
        line: { color: 'EAEFF7', width: 0.5 }
      });
    }
  });

  // 底部 Total 条
  const totalY = colY + colH - 0.65;
  slide.addShape(S.roundRect, {
    x: x + 0.12, y: totalY, w: colW - 0.24, h: 0.55,
    rectRadius: 0.06, fill: { color: t.pale }, line: { color: t.pale }
  });
  addText('合计', {
    x: x + 0.22, y: totalY + 0.08, w: 1.0, h: 0.18, fontSize: 9, color: C.muted
  });
  addText('总收益', {
    x: x + 0.22, y: totalY + 0.25, w: 1.5, h: 0.22, fontSize: 11, bold: true, color: C.ink
  });
  addText(t.total, {
    x: x + 1.2, y: totalY + 0.10, w: colW - 1.4, h: 0.38,
    fontSize: 20, bold: true, color: t.color, align: 'right'
  });
  addText(t.highlight, {
    x: x + 0.22, y: totalY + 0.42, w: colW - 0.44, h: 0.13,
    fontSize: 7.3, color: C.muted, align: 'right', italic: true
  });
});

// ====== 底部统一页脚条 ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 6.75, w: 12.05, h: 0.55,
  rectRadius: 0.06, fill: { color: C.navy }, line: { color: C.navy }
});
addText('阶梯洞察', { x: 0.85, y: 6.85, w: 1.5, h: 0.16, fontSize: 9.5, bold: true, color: '9FE7DB' });
addText('商城 GMV 线性扩展（户数 × ARPU 210），B 端 / 数据资产超线性（网络效应），C 端会员订阅率随规模 10% → 13% → 14% 阶梯提升。', {
  x: 2.45, y: 6.85, w: 7.45, h: 0.16, fontSize: 8.6, color: 'DCE7FF', align: 'center'
});
addText('注：所有数字均为项目组基于试点期合理假设的敏感性测算；不同家庭规模下的 B 端议价能力与数据资产品质存在差异，仅作战略参考。', {
  x: 0.85, y: 7.05, w: 11.7, h: 0.2, fontSize: 7.5, color: 'B5C5E0', align: 'center'
});
addText('可解释 · 可追溯 · 可复制', { x: 10.7, y: 6.85, w: 1.85, h: 0.16, fontSize: 8.4, bold: true, color: '9FE7DB', align: 'right' });

// ====== 输出 ======
pptx.writeFile({
  fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-three-tier-revenue-snapshot.pptx'
}).then(fn => console.log('✔ PPT 已生成：', fn));