"""Versioned public full-reading package. Never export notes, triage or secrets."""
import hashlib
import json
import copy
import threading
import time
from . import storage,frontier,attention,research_tools

REPORT_FIELDS=['item_id','document_id','source_url','paper_version','mode','review_status','model','created','prompt_version','overview','coverage','notice','findings','hypotheses','frontier_brief','attention','adoption','release_of']
SIGNAL_FIELDS=['id','title','paper_title','published','first_published','topics','kind','source_url','code_url','source_name','delta','before','after','relevance','caveat','question','evidence','mechanism','change_type','reviewed','publication_ready','evidence_level','checked_at','reading_document_id','reading_model','reading_coverage','version_signature','experiment_suggestion','hypothesis_suggestion','reuse','related_ids','attention']
SIGNAL_FIELDS+=['research_group','related_sources','source_id','source_revision','abstract']

_CACHE=None
_CACHE_LOCK=threading.Lock()

def fingerprint():
    paths=[storage.DB,storage.DB.with_name(storage.DB.name+'-wal'),storage.ROOT/'content/reading-adoptions.json']
    return (str(storage.DB),tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else (str(p),0,0) for p in paths))

def package():
    global _CACHE
    with _CACHE_LOCK:
        key=fingerprint()
        if _CACHE and _CACHE[0]==key and time.monotonic()-_CACHE[1]<5:return copy.deepcopy(_CACHE[2])
        value=build_package()
        if fingerprint()==key:_CACHE=(key,time.monotonic(),value)
        return copy.deepcopy(value)

def build_package():
    frontier.init();frontier.deep_read.init()
    with storage.db() as c:
        items=[]
        for row in c.execute("SELECT id,title,title_zh,url,pdf_url,code_url,source_id,kind,published,updated,source_revision,summary,authors,topics,curated FROM items WHERE curated=0"):
            item=dict(row);item['topics']=json.loads(item['topics']);items.append(item)
        documents={r['id']:dict(r) for r in c.execute('SELECT d.id,d.url,d.format,d.passages,r.payload FROM reading_documents d JOIN reading_results r ON r.document_id=d.id')}
    signals=frontier.build(items)['signals']
    # A public package must not encode personal triage indirectly through order.
    signals.sort(key=lambda r:attention.order(r,personal=False),reverse=True)
    research_tools.related(signals)
    readings={};public_signals=[]
    for row in signals:
        doc=documents.get(row['reading_document_id'])
        if not doc:continue
        report=json.loads(doc['payload']);passages=json.loads(doc['passages'])
        report['attention']=row['attention']
        if report.get('adoption') is not None:report['adoption']=research_tools.adoption(report,passages)
        if report.get('release_of') is not None:report['release_of']={k:report['release_of'][k] for k in ['item_id','evidence_ids','quote']}
        # The original RAFT pilot uses the version-matched editorial brief that
        # frontier.build already validated. Carry it into the downloadable copy.
        if not report.get('frontier_brief'):
            report['frontier_brief']={k:row[k] for k in ['title','delta','before','after','relevance','caveat','question','evidence','mechanism','change_type'] if k in row}
        frontier.publication(report,passages)
        readings[row['id']]={'document':{k:doc[k] for k in ['id','url','format']},
            'analysis':{k:report[k] for k in REPORT_FIELDS if k in report},
            'model_configured':False,'status':{'status':'ready','message':'当前版本全文与解读已缓存，可离线阅读'}}
        readings[row['id']]['document']['passages']=passages
        public_signals.append({**{k:row[k] for k in SIGNAL_FIELDS if k in row},'status':'new'})
    value={'schema_version':1,'signals':public_signals,'readings':readings}
    version=hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest={'version':version,'count':len(readings),'documents':{key:value['document']['id'] for key,value in readings.items()},
              'reading_versions':{key:hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest() for key,value in readings.items()},
              'latest_date':max((r['published'] for r in public_signals),default=''),
              'checked_at':max((r.get('checked_at','') for r in public_signals),default='')}
    return {**value,'manifest':manifest,'version':version}
