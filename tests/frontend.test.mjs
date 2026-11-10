import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const queueSource=fs.readFileSync(new URL('../public/queue.js',import.meta.url),'utf8');
const frontierSource=fs.readFileSync(new URL('../public/frontier.js',import.meta.url),'utf8');
const source=fs.readFileSync(new URL('../public/app.js',import.meta.url),'utf8');
const paper={id:'arxiv:2406.09246',title:'OpenVLA',title_zh:'开放动作模型',summary:'Original abstract',authors:'Researchers',url:'https://arxiv.org/abs/2406.09246',pdf_url:'https://arxiv.org/pdf/2406.09246',code_url:'https://github.com/openvla/openvla',source_id:'foundation',kind:'paper',published:'2024-06-13',updated:'2024-06-13',topics:['vla'],curated:true,saved:false,reading:'unread',notes:'',note_level:'摘要筛选',note_updated:'',analysis:{problem:'Explicit research problem',question:'A hypothesis to test'},events:[]};
const technologies=JSON.parse(fs.readFileSync(new URL('../content/technologies.json',import.meta.url),'utf8'));
const signalSeed=JSON.parse(fs.readFileSync(new URL('../ios/ResearchRadar/Resources/ReadingShelf.json',import.meta.url),'utf8'));
const fixture={reading_queue:{tasks:[],counts:{},notice:'等待代理，不自动调用API'},signals:signalSeed.signals,frontier_meta:signalSeed.frontier_meta,technology_briefs:technologies,items:[paper],topics:[{id:'vla',name:'视觉语言动作模型',short:'VLA',description:'Vision to action',questions:['What generalizes?'],related:[]}],sources:[{id:'arxiv',name:'arXiv',description:'Source',url:'https://arxiv.org',collector:'arxiv',enabled:true,error:'',count:0}],ideas:[],sessions:[],settings:{focus:['vla'],auto_sync:true,interval_minutes:180},recommended:[paper.id],sync:{running:false}};
function setup(hash=''){
 const elements=new Map(),listeners={};
 class Element{
  constructor(id){this.id=id;this._html='';this.value='';this.open=false;this.listeners={};this.classList={add(){},remove(){},contains(){return false;}};}
  set innerHTML(v){this._html=v;for(const m of v.matchAll(/\bid="([^"]+)"/g))if(!elements.has(m[1]))elements.set(m[1],new Element(m[1]));}
  get innerHTML(){return this._html;}
  addEventListener(n,f){this.listeners[n]=f;}
  setAttribute(){} focus(){} scrollIntoView(){} showModal(){this.open=true;} close(){this.open=false;}
 }
 for(const id of ['app','detail-dialog','idea-dialog','technology-dialog','frontier-dialog','toast'])elements.set(id,new Element(id));
 const sandbox={URL,URLSearchParams,Date,Set,console,fixture:structuredClone(fixture),history:{replaceState(a,b,value){sandbox.location.hash=value;},pushState(a,b,value){sandbox.location.hash=value;}},location:{hash},setTimeout(){return 1;},clearTimeout(){},setInterval(){return 1;},confirm(){return true;},document:{querySelector(s){return elements.get(s.replace(/^#/,''))||null;},getElementById(s){return elements.get(s)||null;},addEventListener(n,f){(listeners[n]??=[]).push(f);}},window:{scrollTo(){},addEventListener(n,f){(listeners['window:'+n]??=[]).push(f);}},
 fetch:async(path,options={})=>{
  let body;
  if(path==='/api/state')body=sandbox.fixture;
  else if(path.startsWith('/api/reading-queue')){body=path==='/api/reading-queue'&&options.method!=='POST'?sandbox.fixture.reading_queue:{queue:sandbox.fixture.reading_queue};}
  else if(path.startsWith('/api/items/')){body={...sandbox.fixture.items[0],...(options.body?JSON.parse(options.body):{})};sandbox.fixture.items[0]=body;}
  else throw new Error('Unexpected request '+path);
  return {ok:true,json:async()=>structuredClone(body)};
 }};
 vm.createContext(sandbox);vm.runInContext(queueSource,sandbox);vm.runInContext(frontierSource,sandbox);vm.runInContext(source,sandbox);
 return {sandbox,elements,listeners,run:s=>vm.runInContext(s,sandbox)};
}
test('Evidence-backed important work precedes newer routine items and respects learned and date-filtered states',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.signals=[{...D.signals[0],id:'older',published:'2026-10-20',status:'new',attention:{level:'priority',reason:'Changes the training budget'}},{...D.signals[0],id:'newer',published:'2026-11-07',status:'new',attention:{level:'unassessed'}}];frontierDays=0;frontierTopic='all';frontierUnread=false;query='';`);
 assert.equal(c.run('frontierRows()[0].id'),'older');
 assert.equal(c.run('featuredRows(frontierRows())[0].id'),'older');
 c.run(`D.signals[0].status='seen'`);assert.equal(c.run('frontierRows()[0].id'),'newer');
 c.run(`D.signals[0].status='new';frontierDays=7`);assert.ok(!c.run('frontierRows().some(s=>s.id==="older")'));
});
test('Method comparison uses only published papers and preserves conditions and escaped evidence',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('frontierCompareIDs=D.signals.slice(0,2).map(s=>s.id);openComparison()');
 assert.equal(c.elements.get('frontier-dialog').open,true);
 const html=c.elements.get('frontier-dialog').innerHTML;
 assert.ok(html.includes('作者证据与评测条件'));
 assert.ok(html.includes('不同')||html.includes('可能不同'));
 assert.ok(html.includes('核对全文证据'));
 c.run('D.signals[0].publication_ready=false');
 assert.equal(c.run('compareRows().length'),1);
 const escaped=c.run('comparisonHTML([{...D.signals[1],title:"<img src=x>",delta:"<script>bad</script>"}])');
 assert.ok(!escaped.includes('<img'));assert.ok(escaped.includes('&lt;img'));
});
test('Featured overview compares reach, avoids duplicate projects, and never opens an article automatically',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`const base=D.signals[0];D.signals=[{...base,id:'new-tool',research_group:'tool',published:'2026-11-09',attention:{level:'priority',impact:{rank:1,support_rank:2,area:'evaluation'}}},{...base,id:'older-route',research_group:'route',published:'2026-10-20',attention:{level:'priority',impact:{rank:3,support_rank:2,area:'training'}}},{...base,id:'new-release',research_group:'route',published:'2026-11-09',attention:{level:'notable',impact:{rank:1,support_rank:1,area:'data'}}}];frontierSelected=null;renderMain()`);
 assert.equal(c.run('frontierSelected'),null);
 assert.equal(c.run('frontierRows()[0].id'),'older-route');
 assert.equal(c.run('featuredRows(frontierRows()).filter(r=>r.research_group==="route").length'),1);
 const html=c.elements.get('main').innerHTML;assert.ok(html.includes('先看这些'));assert.ok(!html.includes('class="method-story"'));
 c.run('D.signals[1].status="seen"');assert.ok(!c.run('featuredRows(frontierRows()).some(r=>r.id==="older-route")'));
});
test('Reuse preparation is sourced from the current full reading and never auto-saves an idea',async()=>{
 const c=setup();await new Promise(setImmediate);
 const html=c.run('reuseHTML(D.signals.find(s=>s.reuse?.changes?.length))');
 assert.ok(html.includes('需要改变的步骤'));assert.ok(html.includes('采纳前先核对'));assert.ok(html.includes('核对依据与原文'));
 assert.equal(c.run('D.ideas.length'),0);
});
test('All eight application views render with a populated data contract',async()=>{
 const c=setup();await new Promise(setImmediate);
 for(const p of ['queue','today','fundamentals','library','map','ideas','industry','saved','sources','integrations']){
  c.run('go('+JSON.stringify(p)+')');
  assert.ok(c.elements.get('main').innerHTML.length>100);
  assert.ok(!c.elements.get('main').innerHTML.includes('[object Object]'));
 }
});
test('Reading queue distinguishes waiting, review, history and stale versions without injecting source text',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.reading_queue={notice:'等待代理，不自动调用API',counts:{ready_for_agent:1,needs_review:1,completed:1},tasks:[{id:'a',item_id:'arxiv:1',title:'<script>source</script>',status:'ready_for_agent',status_label:'等待代理精读',message:'等待代理',updated:'2026-11-05',revision:2,attempts:1,document_id:'doc',events:[]},{id:'b',item_id:'arxiv:2',title:'Review',status:'needs_review',status_label:'待你核查',updated:'2026-11-05',revision:3,document_id:'doc2',events:[]},{id:'c',item_id:'arxiv:3',title:'History',status:'completed',status_label:'已核查',updated:'2026-11-05',events:[]}]};go('queue');`);
 let html=c.elements.get('main').innerHTML;
 assert.ok(html.includes('等待代理精读')&&html.includes('我已核查'));
 assert.ok(html.includes('&lt;script&gt;source&lt;/script&gt;'));assert.ok(!html.includes('<script>'));
 assert.ok(!html.includes('<h2>History</h2>'));
 c.run(`readingQueueFilter='review';renderMain();`);html=c.elements.get('main').innerHTML;
 assert.ok(html.includes('<h2>Review</h2>'));assert.ok(!html.includes('&lt;script&gt;source'));
 c.run(`readingQueueFilter='all';D.reading_queue.tasks[0].stale=true;renderMain();`);html=c.elements.get('main').innerHTML;
 assert.ok(html.includes('为当前版本新建任务')&&html.includes('<h2>History</h2>'));
});
test('Queue enqueue navigates to the saved task and leaves subsequent actions enabled',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.reading_queue={counts:{queued:1},tasks:[{id:'task',item_id:'arxiv:1',title:'A queued paper',status:'queued',status_label:'等待准备',updated:'2026-11-05',message:'等待准备',revision:1,attempts:0,events:[]}]};fixture.reading_queue=D.reading_queue;readingQueueFilter='review';`);
 const button={dataset:{readingQueue:'enqueue',item:'arxiv:1'},disabled:false};
 await c.listeners.click[0]({target:{closest:s=>s==='[data-reading-queue]'?button:null}});
 assert.equal(c.run('page'),'queue');assert.equal(c.run('readingQueueBusy'),false);
 assert.equal(button.disabled,false);assert.ok(c.elements.get('main').innerHTML.includes('取消任务'));
 assert.ok(!c.elements.get('main').innerHTML.includes('disabled'));
});
test('Untrusted source text and links are escaped',async()=>{
 const c=setup();await new Promise(setImmediate);
 assert.equal(c.run('url("javascript:alert(1)")'),'#');
 const html=c.run('card({...D.items[0],title_zh:"<script>alert(1)</script>",summary:"<img src=x onerror=alert(1)>"})');
 assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img'));
 assert.ok(html.includes('&lt;script&gt;'));
});
test('Search and topic filtering include personal notes',async()=>{
 const c=setup();await new Promise(setImmediate);
 assert.equal(c.run('query="absent";matches(D.items[0])'),false);
 assert.equal(c.run('D.items[0].notes="control latency";query="control latency";matches(D.items[0])'),true);
 assert.equal(c.run('topic="other";matches(D.items[0])'),false);
});
test('Reading notes persist through the API contract',async()=>{
 const c=setup();await new Promise(setImmediate);
 await c.run('openDetail(D.items[0].id)');
 assert.equal(c.elements.get('detail-dialog').open,true);
 c.elements.get('note-editor').value='An evidence-backed observation.';
 c.elements.get('note-level').value='全文分析';
 await c.run('saveNote()');
 assert.equal(c.sandbox.fixture.items[0].notes,'An evidence-backed observation.');
 assert.equal(c.sandbox.fixture.items[0].note_level,'全文分析');
});
test('A new idea retains its source evidence',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('ideaForm(null,D.items[0])');
 assert.equal(c.elements.get('idea-dialog').open,true);
 assert.ok(c.elements.get('idea-dialog').innerHTML.includes('https://arxiv.org/abs/2406.09246'));
});

test('Integration exports identify snapshot mode and available content',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('go("integrations")');
 assert.ok(c.elements.get('main').innerHTML.includes('在线同步状态单独显示'));
 c.run('integrationScope="all";renderMain()');
 const html=c.elements.get('main').innerHTML;
 for(const target of ['zotero','notion','obsidian'])assert.ok(html.includes('target='+target+'&scope=all'));
});

test('Background guides stay available outside the frontier home',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('go("fundamentals")');
 const html=c.elements.get('main').innerHTML;
 assert.ok(html.includes('视觉语言动作模型（VLA）'));
 assert.ok(html.includes('让机器人把'));
 assert.ok(html.includes('为什么重要'));
 assert.ok(html.indexOf('为什么重要')<html.indexOf('了解原理与进展'));
 for(const removed of ['开始今日精读','今天的 30 分钟','metric-label','Original abstract'])assert.ok(!html.includes(removed));
 c.run('topic="world";renderMain()');assert.ok(c.elements.get('main').innerHTML.includes('世界动作模型（WAM）'));
 assert.ok(!c.elements.get('main').innerHTML.includes('视觉语言动作模型（VLA）'));
});
test('Optional technology detail explains mechanism before paper links and preserves notes',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('openTechnology("vla")');
 const html=c.elements.get('technology-dialog').innerHTML;
 assert.equal(c.elements.get('technology-dialog').open,true);
 assert.ok(html.indexOf('它如何工作')<html.indexOf('继续深入（可选）'));
 assert.ok(html.includes('OpenVLA'));assert.ok(html.includes('2406.09246v3'));
 assert.equal(c.sandbox.fixture.items[0].notes,'');
 const malicious=c.run('technologyCard({...D.technology_briefs[0],title:"<img src=x onerror=alert(1)>"},0)');
 assert.ok(!malicious.includes('<img'));
});

test('Frontier home starts with specific research changes and evidence instead of definitions',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('D.items.push({...D.items[0],id:D.signals[0].id});frontierDays=0;renderMain()');
 const html=c.elements.get('main').innerHTML;
 assert.ok(html.includes(signalSeed.signals[0].title));
 assert.ok(html.includes('先看这些'));assert.ok(!html.includes('class="method-story"'));
 c.run('selectFrontier(D.signals[0].id)');
 const detail=c.elements.get('main').innerHTML;
 assert.ok(detail.includes('起草验证实验'));
 assert.ok(detail.includes('这次新在哪里'));assert.ok(detail.includes(signalSeed.signals[0].evidence[0].value));
 assert.ok(!html.includes('让机器人把“看到的场景”'));
 assert.ok(detail.indexOf('这次新在哪里')<detail.indexOf('原始来源'));
 assert.ok(!html.includes('交给精读'));
 const button={dataset:{frontierAction:'experiment',id:signalSeed.signals[0].id}};
 for(const handler of c.listeners.click)await handler({target:{closest:s=>s==='[data-frontier-action]'?button:null}});
 const draft=c.elements.get('idea-dialog').innerHTML;
 assert.ok(draft.includes(signalSeed.signals[0].hypothesis_suggestion));
 assert.ok(draft.includes(signalSeed.signals[0].experiment_suggestion));
});
test('Readers can switch published papers before reaching the end of an article',async()=>{
 const c=setup();await new Promise(setImmediate);
 const target=signalSeed.signals[1].id;
 c.run('selectFrontier(D.signals[0].id)');
 let html=c.elements.get('main').innerHTML;
 assert.ok(html.indexOf('选择手记')<html.indexOf('class="method-story"'));
 for(const handler of c.listeners.change)await handler({target:{dataset:{frontierFilter:'article'},value:target}});
 assert.equal(c.run('frontierSelected'),target);
 html=c.elements.get('main').innerHTML;
 assert.ok(html.includes(signalSeed.signals[1].evidence[0].value));
 assert.equal(c.run('frontierDays'),0);
 c.run('selectFrontier("unpublished-id")');assert.equal(c.run('frontierSelected'),target);
});
test('A direct paper address survives reload and browser back restores the prior paper',async()=>{
 const first=signalSeed.signals[0].id,second=signalSeed.signals[1].id;
 const c=setup('#today?paper='+encodeURIComponent(second));await new Promise(setImmediate);
 assert.equal(c.run('frontierSelected'),second);
 c.run('selectFrontier('+JSON.stringify(first)+')');
 assert.ok(c.sandbox.location.hash.includes(encodeURIComponent(first)));
 c.sandbox.location.hash='#today?paper='+encodeURIComponent(second);
 for(const handler of c.listeners['window:hashchange'])handler();
 assert.equal(c.run('frontierSelected'),second);
 const html=c.elements.get('main').innerHTML;
 assert.ok(html.includes('return='+encodeURIComponent(c.sandbox.location.hash)));
 c.run('go("ideas");go("today")');assert.equal(c.run('frontierSelected'),second);
});
test('The learned view keeps older methods available and excludes other processing states',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('D.signals[0].status="seen";D.signals[0].published="2000-01-01";frontierMode="seen";frontierDays=7;frontierUnread=true;renderMain()');
 assert.equal(c.run('frontierRows().length'),1);
 assert.equal(c.run('frontierRows()[0].status'),'seen');
 assert.ok(!c.run('frontierTimeControl()').includes('value="7" selected'));
 c.run('D.signals[0].publication_ready=false');assert.equal(c.run('frontierRows().length'),0);
});
test('An existing experiment opens as an edit with its evidence and personal work preserved',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.items.push({...D.items[0],id:D.signals[0].id});D.ideas=[{id:'existing-plan',item_id:D.signals[0].id,title:'My experiment',topic:'vla',status:'实验中',observation:'My observation',evidence:'My checked evidence',hypothesis:'My hypothesis',experiment:'Do not replace my design'}];selectFrontier(D.signals[0].id)`);
 assert.ok(c.elements.get('main').innerHTML.includes('继续完善实验'));
 assert.ok(c.elements.get('main').innerHTML.includes('另起草一个实验'));
 const button={dataset:{frontierAction:'continue',idea:'existing-plan'}};
 for(const handler of c.listeners.click)await handler({target:{closest:s=>s==='[data-frontier-action]'?button:null}});
 const html=c.elements.get('idea-dialog').innerHTML;
 for(const text of ['data-id="existing-plan"','My checked evidence','Do not replace my design'])assert.ok(html.includes(text));
 assert.equal(c.sandbox.fixture.ideas.length,0);
});
test('Reading position is kept within a paper version and stores no personal research text',async()=>{
 const c=setup('#today?paper='+encodeURIComponent(signalSeed.signals[0].id));await new Promise(setImmediate);
 const memory=new Map();c.sandbox.memory=memory;
 c.run('window.sessionStorage={setItem:(k,v)=>memory.set(k,v),getItem:k=>memory.get(k)};window.scrollY=380;document.querySelectorAll=()=>[{open:true},{open:false}];saveFrontierPosition()');
 assert.equal(memory.size,1);
 const value=JSON.parse([...memory.values()][0]);assert.deepEqual(value,{top:380,open:[true,false]});
 const key=c.run('frontierPositionKey()');
 c.run('D.signals[0].version_signature="new-source-version"');
 assert.notEqual(c.run('frontierPositionKey()'),key);
 c.run('resumeFrontierPosition()');
});
test('Unread candidates stay out of the everyday feed and paper list while personal saved work remains accessible',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.items.push({...D.items[0],id:'arxiv:2611.99999',title:'Raw candidate',title_zh:'',curated:false,saved:true});D.signals.push({...D.signals[0],id:'arxiv:2611.99999',publication_ready:false,title:'Raw candidate'});frontierDays=0;frontierMode='all';page='library';`);
 assert.equal(c.run(`frontierRows().some(s=>s.id==='arxiv:2611.99999')`),false);
 assert.equal(c.run(`matches(D.items[1])`),false);
 c.run(`page='saved'`);assert.equal(c.run('matches(D.items[1])'),true);
});
test('Idea sources exclude raw candidates and retain personally saved or already linked sources',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run(`D.items.push({...D.items[0],id:'raw',curated:false},{...D.items[0],id:'personal',curated:false,saved:true});`);
 assert.equal(c.run('ideaSources("").some(r=>r.id==="raw")'),false);
 assert.equal(c.run('ideaSources("").some(r=>r.id==="personal")'),true);
 assert.equal(c.run('ideaSources("raw").some(r=>r.id==="raw")'),true);
});
test('Date and triage filters do not relabel stale content as new',async()=>{
 const c=setup();await new Promise(setImmediate);
 c.run('D.signals[0].published="2000-01-01";frontierDays=7;frontierMode="reviewed";frontierUnread=true');
 assert.equal(c.run('frontierRows().some(s=>s.published==="2000-01-01")'),false);
 c.run('frontierDays=7;D.signals[0].status="later";frontierMode="later"');
 assert.equal(c.run('frontierRows().length'),1);
 c.run('D.signals[0].status="dismissed";frontierMode="reviewed"');
 assert.equal(c.run('frontierRows().some(s=>s.status==="dismissed")'),false);
 c.run('frontierMode="dismissed"');assert.equal(c.run('frontierRows().length'),1);
});
