"""Dated research increments and persistent triage, separate from paper reading state."""
import hashlib
import json
import re
from datetime import datetime,timezone
from . import storage, deep_read
from . import research_tools, attention
STATUSES={'new','seen','later','dismissed'}

def init(c=None):
    if c is None:
        with storage.db() as conn:init(conn)
    else:c.execute('CREATE TABLE IF NOT EXISTS frontier_states(id TEXT PRIMARY KEY,version_signature TEXT NOT NULL,status TEXT NOT NULL,updated TEXT NOT NULL)')

def signature(item):
    fixed=re.fullmatch(r'https://arxiv\.org/abs/(\d{4}\.\d{4,5}v[1-9]\d*)',item['url'])
    if fixed:return hashlib.sha256(('arxiv-revision:'+fixed.group(1)).encode()).hexdigest()[:24]
    return deep_read.signature(item)[:24]

def current(item,row=None,document=None):
    revision=signature(item)
    aliases={revision,deep_read.signature(item)[:24]}
    if row and row['version_signature'] not in aliases:
        docs=[document] if document else []
        if not document:
            with storage.db() as c:docs=c.execute('SELECT * FROM reading_documents WHERE item_id=?',(item['id'],)).fetchall()
        for doc in docs:
            if deep_read.matches(item,doc):aliases.add(doc['source_signature'][:24])
    return {'id':item['id'],'version_signature':revision,'status':row['status'] if row and row['version_signature'] in aliases else 'new'}

def publication(report,passages,editorial=None,calibration=None):
    """Reading and evidence are prerequisites for publication, independent of user triage."""
    if report.get('mode') not in ['agent_pilot','model_interpretation'] or not report.get('model'):raise ValueError('尚无模型精读')
    deep_read.validate_result(report,passages)
    coverage=report.get('coverage',{});ids=coverage.get('evidence_ids',[])
    if coverage.get('read')!=len(passages) or coverage.get('total')!=len(passages) or len(ids)!=len(passages) or set(ids)!={p['id'] for p in passages}:raise ValueError('精读覆盖不完整')
    brief=report.get('frontier_brief') or editorial
    if not isinstance(brief,dict):raise ValueError('尚未生成技术增量卡片')
    for key in ['title','delta','before','after','relevance','caveat','question']:
        if not isinstance(brief.get(key),str) or not brief[key].strip():raise ValueError('技术解读缺少 '+key)
    if not isinstance(brief.get('evidence'),list) or not brief['evidence']:raise ValueError('技术解读缺少实验证据')
    for row in brief['evidence']:
        if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in ['label','value','context']):raise ValueError('实验证据格式无效')
    if not isinstance(brief.get('mechanism'),list) or not brief['mechanism'] or any(not isinstance(r,dict) or not isinstance(r.get('title'),str) or not isinstance(r.get('text'),str) for r in brief['mechanism']):raise ValueError('方法机制格式无效')
    if not any(r['kind']=='method' for r in report['findings']) or not any(r['kind']=='evidence' for r in report['findings']):raise ValueError('精读尚缺方法或实验判断')
    research_tools.adoption(report,passages)
    research_tools.group(report,passages)
    # Only presentation fields can flow out of a model brief; it cannot replace IDs or triage state.
    value={**{k:brief[k] for k in ['title','delta','before','after','relevance','caveat','question','evidence','mechanism','change_type'] if k in brief},'attention':attention.validate({**report,'attention':calibration} if calibration else report,passages)}
    if value['attention'].get('headline'):value['title']=value['attention']['headline']
    return value

def build(items):
    init()
    catalog={r['id']:r for r in json.loads((storage.ROOT/'content/frontier.json').read_text())}
    deep_read.init()
    with storage.db() as c:
        states={r['id']:dict(r) for r in c.execute('SELECT * FROM frontier_states')}
        documents=[dict(r) for r in c.execute('SELECT d.*,r.payload FROM reading_documents d JOIN reading_results r ON r.document_id=d.id ORDER BY d.fetched DESC')]
        calibrated=attention.calibrations(c)
    signals=[];candidates=[]
    # Historic introductions never become current signals just because they were read today.
    for item in items:
        if item.get('curated'):continue
        editorial=catalog.get(item['id'])
        if editorial and item['url'].rstrip('/')!=editorial['source_url'].rstrip('/'):editorial=None
        reviewed=None;document=None;reason='等待全文精读'
        for doc in documents:
            if doc['item_id']!=item['id']:continue
            if not deep_read.matches(item,doc):
                reason='已有精读，当前来源版本尚未匹配'
                continue
            try:
                report=json.loads(doc['payload']);reviewed=publication(report,json.loads(doc['passages']),editorial,calibrated.get(doc['id']));document=doc;break
            except (ValueError,TypeError,KeyError) as exc:reason='精读或技术解读尚未通过展示检查：'+str(exc)[:160]
        if not reviewed:
            candidates.append({'id':item['id'],'title':item['title'],'source_url':item['url'],'reason':reason})
            continue
        row={
            'id':item['id'],'title':item.get('title_zh') or item['title'],'paper_title':item['title'],
            'published':item['updated'][:10],'first_published':item['published'][:10],
            'topics':item['topics'],'kind':item['kind'],'source_url':item['url'],
            'code_url':item.get('code_url',''),'source_name':'arXiv' if item['kind']=='paper' else item.get('source_id',''),
            'source_id':item['source_id'],'source_revision':item.get('source_revision',''),
            'reviewed':bool(reviewed),'delta':'','abstract':item['summary'],
            'change_type':'新论文' if item['kind']=='paper' else '代码发布' if item['kind']=='release' else '模型更新' if item['kind']=='model' else '数据集更新' if item['kind']=='dataset' else '研究动态',
            **current(item,states.get(item['id']),document)}
        row.update(reviewed)
        if row['attention'].get('headline'):row['title']=row['attention']['headline']
        row.update(publication_ready=True,evidence_level='全文文字已精读 · 引文匹配通过 · 未复现' if item['kind']=='paper' else '官方发布正文已读 · 引文匹配通过 · 未运行验证',checked_at=report.get('created',doc['fetched'])[:10],reading_document_id=document['id'],reading_model=report['model'],reading_coverage={'read':len(json.loads(doc['passages'])),'total':len(json.loads(doc['passages']))})
        row['reuse']=research_tools.reuse(report,json.loads(document['passages']))
        row['research_group']=research_tools.group(report,json.loads(document['passages']))
        hypotheses=report.get('hypotheses',[])
        if hypotheses:
            row['experiment_suggestion']=hypotheses[0]['text']
            row['hypothesis_suggestion']=hypotheses[0]['text'].split('。')[0]+'。'
        signals.append(row)
    rank={key:i for i,key in enumerate(catalog)}
    signals.sort(key=attention.order,reverse=True)
    research_tools.related(signals)
    return {'signals':signals,'reading_candidates':candidates,'frontier_meta':{'publication_required':True,'pending_count':len(candidates),'published_count':len(signals),'as_of':storage.now(),'latest_date':max((r['published'] for r in signals),default=''),'reviewed_at':max((r.get('checked_at','') for r in signals),default=''),'selection':'先完成模型精读与引文检查，再展示具体技术增量；不是性能排名，未复现。'}}

def snapshot_states():
    init()
    with storage.db() as c:return [dict(r) for r in c.execute('SELECT * FROM frontier_states')]
