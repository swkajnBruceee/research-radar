'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safe=v=>{try{const u=new URL(v);return u.protocol==='https:'?esc(u.href):'#';}catch{return '#';}};
const id=new URLSearchParams(location.search).get('id')||'';
const evidenceTarget=new URLSearchParams(location.search).get('evidence')||'';
let evidenceFocused=false;
const returnRoute=new URLSearchParams(location.search).get('return')||'#today?paper='+encodeURIComponent(id);
const backLink=$('#back-to-research');
if(backLink)backLink.href='/'+(/^#today(?:\?|$)/.test(returnRoute)&&returnRoute.length<2000?returnRoute:'#today');
let state={},working=false,polling,queueTask=null;
async function loadQueue(){
 const response=await fetch('/api/reading-queue');if(!response.ok)return;
 const queue=await response.json();queueTask=(queue.tasks||[]).find(t=>t.item_id===id&&!t.stale);
 $('#queue-entry').textContent=queueTask?'精读任务 · '+queueTask.status_label:'查看后台处理';
}
async function api(method='GET',body){
 const response=await fetch('/api/reading/'+encodeURIComponent(id),{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
 if(response.status===401){location.assign('/login');throw Error('请先登录研究台');}
 const result=await response.json();if(!response.ok)throw Error(result.error||'操作未完成');return result;
}
function render(){
 const doc=state.document,analysis=state.analysis;
 $('#prepare').hidden=!!doc;
 $('#analyze').hidden=!!analysis||!state.model_configured;
 $('#queue-entry').hidden=!!analysis;
 $('#model-state').hidden=!!analysis;
 $('#prepare').disabled=working||state.status?.status==='running';$('#analyze').disabled=working||state.status?.status==='running'||!state.model_configured;
 $('#status').textContent=analysis?.mode==='agent_pilot'&&state.status?.status==='ready'?'当前版本全文与代理精读已保存；研究结论仍需独立核查。':state.status?.message||'尚未准备全文';
 $('#model-state').textContent=state.model_configured?'模型解读附原文引文，结论仍需核查。':'尚未配置精读模型；原文检索和引用可直接使用。';
 $('#analysis').hidden=!analysis;
 if(analysis){
  const labels={problem:'研究问题',method:'方法机制',evidence:'实验证据',limitation:'适用边界'};
  const pilot=analysis.mode==='agent_pilot';
  const claim=(r,index,hypothesis=false)=>'<details class="finding"'+(!hypothesis&&index===0?' open':'')+'><summary>'+esc(r.title||labels[r.kind]||'待验证假设')+'</summary><p>'+esc(r.text)+'</p><blockquote>'+esc(r.quote)+'</blockquote>'+(r.evidence_ids||[]).map(key=>'<a class="text-button" href="#e-'+esc(key)+'">查看原文证据 '+esc(key)+'</a>').join(' ')+'</details>';
  $('#analysis').innerHTML='<h2>精读解读与原文依据</h2><p>'+esc(analysis.overview)+'</p><details class="coverage"><summary>阅读范围 · '+esc(analysis.coverage?.read)+' / '+esc(analysis.coverage?.total)+' 个文字片段</summary><p>'+esc(analysis.model)+' · '+(pilot?'已读提取文字':'输入覆盖')+' '+esc(analysis.coverage?.read)+' / '+esc(analysis.coverage?.total)+' 个片段</p><p>'+esc(analysis.notice)+'</p></details>'+(analysis.findings||[]).map((r,i)=>claim(r,i)).join('')+((analysis.hypotheses||[]).length?'<h3>值得验证的问题</h3><p>以下为代理提出的实验建议，尚未验证。</p>':'')+(analysis.hypotheses||[]).map((r,i)=>claim(r,i,true)).join('');
 }
 renderPassages();
 if(!evidenceFocused&&evidenceTarget&&(state.document?.passages||[]).some(p=>p.id===evidenceTarget)){
  const row=document.getElementById('e-'+evidenceTarget);
  if(row){row.open=true;row.scrollIntoView?.({block:'center'});evidenceFocused=true;}
 }
}
function renderPassages(){
 const search=$('#search').value.trim().toLowerCase(),all=state.document?.passages||[],rows=all.filter(p=>(p.section+' '+p.text).toLowerCase().includes(search));
 $('#count').textContent=rows.length+' / '+all.length+' 个片段'+(state.document?' · '+state.document.format.toUpperCase()+' · 保存于 '+state.document.fetched:'');
 $('#passages').innerHTML=rows.length?rows.map(p=>'<details class="passage" id="e-'+esc(p.id)+'"><summary>'+esc(p.location)+'<br><small>'+esc(p.text.slice(0,170))+'…</small></summary><p>'+esc(p.text)+'</p><a target="_blank" rel="noopener noreferrer" href="'+safe(p.url)+'">回到原文位置 ↗</a><br><button class="btn small" data-quote="'+esc(p.id)+'">引用到笔记</button><small>证据 '+esc(p.id)+'</small></details>').join(''):'<p>没有匹配的原文。准备全文后，可尝试英文关键词。</p>';
}
async function load(){state=await api();render();}
function poll(){
 clearInterval(polling);let count=0;
 polling=setInterval(async()=>{try{await load();if(state.status?.status!=='running'||++count>120)clearInterval(polling);}catch(e){clearInterval(polling);$('#status').textContent=e.message;}},2000);
}
async function start(model){
 working=true;render();
 try{await api('POST',{model});await load();if(state.status?.status==='running')poll();}
 catch(e){$('#status').textContent=e.message;}
 finally{working=false;$('#prepare').disabled=state.status?.status==='running';$('#analyze').disabled=!state.model_configured||state.status?.status==='running';}
}
$('#prepare').onclick=()=>start(false);$('#analyze').onclick=()=>start(true);$('#refresh').onclick=()=>load().then(()=>{if(state.status?.status==='running')poll();}).catch(e=>$('#status').textContent=e.message);
$('#queue-entry').onclick=async()=>{
 if(queueTask){location.assign('/#queue');return;}
 $('#queue-entry').disabled=true;
 try{
  const response=await fetch('/api/reading-queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:id})});
  const result=await response.json();if(!response.ok)throw Error(result.error||'加入精读队列失败');
  location.assign('/#queue');
 }catch(e){$('#status').textContent=e.message;}
 finally{$('#queue-entry').disabled=false;}
};
$('#search').oninput=renderPassages;
$('#passages').onclick=e=>{
 const button=e.target.closest('[data-quote]');if(!button)return;
 const row=state.document.passages.find(p=>p.id===button.dataset.quote);if(!row)return;
 $('#quote').value='### 原文证据 · '+row.location+'\n\n> '+row.text+'\n\n[原文出处]('+row.url+') · 证据 '+row.id+'\n\n我的理解：\n';$('#copy-state').textContent='';$('#quote-dialog').showModal();
};
$('#analysis').onclick=e=>{const a=e.target.closest('a');if(!a)return;let row=document.getElementById(a.hash.slice(1));if(!row&&$('#search').value){$('#search').value='';renderPassages();row=document.getElementById(a.hash.slice(1));}if(row)row.open=true;};
$('#close-quote').onclick=()=>$('#quote-dialog').close();
$('#copy').onclick=async()=>{try{await navigator.clipboard.writeText($('#quote').value);$('#copy-state').textContent='已复制，可粘贴到精读笔记。';}catch{$('#quote').focus();$('#quote').select();$('#copy-state').textContent='请使用系统复制菜单或 Ctrl/Cmd+C 复制已选中的引用。';}};
(async()=>{const response=await fetch('/api/items/'+encodeURIComponent(id));if(response.ok){const item=await response.json();$('#title').textContent=item.title_zh||item.title;}await load();loadQueue().catch(()=>{});if(state.status?.status==='running')poll();})().catch(e=>$('#status').textContent=e.message);
window.addEventListener('pagehide',()=>clearInterval(polling));
