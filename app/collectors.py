"""Bounded public-source ingestion. Preserves original evidence, not AI conclusions."""
import email.utils
import hashlib
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone,timedelta
from html import unescape
from html.parser import HTMLParser
from . import storage,attention
from .catalog import TOPICS
LOCK=threading.Lock()
STATE_LOCK=threading.Lock()
STATE={"running":False,"started":None,"finished":None,"result":None}
def state():
    with STATE_LOCK: return dict(STATE)
def fetch(url,accept="application/json"):
    req=urllib.request.Request(url,headers={"User-Agent":"EmbodiedResearchRadar/1.0 (personal research reader)","Accept":accept})
    with urllib.request.urlopen(req,timeout=18) as r: data=r.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise ValueError("响应过大")
    return data
def compact(raw):
    return re.sub(r"\s+"," ",unescape(re.sub("<[^>]+>"," ",raw or ""))).strip()
def classify(title,summary=""):
    corpus=(title+" "+summary).lower()
    scored=[(sum(1 for k in t["keywords"] if k in corpus),t["id"]) for t in TOPICS]
    return [tid for score,tid in sorted(scored,key=lambda p:-p[0]) if score][:3]
def canonical_arxiv(url):
    match=re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?",url)
    return "arxiv:"+match.group(1) if match else "arxiv:"+hashlib.sha256(url.encode()).hexdigest()[:20]
def parse_feed(data):
    root=ET.fromstring(data); atom="{http://www.w3.org/2005/Atom}"; entries=root.findall(atom+"entry"); result=[]
    for e in entries:
        title=compact(e.findtext(atom+"title","")); url=e.findtext(atom+"id","").replace("http://","https://")
        if "api/errors" in url: raise ValueError(title)
        if not title or "arxiv.org" not in url: continue
        summary=compact(e.findtext(atom+"summary",""))
        pdf=next((x.attrib.get("href","") for x in e.findall(atom+"link") if x.attrib.get("title")=="pdf"),url.replace("/abs/","/pdf/"))
        result.append({"id":canonical_arxiv(url),"title":title,"summary":summary,"url":url,"pdf_url":pdf.replace("http://","https://"),"authors":", ".join(a.findtext(atom+"name","") for a in e.findall(atom+"author")),"source_id":"arxiv","kind":"paper","published":e.findtext(atom+"published","")[:10],"updated":e.findtext(atom+"updated","")[:10],"topics":classify(title,summary)})
    for e in root.findall("./channel/item"):
        url=e.findtext("link","").replace("http://","https://"); title=re.sub(r"\s*\(arXiv:.*$","",compact(e.findtext("title","")))
        if not title or "arxiv.org" not in url: continue
        summary=compact(e.findtext("description",""))
        try: date=email.utils.parsedate_to_datetime(e.findtext("pubDate","")).date().isoformat()
        except (ValueError,TypeError): date=""
        result.append({"id":canonical_arxiv(url),"title":title,"summary":summary,"url":url,"pdf_url":url.replace("/abs/","/pdf/"),"source_id":"arxiv","kind":"paper","published":date,"updated":date,"topics":classify(title,summary)})
    if not entries and root.find("channel") is None and root.tag!=atom+"feed": raise ValueError("无法识别订阅格式")
    return result
class IngestionBatch(list):
    def __init__(self,rows,warnings=(),cursor=None):super().__init__(rows);self.warnings=list(warnings);self.cursor=cursor
    def commit(self):
        if self.cursor is not None:
            with storage.db() as c:c.execute('INSERT OR REPLACE INTO collector_cursors VALUES (?,?)',('arxiv',json.dumps(self.cursor)))

def arxiv():
    query='(cat:cs.RO OR cat:cs.LG OR cat:cs.AI OR cat:cs.CV) AND (all:"robot learning" OR all:"vision-language-action" OR all:"embodied" OR all:"world model" OR all:"manipulation" OR all:"humanoid" OR all:"whole-body" OR all:"locomotion" OR all:"sim-to-real" OR all:"robotics" OR all:"dexterous")'
    def request(**params):
        return parse_feed(fetch('https://export.arxiv.org/api/query?'+urllib.parse.urlencode(params),'application/atom+xml'))
    try:rows=request(search_query=query,sortBy='submittedDate',sortOrder='descending',max_results=100)
    except Exception as primary:
        try:return IngestionBatch(parse_feed(fetch("https://rss.arxiv.org/rss/cs.RO","application/rss+xml"))[:100],['API 未完成，本次仅使用近期 RSS；历史回扫与关键论文追踪待重试。'])
        except Exception as fallback: raise RuntimeError("arXiv API / RSS 均未完成："+str(primary)+"；"+str(fallback))
    warnings=[];pending_cursor=None
    query_hash=hashlib.sha256(query.encode()).hexdigest()
    # Keep a rotating 30-day backfill window. A bounded recent feed cannot be a
    # historical index, and publication age alone cannot identify significance.
    with storage.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS collector_cursors(source TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        saved=c.execute("SELECT payload FROM collector_cursors WHERE source='arxiv'").fetchone()
    today=datetime.now(timezone.utc).date();cutoff=(today-timedelta(days=30)).strftime('%Y%m%d')
    try:cursor=json.loads(saved[0]) if saved else {'start':cutoff,'offset':100}
    except (ValueError,TypeError):cursor={'start':cutoff,'offset':100}
    if not isinstance(cursor,dict) or not isinstance(cursor.get('start'),str) or not re.fullmatch(r'\d{8}',cursor['start']) or type(cursor.get('offset')) is not int or not 100<=cursor['offset']<=100000:
        cursor={'start':cutoff,'offset':100}
    if cursor.get('query_hash')!=query_hash:cursor={'start':cutoff,'end':today.strftime('%Y%m%d'),'offset':100,'query_hash':query_hash}
    end=cursor.get('end',today.strftime('%Y%m%d'))
    if not isinstance(end,str) or not re.fullmatch(r'\d{8}',end):end=today.strftime('%Y%m%d')
    try:
        start=cursor['start'];offset=cursor['offset']
        if not re.fullmatch(r'\d{8}',start) or type(offset) is not int or not 100<=offset<=100000:raise ValueError('回扫位置无效')
        time.sleep(3)
        older=request(search_query=query+' AND submittedDate:['+start+'0000 TO '+end+'2359]',sortBy='submittedDate',sortOrder='descending',start=offset,max_results=200)
        rows.extend(older)
        cursor={'start':cutoff,'end':today.strftime('%Y%m%d'),'offset':100,'query_hash':query_hash} if len(older)<200 else {'start':start,'end':end,'offset':offset+200,'query_hash':query_hash}
        pending_cursor=cursor
    except Exception as exc:warnings.append('历史回扫未完成，位置已保留：'+str(exc)[:160])
    watched=attention.watchlist()
    if watched:
        try:
            time.sleep(3)
            rows.extend(request(id_list=','.join(r['arxiv_id'] for r in watched),max_results=len(watched)))
        except Exception as exc:warnings.append('关键论文版本追踪未完成：'+str(exc)[:160])
    return IngestionBatch(list({r['id']:r for r in rows}.values()),warnings,cursor=pending_cursor)
def github(source):
    from .research_material import release_revision
    topics=["sim","imitation"] if source["id"]=="isaaclab" else ["imitation","vla","data"]
    try:
        data=json.loads(fetch("https://api.github.com/repos/"+source["repo"]+"/releases?per_page=5"))
        if not isinstance(data,list): raise ValueError("发布源未返回列表")
        return [{"id":"github:"+source["repo"]+":"+r["tag_name"],"title":source["name"]+" · "+(r.get("name") or r["tag_name"]),"summary":(r.get("body") or "该版本没有发布说明。")[:14000],"url":r["html_url"],"source_id":source["id"],"kind":"release","published":(r.get("published_at") or "")[:10],"updated":(r.get("updated_at") or r.get("published_at") or "")[:10],"source_revision":release_revision(r),"topics":topics} for r in data if not r.get("draft") and not r.get("prerelease")]
    except Exception as primary:
        # Official public Atom feed works without the GitHub API rate-limit budget.
        try:
            root=ET.fromstring(fetch("https://github.com/"+source["repo"]+"/releases.atom","application/atom+xml"))
            atom="{http://www.w3.org/2005/Atom}"
            if root.tag!=atom+"feed": raise ValueError("发布订阅格式变化")
            rows=[]
            for e in root.findall(atom+"entry")[:5]:
                link=next((r.attrib.get("href","") for r in e.findall(atom+"link") if r.attrib.get("rel","alternate")=="alternate"),"")
                if "/releases/tag/" not in link: continue
                tag=urllib.parse.unquote(link.split("/releases/tag/",1)[1])
                date=e.findtext(atom+"updated","")[:10]
                rows.append({"id":"github:"+source["repo"]+":"+tag,"title":source["name"]+" · "+compact(e.findtext(atom+"title",tag)),"summary":compact(e.findtext(atom+"content",""))[:14000] or "请打开官方发布页面核查版本内容。","url":link,"source_id":source["id"],"kind":"release","published":e.findtext(atom+"published",date)[:10],"updated":date,"source_revision":e.findtext(atom+'updated',''),"topics":topics})
            return rows
        except Exception as fallback:
            raise RuntimeError("GitHub API / 官方订阅均未完成："+str(primary)+"；"+str(fallback))
def huggingface(datasets=False):
    data=json.loads(fetch("https://huggingface.co/api/"+('datasets' if datasets else 'models')+"?author=lerobot&sort=lastModified&direction=-1&limit=10"))
    if not isinstance(data,list): raise ValueError("模型源未返回列表")
    result=[]
    for r in data:
        mid=r["id"]; modified=(r.get("lastModified") or r.get("createdAt") or "")[:10]
        result.append({"id":"hf:"+mid,"title":mid,"summary":"LeRobot 官方组织模型。最近修改时间："+(modified or "来源未提供")+"。这是模型可用性信号，训练设置、许可与评测请查阅模型卡。","url":"https://huggingface.co/"+mid,"source_id":"huggingface","kind":"model","published":(r.get("createdAt") or "")[:10],"updated":modified,"source_revision":r.get('sha') or r.get('lastModified') or r.get('createdAt') or '',"topics":classify(mid,"vision-language-action robot learning")})
        if datasets:result[-1].update(id='hf-dataset:'+mid,url='https://huggingface.co/datasets/'+mid,source_id='huggingface-datasets',kind='dataset',summary='LeRobot 官方组织数据集卡；更新时间不表示数据质量已核查。')
    from . import research_material
    warnings=[]
    for row in result:
        try:
            captured=research_material.snapshot(row,verify=False)
            row['source_revision']=captured['commit'] or captured['revision'];row['summary']=captured['text'][:14000]
        except Exception as exc:warnings.append(row['id']+' 官方卡片全文待重试：'+str(exc)[:90])
    return IngestionBatch(result,warnings)
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a": self.href=dict(attrs).get("href"); self.parts=[]
    def handle_data(self,data):
        if self.href: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.href:
            self.links.append((self.href,compact(" ".join(self.parts)))); self.href=None; self.parts=[]
def pi():
    parser=Links(); parser.feed(fetch("https://www.pi.website/blog","text/html").decode("utf-8","replace")); result=[]
    for href,label in parser.links:
        m=re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})",label)
        if not m: continue
        url=urllib.parse.urljoin("https://www.pi.website/blog",href)
        if urllib.parse.urlparse(url).hostname not in ["www.pi.website","pi.website","www.physicalintelligence.company"]: continue
        title=label[:m.start()].strip()
        if not title: continue
        date=datetime.strptime(m.group(1),"%B %d, %Y").date().isoformat()
        result.append({"id":"pi:"+hashlib.sha256(url.encode()).hexdigest()[:18],"title":title,"summary":label[m.end():].strip() or "机构研究发布，请打开原文核查方法、评测与可用性。","url":url,"source_id":"pi","kind":"industry","published":date,"updated":date,"topics":classify(title,label) or ["vla"]})
    if not result: raise ValueError("博客结构变化，未提取到带日期文章，请打开原始入口")
    from . import research_material
    warnings=[]
    for row in result[:12]:
        try:
            captured=research_material.snapshot(row,verify=False)
            row['source_revision']=captured['revision'];row['summary']=captured['text'][:14000]
        except Exception as exc:warnings.append(row['id']+' 机构正文版本追踪待重试：'+str(exc)[:90])
    return IngestionBatch(result[:12],warnings)
def start_sync():
    if not LOCK.acquire(blocking=False): return False
    with STATE_LOCK: STATE.update(running=True,started=storage.now(),finished=None,result=None)
    threading.Thread(target=run_sync,daemon=True).start()
    return True
def run_sync():
    result={"new":0,"updated":0,"unchanged":0,"sources":[]}
    try:
        for source in storage.source_states():
            if not source["enabled"] or source["collector"]=="manual": continue
            if source["last_attempt"]:
                try:
                    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(source["last_attempt"])).total_seconds()
                    if elapsed<60:
                        result["sources"].append({"id":source["id"],"status":"skipped","message":"一分钟内不重复请求"}); continue
                except ValueError: pass
            with storage.db() as c: c.execute("UPDATE sources SET last_attempt=? WHERE id=?",(storage.now(),source["id"]))
            try:
                name=source["collector"]
                rows=arxiv() if name=="arxiv" else github(source) if name=="github" else huggingface(name=='huggingface-datasets') if name in ['huggingface','huggingface-datasets'] else pi()
                for row in rows:
                    if row["url"].startswith("https://"): result[storage.upsert(row)]+=1
                if isinstance(rows,IngestionBatch):rows.commit()
                warning='；'.join(getattr(rows,'warnings',[]))
                with storage.db() as c: c.execute("UPDATE sources SET last_success=?,error=?,count=? WHERE id=?",(storage.now(),warning,len(rows),source["id"]))
                result["sources"].append({"id":source["id"],"status":"partial" if warning else "ok","count":len(rows),**({'message':warning} if warning else {})})
            except Exception as exc:
                error=str(exc)[:700]
                with storage.db() as c: c.execute("UPDATE sources SET error=? WHERE id=?",(error,source["id"]))
                result["sources"].append({"id":source["id"],"status":"error","message":error})
    finally:
        try:
            from . import reading_queue
            reading_queue.register_candidates()
        except Exception as exc:print('Reading candidate registration:',repr(exc),flush=True)
        with STATE_LOCK: STATE.update(running=False,finished=storage.now(),result=result)
        LOCK.release()
