const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.defineLayout({ name: 'LIANGDA', width: 13.333, height: 7.5 });
pptx.layout = 'LIANGDA';
pptx.author = '粮达健康';
pptx.company = '粮达健康';
pptx.subject = '自适应反馈进化';
pptx.title = '04/核心功能展示｜自适应反馈进化';
pptx.lang = 'zh-CN';
pptx.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN' };

const S = pptx.ShapeType;
const C = {
  navy: '1237B8', ink: '18263D', muted: '63738C', white: 'FFFFFF',
  panel: 'F6F9FD', line: 'D7E1EE', bluePale: 'EAF1FF',
  green: '10B981', greenPale: 'E8FAF3', violet: '7057E8', violetPale: 'F0EDFF',
  softBlue: '8EAAE8', softText: 'A8B7CC'
};
const slide = pptx.addSlide();
slide.background = { color: C.white };
const screenshotPath = '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/adaptive-feedback-product-crop.png';

function txt(text, opts = {}) {
  slide.addText(text, {
    fontFace: 'Microsoft YaHei', margin: 0, fit: 'shrink', color: C.ink,
    breakLine: false, ...opts
  });
}

function rounded(x, y, w, h, fill, line = fill, radius = 0.06) {
  slide.addShape(S.roundRect, {
    x, y, w, h, rectRadius: radius, fill: { color: fill }, line: { color: line, width: 0.9 }
  });
}

function arrow(x1, y1, x2, y2, color = C.softBlue, width = 1.25) {
  slide.addShape(S.line, {
    x: x1, y: y1, w: x2 - x1, h: y2 - y1,
    line: { color, width, endArrowType: 'triangle' }
  });
}

// Header
txt('04/核心功能展示', { x: 0.58, y: 0.30, w: 3.8, h: 0.36, fontSize: 25, bold: true, color: C.navy });
txt('自适应反馈进化', { x: 0.60, y: 0.86, w: 4.5, h: 0.42, fontSize: 22, bold: true });
txt('让每一次对话、选择与反馈，成为下一次健康决策的依据', {
  x: 0.62, y: 1.33, w: 6.9, h: 0.23, fontSize: 10.5, color: C.muted
});
slide.addShape(S.ellipse, { x: 10.55, y: 0.24, w: 0.28, h: 0.28, fill: { color: 'F3B21A' }, line: { color: 'F3B21A' } });
slide.addShape(S.ellipse, { x: 10.71, y: 0.38, w: 0.22, h: 0.22, fill: { color: C.green }, line: { color: C.green } });
slide.addShape(S.ellipse, { x: 10.78, y: 0.19, w: 0.19, h: 0.19, fill: { color: C.navy }, line: { color: C.navy } });
txt('中粮', { x: 11.04, y: 0.26, w: 0.48, h: 0.18, fontSize: 11, bold: true, color: '4A2B29' });
txt('COFCO', { x: 11.04, y: 0.46, w: 0.48, h: 0.10, fontSize: 5.5, bold: true, color: '4A2B29', charSpacing: 0.8 });
txt('阿里云智能集团', { x: 11.54, y: 0.29, w: 1.18, h: 0.18, fontSize: 10.8, bold: true, color: C.navy });
txt('ALIBABA CLOUD INTELLIGENCE GROUP', { x: 11.54, y: 0.49, w: 1.18, h: 0.08, fontSize: 4.7, color: C.navy, charSpacing: 0.25 });

// Left: proof from the actual product.
rounded(0.58, 1.83, 5.43, 4.88, C.panel, C.line, 0.07);
txt('真实产品交互', { x: 0.87, y: 2.10, w: 1.6, h: 0.24, fontSize: 12.5, bold: true, color: C.navy });
txt('家庭健康状态与 AI 对话，共同沉淀可用反馈', { x: 0.87, y: 2.40, w: 3.55, h: 0.18, fontSize: 8.9, color: C.muted });
rounded(0.87, 2.76, 4.85, 2.74, '091220', '091220', 0.04);
slide.addImage({ path: screenshotPath, x: 0.90, y: 2.79, w: 4.79, h: 2.68, altText: '粮达健康驾驶舱与 AI 对话界面' });

// Callout markers on the screenshot, all editable.
slide.addShape(S.ellipse, { x: 1.49, y: 3.33, w: 0.28, h: 0.28, fill: { color: C.green }, line: { color: C.white, width: 1 } });
txt('1', { x: 1.49, y: 3.405, w: 0.28, h: 0.10, fontSize: 7.2, bold: true, color: C.white, align: 'center' });
arrow(1.75, 3.47, 2.47, 3.14, C.green, 1);
rounded(1.95, 2.80, 1.36, 0.33, C.green, C.green, 0.05);
txt('识别近期状态', { x: 2.05, y: 2.90, w: 1.15, h: 0.12, fontSize: 7.3, bold: true, color: C.white, align: 'center' });
slide.addShape(S.ellipse, { x: 4.80, y: 4.23, w: 0.28, h: 0.28, fill: { color: C.violet }, line: { color: C.white, width: 1 } });
txt('2', { x: 4.80, y: 4.305, w: 0.28, h: 0.10, fontSize: 7.2, bold: true, color: C.white, align: 'center' });
arrow(4.80, 4.34, 4.17, 3.86, C.violet, 1);
rounded(3.45, 3.43, 1.55, 0.33, C.violet, C.violet, 0.05);
txt('对话持续学习', { x: 3.54, y: 3.53, w: 1.36, h: 0.12, fontSize: 7.3, bold: true, color: C.white, align: 'center' });

rounded(0.87, 5.79, 4.85, 0.58, C.navy, C.navy, 0.05);
txt('不是一次性问答，而是持续理解家庭的健康决策助手', {
  x: 1.13, y: 5.99, w: 4.33, h: 0.14, fontSize: 9.1, bold: true, color: C.white, align: 'center'
});

// Right: the actual adaptive loop.
rounded(6.28, 1.83, 6.47, 4.88, 'FBFCFE', C.line, 0.07);
txt('反馈如何推动下一次推荐？', { x: 6.58, y: 2.10, w: 3.7, h: 0.24, fontSize: 12.5, bold: true, color: C.navy });
txt('以“爸爸不喜欢鱼”为例，健康安全边界不变，推荐策略动态调整', { x: 6.58, y: 2.40, w: 5.54, h: 0.18, fontSize: 8.9, color: C.muted });

const steps = [
  { n: '01', y: 2.86, color: C.violet, pale: C.violetPale, title: '捕捉反馈', body: '对话表达、商品点击、购物选择、推荐采纳', quote: '“爸爸不喜欢鱼”' },
  { n: '02', y: 3.82, color: C.navy, pale: C.bluePale, title: '形成记忆', body: '沉淀为排斥偏好，关联家庭成员与有效时间', quote: '记忆：不喜欢鱼' },
  { n: '03', y: 4.78, color: C.green, pale: C.greenPale, title: '调整推荐', body: '仍满足低脂原则，替换为鸡胸肉、豆制品方案', quote: '低脂 · 高蛋白 · 更愿意执行' }
];

steps.forEach((item, index) => {
  rounded(6.58, item.y, 5.84, 0.70, C.white, C.line, 0.05);
  slide.addShape(S.ellipse, { x: 6.76, y: item.y + 0.16, w: 0.38, h: 0.38, fill: { color: item.color }, line: { color: item.color } });
  txt(item.n, { x: 6.76, y: item.y + 0.27, w: 0.38, h: 0.10, fontSize: 6.9, bold: true, color: C.white, align: 'center' });
  txt(item.title, { x: 7.34, y: item.y + 0.11, w: 1.12, h: 0.16, fontSize: 10.2, bold: true, color: item.color });
  txt(item.body, { x: 7.34, y: item.y + 0.34, w: 3.15, h: 0.13, fontSize: 8.1, color: C.muted });
  rounded(10.61, item.y + 0.18, 1.54, 0.30, item.pale, item.pale, 0.04);
  txt(item.quote, { x: 10.68, y: item.y + 0.28, w: 1.40, h: 0.10, fontSize: 7.0, bold: true, color: item.color, align: 'center' });
  if (index < steps.length - 1) arrow(6.95, item.y + 0.72, 6.95, item.y + 0.91, C.softBlue, 1.1);
});

// The safety constraint makes the business logic credible.
rounded(6.58, 5.73, 5.84, 0.47, 'FFF8EA', 'F7D89B', 0.05);
txt('健康约束始终优先：记忆优化个性化，不覆盖健康安全边界', {
  x: 6.80, y: 5.89, w: 5.38, h: 0.13, fontSize: 8.5, bold: true, color: 'A16107', align: 'center'
});

// Footer statement.
rounded(0.58, 6.93, 12.17, 0.31, C.navy, C.navy, 0.03);
txt('用户反馈', { x: 1.15, y: 7.035, w: 1.0, h: 0.10, fontSize: 8.2, bold: true, color: C.white, align: 'center' });
txt('→', { x: 2.16, y: 7.00, w: 0.23, h: 0.15, fontSize: 11, bold: true, color: '9FC0FF', align: 'center' });
txt('互动记忆', { x: 2.47, y: 7.035, w: 1.0, h: 0.10, fontSize: 8.2, bold: true, color: C.white, align: 'center' });
txt('→', { x: 3.49, y: 7.00, w: 0.23, h: 0.15, fontSize: 11, bold: true, color: '9FC0FF', align: 'center' });
txt('更贴合的健康决策', { x: 3.81, y: 7.035, w: 1.65, h: 0.10, fontSize: 8.2, bold: true, color: 'A8F1D5', align: 'center' });
txt('→', { x: 5.53, y: 7.00, w: 0.23, h: 0.15, fontSize: 11, bold: true, color: '9FC0FF', align: 'center' });
txt('持续产生新反馈', { x: 5.85, y: 7.035, w: 1.38, h: 0.10, fontSize: 8.2, bold: true, color: C.white, align: 'center' });
txt('从一次性推荐，进化为持续理解家庭的健康决策助手', { x: 8.20, y: 7.035, w: 3.92, h: 0.10, fontSize: 8.3, color: 'D7E4FF', align: 'right' });

pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-adaptive-feedback-evolution-editable.pptx' });
