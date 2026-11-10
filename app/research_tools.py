"""Reuse preparation from versioned evidence; unknown requirements stay unknown."""
import json
import re
from urllib.parse import urlparse
from . import storage

def adoption(report,passages):
    value=report.get('adoption')
    if value is None:
        try:value=json.loads((storage.ROOT/'content/reading-adoptions.json').read_text()).get(report.get('document_id'))
        except (OSError,ValueError,TypeError):pass
    if value is None:return None
    if not isinstance(value,dict) or not isinstance(value.get('requirements'),list):raise ValueError('复用条件格式无效')
    known={p['id']:p['text'] for p in passages}
    from .deep_read import normalize
    if len(value['requirements'])>24:raise ValueError('复用条件过多')
    for row in value['requirements']:
        if not isinstance(row,dict) or row.get('status') not in ['known','unknown'] or not row.get('label') or not row.get('text'):raise ValueError('复用条件须区分已核对与尚未确认')
        if row['status']=='known':
            ids=row.get('evidence_ids',[]);q=row.get('quote','')
            if not isinstance(ids,list) or not all(isinstance(i,str) for i in ids) or not isinstance(q,str) or len(normalize(q))<12 or not ids or any(i not in known for i in ids) or not any(normalize(q) in normalize(known[i]) for i in ids):raise ValueError('已核对的复用条件缺少匹配原文')
    return {'requirements':[{k:r[k] for k in ['label','text','status','evidence_ids','quote'] if k in r} for r in value['requirements']]}

def reuse(report,passages=None):
    def rows(kind):
        return [{k:r[k] for k in ['title','text','evidence_ids','quote'] if k in r}
                for r in report.get('findings',[]) if r.get('kind')==kind]
    prepared=adoption(report,passages) if passages is not None else None
    resources=[];seen=set()
    # Only resources literally mentioned in cited passages are exposed; being
    # mentioned never means a link works or belongs to the authors.
    cited={i for f in report.get('findings',[]) for i in f.get('evidence_ids',[])}
    for p in passages or []:
        if p['id'] not in cited:continue
        for link in re.findall(r'https://[^\s<>\[\](){}"\\]+',p['text']):
            link=link.rstrip('.,;:')
            host=urlparse(link).hostname or ''
            if host not in ['github.com','huggingface.co'] and not host.endswith('.github.io'):continue
            if link in seen:continue
            seen.add(link);resources.append({'url':link,'label':'原文提及的资源','evidence_ids':[p['id']]})
    return {'changes':rows('method'),'checks':rows('limitation'),
            'requirements':prepared['requirements'] if prepared else [{'label':label,'status':'unknown','text':'本次解读尚未结构化确认，复用前需回原文核对。','evidence_ids':[]} for label in ['数据与监督','模型与硬件','接口与许可']],
            'resources':resources[:8],
            'experiment':next((r['text'] for r in report.get('hypotheses',[])),''),
            'experiment_evidence_ids':next((r['evidence_ids'] for r in report.get('hypotheses',[])),[]),
            'notice':'条件来自当前版本原文；实验为待验证建议。资源链接未运行验证，尚未确认的条件保持明确。'}

def related(signals):
    for row in signals:
        topics=set(row.get('topics',[]))
        area=row.get('attention',{}).get('impact',{}).get('area')
        others=[r for r in signals if r['id']!=row['id'] and ((area and area==r.get('attention',{}).get('impact',{}).get('area')) or topics&set(r.get('topics',[])))]
        others.sort(key=lambda r:(bool(area and area==r.get('attention',{}).get('impact',{}).get('area')),len(topics&set(r.get('topics',[]))),r.get('published','')),reverse=True)
        row['related_ids']=[r['id'] for r in others[:3]]
        row['related_sources']=[{k:r[k] for k in ['id','title','kind','source_url']} for r in signals if r['id']!=row['id'] and row.get('research_group',row['id'])==r.get('research_group',r['id'])]
    return signals

def group(report,passages):
    value=report.get('release_of')
    if value is None:return report.get('item_id','')
    from .deep_read import normalize
    if not isinstance(value,dict) or not re.fullmatch(r'arxiv:\d{4}\.\d{4,5}',value.get('item_id','')):raise ValueError('关联发布须指向明确论文标识')
    ids=value.get('evidence_ids',[]);q=value.get('quote','');lookup={p['id']:p['text'] for p in passages}
    if not ids or any(i not in lookup for i in ids) or len(normalize(q))<12 or not any(normalize(q) in normalize(lookup[i]) and value['item_id'].split(':')[1] in lookup[i] for i in ids):raise ValueError('关联发布缺少正文中明确的论文出处')
    return value['item_id']
