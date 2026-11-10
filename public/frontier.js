'use strict';
let frontierMode='reviewed',frontierDays=0,frontierTopic='all',frontierUnread=false,frontierSelected=null,frontierSaving=false;
let frontierCompareIDs=[];
try{const ids=JSON.parse(window.sessionStorage.getItem('method-comparison')||'[]');if(Array.isArray(ids))frontierCompareIDs=ids.filter(id=>typeof id==='string').slice(0,3);}catch{}
function saveComparison(){try{window.sessionStorage.setItem('method-comparison',JSON.stringify(frontierCompareIDs));}catch{}}
function compareRows(){return frontierCompareIDs.map(id=>(D.signals||[]).find(s=>s.id===id&&s.publication_ready)).filter(Boolean);}
function comparisonHTML(rows){
 const fields=[['具体改动',s=>s.delta],['原先做法',s=>s.before],['方法步骤',s=>s.mechanism.map(m=>m.text).join('\n')],['数据、硬件与接口',s=>(s.reuse?.requirements||[]).map(r=>r.label+' · '+(r.status==='known'?'原文条件':'待核对')+'：'+r.text).join('\n')||'尚未结构化核对'],['作者证据与评测条件',s=>s.evidence[0].value+' · '+s.evidence[0].context],['适用边界',s=>s.caveat]];
 return '<div class="compare-sheet"><button class="btn" data-frontier-action="compare-close">关闭</button><h2>方法对照</h2><p>比较技术选择，不做性能排名。任务、数据量、指标和算力可能不同；相近主题不等于直接可比。</p><div class="compare-scroll" tabindex="0" role="region" aria-label="方法对照表"><table><thead><tr><th scope="col">对照项</th>'+rows.map(s=>'<th scope="col">'+esc(s.title)+'<br><small>'+esc(s.published)+'</small><br><a href="/reading.html?id='+encodeURIComponent(s.id)+'&return='+encodeURIComponent(frontierHash())+'">核对全文证据</a></th>').join('')+'</tr></thead><tbody>'+fields.map(([label,value])=>'<tr><th scope="row">'+label+'</th>'+rows.map(s=>'<td data-paper="'+esc(s.title)+'">'+esc(value(s))+(label==='作者证据与评测条件'&&s.evidence.length>1?'<details><summary>其他证据与条件</summary>'+s.evidence.slice(1).map(e=>'<p>'+esc(e.value+' · '+e.context)+'</p>').join('')+'</details>':'')+'</td>').join('')+'</tr>').join('')+'<tr><th scope="row">复用前检查</th>'+rows.map(s=>'<td data-paper="'+esc(s.title)+'"><details><summary>查看采纳条件与证据缺口</summary>'+ (s.reuse?.checks||[]).map(c=>'<p><b>'+esc(c.title)+'</b><br>'+esc(c.text)+'</p>').join('')+'</details><a href="/reading.html?id='+encodeURIComponent(s.id)+'&return='+encodeURIComponent(frontierHash())+'">核对全文证据</a></td>').join('')+'</tr></tbody></table></div></div>';
}
function openComparison(){
 const rows=compareRows();if(rows.length<2){toast('先选择两篇已精读论文');return;}
 const dialog=$('#frontier-dialog');dialog.innerHTML=comparisonHTML(rows);dialog.showModal();
}
function reuseHTML(s){
 const reuse=s.reuse;if(!reuse)return '';
 const findings=(rows)=>(rows||[]).map(r=>'<details class="story-method"><summary>'+esc(r.title)+'</summary><p>'+esc(r.text)+'</p><a href="/reading.html?id='+encodeURIComponent(s.id)+'&evidence='+encodeURIComponent((r.evidence_ids||[])[0]||'')+'&return='+encodeURIComponent(frontierHash())+'">核对依据与原文 →</a></details>').join('');
 const conditions=(reuse.requirements||[]).map(r=>'<li><strong>'+esc(r.label)+' · '+(r.status==='known'?'原文条件':'待核对')+'</strong><p>'+esc(r.text)+'</p>'+(r.evidence_ids?.length?'<a href="/reading.html?id='+encodeURIComponent(s.id)+'&evidence='+encodeURIComponent(r.evidence_ids[0])+'&return='+encodeURIComponent(frontierHash())+'">定位这项条件 →</a>':'')+'</li>').join('');
 return '<details class="story-method reuse-guide"><summary>怎样用于我的研究</summary><p>'+esc(reuse.notice)+'</p><h3>开始前需要什么</h3><ul class="reuse-conditions">'+conditions+'</ul><h3>需要改变的步骤</h3>'+findings(reuse.changes)+'<h3>最小验证实验建议</h3><p>'+esc(reuse.experiment||'当前尚无有依据的实验草案，先核对方法与边界。')+'</p><h3>采纳前先核对</h3>'+findings(reuse.checks)+(reuse.resources?.length?'<h3>原文提及的资源</h3>'+reuse.resources.map(r=>'<p><a href="'+url(r.url)+'" target="_blank" rel="noopener noreferrer">'+esc(r.url)+' ↗</a></p>').join(''):'')+'<p>资源尚未运行验证；没有链接时，代码与许可仍需回原文核查。</p>'+(s.code_url?'<a href="'+url(s.code_url)+'" target="_blank" rel="noopener noreferrer">作者代码 ↗</a>':'')+'</details>';
}
const frontierLabels={new:'未处理',seen:'已了解',later:'稍后读',dismissed:'已略过'};
function frontierHash(){
 const p=new URLSearchParams();
 if(frontierSelected)p.set('paper',frontierSelected);
 if(frontierMode!=='reviewed')p.set('view',frontierMode);
 if(frontierDays)p.set('days',frontierDays);
 if(frontierTopic!=='all')p.set('topic',frontierTopic);
 if(frontierUnread)p.set('unread','1');
 return '#today'+(p.size?'?'+p.toString():'');
}
function restoreFrontierRoute(hash){
 const p=new URLSearchParams(hash.split('?')[1]||'');
 frontierMode=['reviewed','all','seen','later','dismissed'].includes(p.get('view'))?p.get('view'):'reviewed';
 frontierDays=[7,30].includes(Number(p.get('days')))?Number(p.get('days')):0;
 frontierTopic=p.get('topic')||'all';frontierUnread=p.get('unread')==='1';
 frontierSelected=p.get('paper')||null;
}
function writeFrontierRoute(push=false){
 const hash=frontierHash();
 if(location.hash!==hash)history[push?'pushState':'replaceState'](null,'',hash);
}
function frontierPositionKey(){
 const s=(D?.signals||[]).find(s=>s.id===frontierSelected);
 return s?'frontier-position:'+s.id+':'+s.version_signature:null;
}
function saveFrontierPosition(){
 if(page!=='today')return;
 const key=frontierPositionKey();if(!key)return;
 try{window.sessionStorage.setItem(key,JSON.stringify({top:window.scrollY||0,open:[...document.querySelectorAll('.method-story details')].map(d=>d.open)}));}catch{}
}
function resumeFrontierPosition(){
 const key=frontierPositionKey();if(!key)return;
 try{
  const value=JSON.parse(window.sessionStorage.getItem(key));if(!value)return;
  [...document.querySelectorAll('.method-story details')].forEach((d,i)=>d.open=!!value.open?.[i]);
  const top=Number(value.top);
  if(Number.isFinite(top)&&top>=0)setTimeout(()=>{if(page==='today'&&frontierPositionKey()===key)window.scrollTo({top,behavior:'auto'});},0);
 }catch{}
}
function frontierCutoff(days){const d=new Date();d.setHours(0,0,0,0);d.setDate(d.getDate()-(days-1));return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function attentionRank(s){return ['seen','dismissed'].includes(s.status)?0:({priority:2,notable:1}[s.attention?.level]||0);}
function attentionOrder(s){const level=attentionRank(s),p=s.attention?.impact||{};return [Number(level>0),level?(p.rank??level):0,level?(p.support_rank||0):0,level];}
function compareAttention(a,b){const x=attentionOrder(a),y=attentionOrder(b);for(let i=0;i<x.length;i++)if(x[i]!==y[i])return y[i]-x[i];return b.published.localeCompare(a.published)||b.id.localeCompare(a.id);}
function hasHigherAttention(a,b){const x=attentionOrder(a),y=attentionOrder(b);for(let i=0;i<x.length;i++)if(x[i]!==y[i])return x[i]>y[i];return false;}
function featuredRows(rows){const areas=new Set(),groups=new Set(),chosen=[];for(const s of rows){if(!s.publication_ready||s.status!=='new'||!attentionRank(s))continue;const area=s.attention?.impact?.area,group=s.research_group||s.id;if(groups.has(group)||(area&&areas.has(area)))continue;chosen.push(s);areas.add(area);groups.add(group);if(chosen.length===3)break;}return chosen;}
function attentionHTML(s){return attentionRank(s)?'<aside class="attention-note"><strong>'+ (attentionRank(s)===2?'优先看':'值得跟进')+'</strong><span>'+esc(s.attention.reason)+'</span></aside>':'';}
function frontierRows(){
 let rows=(D.signals||[]).filter(s=>{
  if(!s.publication_ready)return false;
  if(frontierDays && !['seen','later','dismissed'].includes(frontierMode) && (!s.published||s.published<frontierCutoff(frontierDays)))return false;
  if(frontierMode==='seen'&&s.status!=='seen')return false;
  if(frontierMode==='later'&&s.status!=='later')return false;
  if(frontierMode==='dismissed'&&s.status!=='dismissed')return false;
  if(['reviewed','all'].includes(frontierMode)&&s.status==='dismissed')return false;
  if(frontierMode==='reviewed'&&!s.reviewed)return false;
  if(frontierUnread&&['reviewed','all'].includes(frontierMode)&&s.status!=='new')return false;
  if(frontierTopic==='focus'&&!s.topics.some(t=>D.settings.focus.includes(t)))return false;
  if(!['all','focus'].includes(frontierTopic)&&!s.topics.includes(frontierTopic))return false;
  const corpus=[s.title,s.paper_title,s.delta,s.before,s.after,s.abstract,...s.topics.map(topicName)].join(' ').toLowerCase();
  return !query||query.split(/\s+/).every(q=>corpus.includes(q));
 });
 rows.sort((a,b)=>['reviewed','all'].includes(frontierMode)?compareAttention(a,b):b.published.localeCompare(a.published));
 return rows;
}
function frontierActions(s,compact=false){
 const buttons=[['seen','已了解','check'],['later',s.status==='later'?'移出稍后读':'稍后读','bookmark'],...(!compact?[['dismissed','略过','close']]:[])];
 return '<div class="signal-actions '+(compact?'compact':'')+'">'+(compact&&s.status==='seen'?'<span class="learned-state">'+icon('check')+'已了解</span>':'')+buttons.filter(([state])=>state!==s.status||state==='later').map(([state,label,ic])=>'<button data-frontier-action="triage" data-id="'+esc(s.id)+'" data-status="'+(state==='later'&&s.status==='later'?'new':state)+'" '+(frontierSaving?'disabled':'')+'>'+icon(ic)+label+'</button>').join('')+(!compact&&s.status!=='new'?'<button data-frontier-action="triage" data-id="'+esc(s.id)+'" data-status="new" '+(frontierSaving?'disabled':'')+'>恢复未处理</button>':'')+'</div>';
}
function frontierRow(s){
 return '<button class="edition-row" data-frontier-action="select" data-id="'+esc(s.id)+'"><time>'+esc(s.published)+(attentionRank(s)===2?' · 优先看':attentionRank(s)===1?' · 值得跟进':'')+'</time><strong>'+esc(s.title)+'</strong><span aria-hidden="true">→</span></button>';
}
function featuredCard(s){
 const area={training:'训练路线',architecture:'策略架构',data:'示范与数据',control:'控制方法',planning:'规划方法',evaluation:'实验与评测',perception:'感知方法',deployment:'部署选择'}[s.attention?.impact?.area]||'值得关注';
 return '<button class="featured-card" data-frontier-action="select" data-id="'+esc(s.id)+'"><small>'+area+' · '+esc(s.published)+'</small><strong>'+esc(s.title)+'</strong><p>'+esc(s.attention?.summary||s.delta)+'</p><span>查看改动与证据 →</span></button>';
}
function frontierPicker(rows){
 if(rows.length<2)return '';
 const index=rows.findIndex(s=>s.id===frontierSelected),next=rows[index+1];
 return '<nav class="edition-picker" aria-label="切换前沿手记"><label><span>选择手记</span><select data-frontier-filter="article" aria-label="选择手记">'+rows.map(s=>'<option value="'+esc(s.id)+'" '+(s.id===frontierSelected?'selected':'')+'>'+esc(s.published+' · '+s.title)+'</option>').join('')+'</select></label><div><span aria-live="polite">'+(index+1)+' / '+rows.length+'</span><button data-frontier-action="select" data-id="'+esc(next?.id||'')+'" '+(next?'':'disabled')+'>下一则 →</button></div></nav>';
}
function selectFrontier(id){
 if(!frontierRows().some(s=>s.id===id))return;
 saveFrontierPosition();frontierSelected=id;renderMain();writeFrontierRoute(true);
 const story=document.getElementById('frontier-detail');
 story.setAttribute('tabindex','-1');story.focus();story.scrollIntoView({block:'start'});
}
function frontierDetail(s){
 const id=esc(s.id),paper=D.items.find(x=>x.id===s.id),report='/reading.html?id='+encodeURIComponent(s.id)+'&return='+encodeURIComponent(frontierHash());
 const ideas=(D.ideas||[]).filter(i=>i.item_id===s.id).sort((a,b)=>(b.updated||b.created||'').localeCompare(a.updated||a.created||''));
 const draft=ideas[0];
 const practice=paper?(draft?'<div class="linked-experiment"><span>'+esc(draft.status)+' · 已记录的研究问题</span><h4>'+esc(draft.title)+'</h4><button class="btn primary" data-frontier-action="continue" data-idea="'+esc(draft.id)+'">继续完善实验</button>'+ideas.slice(1).map(i=>'<button class="text-button" data-frontier-action="continue" data-idea="'+esc(i.id)+'">'+esc(i.title)+' · '+esc(i.status)+'</button>').join('')+'</div>':'')+'<button class="btn '+(draft?'':'primary')+'" data-frontier-action="experiment" data-id="'+id+'">'+(draft?'另起草一个实验':'起草验证实验')+'</button>':'';
 const findings=s.evidence.map(e=>'<div class="result"><strong>'+esc(e.value)+'</strong><div><b>'+esc(e.label)+'</b><p>'+esc(e.context)+'</p></div></div>');
 return '<article class="method-story" id="frontier-detail"><header>'+attentionHTML(s)+'<div class="dateline"><time>'+esc(s.published)+'</time> · '+esc(s.change_type)+' · 作者实验</div><h2 class="signal-title">'+esc(s.title)+'</h2><p class="story-lead">'+esc(s.delta)+'</p></header>'+
 '<div class="story-tools">'+frontierActions(s,true)+'</div><section class="story-evidence"><h3>论文里的证据</h3>'+findings[0]+(findings.length>1?'<details class="story-method"><summary>其他实验结果（'+(findings.length-1)+'）</summary>'+findings.slice(1).join('')+'</details>':'')+'<p class="boundary">'+esc(s.caveat)+'</p><a href="'+esc(report)+'">核对精读报告与原文 →</a></section>'+
 '<details class="story-method"><summary>这次新在哪里</summary><p><b>原先的做法</b>　'+esc(s.before)+'</p><p><b>这篇的改动</b>　'+esc(s.after)+'</p><ol>'+s.mechanism.map(m=>'<li>'+esc(m.text)+'</li>').join('')+'</ol></details>'+
 reuseHTML(s)+'<section class="practice"><h3>值得试的问题</h3><p class="research-question">'+esc(s.question)+'</p><p>'+esc(s.relevance)+'</p>'+practice+'</section><button class="btn" data-frontier-action="compare-toggle" data-id="'+id+'" aria-pressed="'+frontierCompareIDs.includes(s.id)+'">'+(frontierCompareIDs.includes(s.id)?'移出方法对照':'加入方法对照')+'</button>'+
 '<details class="story-method"><summary>论文与阅读记录</summary><p>'+esc(s.paper_title||s.title)+'</p><a href="'+url(s.source_url)+'" target="_blank" rel="noopener noreferrer">原始来源 ↗</a> '+(s.code_url?'<a href="'+url(s.code_url)+'" target="_blank" rel="noopener noreferrer">作者代码 ↗</a>':'')+(paper?'<button class="btn" data-frontier-action="paper" data-id="'+id+'">我的论文笔记</button>':'')+frontierActions(s)+'</details></article>';
}
function frontierTimeControl(){
 const queue=['seen','later','dismissed'].includes(frontierMode),value=queue?0:frontierDays;
 return '<select aria-label="进展时间范围" data-frontier-filter="days" '+(queue?'disabled':'')+'>'+[[7,'近 7 天'],[30,'近 30 天'],[0,'全部时间']].map(([n,label])=>'<option value="'+n+'" '+(value===n?'selected':'')+'>'+label+'</option>').join('')+'</select>';
}
function frontierHome(){
 frontierCompareIDs=compareRows().map(s=>s.id);
 const rows=frontierRows(),all=D.signals||[],latest=D.frontier_meta?.latest_date||'';
 if(!rows.some(s=>s.id===frontierSelected))frontierSelected=null;
 const selected=rows.find(s=>s.id===frontierSelected);
 const urgent=rows[0],priorityCue=urgent&&selected&&urgent.id!==selected.id&&attentionRank(urgent)>0&&hasHigherAttention(urgent,selected)?'<button class="edition-row priority-cue" data-frontier-action="select" data-id="'+esc(urgent.id)+'"><span>还有重要进展</span><strong>'+esc(urgent.title)+'</strong><span aria-hidden="true">→</span></button>':'';
 const modes=[['reviewed','重点'],['all','全部'],['later','稍后读'],['seen','已了解'],['dismissed','已略过']];
 const filter='<details class="edition-filter"><summary>筛选</summary>'+frontierTimeControl()+'<select aria-label="研究方向" data-frontier-filter="topic">'+[['all','全部方向'],['focus','我的关注'],...D.topics.map(t=>[t.id,t.short])].map(([v,n])=>'<option value="'+esc(v)+'" '+(v===frontierTopic?'selected':'')+'>'+esc(n)+'</option>').join('')+'</select>'+(!['seen','later','dismissed'].includes(frontierMode)?'<label><input type="checkbox" data-frontier-filter="unread" '+(frontierUnread?'checked':'')+'> 隐藏已了解</label>':'')+'</details>';
 const highlights=featuredRows(rows),highlightIDs=new Set(highlights.map(s=>s.id));
 const overview=frontierMode==='reviewed'?'<section class="featured-section" aria-label="先看这些"><div class="edition-section-head"><h2>先看这些</h2><span>读懂关键变化，再决定是否深入</span></div>'+(highlights.length?'<div class="featured-list">'+highlights.map(featuredCard).join('')+'</div>':'<p class="featured-empty">当前范围没有新的重点。可以回看已了解，或浏览全部更新。</p>')+'</section><section class="edition-index"><div class="edition-section-head"><h2>继续浏览</h2><button data-frontier-action="mode" data-mode="all">全部 '+rows.length+' 项 →</button></div>'+rows.filter(r=>!highlightIDs.has(r.id)).slice(0,4).map(frontierRow).join('')+'</section>':rows.map(frontierRow).join('');
 return '<div class="edition"><header class="edition-header"><h1>前沿手记</h1><div class="edition-controls">'+modes.map(([v,n])=>'<button aria-pressed="'+(frontierMode===v)+'" data-frontier-action="mode" data-mode="'+v+'">'+n+'</button>').join('')+filter+'</div></header>'+ (frontierCompareIDs.length?'<div class="compare-tray" role="status"><span>已选 '+frontierCompareIDs.length+' / 3 篇</span><button class="btn" data-frontier-action="compare" '+(frontierCompareIDs.length<2?'disabled':'')+'>对照方法</button><button class="text-button" data-frontier-action="compare-clear">清空</button></div>':'')+
 (selected?'<button class="text-button back-to-overview" data-frontier-action="overview">← 返回浏览</button>'+priorityCue+frontierPicker(rows)+frontierDetail(selected)+(rows.length>1?'<section class="edition-index"><h2>继续阅读</h2>'+rows.filter(r=>r.id!==selected.id).map(frontierRow).join('')+'</section>':''):rows.length?overview:'<div class="frontier-empty"><h2>'+ (frontierMode==='seen'?'了解过的方法会留在这里':frontierMode==='later'?'还没有稍后读的论文':frontierMode==='dismissed'?'还没有略过的论文':'当前范围没有已精读的进展')+'</h2><p>'+(frontierMode==='seen'?'阅读手记后标记“已了解”，下次可从这里回看证据和实验。':'可以调整方向和时间，或浏览全部已解读内容。')+'</p><button class="btn" data-frontier-action="reset">浏览全部已解读论文</button></div>')+'</div>';

}
async function triageFrontier(id,status){
 if(frontierSaving)return;
 const s=(D.signals||[]).find(s=>s.id===id);if(!s)return;
 frontierSaving=true;
 try{
  const result=await api('mobile/commit','POST',{id:'frontier-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2),kind:'frontier',target:id,base:{status:s.status,version_signature:s.version_signature},changes:{status}});
  Object.assign(s,result.record);
  toast(status==='later'?'已加入稍后读':status==='seen'?'已标为已了解':status==='dismissed'?'已略过，可在“已略过”中恢复':'已恢复未处理');
 }catch(e){toast(e.message);try{await load();}catch{}}
 finally{frontierSaving=false;renderMain();writeFrontierRoute();}
}
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-frontier-action]');if(!button)return;
 const action=button.dataset.frontierAction;
 if(action==='overview'){saveFrontierPosition();frontierSelected=null;renderMain();writeFrontierRoute(true);window.scrollTo({top:0,behavior:'auto'});return;}
 if(action==='compare-toggle'){
  const id=button.dataset.id;
  if(frontierCompareIDs.includes(id))frontierCompareIDs=frontierCompareIDs.filter(x=>x!==id);
  else if(frontierCompareIDs.length>=3){toast('一次最多对照三篇');return;}
  else if((D.signals||[]).some(s=>s.id===id&&s.publication_ready))frontierCompareIDs.push(id);
  saveComparison();saveFrontierPosition();renderMain();resumeFrontierPosition();return;
 }
 if(action==='compare'){openComparison();return;}
 if(action==='compare-clear'){frontierCompareIDs=[];saveComparison();renderMain();return;}
 if(action==='compare-close'){$('#frontier-dialog').close();return;}
 if(action==='mode'){saveFrontierPosition();frontierMode=button.dataset.mode;frontierSelected=null;renderMain();writeFrontierRoute(true);window.scrollTo({top:0,behavior:'auto'});}
 else if(action==='select')selectFrontier(button.dataset.id);
 else if(action==='experiment'){
  const item=D.items.find(x=>x.id===button.dataset.id),signal=D.signals.find(x=>x.id===button.dataset.id);
  if(item&&signal)ideaForm(null,item,{title:signal.question,observation:signal.delta,evidence:signal.evidence.map(e=>e.label+' '+e.value+'。'+e.context).join('\n')+'\n'+signal.source_url,hypothesis:signal.hypothesis_suggestion||'',experiment:signal.experiment_suggestion||''});
 }
 else if(action==='continue'){const idea=(D.ideas||[]).find(i=>i.id===button.dataset.idea);if(idea)ideaForm(idea);}
 else if(action==='reset'){frontierMode='all';frontierDays=0;frontierTopic='all';frontierUnread=false;renderMain();writeFrontierRoute(true);}
 else if(action==='triage')await triageFrontier(button.dataset.id,button.dataset.status);
 else if(action==='paper'){try{await openDetail(button.dataset.id);$('#frontier-dialog').close();}catch(error){toast(error.message);}}
});
document.addEventListener('change',event=>{
 const filter=event.target.dataset?.frontierFilter;if(!filter)return;
 if(filter==='article'){selectFrontier(event.target.value);return;}
 if(filter==='days')frontierDays=Number(event.target.value);
 if(filter==='topic')frontierTopic=event.target.value;
 if(filter==='unread')frontierUnread=event.target.checked;
 frontierSelected=null;renderMain();writeFrontierRoute(true);
});
