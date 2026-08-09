const pptxgen = require('pptxgenjs');
const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = '粮达健康';
pptx.subject = 'Supervisor 多 Agent 协作核心功能展示';
pptx.title = '04/核心功能展示';
pptx.company = '粮达健康';
pptx.lang = 'zh-CN';
pptx.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN' };
pptx.defineLayout({ name: 'LIANGDA', width: 13.333, height: 7.5 });
pptx.layout = 'LIANGDA';

const C = { navy: '1236B8', text: '1F2937', muted: '64748B', line: '94A3B8', pale: 'F5F8FC', border: 'D9E2EF', cyan: '0EA5A5', green: '18A57A', orange: 'E69025', red: 'D85B62', bluePale: 'EAF1FF', greenPale: 'EAF8F3', orangePale: 'FFF5E7', redPale: 'FFF0F1' };
const slide = pptx.addSlide();
slide.background = { color: 'FFFFFF' };

// Header
slide.addText('04/核心功能展示', { x: 0.54, y: 0.27, w: 4.6, h: 0.48, fontFace: 'Microsoft YaHei', fontSize: 27, bold: true, color: C.navy, margin: 0, breakLine: false });
slide.addText('多 Agent 协作：Supervisor 驱动可信健康决策', { x: 0.56, y: 0.92, w: 6.0, h: 0.35, fontFace: 'Microsoft YaHei', fontSize: 16, bold: true, color: C.text, margin: 0 });
slide.addText('统一理解需求、分派任务并汇总专业 Agent 结果', { x: 0.56, y: 1.31, w: 6.0, h: 0.28, fontFace: 'Microsoft YaHei', fontSize: 10.5, color: C.muted, margin: 0 });

// Left architecture panel
slide.addShape(pptx.ShapeType.roundRect, { x: 0.50, y: 1.82, w: 5.35, h: 4.82, rectRadius: 0.08, fill: { color: C.pale }, line: { color: C.border, width: 1.1 } });
slide.addText('协作架构', { x: 0.78, y: 2.06, w: 1.2, h: 0.24, fontSize: 12, bold: true, color: C.navy, margin: 0 });
slide.addText('Supervisor 统一调度 · 专业 Agent 分工执行', { x: 0.78, y: 2.34, w: 4.45, h: 0.22, fontSize: 9.5, color: C.muted, margin: 0 });

function box(x, y, w, h, fill, line, title, body, titleColor = C.text) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: line, width: 1.1 }, shadow: { type: 'outer', color: '64748B', blur: 2, angle: 45, distance: 1, opacity: 0.12 } });
  slide.addText(title, { x: x + 0.10, y: y + 0.14, w: w - 0.20, h: 0.24, fontSize: 11.5, bold: true, color: titleColor, align: 'center', margin: 0 });
  slide.addText(body, { x: x + 0.10, y: y + 0.43, w: w - 0.20, h: h - 0.52, fontSize: 9.4, color: C.text, align: 'center', valign: 'mid', margin: 0, breakLine: false, fit: 'shrink' });
}

box(1.92, 2.72, 2.46, 0.62, 'FFFFFF', C.navy, '用户健康咨询', '症状 / 需求 / 偏好', C.text);
box(1.68, 3.70, 2.94, 0.86, C.bluePale, C.navy, 'Supervisor', '任务理解 · 路由调度 · 结果汇总', C.navy);

const ay = 5.05, aw = 1.40, ah = 0.90;
box(0.78, ay, aw, ah, C.greenPale, C.green, '健康管家', '健康诉求分析', C.green);
box(2.27, ay, aw, ah, C.orangePale, C.orange, '商品导购', '个性化推荐', C.orange);
box(3.76, ay, aw, ah, C.redPale, C.red, '安全审核', '禁忌与风险校验', C.red);
box(4.96, 5.05, 0.62, ah, 'FFFFFF', C.cyan, '输出', '方案', C.cyan);

function arrow(x1, y1, x2, y2, color = C.line, width = 1.35, dash = 'solid') {
  slide.addShape(pptx.ShapeType.line, { x: x1, y: y1, w: x2 - x1, h: y2 - y1, line: { color, width, dashType: dash, beginArrowType: 'none', endArrowType: 'triangle' } });
}
arrow(3.15, 3.34, 3.15, 3.70, C.navy, 1.5);
arrow(2.98, 4.56, 1.48, 5.05, C.green, 1.2);
arrow(3.15, 4.56, 2.97, 5.05, C.orange, 1.2);
arrow(3.33, 4.56, 4.46, 5.05, C.red, 1.2);
// return paths (dashed)
arrow(1.48, 5.05, 2.32, 4.56, C.green, 1.05, 'dash');
arrow(2.97, 5.05, 3.06, 4.56, C.orange, 1.05, 'dash');
arrow(4.46, 5.05, 3.72, 4.56, C.red, 1.05, 'dash');
arrow(4.46, 5.50, 5.00, 5.50, C.cyan, 1.4);
slide.addText('任务派发', { x: 3.82, y: 4.64, w: 0.7, h: 0.18, fontSize: 8.2, color: C.muted, margin: 0, italic: true });
slide.addText('结果回传', { x: 1.55, y: 5.72, w: 0.7, h: 0.18, fontSize: 8.2, color: C.muted, margin: 0, italic: true });

// bottom value strip
slide.addShape(pptx.ShapeType.roundRect, { x: 0.78, y: 6.22, w: 4.72, h: 0.29, rectRadius: 0.04, fill: { color: 'E9F7F3' }, line: { color: 'C9EDE2', width: 0.7 } });
slide.addText('可信健康方案 = 建议 + 推荐 + 风险说明', { x: 0.92, y: 6.285, w: 4.45, h: 0.15, fontSize: 9.2, bold: true, color: C.cyan, align: 'center', margin: 0 });

// Right screenshot placeholder
slide.addShape(pptx.ShapeType.roundRect, { x: 6.10, y: 1.82, w: 6.73, h: 4.82, rectRadius: 0.06, fill: { color: 'FBFCFE' }, line: { color: C.border, width: 1.1 } });
slide.addText('产品实现场景', { x: 6.38, y: 2.06, w: 1.4, h: 0.24, fontSize: 12, bold: true, color: C.navy, margin: 0 });
slide.addText('替换为系统截图 · 建议保留 Agent 编排、推荐结果与安全提醒', { x: 6.38, y: 2.34, w: 5.75, h: 0.22, fontSize: 9.5, color: C.muted, margin: 0 });
slide.addShape(pptx.ShapeType.rect, { x: 6.38, y: 2.78, w: 6.16, h: 3.20, fill: { color: 'F1F5F9', transparency: 10 }, line: { color: 'B8C6D8', width: 1.1, dash: 'dash' } });
slide.addText('拖入或替换产品截图', { x: 7.15, y: 4.00, w: 4.60, h: 0.40, fontSize: 19, bold: true, color: '94A3B8', align: 'center', margin: 0 });
slide.addText('建议比例：16:9 / 重点区域可读', { x: 7.35, y: 4.53, w: 4.20, h: 0.22, fontSize: 10, color: '94A3B8', align: 'center', margin: 0 });
// numbered callouts to match screenshot regions
[['①','健康管家','6.58','6.15','18A57A'], ['②','商品导购','8.42','6.15','E69025'], ['③','安全审核','10.26','6.15','D85B62']].forEach(([n, label, x, y, col]) => {
  slide.addShape(pptx.ShapeType.ellipse, { x: Number(x), y: Number(y), w: 0.25, h: 0.25, fill: { color: col }, line: { color: col, width: 0.5 } });
  slide.addText(n, { x: Number(x), y: Number(y)+0.035, w: 0.25, h: 0.15, fontSize: 8.5, bold: true, color: 'FFFFFF', align: 'center', margin: 0 });
  slide.addText(label, { x: Number(x)+0.32, y: Number(y)+0.035, w: 0.82, h: 0.16, fontSize: 8.8, color: C.muted, margin: 0 });
});

slide.addText('Supervisor 统筹专业 Agent，在个性化推荐的同时前置拦截健康风险。', { x: 6.38, y: 6.52, w: 6.0, h: 0.25, fontSize: 10.5, color: C.text, bold: true, margin: 0 });
slide.addText('粮达健康', { x: 12.03, y: 7.18, w: 0.8, h: 0.16, fontSize: 8, color: '9AA7B8', align: 'right', margin: 0 });

pptx.writeFile({ fileName: 'docs/ppt/liangda-supervisor-layout-editable.pptx' });
