const pptxgen = require('pptxgenjs');

const pptx = new pptxgen();
pptx.defineLayout({ name: 'LIANGDA', width: 13.333, height: 7.5 });
pptx.layout = 'LIANGDA';
pptx.author = '粮达健康';
pptx.company = '粮达健康';
pptx.subject = '健康预警与通知';
pptx.title = '04/核心功能展示｜健康预警与通知';
pptx.lang = 'zh-CN';
pptx.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN' };

const S = pptx.ShapeType;
const C = { navy: '1237B8', ink: '18263D', muted: '63738C', bg: 'F5F8FC', line: 'D7E1EE', green: '10B981', greenPale: 'E8FAF3', bluePale: 'EAF1FF', orange: 'F59E0B', orangePale: 'FFF5E5', white: 'FFFFFF', red: 'E05A63' };
const slide = pptx.addSlide();
slide.background = { color: C.bg };
const imagePath = '/var/folders/bh/1f0zsws174972bgg3dcz98_r0000gn/T/codex-clipboard-YUJxoY.png';

function txt(text, opts = {}) {
  slide.addText(text, { fontFace: 'Microsoft YaHei', margin: 0, fit: 'shrink', color: C.ink, ...opts });
}
function rr(x, y, w, h, fill, line = C.line, radius = 0.07) {
  slide.addShape(S.roundRect, { x, y, w, h, rectRadius: radius, fill: { color: fill }, line: { color: line, width: 1 } });
}
function line(x, y, w, h, color, width = 1.2, dashType = 'solid', arrow = false) {
  slide.addShape(S.line, { x, y, w, h, line: { color, width, dashType, endArrowType: arrow ? 'triangle' : 'none' } });
}

// Header
txt('04/核心功能展示', { x: 0.58, y: 0.30, w: 3.8, h: 0.36, fontSize: 25, bold: true, color: C.navy });
txt('健康预警与通知', { x: 0.60, y: 0.82, w: 4.9, h: 0.48, fontSize: 23, bold: true, color: C.ink });
txt('从异常指标识别，到多渠道触达，让家庭健康风险被及时看见', { x: 0.62, y: 1.38, w: 6.5, h: 0.25, fontSize: 10.8, color: C.muted });
txt('HEALTH ALERT · FAMILY NOTIFICATION', { x: 9.60, y: 0.44, w: 3.12, h: 0.18, fontSize: 8.4, bold: true, color: C.navy, align: 'right', charSpacing: 0.7 });

// Left story panel
rr(0.60, 1.88, 4.15, 4.72, C.white);
txt('一条预警，如何被及时接住？', { x: 0.90, y: 2.16, w: 3.35, h: 0.28, fontSize: 13, bold: true, color: C.navy });
txt('把复杂配置，变成家庭可以执行的健康动作', { x: 0.90, y: 2.50, w: 3.40, h: 0.20, fontSize: 9.1, color: C.muted });

const steps = [
  { n: '01', title: '识别风险', body: '选择家人，持续监测血压、心率、睡眠等指标。', color: C.navy, pale: C.bluePale },
  { n: '02', title: '自定义规则', body: '设置阈值、持续时长与提醒频率，适配不同成员。', color: C.orange, pale: C.orangePale },
  { n: '03', title: '主动通知', body: '异常后触达本人、家属与照护者，形成干预闭环。', color: C.green, pale: C.greenPale }
];
steps.forEach((s, i) => {
  const y = 2.98 + i * 0.90;
  slide.addShape(S.ellipse, { x: 0.90, y, w: 0.42, h: 0.42, fill: { color: s.color }, line: { color: s.color } });
  txt(s.n, { x: 0.90, y: y + 0.11, w: 0.42, h: 0.12, fontSize: 8.2, bold: true, color: C.white, align: 'center' });
  txt(s.title, { x: 1.52, y: y + 0.01, w: 1.20, h: 0.20, fontSize: 11.2, bold: true, color: s.color });
  txt(s.body, { x: 1.52, y: y + 0.28, w: 2.80, h: 0.29, fontSize: 8.7, color: C.ink, breakLine: false, fit: 'shrink' });
  if (i < 2) line(1.11, y + 0.46, 0, 0.38, C.line, 1.2, 'dash');
});
rr(0.90, 5.88, 3.48, 0.42, C.navy, C.navy, 0.06);
txt('监测数据异常  →  规则匹配  →  家人收到通知', { x: 1.06, y: 6.02, w: 3.15, h: 0.14, fontSize: 8.6, bold: true, color: C.white, align: 'center' });

// Right evidence panel
rr(5.02, 1.88, 7.70, 4.72, C.white);
txt('真实交互：预警规则可配置，通知记录可追溯', { x: 5.32, y: 2.16, w: 4.80, h: 0.25, fontSize: 13, bold: true, color: C.navy });
txt('系统截图 · 重点看见“设置—触发—发送”的完整链路', { x: 9.10, y: 2.19, w: 3.28, h: 0.17, fontSize: 8.5, color: C.muted, align: 'right' });
// Screenshot frame
slide.addShape(S.roundRect, { x: 5.32, y: 2.60, w: 7.10, h: 3.42, rectRadius: 0.05, fill: { color: 'F8FAFD' }, line: { color: 'B8C8DD', width: 1.1 }, shadow: { type: 'outer', color: '8FA3BF', blur: 2, angle: 45, distance: 1, opacity: 0.16 } });
slide.addShape(S.rect, { x: 5.32, y: 2.60, w: 7.10, h: 0.27, fill: { color: 'EAF1F8' }, line: { color: 'EAF1F8' } });
['E25D67', 'F3B43F', '15A57A'].forEach((col, i) => slide.addShape(S.ellipse, { x: 5.52 + i * 0.16, y: 2.70, w: 0.07, h: 0.07, fill: { color: col }, line: { color: col } }));
txt('notice / alert-rule-settings', { x: 6.05, y: 2.69, w: 2.4, h: 0.10, fontSize: 6.8, color: C.muted });
slide.addImage({ path: imagePath, x: 5.48, y: 2.93, w: 5.72, h: 2.98, sizing: { type: 'contain', w: 5.72, h: 2.98 }, altText: '健康预警与通知设置界面截图' });

// Editable callouts
slide.addShape(S.rect, { x: 11.34, y: 2.93, w: 0.94, h: 2.98, fill: { color: 'F5F8FC' }, line: { color: 'E0E8F2', width: 0.6 } });
const callouts = [
  { y: 3.30, label: '指定\n家庭成员', color: C.navy, toX: 6.67 },
  { y: 4.19, label: '设置监测\n指标与阈值', color: C.green, toX: 8.10 },
  { y: 5.08, label: '预警发送\n记录留痕', color: C.orange, toX: 10.20 }
];
callouts.forEach((c, i) => {
  slide.addShape(S.ellipse, { x: 11.55, y: c.y - 0.17, w: 0.28, h: 0.28, fill: { color: c.color }, line: { color: c.color } });
  txt(String(i + 1), { x: 11.55, y: c.y - 0.095, w: 0.28, h: 0.10, fontSize: 7.4, bold: true, color: C.white, align: 'center' });
  txt(c.label, { x: 11.40, y: c.y + 0.17, w: 0.82, h: 0.30, fontSize: 6.4, bold: true, color: c.color, align: 'center', breakLine: false });
  line(11.30, c.y - 0.02, -(11.30 - c.toX), -0.01, c.color, 1.0, 'dash', true);
});

// Bottom value strip
rr(0.60, 6.86, 12.12, 0.36, C.navy, C.navy, 0.04);
txt('采集健康数据', { x: 0.94, y: 6.98, w: 1.16, h: 0.13, fontSize: 8.8, bold: true, color: C.white, align: 'center' });
txt('→', { x: 2.18, y: 6.96, w: 0.22, h: 0.16, fontSize: 12, bold: true, color: '9FC0FF', align: 'center' });
txt('智能识别风险', { x: 2.48, y: 6.98, w: 1.28, h: 0.13, fontSize: 8.8, bold: true, color: C.white, align: 'center' });
txt('→', { x: 3.86, y: 6.96, w: 0.22, h: 0.16, fontSize: 12, bold: true, color: '9FC0FF', align: 'center' });
txt('分级预警', { x: 4.14, y: 6.98, w: 0.94, h: 0.13, fontSize: 8.8, bold: true, color: C.white, align: 'center' });
txt('→', { x: 5.20, y: 6.96, w: 0.22, h: 0.16, fontSize: 12, bold: true, color: '9FC0FF', align: 'center' });
txt('本人 / 家属 / 照护者收到通知', { x: 5.48, y: 6.98, w: 2.30, h: 0.13, fontSize: 8.8, bold: true, color: C.white, align: 'center' });
txt('→', { x: 7.92, y: 6.96, w: 0.22, h: 0.16, fontSize: 12, bold: true, color: '9FC0FF', align: 'center' });
txt('及时干预', { x: 8.22, y: 6.98, w: 0.94, h: 0.13, fontSize: 8.8, bold: true, color: 'A8F1D5', align: 'center' });
txt('预警不是提醒一次，而是让家庭健康风险进入可执行的照护流程', { x: 9.45, y: 6.98, w: 2.86, h: 0.13, fontSize: 7.6, color: 'D7E4FF', align: 'right' });

pptx.writeFile({ fileName: '/Users/tiger/PycharmProjects/liangda-health/docs/ppt/liangda-health-alert-editable.pptx' });
