'use strict';
let readingQueueBusy=false,readingQueueFilter='active';
const readingQueueDone=['completed','cancelled'];
function readingQueueTask(itemID){return (D?.reading_queue?.tasks||[]).find(t=>t.item_id===itemID&&!t.stale);}
function readingQueueEntry(itemID){
 const task=readingQueueTask(itemID);
 return task?'<button class="btn" data-reading-queue="open">精读任务 · '+esc(task.status_label)+'</button>':'<button class="btn primary" data-reading-queue="enqueue" data-item="'+esc(itemID)+'" '+(readingQueueBusy?'disabled':'')+'>交给精读</button>';
}
function readingQueuePage(){
 const queue=D.reading_queue||{tasks:[],counts:{}};
 const tasks=queue.tasks.filter(t=>readingQueueFilter==='all'||(readingQueueFilter==='review'?t.status==='needs_review':!readingQueueDone.includes(t.status)));
 const count=Object.entries(queue.counts).filter(([s])=>!readingQueueDone.includes(s)).reduce((n,[,v])=>n+v,0);
 const buttons=(t)=>{
  const b=(action,label)=>'<button class="btn" data-reading-queue="'+action+'" data-task="'+esc(t.id)+'" data-revision="'+t.revision+'" '+(readingQueueBusy?'disabled':'')+'>'+label+'</button>';
  if(t.stale)return '<button class="btn primary" data-reading-queue="enqueue" data-item="'+esc(t.item_id)+'">为当前版本新建任务</button>'+(!readingQueueDone.includes(t.status)?b('cancel','取消旧版任务'):'');
  return (t.document_id?'<a class="btn '+(t.status==='needs_review'?'primary':'')+'" href="/reading.html?id='+encodeURIComponent(t.item_id)+'">'+(['needs_review','completed'].includes(t.status)?'查看解读与证据':'查看原文证据')+'</a>':'')+(t.status==='needs_review'?b('complete','我已核查'):t.status==='completed'?b('reopen','恢复待核查'):['failed','cancelled'].includes(t.status)?b('retry','重新排队'):'')+(!readingQueueDone.includes(t.status)?b('cancel','取消任务'):'');
 };
 return head('READING WORKFLOW','后台处理','论文自动进入精读流程；前台只展示已有技术解读的内容。','<button class="btn" data-reading-queue="refresh">刷新队列</button>')+'<div class="reading-queue-stats"><span>'+count+' 项进行中</span><span>'+(queue.counts.needs_review||0)+' 项待核查</span><span>'+(queue.counts.ready_for_agent||0)+' 项等待代理</span></div><p class="reading-queue-notice">'+esc(queue.notice||'新论文自动进入后台处理。')+'</p><div class="reading-queue-filters" role="group" aria-label="精读任务范围">'+[['active','进行中'],['review','待核查'],['all','全部记录']].map(([v,label])=>'<button class="btn '+(readingQueueFilter===v?'primary':'')+'" data-reading-queue="filter" data-filter="'+v+'" aria-pressed="'+(readingQueueFilter===v)+'">'+label+'</button>').join('')+'</div><div class="reading-queue-list">'+(tasks.length?tasks.map(t=>'<article class="reading-task"><div class="reading-task-heading"><span class="reading-task-state" data-status="'+esc(t.status)+'">'+esc(t.status_label)+'</span>'+(t.stale?'<span class="tag amber">来源已有新版本</span>':'')+'<small>'+fmt(t.updated)+'</small></div><h2>'+esc(t.title)+'</h2>'+(t.priority?'<p>候选顺序 '+t.priority.position+' · '+esc(t.priority.reason)+'</p>':'')+'<p>'+esc(t.message)+'</p><div class="reading-task-actions">'+buttons(t)+'</div><details><summary>执行记录 · '+t.attempts+' 次原文准备</summary><p><a href="'+url(t.source_url)+'" target="_blank" rel="noopener noreferrer">任务来源版本 ↗</a></p>'+t.events.map(e=>'<p><time>'+fmt(e.at)+'</time> · '+esc(e.message)+'</p>').join('')+'</details></article>').join(''):empty('这个范围暂无精读任务','从前沿动态点开一篇论文，选择“交给精读”。'))+'</div>';
}
async function refreshReadingQueue(){
 const next=await api('reading-queue');
 if(JSON.stringify(next)===JSON.stringify(D.reading_queue))return;
 D.reading_queue=next;renderSidebar();
 if(page==='queue')renderMain();
}
document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-reading-queue]');if(!button)return;
 const action=button.dataset.readingQueue;
 if(action==='open'){readingQueueFilter='all';go('queue');return;}
 if(action==='filter'){readingQueueFilter=button.dataset.filter;renderMain();return;}
 if(readingQueueBusy)return;
 readingQueueBusy=true;button.disabled=true;
 try{
  if(action==='refresh')await refreshReadingQueue();
  else{
   const result=action==='enqueue'?await api('reading-queue','POST',{item_id:button.dataset.item}):await api('reading-queue/'+button.dataset.task,'POST',{action,revision:Number(button.dataset.revision)});
   D.reading_queue=result.queue;
   if(action==='enqueue'){readingQueueFilter='active';if($('#frontier-dialog').open)$('#frontier-dialog').close();go('queue');toast('任务已保存，后台将准备原文');}
   else{renderSidebar();if(page==='queue')renderMain();toast(action==='complete'?'已标记核查完成':action==='cancel'?'任务已取消':action==='retry'?'已重新排队':'已恢复待核查');}
  }
 }catch(error){toast(error.message);try{await refreshReadingQueue();}catch{}}
 finally{readingQueueBusy=false;button.disabled=false;if(page==='queue')renderMain();}
});
setInterval(async()=>{
 if(typeof D==='undefined'||!D||page!=='queue'||readingQueueBusy||document.visibilityState==='hidden')return;
 if(document.activeElement?.closest('[data-reading-queue]'))return;
 try{await refreshReadingQueue();}catch{}
},4000);
