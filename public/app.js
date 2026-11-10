'use strict';
const ICONS={
 home:'M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z',
 book:'M4 3h6a3 3 0 0 1 3 3v15a4 4 0 0 0-4-2H4Zm16 0h-5a2 2 0 0 0-2 3v15a4 4 0 0 1 4-2h3Z',
 map:'m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16',
 bulb:'M9 18h6m-6 3h6m-7-8a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3Z',
 globe:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z',
 bookmark:'M6 3h12v18l-6-4-6 4Z',
 source:'M7 7V3m10 4V3M5 7h14v5a7 7 0 0 1-14 0Zm7 12v3',
 search:'M20 20 15 15m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z',
 arrow:'M5 12h14m-5-5 5 5-5 5',
 external:'M14 3h7v7m0-7L11 13m-1-8H4v15h15v-6',
 refresh:'M20 7a9 9 0 0 0-15-1L2 9m0-6v6h6m-4 8a9 9 0 0 0 15 1l3-3m0 6v-6h-6',
 check:'m5 12 4 4L19 6',
 close:'m6 6 12 12M6 18 18 6',
 plus:'M12 5v14M5 12h14',
 clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 7v5l3 2',
 download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',
 leaf:'M20 3C8 1 2 8 5 15c5 7 16 3 15-12ZM5 19l10-10',
 edit:'m15 4 5 5M4 16 16 4a2 2 0 0 1 4 4L8 20H4Z',
 trash:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7',
 chart:'M4 20V4m0 16h17M8 15l4-5 4 3 5-8',
 calendar:'M5 5h14v16H5ZM8 3v4m8-4v4M5 10h14',
 layers:'m12 3 10 5-10 5L2 8Zm-10 9 10 5 10-5M2 16l10 5 10-5'
};
const icon=(name,cls='')=>'<svg class="icon '+cls+'" viewBox="0 0 24 24" aria-hidden="true"><path d="'+(ICONS[name]||ICONS.book)+'"/></svg>';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const url=v=>{try{const u=new URL(v);return ['http:','https:'].includes(u.protocol)?esc(u.href):'#';}catch{return '#';}};
const $=s=>document.querySelector(s);
const title=x=>x.title_zh||x.title;
const kindName={paper:'论文',release:'代码发布',model:'模型更新',industry:'研究与产业'};
const pageNames={more:'更多',queue:'后台处理',today:'前沿手记',fundamentals:'方法背景',library:'论文精读',map:'技术地图',ideas:'选题池',industry:'产业观察',saved:'我的收藏',sources:'信息源与设置',integrations:'产品联动'};
let integrationScope='selected';
let ideaSaving=false;
let D=null,page='today',query='',topic='all',kind='all',reading='all',sort='new',limit=30,selectedTopic='vla',detailId=null,noteDirty=false,toastTimer,pollTimer;
const day=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');};
const fmt=v=>v?new Date(v.length===10?v+'T12:00:00':v).toLocaleString('zh-CN',v.length===10?{year:'numeric',month:'2-digit',day:'2-digit'}:{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}):'尚未检查';
const topicName=id=>D?.topics.find(t=>t.id===id)?.short||id;
const sourceName=id=>id==='foundation'?'历史基础阅读':D?.sources.find(s=>s.id===id)?.name||id;
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('visible'),3200);}
async function api(path,method='GET',body){
 const res=await fetch('/api/'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(res.status===401){location.assign('/login');throw new Error('请重新输入访问码');}
 const data=await res.json();if(!res.ok)throw new Error(data.error||'操作未完成');return data;
}
async function load(){
 if(D)saveFrontierPosition();
 D=await api('state');if(!$('#main'))mount();render();updateSync();if(D.sync.running)pollSync();
 if(page==='today'){writeFrontierRoute();resumeFrontierPosition();}
}
function mount(){
 $('#app').innerHTML='<div class="shell"><aside class="sidebar" id="sidebar"></aside><div class="workspace"><header class="topbar"><div class="breadcrumb">我的研究空间 <span>/</span> <span id="crumb">前沿动态</span></div><label class="search-wrap">'+icon('search')+'<input id="global-search" aria-label="搜索文献、方法和笔记" placeholder="搜索新方法、论文、问题…" autocomplete="off"><kbd>⌘ K</kbd></label><div class="top-actions"><a class="btn export-button" href="/pair">配对 iPhone</a><a class="btn export-button" href="/api/export" download>'+icon('download')+'导出知识库</a><button class="btn" data-action="sync" id="sync-button">'+icon('refresh')+'检查更新</button></div></header><main id="main" class="content"></main></div></div>';
 $('#global-search').addEventListener('input',e=>{query=e.target.value.trim().toLowerCase();limit=30;renderMain();});
}
function navButton(id,name,ic,count=''){return '<button data-action="nav" data-page="'+id+'" class="'+(page===id?'active':'')+'">'+icon(ic)+'<span>'+name+'</span>'+(count!==''?'<span class="nav-count">'+count+'</span>':'')+'</button>';}
function renderSidebar(){
 $('#sidebar').innerHTML='<div class="brand"><div class="logo-mark"></div><strong>具身研究台</strong></div><nav class="nav" aria-label="主导航">'+navButton('today','前沿手记','home')+navButton('library','论文','book')+navButton('ideas','选题','bulb')+navButton('more','更多','layers')+'</nav>';

}
function head(eyebrow,name,description,extra=''){
 return '<div class="page-head"><div><h1>'+name+'</h1><p>'+description+'</p></div>'+extra+'</div>';
}
function empty(name,description,action=''){return '<div class="empty">'+icon('leaf')+'<h3>'+name+'</h3><p>'+description+'</p>'+action+'</div>';}
function tag(t){return '<span class="tag">'+esc(topicName(t))+'</span>';}
function card(x){
 const interpretation=(D.signals||[]).find(s=>s.id===x.id&&s.publication_ready);
 return '<article class="paper"><div class="paper-top"><div class="tags"><span class="tag kind">'+kindName[x.kind]+'</span>'+(x.curated?'<span class="tag foundation">基础阅读</span>':'')+x.topics.slice(0,2).map(tag).join('')+'</div><span class="paper-date">'+(x.updated?fmt(x.updated):'日期未提供')+'</span></div><button class="paper-title" data-action="open" data-id="'+esc(x.id)+'">'+esc(interpretation?.title||title(x))+'</button>'+(x.title_zh?'<div class="paper-subtitle">'+esc(x.title)+'</div>':'')+'<p class="paper-summary">'+esc(interpretation?.delta||x.summary||'暂无摘要，请打开原始来源。')+'</p><div class="paper-footer"><span class="paper-source">'+esc(sourceName(x.source_id))+' · '+(interpretation?'模型已精读 · '+(x.reading==='read'?'我已读':x.reading==='reading'?'我在读':'我未读'):(x.reading==='read'?'已读':x.reading==='reading'?'在读':esc(x.note_level)))+'</span><div class="paper-actions"><button class="icon-btn '+(x.saved?'saved':'')+'" data-action="save" data-id="'+esc(x.id)+'" aria-label="'+(x.saved?'取消收藏':'收藏')+'" aria-pressed="'+x.saved+'">'+icon('bookmark')+'</button><button class="text-button" data-action="open" data-id="'+esc(x.id)+'">'+(x.kind==='paper'?'进入精读':'查看详情')+icon('arrow')+'</button></div></div></article>';
}
function matches(x){
 if(page==='library'&&x.curated)return false;
 if(page!=='saved'&&x.kind==='paper'&&!x.curated&&!(D.signals||[]).some(s=>s.id===x.id&&s.publication_ready))return false;
 const corpus=[x.title,x.title_zh,x.summary,x.notes,x.authors,...x.topics.map(topicName)].join(' ').toLowerCase();
 return (!query||query.split(/\s+/).every(t=>corpus.includes(t)))&&(topic==='all'||x.topics.includes(topic))&&(kind==='all'||x.kind===kind)&&(reading==='all'||x.reading===reading);
}
function sorted(items){return [...items].sort((a,b)=>sort==='old'?(a.published||'').localeCompare(b.published||''):(b.updated||'').localeCompare(a.updated||''));}
function chips(){return '<div class="chips">'+[['all','全部方向'],...D.settings.focus.map(t=>[t,topicName(t)])].map(([id,name])=>'<button class="chip '+(topic===id?'active':'')+'" data-action="filter-topic" data-topic="'+id+'">'+esc(name)+'</button>').join('')+'</div>';}
function banner(){
 if(D.sync.running)return '<div class="sync-banner">'+icon('refresh','spin')+'正在检查公开信息源，已有内容可以继续阅读。<button class="text-button" data-action="nav" data-page="sources">查看来源状态</button></div>';
 const errors=D.sources.filter(s=>s.enabled&&s.error).length;
 if(errors)return '<div class="sync-banner error">'+errors+' 个来源最近检查未完成，已有内容已保留。<button class="text-button" data-action="nav" data-page="sources">查看原因 '+icon('arrow')+'</button></div>';
 return '';
}
function technologyMatches(brief){
 const corpus=[brief.title,brief.tagline,brief.why,brief.update,brief.category,...(brief.topics||[]).map(topicName)].join(' ').toLowerCase();
 return (topic==='all'||brief.topics.includes(topic))&&(!query||query.split(/\s+/).every(t=>corpus.includes(t)));
}
function technologyCard(brief,index){
 return '<article class="technology-card"><div class="technology-kicker"><span>'+String(index+1).padStart(2,'0')+' / '+esc(brief.category)+'</span><span class="tag">'+esc(brief.update_label)+'</span></div><h2>'+esc(brief.title)+'</h2><p class="technology-definition">'+esc(brief.tagline)+'</p><div class="technology-value"><h3>为什么重要</h3><p>'+esc(brief.why)+'</p></div><div class="technology-update"><h3>'+esc(brief.update_label)+' <time>'+esc(brief.update_date)+'</time></h3><p>'+esc(brief.update)+'</p></div><button class="btn technology-open" data-action="open-technology" data-id="'+esc(brief.id)+'">了解原理与进展 '+icon('arrow')+'</button></article>';
}
function today(){
 const all=D.technology_briefs||[],rows=all.filter(technologyMatches);
 return '<header class="technology-intro"><div class="eyebrow">具身智能 · 技术与方法</div><h1>重要技术，一眼看懂。</h1><p>先了解方法与价值，感兴趣再深入论文。</p></header>'+
 '<div class="technology-toolbar"><div class="chips">'+[['all','全部方法'],['vla','语言与动作'],['world','预测与规划'],['data','数据与迁移'],['control','控制与执行']].map(([id,name])=>'<button class="chip '+(topic===id?'active':'')+'" data-action="filter-topic" data-topic="'+id+'">'+name+'</button>').join('')+'</div><span>导读核对 '+esc(all.map(x=>x.checked_at).sort().reverse()[0]||'尚未更新')+'</span></div>'+
 '<section class="technology-grid" aria-label="重要技术导读">'+(rows.length?rows.map((b)=>technologyCard(b,all.indexOf(b))).join(''):empty('没有匹配的技术导读','试试 VLA、世界模型、数据或控制。','<button class="btn" data-action="clear-filters">查看全部方法</button>'))+'</section>'+
 '<div class="technology-afterword"><p>按方法理解与科研价值组织，顺序属于编辑导读。新论文和模型发布会进入资料库，经过核对后再形成进展解读。</p><div><button class="text-button" data-action="nav" data-page="library">按需查找论文 '+icon('arrow')+'</button><button class="text-button" data-action="nav" data-page="sources">信息源与更新状态</button></div></div>';
}
function openTechnology(id){
 const b=(D.technology_briefs||[]).find(x=>x.id===id);if(!b)return;
 const dialog=$('#technology-dialog');
 dialog.innerHTML='<div class="dialog-head"><strong>技术与方法导读</strong><button class="icon-btn" data-action="close-technology" aria-label="关闭技术导读">'+icon('close')+'</button></div><article class="technology-detail"><div class="eyebrow">'+esc(b.category)+'</div><h2>'+esc(b.title)+'</h2><p class="technology-definition">'+esc(b.tagline)+'</p><section><h3>为什么重要</h3><p>'+esc(b.why)+'</p></section><section><h3>它如何工作</h3><ol class="mechanism-flow">'+b.mechanism.map(step=>'<li><strong>'+esc(step.title)+'</strong><p>'+esc(step.text)+'</p></li>').join('')+'</ol></section><section><h3>放到具体任务中</h3><p>'+esc(b.example)+'</p></section><section class="technology-update"><h3>'+esc(b.update_label)+' <time>'+esc(b.update_date)+'</time></h3><p>'+esc(b.update)+'</p></section><section><h3>理解它时，还要知道</h3><p>'+esc(b.boundary)+'</p></section><section class="technology-question"><h3>值得进一步研究的问题</h3><p>'+esc(b.question)+'</p></section><section class="technology-reading"><div class="section-head"><h3>继续深入（可选）</h3><span>论文 · 全文证据</span></div>'+b.sources.map(source=>{const found=D.items.some(x=>x.id===source.item_id);return '<div class="technology-source"><span class="tag">'+esc(source.role)+'</span><h4>'+esc(source.title)+'</h4><p>'+esc(source.published)+' · '+esc(source.evidence_level)+'</p><div class="detail-links">'+(found?'<button class="btn" data-action="technology-paper" data-id="'+esc(source.item_id)+'">打开论文与笔记</button><a class="btn" target="_blank" rel="noopener" href="/reading.html?id='+encodeURIComponent(source.item_id)+'">精读报告与证据</a>':'')+'<a class="btn" target="_blank" rel="noopener noreferrer" href="'+url(source.url)+'">核对原始来源 '+icon('external')+'</a></div></div>';}).join('')+'</section>'+
 ((b.related_ids||[]).length?'<details class="technology-candidates"><summary>更多可能相关的新资料 · '+b.related_ids.length+' 篇</summary><p>按关键词关联，尚未纳入上面的解读。</p>'+b.related_ids.map(id=>D.items.find(x=>x.id===id)).filter(Boolean).map(item=>'<button class="text-button" data-action="technology-paper" data-id="'+esc(item.id)+'">'+esc(title(item))+'</button>').join('')+'</details>':'')+
 '<p class="technology-review">核对日期 '+esc(b.checked_at)+'。导读依据已链接的原始摘要整理；价值判断与例子用于帮助理解，论文结论仍需结合全文与实验核查。</p></article>';
 if(!dialog.open)dialog.showModal();
 dialog.scrollTop=0;
}

function library(){
 let rows=D.items.filter(x=>page==='saved'?x.saved:page==='industry'?x.kind!=='paper':x.kind==='paper').filter(matches);
 rows=sorted(rows);
 const meta=page==='saved'?['YOUR KNOWLEDGE SHELF','我的收藏','把值得再次阅读的工作，留在手边。']:page==='industry'?['FROM RESEARCH TO REALITY','产业观察','关注真实任务、模型可用性与工具进展，回到一手材料核查。']:['READ. QUESTION. UNDERSTAND.','论文精读','读懂问题与机制，也看清证据和边界。'];
 return head(...meta)+banner()+'<div class="toolbar">'+chips()+'<div class="toolbar-right"><select class="select" id="reading-filter" aria-label="阅读状态">'+[['all','全部阅读状态'],['unread','未读'],['reading','在读'],['read','已读']].map(([v,l])=>'<option value="'+v+'" '+(reading===v?'selected':'')+'>'+l+'</option>').join('')+'</select><select class="select" id="sort-filter" aria-label="排序"><option value="new" '+(sort==='new'?'selected':'')+'>最近更新优先</option><option value="old" '+(sort==='old'?'selected':'')+'>按发表时间正序</option></select>'+(page!=='library'?'<select class="select" id="kind-filter" aria-label="内容类型">'+[['all','全部类型'],...Object.entries(kindName)].map(([v,l])=>'<option value="'+v+'" '+(kind===v?'selected':'')+'>'+l+'</option>').join('')+'</select>':'')+'</div></div><p class="library-count">共 '+rows.length+' 条'+(query?' · 搜索「'+esc(query)+'」':'')+'</p><div class="list">'+(rows.length?rows.slice(0,limit).map(card).join(''):empty(page==='saved'?'还没有收藏':'没有找到匹配内容',page==='saved'?'点击论文卡片上的书签，把它放入自己的研究书架。':'试着清除搜索或调整筛选条件。','<button class="btn" data-action="clear-filters">重置筛选</button>'))+'</div>'+(rows.length>limit?'<button class="btn load-more" data-action="more">继续显示更多</button>':'');
}
function mapPage(){
 const t=D.topics.find(x=>x.id===selectedTopic)||D.topics[0];
 const rows=sorted(D.items.filter(x=>x.topics.includes(t.id)&&matches(x))).sort((a,b)=>(a.published||'').localeCompare(b.published||''));
 return head('CONNECT THE RESEARCH','技术地图','从研究问题出发，理解方法之间的关系。')+'<div class="two-columns">'+D.topics.map((x,i)=>'<button class="topic-card '+(t.id===x.id?'active':'')+'" data-action="select-topic" data-topic="'+x.id+'"><div class="topic-top"><span class="topic-number">0'+(i+1)+'</span><span class="tag">'+D.items.filter(r=>r.topics.includes(x.id)&&matches(r)).length+' 条关联内容</span></div><h3>'+x.name+'</h3><p>'+x.description+'</p><div class="topic-related">相关方向 '+x.related.map(r=>'<span class="tag">'+topicName(r)+'</span>').join('')+'</div></button>').join('')+'</div><section class="topic-view" id="topic-view"><div class="section-head"><h2>'+t.name+' <small>RESEARCH THREAD</small></h2></div><div class="question-box"><h3>值得带着阅读的问题</h3>'+t.questions.map(q=>'<p>· '+q+'</p>').join('')+'</div><p class="wide-note">按发布时间排列关联工作。主题之间的联系是阅读导航，尚未核查的论文引用或方法继承关系不会自动生成。</p><div class="timeline">'+(rows.length?rows.slice(0,30).map(x=>'<div class="timeline-entry">'+card(x)+'</div>').join(''):empty('这个方向还在积累','下次采集的新内容会按关键词关联到这里，也可以切换其他方向。'))+'</div></section>';
}
function ideaCard(x){
 return '<article class="idea-card"><span class="tag">'+topicName(x.topic)+'</span><h4>'+esc(x.title)+'</h4><p>'+esc(x.hypothesis||x.observation||'先记录观察，再补充证据和验证方法。')+'</p><div class="paper-actions"><button class="text-button" data-action="edit-idea" data-id="'+x.id+'">'+icon('edit')+'编辑选题</button></div><select class="select idea-status" data-id="'+x.id+'" aria-label="选题状态">'+['待调研','待验证','实验中','已归档'].map(s=>'<option '+(s===x.status?'selected':'')+'>'+s+'</option>').join('')+'</select></article>';
}
function ideasPage(){
 const rows=D.ideas.filter(x=>!query||[x.title,x.observation,x.evidence,x.hypothesis,x.experiment].join(' ').toLowerCase().includes(query));
 return head('TURN QUESTIONS INTO RESEARCH','选题池','让每个灵感都有证据、可验证的假设和下一步。','<button class="btn primary" data-action="new-idea">'+icon('plus')+'记录一个问题</button>')+'<div class="question-box"><p>问题观察 → 支持证据与相关工作 → 待验证假设 → 最小实验</p></div>'+(!D.ideas.length?'<p class="wide-note">你的第一个选题可以从精读页发起。先留下一个问题，不需要马上确定它是否成立。</p>':'')+'<div class="idea-grid">'+['待调研','待验证','实验中'].map(s=>'<section class="idea-column"><h3>'+s+'<span>'+rows.filter(x=>x.status===s).length+'</span></h3>'+rows.filter(x=>x.status===s).map(ideaCard).join('')+(rows.every(x=>x.status!==s)?'<div class="idea-zero">给值得探索的问题<br>留一个位置</div>':'')+'</section>').join('')+'</div><details class="archive-row"><summary>已归档 · '+rows.filter(x=>x.status==='已归档').length+'</summary><div class="idea-grid">'+rows.filter(x=>x.status==='已归档').map(ideaCard).join('')+'</div></details>';
}
function sourcesPage(){
 const settings=D.settings;
 return head('CURATE YOUR SIGNAL','信息源与设置','优先一手材料，保留检查记录与原始链接。')+
 '<section class="settings-panel"><h3>让推荐贴近你的研究</h3><p>选择关注方向，今日精选会优先考虑这些主题。仍会保留其他方向的重要进展。</p><div class="chips">'+D.topics.map(t=>'<button class="chip '+(settings.focus.includes(t.id)?'active':'')+'" data-action="focus" data-topic="'+t.id+'" aria-pressed="'+settings.focus.includes(t.id)+'">'+t.name+'</button>').join('')+'</div><div class="settings-row"><div>服务运行期间自动检查<small>电脑睡眠或服务退出期间不会更新；手动检查始终可用。</small></div><button class="switch '+(settings.auto_sync?'on':'')+'" data-action="auto-sync" aria-label="自动检查更新" role="switch" aria-checked="'+settings.auto_sync+'"><span></span></button></div><div class="settings-row"><div>更新检查间隔<small>按来源更新节奏检查，同一来源一分钟内不重复请求。</small></div><select class="select" id="interval-setting" aria-label="检查间隔">'+[[60,'每小时'],[180,'每 3 小时'],[360,'每 6 小时'],[1440,'每天']].map(([v,l])=>'<option value="'+v+'" '+(v===settings.interval_minutes?'selected':'')+'>'+l+'</option>').join('')+'</select></div><div class="settings-row"><div>知识库备份<small>导出文献、笔记、选题和设置，个人笔记另以 Markdown 保存。</small></div><a class="btn small" href="/api/export" download>'+icon('download')+'导出 ZIP</a></div></section>'+banner()+
 '<div class="section-head"><h2>公开信息源 <small>PRIMARY SOURCES</small></h2><button class="text-button" data-action="sync">'+icon('refresh')+'立即检查</button></div><div class="sources-grid">'+D.sources.map(s=>'<section class="source-card"><div class="source-card-top"><h3>'+s.name+'</h3>'+(s.collector!=='manual'?'<button class="switch '+(s.enabled?'on':'')+'" data-action="source-toggle" data-id="'+s.id+'" aria-label="'+esc(s.name)+' 自动采集" role="switch" aria-checked="'+s.enabled+'"><span></span></button>':'<span class="tag">手动入口</span>')+'</div><p>'+s.description+'</p><div class="tags">'+(s.collector==='manual'?'<span class="tag">未接入自动采集</span>':!s.enabled?'<span class="tag">已暂停</span>':s.error?'<span class="tag amber">最近检查未完成</span>':s.last_success?'<span class="tag kind">'+icon('check')+'已连接</span>':'<span class="tag">等待首次检查</span>')+'</div><div class="source-stats"><span>最近检查 '+fmt(s.last_attempt)+'</span><span>最近成功 '+fmt(s.last_success)+'</span>'+(s.last_success?'<span>返回 '+s.count+' 条</span>':'')+'</div>'+(s.error?'<div class="source-error">'+esc(s.error)+'</div>':'')+'<a class="text-button" href="'+url(s.url)+'" target="_blank" rel="noopener noreferrer" style="margin-top:11px">打开原始来源 '+icon('external')+'</a></section>').join('')+'</div><p class="wide-note" style="margin-top:20px">自动采集保留原始摘要或发布说明，按关键词关联主题。全文分析与代码核查由你在精读工作台明确记录；候选问题始终需要进一步验证。</p>';
}
function syncPanel(){
 const state=D.integrations||{},n=state.notion||{},z=state.zotero||{};
 return '<section class="settings-panel"><h3>在线同步与批注回流</h3><div class="settings-row"><div><strong>Zotero 只读批注</strong><small>已导入 '+(z.imported||0)+' 条。先检查匹配与页码，确认后导入；保留个人精读笔记。</small></div><button class="btn" data-action="zotero-preview">检查并预览批注</button></div><div class="settings-row"><div><strong>Notion 精选资料</strong><small>已同步 '+(n.synced||0)+' 条 · 待同步 '+(n.pending||0)+' 条。'+(n.runtime_configured?'网页同步已配置，人工修改会先检查冲突。':'网页持续同步未配置；当前可通过对话执行同步。')+'</small></div><div class="paper-actions">'+(n.target?'<a class="btn" href="'+url(n.target)+'" target="_blank" rel="noopener noreferrer">打开 Notion 资料库</a>':'')+'<button class="btn primary" data-action="notion-sync" '+(n.runtime_configured?'':'disabled')+'>同步精选与选题</button></div></div>'+(state.runs?.length?'<details style="margin-top:14px"><summary>最近同步记录</summary>'+state.runs.map(r=>'<p class="history-row">'+fmt(r.at)+' · '+esc(r.provider)+' · '+esc(r.status)+' · '+esc(r.detail)+'</p>').join('')+'</details>':'')+'</section>';
}
function previewAnnotations(result){
 const rows=result.annotations||[];
 $('#sync-dialog').innerHTML='<div class="dialog-head"><strong>Zotero 批注预览 · 匹配 '+result.matched+' 篇文献</strong><button class="icon-btn" data-action="close-sync" aria-label="关闭">'+icon('close')+'</button></div><div class="idea-form"><p class="wide-note">批注独立保存，保留页码和 Zotero 回跳链接，不写入或替换你的精读笔记。只匹配研究台中 arXiv 标识一致的论文。</p>'+rows.map(r=>'<label class="source-card" style="display:block;margin-bottom:12px"><input type="checkbox" class="annotation-choice" value="'+esc(r.id)+'" checked> '+esc(D.items.find(x=>x.id===r.item_id)?.title||r.item_id)+' · 第 '+esc(r.page||'?')+' 页<p style="white-space:pre-wrap;margin-top:10px">'+esc(r.quote)+'</p><p style="white-space:pre-wrap">'+esc(r.comment)+'</p></label>').join('')+(rows.length?'<button class="btn primary" data-action="zotero-import">导入选中的批注</button>':'<p>没有找到与研究台现有论文匹配的批注。请确认 Zotero 文献保留了 arXiv 链接或标识，并已在 PDF 中做批注。</p>')+'</div>';
 $('#sync-dialog').showModal();
}
function integrationsPage(){
 const selected=D.items.filter(x=>x.saved||x.notes||x.reading!=='unread');
 const items=integrationScope==='all'?D.items:selected;
 const papers=items.filter(x=>x.kind==='paper').length;
 const download=(target,text,available)=>available?'<a class="btn primary" href="/api/integrations/export?target='+target+'&scope='+integrationScope+'" download>'+icon('download')+text+'</a>':'<button class="btn" disabled>'+text+' · 暂无内容</button>';
 return head('A CONNECTED RESEARCH WORKFLOW','产品联动','发现、阅读、思考与写作，让工具各自做好一件事。')+syncPanel()+
 '<div class="integration-flow">'+[['01','研究台','发现与筛选'],['02','Zotero','论文、批注与引用'],['03','Notion / Obsidian','选题与长期知识'],['04','回到研究','验证假设、记录结果']].map(([n,t,d])=>'<div><span class="eyebrow">'+n+'</span><h3>'+t+'</h3><p>'+d+'</p></div>').join('')+'</div>'+
 '<section class="settings-panel"><div class="settings-row"><div>选择要带走的内容<small>“我的研究内容”包含收藏、已写笔记和开始阅读的条目；Notion / Obsidian 包另附全部选题。</small></div><select class="select" id="integration-scope" aria-label="导出范围"><option value="selected" '+(integrationScope==='selected'?'selected':'')+'>我的研究内容</option><option value="all" '+(integrationScope==='all'?'selected':'')+'>全部内容</option></select></div><p style="margin:12px 0 0">当前范围：'+items.length+' 条内容，其中 '+papers+' 篇论文；另有 '+D.ideas.length+' 个选题。文件导出为一次性快照；在线同步状态单独显示。</p></section>'+
 '<div class="sources-grid"><section class="source-card"><div class="source-card-top"><h3>Zotero · 建议优先使用</h3><span class="tag kind">RIS 导出可用</span></div><p>把选中的论文放入文献库，继续阅读 PDF、做批注和管理引用。保留原始标题、可用作者、arXiv 标识、日期与来源。</p>'+download('zotero','导出论文 RIS',papers>0)+'<p class="integration-help">下载后，在 Zotero 选择“文件 → 导入 → 文件”。PDF 链接会保留，附件下载与作者元数据仍需核查。个人笔记不放入 RIS。</p><a class="text-button" href="https://www.zotero.org/support/kb/importing_standardized_formats" target="_blank" rel="noopener noreferrer">官方导入说明 '+icon('external')+'</a></section>'+
 '<section class="source-card"><div class="source-card-top"><h3>Notion · 研究项目与选题</h3><span class="tag kind">导入包可用</span></div><p>将精选笔记和选题整理为云端页面与数据库，方便手机查看和后续协作。导出含文献表、选题表与 Markdown 正文。</p>'+download('notion','导出 Notion 导入包',items.length+D.ideas.length>0)+'<p class="integration-help">在 Notion 电脑端或网页端导入 CSV / Markdown。表格和正文不会自动关联；重复导入会新增记录。在线同步的目标库与配置状态见上方。</p><a class="text-button" href="https://www.notion.com/help/import-data-into-notion" target="_blank" rel="noopener noreferrer">官方导入说明 '+icon('external')+'</a></section>'+
 '<section class="source-card"><div class="source-card-top"><h3>Obsidian · 个人方法知识库</h3><span class="tag kind">笔记库导出可用</span></div><p>保留本地 Markdown，通过文献、方向和选题之间的链接积累知识。适合长期写作和自己的方法体系。</p>'+download('obsidian','导出 Obsidian 笔记库',items.length+D.ideas.length>0)+'<p class="integration-help">解压到新文件夹，再在 Obsidian 中打开为仓库，从 Home.md 开始。内容包含个人笔记；在 Obsidian 中的修改暂不会回写研究台。</p><a class="text-button" href="https://help.obsidian.md/Files+and+folders/Manage+vaults" target="_blank" rel="noopener noreferrer">官方仓库说明 '+icon('external')+'</a></section>'+
 '<section class="source-card"><div class="source-card-top"><h3>Readwise Reader · 随身阅读</h3><span class="tag amber">候选 · 未接入</span></div><p>适合手机阅读技术文章、访谈与长文，并将高亮沉淀到笔记工具。等移动阅读成为高频需求，再评估接入。</p><p>拟议路径：研究台精选 → Reader 阅读与高亮 → Notion / Obsidian。Reader 与研究台目前没有自动同步。</p><a class="btn" href="https://docs.readwise.io/reader/docs/faqs/exporting" target="_blank" rel="noopener noreferrer">查看官方导出能力 '+icon('external')+'</a></section>'+
 '<section class="source-card"><div class="source-card-top"><h3>Semantic Scholar · 相关工作</h3><span class="tag amber">候选 · 未接入</span></div><p>下一步可补充引用、参考文献和相关论文推荐，帮助判断一项工作的前因后果。需要核查匹配准确度与接口可用性。</p><p>这比单纯按关键词聚类更接近“方法脉络”；引用关系也不自动等于方法继承关系。</p><a class="btn" href="https://webflow.semanticscholar.org/product/api/tutorial" target="_blank" rel="noopener noreferrer">查看官方接口能力 '+icon('external')+'</a></section>'+
 '<section class="source-card"><h3>下一步的联动原则</h3><p>优先只同步收藏、精读与选题，避免把全部信息流复制到多个工具。每篇论文保留稳定标识和原始来源。</p><p>自动同步阶段需要指定目标库，记录同步时间与失败原因；外部笔记的人工修改应保留，发生冲突时不静默覆盖。</p><span class="tag">当前已实现：文件交换</span> <span class="tag">待配置：账号同步</span></section></div>';
}

function renderMain(){
 const more=()=>head('', '更多','')+'<div class="tool-menu">'+[['saved','收藏'],['map','技术地图'],['fundamentals','方法背景'],['industry','产业观察'],['integrations','产品联动'],['sources','信息源与设置'],['queue','后台处理']].map(([id,name])=>navButton(id,name,'arrow')).join('')+'<a href="/pair">配对 iPhone</a><a href="/api/export" download>导出知识库</a></div>';
 $('#main').innerHTML=page==='more'?more():page==='queue'?readingQueuePage():page==='today'?frontierHome():page==='fundamentals'?today():page==='map'?mapPage():page==='ideas'?ideasPage():page==='sources'?sourcesPage():page==='integrations'?integrationsPage():library();

}
function render(){renderSidebar();$('#crumb').textContent=pageNames[page];renderMain();}
function go(next){
 saveFrontierPosition();
 page=pageNames[next]?next:'today';topic='all';kind='all';reading='all';limit=30;
 render();const hash=page==='today'?frontierHash():'#'+page;
 if(location.hash!==hash)history.pushState(null,'',hash);
 window.scrollTo({top:0,behavior:'auto'});if(page==='today')resumeFrontierPosition();
}
function updateSync(){
 const button=$('#sync-button');if(!button)return;
 button.disabled=Boolean(D.sync.running);button.innerHTML=icon('refresh',D.sync.running?'spin':'')+(D.sync.running?'正在检查':'检查更新');
}
async function pollSync(){
 if(pollTimer)return;
 pollTimer=setTimeout(async()=>{
  pollTimer=null;
  try{
   const s=await api('sync');D.sync=s;updateSync();
   if(s.running){pollSync();return;}
   D=await api('state');render();updateSync();
   const r=s.result;if(r){const failed=r.sources.filter(x=>x.status==='error').length;toast('检查完成：新增 '+r.new+' 条，更新 '+r.updated+' 条'+(failed?'；'+failed+' 个来源待重试':''));}
  }catch(e){toast('连接中断，请确认本地服务仍在运行');}
 },1800);
}

async function openDetail(id){
 if($('#detail-dialog').open&&noteDirty&&!confirm('笔记尚未保存，仍要切换文献吗？'))return;
 const x=await api('items/'+encodeURIComponent(id));detailId=id;noteDirty=false;
 const interpreted=(D.signals||[]).some(s=>s.id===x.id&&s.publication_ready);
 const a=x.analysis,related=D.items.filter(r=>r.id!==x.id&&r.kind==='paper'&&(D.signals||[]).some(s=>s.id===r.id&&s.publication_ready)&&r.topics.some(t=>x.topics.includes(t))).slice(0,3);
 const sections=[['problem','研究问题'],['method','方法机制'],['evidence','证据与核查'],['limitations','适用边界'],['question','候选问题 · 待验证']];
 $('#detail-dialog').innerHTML='<div class="dialog-head"><strong>'+icon('book')+' '+(x.kind==='paper'?'论文精读工作台':'原始动态与研究笔记')+'</strong><button class="icon-btn" data-action="close-detail" aria-label="关闭精读">'+icon('close')+'</button></div><div class="detail-body"><article><div class="tags"><span class="tag kind">'+kindName[x.kind]+'</span>'+(x.curated?'<span class="tag foundation">历史基础阅读</span>':'')+x.topics.map(tag).join('')+'</div><h2 class="detail-title">'+esc(title(x))+'</h2>'+(x.title_zh?'<p class="detail-english">'+esc(x.title)+'</p>':'')+'<div class="detail-meta">'+esc(x.authors||sourceName(x.source_id))+'<br>发表 '+fmt(x.published)+' · 来源更新 '+fmt(x.updated)+'</div><div class="detail-links"><a class="btn small" target="_blank" rel="noopener noreferrer" href="'+url(x.url)+'">'+icon('external')+'原始来源</a>'+(x.pdf_url?'<a class="btn small" target="_blank" rel="noopener noreferrer" href="'+url(x.pdf_url)+'">'+icon('book')+'论文 PDF</a>':'')+(x.kind==='paper'?'<a class="btn small" target="_blank" rel="noopener" href="/reading.html?id='+encodeURIComponent(x.id)+'">'+icon('search')+'精读报告与证据</a><a class="btn small" href="/api/integrations/export?target=zotero&item_id='+encodeURIComponent(x.id)+'" download>'+icon('download')+'导出 Zotero RIS</a>':'')+(x.code_url?'<a class="btn small" target="_blank" rel="noopener noreferrer" href="'+url(x.code_url)+'">'+icon('source')+'作者代码</a>':'')+'<button class="btn small" data-action="save" data-id="'+esc(x.id)+'" id="detail-save">'+icon('bookmark')+(x.saved?'已收藏':'收藏')+'</button></div><div class="evidence-note">'+(interpreted?'已完成模型精读，可打开“精读报告与证据”查看完整方法、实验与局限。下方保留原始摘要供核对。':x.curated?'基础导读根据已核查的元数据与摘要整理，不代表已阅读全文或复现。下面的问题是阅读启发，仍需文献检索与实验验证。':'此处保留来源摘要或发布说明。主题由关键词关联，尚未自动分析全文；请结合原文记录自己的判断。')+'</div><section class="reading-section source-summary"><h3>'+(x.curated?'基础导读':'原始摘要 / 发布说明')+'</h3><p>'+esc(x.summary)+'</p></section>'+sections.filter(([k])=>a[k]).map(([k,l])=>'<section class="reading-section"><h3>'+l+'</h3><p>'+esc(a[k])+'</p></section>').join('')+(x.zotero_annotations?.length?'<section class="reading-section"><h3>Zotero 阅读证据</h3>'+x.zotero_annotations.map(r=>'<div class="evidence-note"><a href="'+esc(r.source)+'">第 '+esc(r.page||'?')+' 页 · 回到 Zotero</a><p style="white-space:pre-wrap">'+esc(r.quote)+'</p><p style="white-space:pre-wrap">'+esc(r.comment)+'</p></div>').join('')+'</section>':'')+(!Object.keys(a).length?'<section class="reading-section"><h3>带着这些问题读原文</h3><ul class="checklist"><li>具体解决什么问题？与最接近的方法相比改变了什么？</li><li>方法的输入、动作表示、训练目标与执行流程是什么？</li><li>数据、算力与评测条件是否可比？仿真还是真机？</li><li>是否报告重复试验、失败案例与分布外结果？</li><li>什么假设值得用一个最小实验验证？</li></ul></section>':'')+'<button class="btn soft" data-action="idea-from-paper" data-id="'+esc(x.id)+'">'+icon('bulb')+'从这项工作记录一个问题</button>'+(related.length?'<section class="reading-section"><h3>同方向延伸阅读</h3>'+related.map(r=>'<button class="text-button" data-action="open" data-id="'+esc(r.id)+'">'+esc(title(r))+icon('arrow')+'</button>').join('')+'</section>':'')+'<section class="reading-section"><h3>来源变更记录</h3>'+x.events.map(e=>'<div class="history-row">'+fmt(e.at)+' · '+esc(e.description)+'</div>').join('')+'</section></article><aside class="notes-pane"><h3>我的精读笔记</h3><p class="subtitle">写下自己的理解与疑问。点击保存后，笔记会同步存入本地 Markdown。</p><div class="form-columns"><div class="field"><label for="detail-reading">阅读状态</label><select id="detail-reading">'+[['unread','未读'],['reading','在读'],['read','已读']].map(([v,l])=>'<option value="'+v+'" '+(v===x.reading?'selected':'')+'>'+l+'</option>').join('')+'</select></div><div class="field"><label for="note-level">已完成的分析程度</label><select id="note-level">'+['摘要筛选','全文分析','代码核查'].map(l=>'<option '+(l===x.note_level?'selected':'')+'>'+l+'</option>').join('')+'</select></div></div><div class="field"><label for="note-editor">笔记 · 支持 Markdown 文本</label><textarea class="notes" id="note-editor" placeholder="研究问题：&#10;&#10;与已有方法的区别：&#10;&#10;关键实验与证据位置：&#10;&#10;局限与待验证假设：">'+esc(x.notes)+'</textarea></div><div class="paper-actions"><button class="btn primary" data-action="save-note" id="save-note-button">'+icon('check')+'保存笔记</button><button class="btn" data-action="note-template">插入模板</button></div><div class="note-status" id="note-status">'+(x.note_updated?'最近保存 '+fmt(x.note_updated):'尚未保存个人笔记')+'</div><a class="text-button" href="/api/items/'+encodeURIComponent(x.id)+'?format=markdown" download>'+icon('download')+'导出这篇精读笔记</a></aside></div>';
 const dialog=$('#detail-dialog');if(!dialog.open)dialog.showModal();
}
function closeDetail(){
 if(noteDirty&&!confirm('笔记尚未保存，仍要关闭吗？'))return false;
 $('#detail-dialog').close();detailId=null;noteDirty=false;return true;
}
async function saveNote(){
 const button=$('#save-note-button');button.disabled=true;
 try{
  const x=await api('items/'+encodeURIComponent(detailId),'PATCH',{notes:$('#note-editor').value,note_level:$('#note-level').value});
  const i=D.items.findIndex(r=>r.id===x.id);D.items[i]=x;noteDirty=false;
  $('#note-status').textContent='已保存到本地 · '+fmt(x.note_updated);toast('笔记已保存，Markdown 已同步');renderMain();
 }finally{button.disabled=false;}
}
function ideaSources(selectedID){
 const published=new Set((D.signals||[]).filter(s=>s.publication_ready).map(s=>s.id));
 return D.items.filter(r=>r.id===selectedID||r.kind==='paper'&&(r.curated||r.saved||r.notes||published.has(r.id)));
}
function ideaForm(idea=null,source=null,prefill={}){
 const x=idea||{title:source?.analysis.question||'',topic:source?.topics[0]||selectedTopic||'vla',status:'待调研',observation:'',evidence:source?'起点文献：'+source.title+'\n'+source.url+'\n相关工作与研究空白仍待核查。':'',hypothesis:'',experiment:'',item_id:source?.id||'',...prefill};
 $('#idea-dialog').innerHTML='<div class="dialog-head"><strong>'+icon('bulb')+' '+(idea?'编辑研究问题':'记录一个研究问题')+'</strong><div class="dialog-head-actions"><button class="btn primary" type="submit" form="idea-form" id="idea-top-submit">保存</button><button class="icon-btn" data-action="close-idea" aria-label="关闭选题编辑">'+icon('close')+'</button></div></div><form id="idea-form" class="idea-form" data-id="'+(idea?.id||'')+'"><div class="field"><label for="idea-title">问题标题 *</label><input id="idea-title" name="title" maxlength="240" required value="'+esc(x.title)+'" placeholder="你想弄清楚什么？"></div><div class="form-columns"><div class="field"><label for="idea-topic">研究方向</label><select name="topic" id="idea-topic">'+D.topics.map(t=>'<option value="'+t.id+'" '+(x.topic===t.id?'selected':'')+'>'+t.name+'</option>').join('')+'</select></div><div class="field"><label for="idea-status">当前状态</label><select name="status" id="idea-status">'+['待调研','待验证','实验中','已归档'].map(s=>'<option '+(s===x.status?'selected':'')+'>'+s+'</option>').join('')+'</select></div></div><div class="field"><label for="idea-paper">关联起点文献</label><select name="item_id" id="idea-paper"><option value="">暂不关联</option>'+ideaSources(x.item_id).map(r=>'<option value="'+esc(r.id)+'" '+(x.item_id===r.id?'selected':'')+'>'+esc(title(r))+'</option>').join('')+'</select></div><div class="form-columns">'+[['observation','问题观察','从哪个现象、失败或矛盾中发现问题？'],['evidence','证据与相关工作','原文链接、章节、对照方法，以及仍待检索的相关工作。'],['hypothesis','待验证假设','用可以被证伪的句子描述；不预先断言研究空白。'],['experiment','最小验证实验','对照组、数据预算、指标，以及什么结果会推翻假设？']].map(([k,l,p])=>'<div class="field"><label for="idea-'+k+'">'+l+'</label><textarea name="'+k+'" id="idea-'+k+'" maxlength="20000" placeholder="'+p+'">'+esc(x[k])+'</textarea></div>').join('')+'</div><div class="form-error" id="idea-error" role="alert"></div><div class="form-actions"><div>'+(idea?'<button type="button" class="btn danger" data-action="delete-idea" data-id="'+idea.id+'">'+icon('trash')+'删除</button>':'<span class="hint">先留下问题，再逐步补齐证据。</span>')+'</div><div class="paper-actions"><button type="button" class="btn" data-action="close-idea">取消</button><button type="submit" class="btn primary" id="idea-submit">'+icon('check')+'保存选题</button></div></div></form>';
 $('#idea-dialog').showModal();
}
async function submitIdea(form){
 if(ideaSaving)return;ideaSaving=true;
 const button=$('#idea-submit'),topButton=$('#idea-top-submit');button.disabled=true;if(topButton)topButton.disabled=true;
 try{
  const body=Object.fromEntries(new FormData(form).entries());body.item_id=body.item_id||null;
  const id=form.dataset.id;await api(id?'ideas/'+id:'ideas',id?'PATCH':'POST',body);
  $('#idea-dialog').close();await load();toast('选题已保存，继续积累证据。');
 }catch(e){$('#idea-error').textContent=e.message;}finally{ideaSaving=false;button.disabled=false;if(topButton)topButton.disabled=false;}
}
document.addEventListener('click',async e=>{
 const button=e.target.closest('[data-action]');if(!button)return;
 const action=button.dataset.action,id=button.dataset.id;
 try{
  if(action==='nav')go(button.dataset.page);
  else if(action==='open-technology')openTechnology(id);
  else if(action==='close-technology')$('#technology-dialog').close();
  else if(action==='technology-paper'){
   const opened=await openDetail(id);
   if($('#detail-dialog').open)$('#technology-dialog').close();
  }
  else if(action==='open')await openDetail(id);
  else if(action==='save'){
   const old=D.items.find(x=>x.id===id);if(!old)return;
   const x=await api('items/'+encodeURIComponent(id),'PATCH',{saved:!old.saved});
   D.items[D.items.findIndex(r=>r.id===id)]=x;render();
   if(detailId===id&&$('#detail-save'))$('#detail-save').innerHTML=icon('bookmark')+(x.saved?'已收藏':'收藏');
   toast(x.saved?'已加入我的收藏':'已取消收藏');
  }else if(action==='sync'){
   D.sync=await api('sync','POST');renderMain();updateSync();pollSync();toast('正在检查公开信息源');
  }else if(action==='start'){
   const pick=D.recommended.map(r=>D.items.find(x=>x.id===r)).find(x=>x?.kind==='paper'&&x.reading!=='read')||D.items.find(x=>x.kind==='paper');
   if(!pick)return toast('暂无论文，请先检查更新');
   const x=await api('items/'+encodeURIComponent(pick.id),'PATCH',{reading:'reading'});
   D.items[D.items.findIndex(r=>r.id===x.id)]=x;await openDetail(x.id);renderMain();
  }else if(action==='filter-topic'){topic=button.dataset.topic;limit=30;renderMain();}
  else if(action==='clear-filters'){query='';topic='all';reading='all';kind='all';$('#global-search').value='';renderMain();}
  else if(action==='more'){limit+=30;renderMain();}
  else if(action==='map-topic'){selectedTopic=button.dataset.topic;go('map');$('#topic-view')?.scrollIntoView({behavior:'smooth',block:'start'});}
  else if(action==='select-topic'){selectedTopic=button.dataset.topic;renderMain();$('#topic-view')?.scrollIntoView({behavior:'smooth',block:'start'});}
  else if(action==='step'){
   const step=Number(button.dataset.step);await api('session','POST',{day:day(),step});D.sessions=D.sessions.filter(s=>s.day!==day());D.sessions.push({day:day(),step});renderMain();
  }else if(action==='focus'){
   const focus=new Set(D.settings.focus),tid=button.dataset.topic;focus.has(tid)?focus.delete(tid):focus.add(tid);
   D.settings=await api('settings','PATCH',{focus:[...focus]});const latest=await api('state');D.recommended=latest.recommended;renderMain();
  }else if(action==='auto-sync'){D.settings=await api('settings','PATCH',{auto_sync:!D.settings.auto_sync});renderMain();}
  else if(action==='source-toggle'){const s=D.sources.find(x=>x.id===id);await api('sources/'+id,'PATCH',{enabled:!s.enabled});await load();}
  else if(action==='close-detail')closeDetail();
  else if(action==='save-note')await saveNote();
  else if(action==='close-sync')$('#sync-dialog').close();
  else if(action==='zotero-preview'){
   button.disabled=true;
   try{previewAnnotations(await api('integrations/zotero/preview','POST'));}finally{button.disabled=false;}
  }else if(action==='zotero-import'){
   const ids=[...document.querySelectorAll('.annotation-choice:checked')].map(x=>x.value);
   button.disabled=true;
   try{const r=await api('integrations/zotero/import','POST',{ids});$('#sync-dialog').close();await load();toast('已导入 '+r.imported+' 条批注');}finally{button.disabled=false;}
  }else if(action==='notion-sync'){
   button.disabled=true;
   try{const r=await api('integrations/notion/sync','POST');await load();toast('新增 '+r.new+' 条，更新 '+r.updated+' 条，冲突 '+r.conflicts.length+' 条');}finally{button.disabled=false;}
  }
  else if(action==='note-template'){
   const field=$('#note-editor');
   if(field.value.trim())return toast('已有笔记，保留当前内容。可在下方继续补充。');
   field.value='## 研究问题\n\n## 与已有方法的区别\n\n## 核心机制\n\n## 实验证据（原文章节 / 表格）\n\n## 适用边界与失败案例\n\n## 待验证的假设\n\n## 下一步最小实验\n';noteDirty=true;$('#note-status').textContent='有未保存的修改';field.focus();
  }else if(action==='new-idea')ideaForm();
  else if(action==='edit-idea')ideaForm(D.ideas.find(x=>x.id===id));
  else if(action==='idea-from-paper')ideaForm(null,D.items.find(x=>x.id===id));
  else if(action==='close-idea')$('#idea-dialog').close();
  else if(action==='delete-idea'){
   if(!confirm('删除这个选题及其本地 Markdown 文件？'))return;
   await api('ideas/'+id,'DELETE');$('#idea-dialog').close();await load();toast('选题已删除');
  }
 }catch(error){toast(error.message||'操作未完成，请重试');}
});
document.addEventListener('change',async e=>{
 try{
  if(e.target.id==='integration-scope'){integrationScope=e.target.value;renderMain();}
  else if(e.target.id==='reading-filter'){reading=e.target.value;renderMain();}
  else if(e.target.id==='sort-filter'){sort=e.target.value;renderMain();}
  else if(e.target.id==='kind-filter'){kind=e.target.value;renderMain();}
  else if(e.target.id==='interval-setting'){D.settings=await api('settings','PATCH',{interval_minutes:Number(e.target.value)});toast('检查间隔已更新');}
  else if(e.target.id==='detail-reading'){
   const x=await api('items/'+encodeURIComponent(detailId),'PATCH',{reading:e.target.value});D.items[D.items.findIndex(r=>r.id===x.id)]=x;render();toast('阅读状态已保存');
  }else if(e.target.id==='note-level'){noteDirty=true;$('#note-status').textContent='有未保存的修改';}
  else if(e.target.classList.contains('idea-status')){
   await api('ideas/'+e.target.dataset.id,'PATCH',{status:e.target.value});await load();toast('选题状态已更新');
  }
 }catch(error){toast(error.message);}
});
document.addEventListener('input',e=>{if(e.target.id==='note-editor'){noteDirty=true;$('#note-status').textContent='有未保存的修改';}});
document.addEventListener('submit',e=>{if(e.target.id==='idea-form'){e.preventDefault();submitIdea(e.target);}});
$('#detail-dialog').addEventListener('cancel',e=>{e.preventDefault();closeDetail();});
document.addEventListener('keydown',e=>{
 if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#global-search')?.focus();}
 if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='s'&&$('#detail-dialog').open){e.preventDefault();saveNote().catch(e=>toast(e.message));}
});
window.addEventListener('beforeunload',e=>{if(noteDirty){e.preventDefault();e.returnValue='';}});
window.addEventListener('pagehide',saveFrontierPosition);
window.addEventListener('hashchange',()=>{
 saveFrontierPosition();
 const next=location.hash.slice(1).split('?')[0]||'today';
 if(pageNames[next]){
  page=next;topic='all';kind='all';reading='all';
  if(page==='today')restoreFrontierRoute(location.hash);
  render();if(page==='today')resumeFrontierPosition();
 }
});
page=pageNames[location.hash.slice(1).split('?')[0]]?location.hash.slice(1).split('?')[0]:'today';
if(page==='today')restoreFrontierRoute(location.hash);
load().catch(error=>{
 $('#app').innerHTML='<div class="boot"><div class="logo-mark"></div><h2>还没有连接到研究台</h2><p>'+esc(error.message)+' · 请确认本地服务正在运行。</p><a class="btn" href="/">重新连接</a></div>';
});
