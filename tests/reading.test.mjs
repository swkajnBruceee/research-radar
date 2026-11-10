import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../public/reading.js',import.meta.url),'utf8');
function setup(search='?id=arxiv%3A2303.04137'){
 const elements=new Map();
 for(const name of ['back-to-research','queue-entry','title','prepare','analyze','refresh','status','model-state','analysis','search','count','passages','quote','quote-dialog','copy','close-quote','copy-state'])elements.set(name,{innerHTML:'',textContent:'',value:'',disabled:false,hidden:false,open:false,focus(){},select(){},showModal(){this.open=true;},close(){this.open=false;}});
 const result={status:{status:'ready',message:'全文已准备'},model_configured:false,analysis:null,document:{format:'html',fetched:'2026-11-05',passages:[{id:'e1',section:'<script>method</script>',location:'Methods',text:'Ablation evidence <img src=x onerror=alert(1)>',url:'https://arxiv.org/html/2303.04137v1#S1.p1'},{id:'e2',section:'Experiments',location:'Experiments',text:'Testing generalization across novel objects.',url:'javascript:alert(1)'}]}};
 const sandbox={URL,URLSearchParams,location:{search,assign(){}},navigator:{},window:{addEventListener(){}},setInterval(){return 1;},clearInterval(){},document:{querySelector:s=>elements.get(s.slice(1)),getElementById:s=>elements.get(s)},fetch:async path=>({status:200,ok:true,json:async()=>structuredClone(path.includes('/api/items/')?{title:'Paper'}:result)})};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);return {elements,sandbox,run:s=>vm.runInContext(s,sandbox)};
}
test('Original evidence is escaped, searchable, and model generation stays disabled without configuration',async()=>{
 const c=setup();await new Promise(setImmediate);
 assert.ok(!c.elements.get('passages').innerHTML.includes('<img'));
 assert.equal(c.elements.get('analyze').disabled,true);
 c.elements.get('search').value='ablation';c.elements.get('search').oninput();
 assert.ok(c.elements.get('count').textContent.startsWith('1 / 2'));
 assert.ok(c.elements.get('passages').innerHTML.includes('2303.04137v1#S1.p1'));
 assert.equal(c.run('safe("javascript:alert(1)")'),'#');
 assert.equal(c.elements.get('back-to-research').href,'/#today?paper=arxiv%3A2303.04137');
});
test('A reuse evidence link opens only a matching source passage',async()=>{
 const c=setup('?id=arxiv%3A2303.04137&evidence=e1');
 const passage={open:false};c.elements.set('e-e1',passage);
 await new Promise(setImmediate);assert.equal(passage.open,true);
 const invalid=setup('?id=arxiv%3A2303.04137&evidence=not-in-source');
 const other={open:false};invalid.elements.set('e-not-in-source',other);
 await new Promise(setImmediate);assert.equal(other.open,false);
});
test('The return link restores a local article filter and rejects external destinations',async()=>{
 const route='#today?paper=arxiv%3A2611.06881&view=seen';
 const c=setup('?id=arxiv%3A2611.06881&return='+encodeURIComponent(route));await new Promise(setImmediate);
 assert.equal(c.elements.get('back-to-research').href,'/'+route);
 const invalid=setup('?id=arxiv%3A2611.06881&return='+encodeURIComponent('https://example.com'));
 await new Promise(setImmediate);assert.equal(invalid.elements.get('back-to-research').href,'/#today');
});
test('A quotation retains version, section and evidence ID without modifying notes',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.elements.get('passages').onclick({target:{closest:()=>({dataset:{quote:'e1'}})}});
 assert.equal(c.elements.get('quote-dialog').open,true);
 const quote=c.elements.get('quote').value;
 assert.ok(quote.includes('### 原文证据 · Methods'));assert.ok(quote.includes('2303.04137v1#S1.p1'));assert.ok(quote.includes('证据 e1'));
 assert.ok(quote.includes('我的理解：'));
});
test('An agent pilot is readable without an API key, with hypotheses separate and safe disclosure text',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`state.analysis={mode:'agent_pilot',overview:'试跑结论',model:'当前会话代理',coverage:{read:2,total:2},notice:'未复现',findings:[{kind:'method',title:'<img src=x>',text:'配方变化',quote:'reliable actions',evidence_ids:['e1']}],hypotheses:[{title:'噪声实验',text:'待验证',quote:'evidence text',evidence_ids:['e2']}]};render();`);
 const html=c.elements.get('analysis').innerHTML;
 assert.equal(c.elements.get('analysis').hidden,false);
 assert.equal(c.elements.get('analyze').disabled,true);
 assert.ok(html.includes('精读解读与原文依据'));
 assert.equal(c.elements.get('analyze').hidden,true);
 assert.equal(c.elements.get('model-state').hidden,true);
 assert.equal(c.elements.get('prepare').hidden,true);
 assert.ok(html.includes('已读提取文字 2 / 2'));
 assert.ok(html.includes('值得验证的问题'));
 assert.ok(html.includes('href="#e-e1"'));
 assert.ok(html.includes('&lt;img src=x&gt;'));assert.ok(!html.includes('<img'));
 c.elements.set('e-e1',{open:false});
 c.elements.get('analysis').onclick({target:{closest:()=>({hash:'#e-e1'})}});
 assert.equal(c.elements.get('e-e1').open,true);
});
