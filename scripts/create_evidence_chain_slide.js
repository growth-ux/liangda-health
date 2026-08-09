const pptxgen = require('pptxgenjs');
const pptx = new pptxgen();
pptx.defineLayout({ name: 'LIANGDA', width: 13.333, height: 7.5 });
pptx.layout = 'LIANGDA';
pptx.author = '粮达健康';
pptx.title = '04/核心功能展示｜证据链（可解释 AI）';
pptx.lang = 'zh-CN';
pptx.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN' };
const C = { navy:'1236B8', text:'1F2937', muted:'64748B', pale:'F5F8FC', border:'D9E2EF', blue:'2F6FED', bluePale:'EAF1FF', orange:'E69025', orangePale:'FFF5E7', red:'D85B62', redPale:'FFF0F1', green:'159A78', greenPale:'EAF8F3', teal:'0EA5A5' };
const s = pptx.addSlide(); s.background = { color:'FFFFFF' };
function txt(t,o){s.addText(t,Object.assign({fontFace:'Microsoft YaHei',margin:0},o));}
function card(x,y,w,h,fill,line,title,body,titleColor){
  s.addShape(pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:0.06,fill:{color:fill},line:{color:line,width:1.1},shadow:{type:'outer',color:'64748B',blur:2,angle:45,distance:1,opacity:0.12}});
  txt(title,{x:x+0.16,y:y+0.12,w:w-0.32,h:0.28,fontSize:11.5,bold:true,color:titleColor||C.text,align:'left'});
  txt(body,{x:x+0.16,y:y+0.46,w:w-0.32,h:h-0.56,fontSize:9.6,color:C.text,breakLine:false,fit:'shrink',valign:'mid'});
}
function arrow(x1,y1,x2,y2,color,dash){s.addShape(pptx.ShapeType.line,{x:x1,y:y1,w:x2-x1,h:y2-y1,line:{color:color||C.muted,width:1.35,dashType:dash||'solid',endArrowType:'triangle'}});}

txt('04/核心功能展示',{x:0.54,y:0.27,w:4.6,h:0.48,fontSize:27,bold:true,color:C.navy});
txt('证据链（可解释 AI）：让每一次健康决策都有依据',{x:0.56,y:0.92,w:7.2,h:0.35,fontSize:16,bold:true,color:C.text});
txt('统一证据链能力，让健康决策从“生成结果”走向“可信解释”',{x:0.56,y:1.31,w:7.2,h:0.28,fontSize:10.5,color:C.muted});

// left evidence-chain panel
s.addShape(pptx.ShapeType.roundRect,{x:0.50,y:1.82,w:5.35,h:4.82,rectRadius:0.08,fill:{color:C.pale},line:{color:C.border,width:1.1}});
txt('证据链机制',{x:0.78,y:2.06,w:1.35,h:0.24,fontSize:12,bold:true,color:C.navy});
txt('Evidence Grounding · Recommendation Evidence · Safety Guardrail',{x:0.78,y:2.34,w:4.65,h:0.22,fontSize:8.8,color:C.muted});
card(1.18,2.70,3.98,0.56,'FFFFFF',C.navy,'用户健康需求','症状 · 家庭画像 · 偏好 · 历史健康事实',C.navy);
card(0.88,3.55,4.40,0.72,C.bluePale,C.blue,'① 生成依据 / Evidence Grounding','从报告事实、健康画像与家庭记忆中提取真实依据，为每条健康建议建立可追溯的事实来源。',C.blue);
card(0.88,4.45,4.40,0.72,C.orangePale,C.orange,'② 推荐依据 / Recommendation Evidence','结合商品健康标签、营养成分与适配人群，解释“为什么推荐”，让结果可理解、可验证。',C.orange);
card(0.88,5.35,4.40,0.72,C.redPale,C.red,'③ 安全拦截 / Safety Guardrail','基于过敏禁忌、特殊人群与风险规则前置校验，安全约束优先于偏好与营销目标。',C.red);
card(1.18,6.25,3.98,0.30,C.greenPale,C.green,'可信健康方案','健康建议 + 商品推荐 + 风险说明',C.green);
arrow(3.17,3.26,3.17,3.55,C.navy); arrow(3.08,4.27,3.08,4.45,C.blue); arrow(3.08,5.17,3.08,5.35,C.orange); arrow(3.08,6.07,3.08,6.25,C.red);

// right screenshot panel
s.addShape(pptx.ShapeType.roundRect,{x:6.10,y:1.82,w:6.73,h:4.82,rectRadius:0.06,fill:{color:'FBFCFE'},line:{color:C.border,width:1.1}});
txt('真实交互：证据随结果生成，解释在对话中呈现',{x:6.38,y:2.06,w:5.8,h:0.24,fontSize:12,bold:true,color:C.navy});
txt('替换为系统截图 · 建议保留生成依据、推荐依据与安全拦截区域',{x:6.38,y:2.34,w:5.9,h:0.22,fontSize:9.5,color:C.muted});
s.addShape(pptx.ShapeType.rect,{x:6.38,y:2.78,w:6.16,h:3.20,fill:{color:'F1F5F9',transparency:10},line:{color:'B8C6D8',width:1.1,dashType:'dash'}});
txt('拖入或替换产品截图',{x:7.15,y:4.00,w:4.60,h:0.40,fontSize:19,bold:true,color:'94A3B8',align:'center'});
txt('建议比例：16:9 / 重点区域可读',{x:7.35,y:4.53,w:4.20,h:0.22,fontSize:10,color:'94A3B8',align:'center'});
[['①','生成依据',6.58,C.blue],['②','推荐依据',8.42,C.orange],['③','安全拦截',10.26,C.red]].forEach(([n,l,x,col])=>{s.addShape(pptx.ShapeType.ellipse,{x,y:6.15,w:0.25,h:0.25,fill:{color:col},line:{color:col,width:0.5}});txt(n,{x,y:6.185,w:0.25,h:0.15,fontSize:8.5,bold:true,color:'FFFFFF',align:'center'});txt(l,{x:x+0.32,y:6.185,w:0.9,h:0.16,fontSize:8.8,color:C.muted});});
txt('通过证据引用与安全规则约束，降低健康场景中的 AI 幻觉与无依据推荐风险。',{x:6.38,y:6.52,w:6.0,h:0.25,fontSize:10.2,bold:true,color:C.text});
txt('证据可追溯 · 推荐可解释 · 风险可拦截 · 决策可复核',{x:0.78,y:7.13,w:7.2,h:0.18,fontSize:9.5,bold:true,color:C.teal});
txt('粮达健康',{x:12.03,y:7.18,w:0.8,h:0.16,fontSize:8,color:'9AA7B8',align:'right'});
pptx.writeFile({fileName:'docs/ppt/liangda-evidence-chain-layout-editable.pptx'});
