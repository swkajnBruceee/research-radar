"""Evidence-grounded reading priority, separate from personal reading state."""
import json
import re
from . import storage

LEVELS = {'priority': 2, 'notable': 1, 'routine': 0, 'unassessed': 0}
BASES = {'training_change', 'compute_shift', 'controlled_comparison', 'real_robot',
         'capability_change', 'reusable_resource', 'negative_result'}
SCOPES = {'route':3,'method':2,'task':1,'tool':1}
SUPPORT = {'controlled':2,'limited':1,'insufficient':0}
AREAS = {'training','architecture','data','control','planning','evaluation','perception','deployment'}

def impact(value,report,passages):
    if not isinstance(value,dict) or value.get('scope') not in SCOPES or value.get('support') not in SUPPORT or value.get('area') not in AREAS:
        raise ValueError('重要性比较须包含影响范围、证据强度与研究决策类别')
    reason=value.get('comparison','');ids=value.get('evidence_ids',[])
    if not isinstance(reason,str) or not 12<=len(reason.strip())<=300:raise ValueError('须说明相对其他工作为何值得先读及影响边界')
    if not isinstance(ids,list) or not ids or not all(isinstance(i,str) for i in ids) or not set(ids)<={p['id'] for p in passages}:raise ValueError('跨论文判断缺少当前论文的有效依据')
    for kind in ['method','evidence']:
        if not set(ids)&{i for f in report.get('findings',[]) if f.get('kind')==kind for i in f.get('evidence_ids',[])}:
            raise ValueError('影响范围判断须同时引用方法和实验')
    rank=min(SCOPES[value['scope']],SUPPORT[value['support']]+1)
    references=value.get('compared_with',[])
    if not isinstance(references,list) or len(references)>5 or any(not isinstance(x,str) or not re.fullmatch(r'[a-f0-9]{64}',x) or x==report.get('document_id') for x in references):raise ValueError('比较对象须为其他固定版本的全文文档ID')
    return {**{k:value[k] for k in ['scope','support','area']},'comparison':reason.strip(),'compared_with':references,
            'evidence_ids':list(dict.fromkeys(ids)),'rank':rank,'support_rank':SUPPORT[value['support']]}


def watchlist():
    try:
        rows = json.loads((storage.ROOT / 'content/research-watchlist.json').read_text()).get('papers', [])
        return [r for r in rows if isinstance(r, dict) and re.fullmatch(r'\d{4}\.\d{4,5}', r.get('arxiv_id', ''))]
    except (OSError, ValueError, TypeError):
        return []


def validate(report, passages):
    value = report.get('attention')
    if value is None:
        try:
            assessments=json.loads((storage.ROOT/'content/reading-attention.json').read_text())
            value=assessments.get('assessments',{}).get(report.get('document_id',''))
        except (OSError,ValueError,TypeError):pass
    if value is None:
        return {'level': 'unassessed', 'rank': 0, 'reason': '', 'basis': [], 'evidence_ids': []}
    if not isinstance(value, dict) or value.get('level') not in LEVELS:
        raise ValueError('重要性判断格式无效')
    reason = value.get('reason', '')
    ids = value.get('evidence_ids', [])
    basis = value.get('basis', [])
    if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 240:
        raise ValueError('重要性判断必须说明具体研究影响')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids) or not set(ids) <= {p['id'] for p in passages}:
        raise ValueError('重要性判断缺少有效出处')
    if not isinstance(basis, list) or not basis or any(b not in BASES for b in basis):
        raise ValueError('重要性判断依据无效')
    findings = report.get('findings', [])
    if value['level'] in ['priority', 'notable']:
        for kind in ['method', 'evidence']:
            supported = {i for f in findings if f.get('kind') == kind for i in f.get('evidence_ids', [])}
            if not set(ids) & supported:
                raise ValueError('优先展示须同时关联已精读的方法与实验证据')
    result={'level': value['level'], 'rank': LEVELS[value['level']], 'reason': reason.strip(),
            'basis': list(dict.fromkeys(basis)), 'evidence_ids': list(dict.fromkeys(ids)),
            'assessed_at': value.get('assessed_at',report.get('created', '')),
            'notice':'阅读优先级判断，不是科学质量定论。'}
    if value.get('impact') is not None:result['impact']=impact(value['impact'],report,passages)
    for key,limit in [('headline',90),('summary',180)]:
        if value.get(key):
            if not isinstance(value[key],str) or not 6<=len(value[key].strip())<=limit:raise ValueError('重点导读标题或摘要长度无效')
            result[key]=value[key].strip()
    return result


def rank(signal):
    if signal.get('status') in ['seen', 'dismissed']:
        return 0
    return LEVELS.get(signal.get('attention', {}).get('level'), 0)

def order(signal,personal=True):
    value=signal.get('attention',{});profile=value.get('impact',{})
    level=LEVELS.get(value.get('level'),0)
    active=not personal or signal.get('status') not in ['seen','dismissed']
    # Routine material never displaces a specifically recommended method.
    return (int(active and level>0),profile.get('rank',level) if active and level else 0,
            profile.get('support_rank',0) if active and level else 0,level if active else 0,
            signal.get('published',''),signal.get('id',''))

def featured(signals,limit=3):
    chosen=[];areas=set();groups=set()
    rows=sorted((r for r in signals if r.get('publication_ready') and r.get('status','new')=='new' and rank(r)>0),key=order,reverse=True)
    for row in rows:
        area=row.get('attention',{}).get('impact',{}).get('area')
        group=row.get('research_group',row['id'])
        if group in groups:continue
        if area and area in areas:continue
        chosen.append(row);areas.add(area);groups.add(group)
        if len(chosen)>=limit:break
    return chosen

def calibrations(c):
    c.execute('CREATE TABLE IF NOT EXISTS reading_calibrations(document_id TEXT PRIMARY KEY,payload TEXT NOT NULL,assessed_at TEXT NOT NULL)')
    return {r['document_id']:json.loads(r['payload']) for r in c.execute('SELECT * FROM reading_calibrations')}

def check_references(value,c):
    from . import deep_read
    for reference in value.get('impact',{}).get('compared_with',[]):
        other=c.execute('SELECT d.passages,r.payload FROM reading_documents d JOIN reading_results r ON r.document_id=d.id WHERE d.id=?',(reference,)).fetchone()
        if not other:raise ValueError('比较对象尚未完成全文精读')
        report=json.loads(other['payload']);passages=json.loads(other['passages'])
        deep_read.validate_result(report,passages)
        coverage=report.get('coverage',{})
        if not report.get('model') or coverage.get('read')!=len(passages) or coverage.get('total')!=len(passages) or set(coverage.get('evidence_ids',[]))!={p['id'] for p in passages}:raise ValueError('比较对象缺少完整精读范围')

def calibrate(rows):
    """Re-evaluate public editorial judgments, preserving the full-reading record."""
    from . import frontier,deep_read
    deep_read.init()
    if not isinstance(rows,list) or not rows:raise ValueError('缺少校准判断')
    with storage.db() as c:
        calibrations(c);c.execute('BEGIN IMMEDIATE')
        for row in rows:
            doc=c.execute('SELECT d.*,r.payload FROM reading_documents d JOIN reading_results r ON r.document_id=d.id WHERE d.id=?',(row.get('document_id'),)).fetchone()
            if not doc:raise ValueError('只能校准已完成全文精读的固定版本')
            item=c.execute('SELECT * FROM items WHERE id=?',(doc['item_id'],)).fetchone()
            if not deep_read.matches(item,doc):raise ValueError('校准来源版本已变化')
            report=json.loads(doc['payload']);passages=json.loads(doc['passages'])
            editorial=next((r for r in json.loads((storage.ROOT/'content/frontier.json').read_text()) if r['id']==item['id'] and r['source_url']==item['url']),None)
            frontier.publication(report,passages,editorial)
            value=validate({**report,'attention':row['attention']},passages)
            if not value.get('impact'):raise ValueError('校准必须包含跨论文比较')
            check_references(value,c)
            c.execute('INSERT OR REPLACE INTO reading_calibrations VALUES (?,?,?)',(doc['id'],json.dumps(value,ensure_ascii=False),storage.now()))


def init(c):
    c.execute('''CREATE TABLE IF NOT EXISTS reading_attention(
        item_id TEXT PRIMARY KEY,source_signature TEXT NOT NULL,level INTEGER NOT NULL,
        reason TEXT NOT NULL,quote TEXT NOT NULL,assessed_at TEXT NOT NULL)''')
    if 'profile' not in {r['name'] for r in c.execute('PRAGMA table_info(reading_attention)')}:c.execute("ALTER TABLE reading_attention ADD COLUMN profile TEXT DEFAULT '{}'")


def screening(c):
    init(c)
    return {r['item_id']: dict(r) for r in c.execute('SELECT * FROM reading_attention')}


def queue_hint(row):
    row = dict(row)
    if row.get('screening_level') is not None:
        return int(row['screening_level'])
    return 2 if any('arxiv:' + r['arxiv_id'] == row.get('item_id') for r in watchlist()) else 0


def assess(item_id, level, reason, quote):
    """Metadata-only triage can accelerate reading but never publishes a paper."""
    assess_many([{'item_id':item_id,'level':level,'reason':reason,'quote':quote}])

def assess_many(rows):
    """Validate and commit a complete group atomically; no partial success."""
    from .deep_read import signature, normalize
    if not isinstance(rows,list) or not rows or len(rows)>24:raise ValueError('每批须含1至24条初筛判断')
    with storage.db() as c:
        init(c)
        c.execute('BEGIN IMMEDIATE')
        for row in rows:
            if not isinstance(row,dict):raise ValueError('初筛判断必须是对象')
            item_id=row.get('item_id');level=row.get('level');reason=row.get('reason');quote=row.get('quote')
            if type(level) is not int or level not in [0,1,2] or not isinstance(reason,str) or not 8<=len(reason.strip())<=240:
                raise ValueError('初筛等级或理由无效：'+str(item_id))
            item=c.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone()
            if item and row.get('source_signature') and row['source_signature']!=signature(item):raise ValueError('初筛期间候选版本变化，请重新获取 shortlist')
            from .research_material import supported
            if not item or item['curated'] or not supported(item):raise ValueError('仅初筛已支持的公开研究材料候选')
            if not isinstance(quote,str) or len(normalize(quote))<12 or normalize(quote) not in normalize(item['title']+' '+item['summary']):
                raise ValueError('初筛须引用标题或摘要中至少12字符的逐字原文：'+item_id)
            profile=row.get('profile',{})
            if profile and (not isinstance(profile,dict) or profile.get('scope') not in SCOPES or profile.get('area') not in AREAS):raise ValueError('摘要初筛的预期影响范围或方向无效')
            c.execute('INSERT OR REPLACE INTO reading_attention(item_id,source_signature,level,reason,quote,assessed_at,profile) VALUES (?,?,?,?,?,?,?)',
                      (item_id,signature(item),level,reason.strip(),quote,storage.now(),json.dumps(profile,ensure_ascii=False)))
