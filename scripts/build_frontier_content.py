#!/usr/bin/env python3
"""Bundle public, versioned full readings without accessing the private database."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(root))
from app.frontier import signature,publication
from app import research_tools,attention
seed=root/'ios/ResearchRadar/Resources/ReadingShelf.json';raw=json.loads(seed.read_text())
if '--from-server' in sys.argv:
    # Only the credential-free public package is read. Never request /api/state
    # or open the private database as part of an App content build.
    import urllib.request
    with urllib.request.urlopen('http://127.0.0.1:8765/api/content',timeout=60) as response:payload=json.load(response)
    signals=payload['signals'];readings=payload['readings'];manifest=payload['manifest']
    if {s['id'] for s in signals}!=set(readings) or set(readings)!=set(manifest['documents']):raise ValueError('公开内容清单不完整')
    for s in signals:
        r=readings[s['id']];d=r['document'];a=r['analysis']
        if not s.get('publication_ready') or d['id']!=manifest['documents'][s['id']] or a['document_id']!=d['id'] or a['source_url']!=d['url']:raise ValueError('公开全文与来源不匹配')
        if s['version_signature']!=signature({'url':s['source_url'],'updated':s['published'],'source_revision':s.get('source_revision','')}):raise ValueError('服务仍在更新版本标识，请待启动完成后重试')
        publication(a,d['passages'],s)
    items=[{**{k:i[k] for k in ['id','title','title_zh','summary','authors','url','pdf_url','code_url','source_id','kind','published','updated','topics','curated','analysis'] if k in i},'notes':'','saved':False,'reading':'unread'} for i in raw['items'] if i.get('curated')]
    for s in signals:
        items.append(dict(id=s['id'],title=s.get('paper_title',s['title']),url=s['source_url'],kind=s['kind'],source_id=s.get('source_id','arxiv' if s['kind']=='paper' else s['source_name']),source_revision=s.get('source_revision',''),published=s['first_published'],updated=s['published'],summary=s.get('abstract',''),topics=s['topics'],curated=False,notes='',saved=False,reading='unread',analysis={}))
    raw.update(items=items,signals=signals,public_readings=readings,content_manifest={**manifest,'kind':'bundled'},frontier_meta=dict(as_of='',latest_date=manifest['latest_date'],reviewed_at=manifest['checked_at'],publication_required=True,published_count=len(signals),pending_count=0,selection='已完成精读与展示检查的公开离线快照。'))
    seed.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
    print('Bundled',len(signals),'fully read public increments from the public endpoint.');sys.exit(0)
catalog={r['id']:r for r in json.loads((root/'content/frontier.json').read_text())}
existing={r['id']:r for r in raw['items']}
signals=[]
public_items=[item for item in raw['items'] if item.get('curated')]
readings={}
versions={}
calibrations={r['document_id']:r['attention'] for r in json.loads((root/'content/reading-calibration.json').read_text())} if (root/'content/reading-calibration.json').exists() else {}
for path in sorted((root/'content/reading-pilots').glob('*.json')):
    if path.stem.endswith('-evidence'):continue
    report=json.loads(path.read_text());evidence_path=path.with_name(path.stem+'-evidence.json')
    if not evidence_path.exists():continue
    evidence=json.loads(evidence_path.read_text())
    if evidence['id']!=report['document_id'] or evidence['url']!=report['source_url']:continue
    editorial=catalog.get(report['item_id'])
    # New reports carry public source metadata; the original pilot uses its public seed.
    paper=report.get('paper') or existing.get(report['item_id'])
    if not paper or paper['id']!=report['item_id']:continue
    if not all(paper.get(k) for k in ['url','published','updated','topics']):continue
    kind=paper.get('kind','paper')
    if kind=='paper':
        if evidence['url'].replace('/html/','/abs/').replace('/pdf/','/abs/')!=paper['url']:continue
    else:
        from app import research_material
        if not research_material.supported(paper):continue
        if kind in ['model','dataset']:
            if not evidence['url'].startswith(paper['url'].rstrip('/')+'/blob/'):continue
        elif evidence['url']!=paper['url']:continue
    try:brief=publication(report,evidence['passages'],editorial,calibrations.get(report['document_id']))
    except (ValueError,KeyError,TypeError):continue
    import re
    revision=re.search(r'v(\d+)$',paper['url'])
    version=(paper['updated'],int(revision.group(1)) if revision else 0,report.get('created',''))
    if report['item_id'] in versions and versions[report['item_id']]>=version:continue
    versions[report['item_id']]=version
    signals=[r for r in signals if r['id']!=report['item_id']]
    public_items=[r for r in public_items if r['id']!=report['item_id']]
    row={**brief,'id':report['item_id'],'topics':paper['topics'],'source_url':paper['url']}
    if row['attention'].get('headline'):row['title']=row['attention']['headline']
    row.update(checked_at=report['created'][:10],publication_ready=True,
        evidence_level='全文文字已精读 · 引文匹配通过 · 未复现',reading_document_id=report['document_id'],
        reading_model=report['model'],reading_coverage={'read':len(evidence['passages']),'total':len(evidence['passages'])},
        reviewed=True,status='new',published=paper['updated'][:10],first_published=paper['published'][:10],kind=kind,
        source_name='arXiv' if kind=='paper' else paper.get('source_id','官方来源'),abstract=paper.get('summary',''),paper_title=paper['title'],code_url='')
    if kind!='paper':row['evidence_level']='官方发布正文已读 · 引文匹配通过 · 未运行验证'
    row['version_signature']=signature({'url':row['source_url'],'updated':paper['updated'],'source_revision':paper.get('source_revision','')})
    row['experiment_suggestion']=next((h['text'] for h in report['hypotheses']), '')
    row['hypothesis_suggestion']=row['experiment_suggestion'].split('。')[0]+'。' if row['experiment_suggestion'] else ''
    row['reuse']=research_tools.reuse(report,evidence['passages'])
    row['research_group']=research_tools.group(report,evidence['passages'])
    report['attention']=row['attention']
    public_items.append(dict(id=row['id'],title=paper['title'],url=row['source_url'],kind=kind,source_id=paper.get('source_id','arxiv'),source_revision=paper.get('source_revision',''),
        published=paper['published'],updated=paper['updated'],summary=paper.get('summary',''),topics=row['topics'],curated=False,
        reading='unread',saved=False,notes='',analysis={}))
    readings[row['id']]=dict(document=evidence,analysis=report,model_configured=False,status=dict(status='ready',message='内置版本的原文与解读可离线阅读'))
    signals.append(row)
signals.sort(key=attention.order,reverse=True)
research_tools.related(signals)
raw['signals']=signals
raw['items']=public_items
raw['public_readings']=readings
import hashlib
content_version=hashlib.sha256(json.dumps(readings,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
raw['content_manifest']={'version':content_version,'count':len(readings),'documents':{key:value['document']['id'] for key,value in readings.items()},'kind':'bundled'}
reviewed_at=max((r['checked_at'] for r in signals),default='')
raw['frontier_meta']={'as_of':reviewed_at+'T00:00:00+00:00' if reviewed_at else '',
    'latest_date':max((r['published'] for r in signals),default=''),
    'reviewed_at':reviewed_at,'publication_required':True,'published_count':len(signals),
    'pending_count':0,'selection':'仅展示已完成模型精读与引文检查的公开快照。'}
seed.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
print('Bundled',len(signals),'fully read public research increments.')
