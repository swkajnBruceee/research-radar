"""Explicit read/import and conservative Notion upserts; no credential exposure."""
import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from . import storage, exports

LOCK=threading.Lock()
MANAGED=['标题','研究台ID','类型','来源','研究台摘要']

def init():
    with storage.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS notion_links(local_id TEXT PRIMARY KEY,page_id TEXT,url TEXT,source_hash TEXT,remote_hash TEXT,synced TEXT);
        CREATE TABLE IF NOT EXISTS integration_runs(id INTEGER PRIMARY KEY,provider TEXT,at TEXT,status TEXT,detail TEXT);
        CREATE TABLE IF NOT EXISTS zotero_preview(id TEXT PRIMARY KEY,payload TEXT);
        CREATE TABLE IF NOT EXISTS zotero_annotations(id TEXT PRIMARY KEY,item_id TEXT,payload TEXT,imported TEXT);''')

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def log(provider,status,detail):
    with storage.db() as c:c.execute('INSERT INTO integration_runs(provider,at,status,detail) VALUES (?,?,?,?)',(provider,storage.now(),status,detail))

def target():
    path=storage.DATA/'notion-target.json'
    return json.loads(path.read_text()) if path.exists() else {}

def jobs():
    init()
    with storage.db() as c: annotated={r[0] for r in c.execute('SELECT DISTINCT item_id FROM zotero_annotations')}
    selected=[x for x in storage.all_items() if x['kind']=='paper' and (x['saved'] or x['notes'] or x['reading']!='unread' or x['id'] in annotated)]
    with storage.db() as c:
        ideas=[dict(r) for r in c.execute('SELECT * FROM ideas')]
        links={r['local_id']:dict(r) for r in c.execute('SELECT * FROM notion_links')}
    result=[]
    for x in selected+ideas:
        paper='kind' in x
        identity=x['id'] if paper else 'idea:'+x['id']
        summary=('阅读状态：'+x['reading']+'；分析程度：'+x['note_level']+'\n\n'+x['summary'][:1000]+('\n\n我的精读笔记：\n'+x['notes'] if x['notes'] else '')) if paper else '\n\n'.join(k+'：'+x[field] for k,field in [('问题观察','observation'),('证据','evidence'),('待验证假设','hypothesis'),('最小实验','experiment')])
        if paper:
            evidence=annotations(x['id'])
            if evidence:
                excerpt='\n\n'.join('第 '+r['page']+' 页\n'+r['quote']+'\n'+r['comment']+'\n'+r['source'] for r in evidence)
                summary+='\n\nZotero 阅读证据：\n'+excerpt[:30000]+('\n（更多批注见研究台）' if len(excerpt)>30000 else '')
        props={'标题':(x.get('title_zh') or x['title']),'研究台ID':identity,'类型':'论文' if paper else '选题','来源':x['url'] if paper else '', '研究台摘要':summary}
        link=links.get(identity)
        result.append({'id':identity,'properties':props,'hash':digest(props),'link':link,'state':'new' if not link else 'synced' if link['source_hash']==digest(props) else 'changed'})
    return result

def acknowledge(job,page_id,url,remote=None):
    init()
    with storage.db() as c:c.execute('INSERT OR REPLACE INTO notion_links VALUES (?,?,?,?,?,?)',(job['id'],page_id,url,job['hash'],digest(remote or job['properties']),storage.now()))

def status():
    init(); pending=jobs()
    with storage.db() as c:
        links=[dict(r) for r in c.execute('SELECT local_id,url,synced FROM notion_links')]
        runs=[dict(r) for r in c.execute('SELECT provider,at,status,detail FROM integration_runs ORDER BY id DESC LIMIT 12')]
        count=c.execute('SELECT COUNT(*) FROM zotero_annotations').fetchone()[0]
    return {'notion':{'target':target().get('url'),'runtime_configured':bool(os.environ.get('NOTION_API_KEY') and target()),'pending':sum(j['state']!='synced' for j in pending),'synced':len(links),'links':links},'zotero':{'imported':count},'runs':runs}

def request_json(url,method='GET',body=None,headers=None):
    req=urllib.request.Request(url,method=method,data=json.dumps(body).encode() if body is not None else None,headers=headers or {})
    with urllib.request.urlopen(req,timeout=12) as r:
        raw=r.read(8*1024*1024+1)
        if len(raw)>8*1024*1024:raise ValueError('响应过大，请缩小同步范围')
        return json.loads(raw),dict(r.headers)

def notion_request(path,method='GET',body=None):
    key=os.environ.get('NOTION_API_KEY')
    if not key:raise ValueError('本次对话可同步 Notion；网页持续同步需在服务器配置 NOTION_API_KEY 并授权目标库')
    return request_json('https://api.notion.com/v1/'+path,method,body,{'Authorization':'Bearer '+key,'Notion-Version':'2025-09-03','Content-Type':'application/json'})[0]

def plain(properties):
    out={}
    for name in MANAGED:
        value=properties.get(name,{})
        kind=value.get('type') or ('title' if name=='标题' else 'url' if name=='来源' else 'select' if name=='类型' else 'rich_text')
        out[name]=value.get('url') or '' if kind=='url' else (value.get('select') or {}).get('name','') if kind=='select' else ''.join(t.get('plain_text',t.get('text',{}).get('content','')) for t in value.get(kind,[]))
    return out

def wire(props):
    result={}
    for k,v in props.items():
        if k=='来源':result[k]={'url':v or None}
        elif k=='类型':result[k]={'select':{'name':v}}
        else:result[k]={'title' if k=='标题' else 'rich_text':[{'text':{'content':v[i:i+2000]}} for i in range(0,len(v),2000)]}
    result['同步时间']={'date':{'start':storage.now()}}
    return result

def sync_notion():
    init()
    if not os.environ.get('NOTION_API_KEY'):raise ValueError('网页持续同步尚未配置服务器端 NOTION_API_KEY；可通过对话继续同步')
    if not LOCK.acquire(False):raise ValueError('已有同步正在执行')
    result={'new':0,'updated':0,'unchanged':0,'conflicts':[]}
    try:
        ds=target().get('data_source_id')
        if not ds:raise ValueError('尚未指定 Notion 资料库')
        for job in jobs():
            link=job['link']
            if not link:
                found=notion_request('data_sources/'+ds+'/query','POST',{'filter':{'property':'研究台ID','rich_text':{'equals':job['id']}}})['results']
                if found:
                    remote=found[0]
                    # A page without our baseline is never blindly overwritten.
                    if len(found)>1 or plain(remote['properties'])!=job['properties']:
                        result['conflicts'].append(job['id']);continue
                    acknowledge(job,remote['id'],remote['url']);result['unchanged']+=1;continue
                remote=notion_request('pages','POST',{'parent':{'data_source_id':ds},'properties':wire(job['properties'])})
                acknowledge(job,remote['id'],remote['url']);result['new']+=1
            else:
                remote=notion_request('pages/'+link['page_id'])
                if digest(plain(remote['properties']))!=link['remote_hash']:
                    result['conflicts'].append(job['id']);continue
                if job['state']=='synced':result['unchanged']+=1;continue
                remote=notion_request('pages/'+link['page_id'],'PATCH',{'properties':wire(job['properties'])})
                acknowledge(job,remote['id'],remote['url']);result['updated']+=1
        log('notion','conflict' if result['conflicts'] else 'ok',json.dumps(result,ensure_ascii=False));return result
    except urllib.error.HTTPError as e:
        log('notion','error','Notion HTTP '+str(e.code));raise ValueError('Notion 返回 HTTP '+str(e.code)+'，请检查目标库权限')
    except urllib.error.URLError:
        log('notion','error','连接 Notion 未完成；重试会先按稳定 ID 检查已有记录')
        raise ValueError('无法连接 Notion；请稍后重试，同步会先核查已有记录以避免重复')
    finally:LOCK.release()

def identifiers(value):
    text=' '.join(str(value.get(k,'')) for k in ['url','DOI','extra','archiveID'])
    found=re.findall(r'(?:arxiv\.org/(?:abs|pdf)/|arxiv[:. ]+)(\d{4}\.\d{4,5})(?:v\d+)?',text,re.I)
    archive=str(value.get('archiveID','')).strip()
    if re.fullmatch(r'\d{4}\.\d{4,5}(?:v\d+)?',archive):found.append(re.sub(r'v\d+$','',archive))
    return {identity for identity in found if 1<=int(identity[2:4])<=12}

def zotero_preview():
    init()
    records=[];server_id=None
    try:
        for start in range(0,3000,100):
            rows,headers=request_json('http://127.0.0.1:23119/api/users/0/items?'+urllib.parse.urlencode({'limit':100,'start':start}),headers={'Zotero-API-Version':'3'})
            server_id=headers.get('Zotero-Server-ID') or headers.get('Zotero-Server-Id') or server_id
            records.extend(rows)
            if len(rows)<100:break
        else:raise ValueError('文库超过 3000 个对象，请缩小范围后再导入')
    except urllib.error.HTTPError as e:
        if e.code==403:raise ValueError('Zotero 本地 API 未开启：设置 → 高级 → 允许此计算机上的其他应用与 Zotero 通信')
        raise ValueError('Zotero 返回 HTTP '+str(e.code))
    except urllib.error.URLError:raise ValueError('请先在 Mac 上打开 Zotero')
    if not server_id and records:
        # Old clients have no instance header: do not mix cached objects across libraries.
        libraries=sorted({json.dumps(x.get('library',{}),sort_keys=True) for x in records})
        if not libraries or libraries==['{}']:raise ValueError('无法识别 Zotero 文库，请升级客户端后重试')
        server_id='legacy-'+digest(libraries)[:20]
    data={r['key']:r['data'] for r in records}
    papers={x['id'].split(':',1)[1]:x for x in storage.all_items() if x['id'].startswith('arxiv:')}
    matches={}
    for key,d in data.items():
        matched=[papers[i] for i in identifiers(d) if i in papers]
        if len(matched)==1:matches[key]=matched[0]['id']
    preview=[]
    for key,d in data.items():
        if d.get('itemType')!='annotation':continue
        attachment=d.get('parentItem');parent=data.get(attachment,{}).get('parentItem');item_id=matches.get(parent)
        if not item_id:continue
        try:position=json.loads(d.get('annotationPosition') or '{}')
        except ValueError:position={}
        page=position.get('pageIndex');page=page+1 if isinstance(page,int) else None
        row={'id':server_id+':'+key,'item_id':item_id,'page':d.get('annotationPageLabel') or str(page or ''),'quote':d.get('annotationText',''),'comment':d.get('annotationComment',''),'source':'zotero://open-pdf/library/items/'+attachment+'?annotation='+key+('&page='+str(page) if page else ''),'version':d.get('version',0)}
        preview.append(row)
    with storage.db() as c:
        c.execute('DELETE FROM zotero_preview')
        for row in preview:c.execute('INSERT INTO zotero_preview VALUES (?,?)',(row['id'],json.dumps(row,ensure_ascii=False)))
    log('zotero','preview','匹配 '+str(len(matches))+' 篇文献，预览 '+str(len(preview))+' 条批注')
    return {'matched':len(matches),'annotations':preview}

def import_annotations(ids):
    init()
    if not isinstance(ids,list) or len(ids)>3000 or not all(isinstance(i,str) for i in ids):raise ValueError('无效批注选择')
    with storage.db() as c:
        rows=[]
        for identity in set(ids):
            r=c.execute('SELECT payload FROM zotero_preview WHERE id=?',(identity,)).fetchone()
            if not r:raise ValueError('预览已变化，请重新检查')
            rows.append((identity,json.loads(r[0])))
        for identity,row in rows:c.execute('INSERT OR REPLACE INTO zotero_annotations VALUES (?,?,?,?)',(identity,row['item_id'],json.dumps(row,ensure_ascii=False),storage.now()))
    log('zotero','ok','导入 '+str(len(rows))+' 条批注');return {'imported':len(rows)}

def annotations(item_id):
    init()
    with storage.db() as c:return [json.loads(r[0]) for r in c.execute('SELECT payload FROM zotero_annotations WHERE item_id=?',(item_id,))]
