// 粮达健康 · 三阶段投入测算 × 6 类盈利模式 · 单页 PPT
// 风格沿用 docs/ppt/{group-cockpit, data-source-layer}-slide.js

const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = '三阶段投入测算与6类盈利模式';
pptx.title = '粮达健康 · 三阶段推广测算 × 6 类盈利';
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
  green: '16A085',
  paleGreen: 'E8F6F1',
  red: 'E85D6A',
  paleRed: 'FFEEF0',
  white: 'FFFFFF',
  rowHead: 'F1F5FB'
};

const S = pptx.ShapeType;
function addText(text, opts = {}) {
  slide.addText(text, {
    fontFace: 'Aptos', color: C.ink, margin: 0,
    breakLine: false, fit: 'shrink', ...opts
  });
}

// ====== 顶部标题区 ======
addText('08 / 推广价值', { x: 0.62, y: 0.38, w: 4.6, h: 0.34, fontFace: 'Aptos Display', fontSize: 24, bold: true, color: C.navy });
addText('三阶段投入测算 × 6 类盈利模式', { x: 0.62, y: 0.84, w: 8.5, h: 0.48, fontFace: 'Aptos Display', fontSize: 28, bold: true, color: C.ink });
addText('M0–M3 用 265 万打通"数据 + 硬件"双底座；M3–M6 用 92 万接入集团自有品牌矩阵；M6–M9 以 6 类盈利同步启动商业化。', {
  x: 0.64, y: 1.32, w: 8.6, h: 0.36, fontSize: 10.5, color: C.muted, breakLine: true
});
addText('LIANGDA HEALTH', { x: 11.55, y: 0.52, w: 1.25, h: 0.18, fontSize: 7.5, bold: true, color: C.navy, charSpacing: 1.4, align: 'right' });
slide.addShape(S.ellipse, { x: 12.78, y: 0.55, w: 0.14, h: 0.14, fill: { color: C.green }, line: { color: C.green } });

// ====== 左侧：三阶段投入测算表格 ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 1.88, w: 8.18, h: 4.62,
  rectRadius: 0.06,
  fill: { color: C.white },
  line: { color: C.line, width: 1.0 },
  shadow: { type: 'outer', color: '9AA8C4', blur: 3, offset: 1, angle: 135, opacity: 0.12 }
});

addText('三阶段投入测算', { x: 0.85, y: 2.0, w: 4.6, h: 0.26, fontSize: 14, bold: true, color: C.ink });
addText('COFCO 自有品牌 × 多 Agent 闭环 × 数据资产变现', { x: 0.85, y: 2.31, w: 6.4, h: 0.18, fontSize: 9.5, color: C.muted });

// 阶段小标签（每行上方）
const phaseTag = (x, y, num, label, color) => {
  slide.addShape(S.roundRect, { x, y, w: 1.55, h: 0.32, rectRadius: 0.05, fill: { color }, line: { color } });
  addText(`${num}  ${label}`, { x, y: y + 0.06, w: 1.55, h: 0.18, fontSize: 9, bold: true, color: C.white, align: 'center' });
};
phaseTag(0.85, 2.62, 'Phase 1', '闭环验证', C.blue);
phaseTag(0.85, 3.78, 'Phase 2', '品类接入', C.teal);
phaseTag(0.85, 4.94, 'Phase 3', '商业起飞', C.orange);

// 表格本体（pptxgenjs addTable，可双击编辑）
const tableData = [
  [
    { text: '阶段', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } },
    { text: '人工成本', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } },
    { text: '第三方数据 / 生态合作', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } },
    { text: '基础设施与运维', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } },
    { text: '阶段投入', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } },
    { text: '阶段盈利 / KPI', options: { bold: true, color: C.white, fill: { color: C.navy }, align: 'center', valign: 'middle' } }
  ],
  [
    { text: '第一阶段\nM0–M3', options: { bold: true, color: C.blue, fill: { color: C.paleBlue }, valign: 'middle' } },
    { text: '核心 5 人编制\n（产品 1 / 全栈 2 / AI 工程 1 / 设计运营 1）\n× 3 月 = 15 人月\n按 3 万 / 人月 → 45 万\n覆盖 P0–P2：健康事实库、家庭画像、记忆、Agent 工具路由雏形', options: { color: C.ink, valign: 'middle' } },
    { text: '① 医院 / 体检 / 药店等数据授权 100 万\n   （1–2 家头部体检连锁 + 3–5 家三甲医院营养科样本库）\n② 手环 / 血压 / 体重硬件 100 万\n   （小米手环 8 Pro ×1500 台 + 血压 / 体脂样机各 200 台）\n合计 200 万', options: { color: C.ink, valign: 'middle' } },
    { text: '服务器（应用 + GPU 推理）\nMilvus 向量存储 + 对象存储\n大模型 Token\n（报告抽取 + Agent 对话 + Embedding）\n按 3 月摊销 → 20 万', options: { color: C.ink, valign: 'middle' } },
    { text: '265 万', options: { bold: true, color: C.blue, fontSize: 16, align: 'center', valign: 'middle', fill: { color: C.paleBlue } } },
    { text: '— 以"闭环验证"为目标，不直接计入盈利\n• 覆盖家庭 ≥ 500 户\n• 报告解析准确率 ≥ 90%\n• 推荐点击率 ≥ 8%\n• 餐单 → 加购转化 ≥ 15%', options: { color: C.muted, valign: 'middle' } }
  ],
  [
    { text: '第二阶段\nM3–M6', options: { bold: true, color: C.teal, fill: { color: C.paleTeal }, valign: 'middle' } },
    { text: '扩到 8 人\n（新增 IoT 工程师、推荐算法、B 端 BD）\n× 3 月 = 24 人月\n按 3 万 / 人月 → 72 万\n覆盖 P3–P5：跨品牌推荐引擎、证据链卡片、反馈闭环、Harness 评测', options: { color: C.ink, valign: 'middle' } },
    { text: '集团自有商城 SKU 接入\n（福临门 · 悦鲜活 · 中茶 · 香雪 · 中粮我买网）\n粮达网 B2B 接口打通\n商品上架：粮油 / 调味 / 乳品 / 茶饮 / 健康硬件 / 节令礼盒\n说明：作为 COFCO B2B2C 平台，商城主线是集团自有品牌 + 我买网', options: { color: C.ink, valign: 'middle' } },
    { text: '用户量与推理量爬坡期\n服务器、存储、大模型 Token\n同步扩容 → 20 万', options: { color: C.ink, valign: 'middle' } },
    { text: '92 万', options: { bold: true, color: C.teal, fontSize: 16, align: 'center', valign: 'middle', fill: { color: C.paleTeal } } },
    { text: '— 以"商业化准备"为目标\n• 覆盖家庭 ≥ 5,000 户\n• 集团 4 大品类 SKU 上线 ≥ 200 个\n• 推荐转化率 ≥ 3%\n• 试销 GMV ≥ 50 万（破 0 验证）', options: { color: C.muted, valign: 'middle' } }
  ],
  [
    { text: '第三阶段\nM6–M9', options: { bold: true, color: C.orange, fill: { color: C.paleOrange }, valign: 'middle' } },
    { text: '扩到 10 人\n（新增运营、商务、客服、营养师）\n× 3 月 ≈ 90 万\n本阶段摊销约 22 万（其余进 Y2）\n※ 待你拍板', options: { color: C.ink, valign: 'middle' } },
    { text: '家庭健康脱敏数据资产持续运营\n+ 区域健康洞察合作\n（保险 / 体检机构 BD 试点）\n≈ 20 万 ※ 待你拍板', options: { color: C.ink, valign: 'middle' } },
    { text: '用户 / 数据量进入指数增长\n推理与存储扩容\n≈ 30 万 ※ 待你拍板', options: { color: C.ink, valign: 'middle' } },
    { text: '约 72 万\n（22 + 20 + 30，建议值）', options: { bold: true, color: C.orange, fontSize: 14, align: 'center', valign: 'middle', fill: { color: C.paleOrange } } },
    { text: '6 类盈利同步启动\n① 广告费  ② 商城 GMV  ③ 入驻费\n④ B 端赋能  ⑤ C 端会员  ⑥ 数据资产\n详见右侧拆解', options: { bold: true, color: C.ink, valign: 'middle', fill: { color: 'FFF8EC' } } }
  ]
];

slide.addTable(tableData, {
  x: 2.55, y: 2.55, w: 6.15,
  colW: [0.85, 1.20, 1.40, 1.05, 0.65, 1.00],
  rowH: [0.35, 0.85, 0.85, 0.85],
  border: { type: 'solid', pt: 0.5, color: C.line },
  fontSize: 7.4,
  fontFace: 'Aptos',
  autoPage: false
});

// ====== 右侧：6 类盈利同步启动 ======
addText('第三阶段 · 6 类盈利同步启动', { x: 9.18, y: 1.96, w: 3.8, h: 0.26, fontSize: 14, bold: true, color: C.ink });
addText('合计 ≈ 1440 万 / 年 · 首年 ROI 297%', { x: 9.18, y: 2.28, w: 3.8, h: 0.18, fontSize: 9.5, color: C.muted });

const profits = [
  { n: '①', title: '广告费', amount: '30–50 万', pct: '2–4%', desc: '健康场景原生广告位（CPT/CPC/CPS）+ 品牌联合营销 + 私域 SCRM 代运营', fill: C.palePurple, accent: C.purple, tag: '新增场景' },
  { n: '②', title: '商城 GMV', amount: '960 万', pct: '75%', desc: 'COFCO 自有品牌（福临门 / 中茶 / 蒙牛 / 中粮肉食 / 香雪）精准转化 + 第三方品牌抽佣', fill: C.paleBlue, accent: C.blue, tag: '核心主营' },
  { n: '③', title: '店铺入驻费', amount: '30–50 万', pct: '2–4%', desc: '健康场景货架坑位费：三高压粮 / 儿童成长 / 银发食养 / 慢病专区', fill: C.paleTeal, accent: C.teal, tag: '场景货架' },
  { n: '④', title: 'B 端机构赋能', amount: '200 万', pct: '16%', desc: '体检机构 / 医院 / 保险 / 养老 / 工会 SaaS 年费 + 保单分成 5–15%', fill: C.paleOrange, accent: C.orange, tag: '毛利最高' },
  { n: '⑤', title: 'C 端会员费用', amount: '80–150 万', pct: '6–12%', desc: '个人 / 家庭 / 银发慢病订阅包 + 营养师 1v1 + 央企福利集采', fill: C.paleGreen, accent: C.green, tag: '用户 LTV' },
  { n: '⑥', title: '数据资产变现', amount: '120 万', pct: '9%', desc: '区域健康消费指数 + 白皮书 + 国标提案 + 品牌定位咨询', fill: C.paleRed, accent: C.red, tag: '长期复利' }
];

profits.forEach((p, i) => {
  const y = 2.66 + i * 0.62;
  slide.addShape(S.roundRect, { x: 9.18, y, w: 3.82, h: 0.54, rectRadius: 0.05, fill: { color: C.white }, line: { color: C.line, width: 0.75 } });
  slide.addShape(S.rect, { x: 9.18, y, w: 0.07, h: 0.54, fill: { color: p.accent }, line: { color: p.accent } });
  // 编号 + 标题
  slide.addShape(S.roundRect, { x: 9.34, y: y + 0.08, w: 0.32, h: 0.32, rectRadius: 0.04, fill: { color: p.fill }, line: { color: p.fill } });
  addText(p.n, { x: 9.34, y: y + 0.16, w: 0.32, h: 0.18, fontSize: 11, bold: true, color: p.accent, align: 'center' });
  addText(p.title, { x: 9.74, y: y + 0.05, w: 1.4, h: 0.20, fontSize: 11, bold: true, color: C.ink });
  // 金额 + 占比
  addText(p.amount, { x: 9.74, y: y + 0.27, w: 1.4, h: 0.18, fontSize: 9, bold: true, color: p.accent });
  addText(p.pct, { x: 11.18, y: y + 0.07, w: 0.7, h: 0.18, fontSize: 8.5, color: C.muted, align: 'right' });
  // 标签
  slide.addShape(S.roundRect, { x: 11.9, y: y + 0.07, w: 1.0, h: 0.22, rectRadius: 0.04, fill: { color: p.fill }, line: { color: p.fill } });
  addText(p.tag, { x: 11.9, y: y + 0.105, w: 1.0, h: 0.14, fontSize: 7.5, bold: true, color: p.accent, align: 'center' });
  // 描述
  addText(p.desc, { x: 9.74, y: y + 0.41, w: 3.16, h: 0.13, fontSize: 7.6, color: C.muted });
});

// ====== 左侧表格下方：3 阶段里程碑条 ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 6.56, w: 8.18, h: 0.18,
  rectRadius: 0.04, fill: { color: 'F1F5FB' }, line: { color: 'F1F5FB' }
});
addText('阶段切换定位：闭环验证 → 资产沉淀 → 商业放大  ｜  任一阶段 KPI 未达成即触发回退（Phase 1 GMV < 50 万则不进入 Phase 2 自有 SKU 全面接入）', {
  x: 0.78, y: 6.56, w: 7.96, h: 0.18, fontSize: 7.6, color: C.muted, align: 'center'
});

// ====== 底部统一页脚条 ======
slide.addShape(S.roundRect, {
  x: 0.62, y: 6.85, w: 12.05, h: 0.43,
  rectRadius: 0.05, fill: { color: C.navy }, line: { color: C.navy }
});
addText('投入曲线  265 万 → 92 万 → 商业起飞', { x: 0.9, y: 6.99, w: 3.0, h: 0.14, fontSize: 9.5, bold: true, color: C.white });
addText('年化总收益 ≈ 1440 万  ｜  首年 ROI ≈ 297%  ｜  投资回收期 ≈ 3 月  ｜  三年累计净收益 ≈ 3300 万', {
  x: 4.0, y: 6.97, w: 6.55, h: 0.14, fontSize: 9, color: 'DCE7FF', align: 'center'
});
addText('可解释 · 可追溯 · 可复制', { x: 10.7, y: 6.98, w: 1.85, h: 0.14, fontSize: 8.4, bold: true, color: '9FE7DB', align: 'right' });

// ====== 输出 ======
pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-three-phase-promotion-value.pptx' })
  .then(fn => console.log('✔ PPT 已生成：', fn));