import argparse
import io
import json
import mimetypes
import re
import signal
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
from . import storage, collectors
from . import exports, integration_sync, mobile, connection, deep_read, briefs, frontier, reading_queue
from .access import Access, local_ipv4
from .catalog import TOPICS, SOURCES
PUBLIC=storage.ROOT/"public"
TOPIC_IDS={t["id"] for t in TOPICS}
READING={"unread","reading","read"}
LEVELS={"摘要筛选","全文分析","代码核查"}
IDEA_STATUSES={"待调研","待验证","实验中","已归档"}
class ValidationError(ValueError): pass
def require(condition,message):
    if not condition: raise ValidationError(message)
def safe_string(obj,key,limit=20000,default=""):
    value=obj.get(key,default)
    require(isinstance(value,str),key+" 必须为文本")
    require(len(value)<=limit,key+" 过长")
    return value.strip()
def idea_payload(body):
    title=safe_string(body,"title",240); require(bool(title),"请填写选题标题")
    topic=body.get("topic","vla"); status=body.get("status","待调研")
    require(isinstance(topic,str) and topic in TOPIC_IDS,"无效研究方向"); require(isinstance(status,str) and status in IDEA_STATUSES,"无效选题状态")
    item_id=body.get("item_id") or None
    require(item_id is None or isinstance(item_id,str),"无效关联文献")
    require(item_id is None or storage.get_item(item_id) is not None,"关联文献不存在")
    return {"title":title,"topic":topic,"status":status,**{k:safe_string(body,k) for k in ["observation","evidence","hypothesis","experiment"]},"item_id":item_id}
def recommend(items,focus):
    def score(x):
        try: age=max(0,(datetime.now(timezone.utc).date()-datetime.fromisoformat(x["updated"][:10]).date()).days)
        except (ValueError,TypeError): age=365
        return (12 if x["kind"]=="paper" else 0)+sum(5 for t in x["topics"] if t in focus)+(15 if not x["curated"] and age<=14 else 0)+(5 if x["reading"]=="unread" else -10 if x["reading"]=="read" else 0)+max(0,10-age/3)
    return sorted(items,key=score,reverse=True)
def idea_markdown(idea):
    return "# "+idea["title"]+"\n\n- 状态："+idea["status"]+"\n- 方向："+idea["topic"]+"\n\n"+"\n\n".join("## "+label+"\n\n"+(idea[key] or "待补充") for key,label in [("observation","问题观察"),("evidence","支持证据与相关工作"),("hypothesis","待验证假设"),("experiment","最小验证实验")])+"\n"
def write_idea(idea):
    folder=storage.DATA/"ideas"; folder.mkdir(parents=True,exist_ok=True)
    (folder/(idea["id"]+".md")).write_text(idea_markdown(idea),encoding="utf-8")
class Handler(BaseHTTPRequestHandler):
    server_version="ResearchRadar/1.0"
    def log_message(self,fmt,*args):
        if self.path.startswith("/api/sync") and self.command=="GET": return
        super().log_message(fmt,*args)
    def respond(self,status,payload,ctype="application/json; charset=utf-8",filename=None,headers=None):
        raw=json.dumps(payload,ensure_ascii=False).encode() if ctype.startswith("application/json") else payload.encode() if isinstance(payload,str) else payload
        self.send_response(status)
        for k,v in {"Content-Type":ctype,"Content-Length":str(len(raw)),"X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","Cache-Control":"no-store","Content-Security-Policy":"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"}.items(): self.send_header(k,v)
        for key,value in (headers or {}).items(): self.send_header(key,value)
        if filename: self.send_header("Content-Disposition",'attachment; filename="'+filename+'"')
        self.end_headers(); self.wfile.write(raw)
    def body(self):
        try: length=int(self.headers.get("Content-Length","0"))
        except ValueError: raise ValidationError("请求长度无效")
        require(0<=length<=(600000 if self.path=="/api/mobile/commit" else 200000),"请求体过大")
        try: value=json.loads(self.rfile.read(length))
        except (ValueError,TypeError): raise ValidationError("请求必须为 JSON")
        require(isinstance(value,dict),"请求必须为对象")
        return value
    def valid_host(self):
        allowed=getattr(self.server,"allowed_hosts",["127.0.0.1:"+str(self.server.server_port),"localhost:"+str(self.server.server_port)])
        return self.headers.get("Host","").lower() in [h.lower() for h in allowed]
    def mutation_allowed(self):
        host=self.headers.get("Host",""); origin=self.headers.get("Origin")
        require(self.valid_host(),"无效访问主机")
        require(not origin or origin=="http://"+host,"不允许跨站写入")
    def do_GET(self): self.dispatch("GET")
    def do_POST(self): self.dispatch("POST")
    def do_PATCH(self): self.dispatch("PATCH")
    def do_DELETE(self): self.dispatch("DELETE")
    def dispatch(self,method):
        try:
            parsed=urlparse(self.path); path=unquote(parsed.path); query=parse_qs(parsed.query)
            require(self.valid_host(),"无效访问主机")
            if method!="GET": self.mutation_allowed()
            access=getattr(self.server,"access",None)
            if path=="/api/discovery" and method=="GET":
                return self.respond(200,{"id":connection.identity(),"name":"具身研究台","protocol":1})
            if path=="/api/login" and method=="POST":
                if access is None: return self.respond(200,{"ok":True})
                status,token=access.login(self.body().get("code"),self.client_address[0])
                if status!=200: return self.respond(status,{"error":"尝试次数较多，请 5 分钟后重试" if status==429 else "访问码不正确"})
                return self.respond(200,{"ok":True},headers={"Set-Cookie":"radar_session="+token+"; Path=/; HttpOnly; SameSite=Strict; Max-Age=604800"})
            if access and not access.authenticated(self):
                if path.startswith("/api/"): return self.respond(401,{"error":"请先输入访问码"})
                if method!="GET": return self.respond(401,{"error":"请先输入访问码"})
                if path not in ["/styles.css","/radar.svg","/login.js"]:
                    return self.respond(200,(PUBLIC/"login.html").read_bytes(),"text/html; charset=utf-8")
            if path=="/login" and method=="GET":
                return self.respond(200,(PUBLIC/"login.html").read_bytes(),"text/html; charset=utf-8")
            if path=="/api/health" and method=="GET": return self.respond(200,{"ok":True,"version":"1.0"})
            if path in ['/api/content','/api/content/manifest'] and method=='GET':
                from . import public_content
                content=public_content.package()
                return self.respond(200,content['manifest'] if path.endswith('/manifest') else content)
            if path=='/api/content/reading' and method=='GET':
                from . import public_content
                content=public_content.package();iid=query.get('item_id',[''])[0]
                if query.get('version',[''])[0]!=content['version']:return self.respond(412,{'error':'内容版本已更新，请重新同步。'})
                if iid not in content['readings']:return self.respond(404,{'error':'这项材料尚未通过当前版本展示检查。'})
                return self.respond(200,{'version':content['version'],'item_id':iid,'reading_version':content['manifest']['reading_versions'][iid],'reading':content['readings'][iid]})
            if path=='/api/content/receipt' and method=='POST':
                from . import public_content,content_delivery
                try:return self.respond(200,content_delivery.acknowledge(self.body(),public_content.package()['manifest']))
                except ValueError as exc:raise ValidationError(str(exc))
            if path=='/api/content/delivery' and method=='GET':
                from . import public_content,content_delivery
                try:return self.respond(200,content_delivery.status(query.get('device',[''])[0],public_content.package()['manifest']))
                except ValueError as exc:raise ValidationError(str(exc))
            if path=="/api/pairing" and method=="GET": return self.respond(200,connection.pairing(getattr(self.server,'pairing_port',self.server.server_port)))
            if path=="/api/pairing/access-code" and method=="GET":
                host=self.headers.get('Host','').split(':')[0].lower()
                if self.client_address[0]!='127.0.0.1' or host not in ['localhost','127.0.0.1']:
                    return self.respond(403,{'error':'请在 Mac 本机的配对页查看访问码'})
                return self.respond(200,{'code':access.code if access else ''})
            if path=='/api/reading-queue' or path.startswith('/api/reading-queue/'):
                try:
                    if path=='/api/reading-queue':
                        if method=='GET':return self.respond(200,reading_queue.snapshot())
                        if method=='POST':
                            body=self.body();require(set(body)=={'item_id'} and isinstance(body['item_id'],str),'无效精读任务')
                            task_id=reading_queue.enqueue(body['item_id'])
                            return self.respond(202,{'task_id':task_id,'queue':reading_queue.snapshot()})
                    elif method=='POST':
                        body=self.body();require(set(body)=={'action','revision'} and isinstance(body['action'],str) and type(body['revision']) is int,'无效任务操作')
                        reading_queue.action(path[len('/api/reading-queue/'):],body['action'],body['revision'])
                        return self.respond(200,{'queue':reading_queue.snapshot()})
                except reading_queue.Conflict as exc:return self.respond(409,{'error':str(exc),'queue':reading_queue.snapshot()})
                except ValueError as exc:raise ValidationError(str(exc))
                return self.respond(404,{'error':'接口不存在'})
            if path.startswith('/api/reading/'):
                iid=path[len('/api/reading/'):]
                item=storage.get_item(iid)
                from . import research_material
                if not research_material.supported(item):return self.respond(404,{'error':'研究材料不存在或来源不受支持'})
                if method=='GET':return self.respond(200,deep_read.state(iid))
                if method=='POST':
                    body=self.body();require(set(body)<={'model'} and type(body.get('model',False)) is bool,'无效精读请求')
                    try:return self.respond(202,deep_read.start(iid,body.get('model',False)))
                    except ValueError as exc:raise ValidationError(str(exc))
            if path=="/api/state" and method=="GET":
                items=storage.all_items(); prefs=storage.settings(); ranked=recommend(items,prefs["focus"])
                with storage.db() as c:
                    ideas=[dict(r) for r in c.execute("SELECT * FROM ideas ORDER BY updated DESC")]
                    sessions=[dict(r) for r in c.execute("SELECT * FROM sessions ORDER BY day DESC LIMIT 60")]
                return self.respond(200,{"items":items,"technology_briefs":briefs.build(items),**frontier.build(items),"reading_queue":reading_queue.snapshot(),"topics":TOPICS,"sources":storage.source_states(),"ideas":ideas,"settings":prefs,"sessions":sessions,"sync":collectors.state(),"recommended":[x["id"] for x in ranked[:12]],"integrations":integration_sync.status(),"server_time":storage.now()})
            if path=='/api/mobile/commit' and method=='POST':
                command=self.body()
                try:
                    return self.respond(200,mobile.commit(command,idea_payload))
                except mobile.Conflict as exc:
                    return self.respond(409,{'error':'进展版本或处理状态已变化，请刷新后重试' if command.get('kind')=='frontier' else '服务器内容已变化，本机草稿已保留','current':exc.current})
                except (ValueError,TypeError) as exc:
                    raise ValidationError(str(exc))
            if path=="/api/sync":
                if method=="GET": return self.respond(200,collectors.state())
                if method=="POST":
                    started=collectors.start_sync()
                    return self.respond(202,{**collectors.state(),"started":started})
            if path.startswith('/api/integrations/') and path!='/api/integrations/export':
                try:
                    if path=='/api/integrations/status' and method=='GET': return self.respond(200,integration_sync.status())
                    if path=='/api/integrations/zotero/preview' and method=='POST': return self.respond(200,integration_sync.zotero_preview())
                    if path=='/api/integrations/zotero/import' and method=='POST': return self.respond(200,integration_sync.import_annotations(self.body().get('ids')))
                    if path=='/api/integrations/notion/sync' and method=='POST': return self.respond(200,integration_sync.sync_notion())
                except ValueError as exc:
                    raise ValidationError(str(exc))
            if path=="/api/integrations/export" and method=="GET":
                target=query.get('target',[''])[0]
                require(target in {'zotero','notion','obsidian'},'无效的导出目标')
                try:
                    items=exports.select_items(query.get('scope',['selected'])[0],query.get('item_id',[None])[0])
                except ValueError as exc:
                    raise ValidationError(str(exc))
                if target=='zotero':
                    papers=[x for x in items if x['kind']=='paper']
                    require(bool(papers),'该范围没有论文，请先收藏论文或选择全部内容')
                    return self.respond(200,exports.ris(papers),'application/x-research-info-systems; charset=utf-8','research-papers.ris')
                with storage.db() as c:
                    ideas=[dict(r) for r in c.execute('SELECT * FROM ideas ORDER BY updated DESC')]
                return self.respond(200,exports.bundle(target,items,ideas),'application/zip','research-'+target+'.zip')
            if path.startswith("/api/items/"):
                iid=path[len("/api/items/"):]; item=storage.get_item(iid)
                if not item: return self.respond(404,{"error":"文献不存在"})
                if method=="GET":
                    if query.get("format")==["markdown"]: return self.respond(200,storage.markdown(item),"text/markdown; charset=utf-8","reading-note.md")
                    item["zotero_annotations"]=integration_sync.annotations(iid)
                    return self.respond(200,item)
                if method=="PATCH":
                    value=self.body(); require(set(value)<={"saved","reading","notes","note_level"},"存在不支持的字段")
                    if "saved" in value: require(type(value["saved"]) is bool,"收藏状态必须为布尔值")
                    if "reading" in value: require(isinstance(value["reading"],str) and value["reading"] in READING,"无效阅读状态")
                    if "note_level" in value: require(isinstance(value["note_level"],str) and value["note_level"] in LEVELS,"无效分析程度")
                    if "notes" in value: value["notes"]=safe_string(value,"notes",60000)
                    if value:
                        value["note_updated"]=storage.now()
                        with storage.db() as c: c.execute("UPDATE items SET "+",".join(k+"=?" for k in value)+" WHERE id=?",list(value.values())+[iid])
                    item=storage.get_item(iid); storage.write_note(item)
                    return self.respond(200,item)
            if path=="/api/ideas" and method=="POST":
                value=idea_payload(self.body()); stamp=storage.now()
                value.update(id=uuid.uuid4().hex,created=stamp,updated=stamp)
                with storage.db() as c: c.execute("INSERT INTO ideas("+",".join(value)+") VALUES ("+",".join("?" for _ in value)+")",list(value.values()))
                write_idea(value); return self.respond(201,value)
            if path.startswith("/api/ideas/"):
                iid=path[len("/api/ideas/"):]
                with storage.db() as c: old=c.execute("SELECT * FROM ideas WHERE id=?",(iid,)).fetchone()
                if not old: return self.respond(404,{"error":"选题不存在"})
                if method=="PATCH":
                    value=idea_payload({**dict(old),**self.body()}); value["updated"]=storage.now()
                    with storage.db() as c: c.execute("UPDATE ideas SET "+",".join(k+"=?" for k in value)+" WHERE id=?",list(value.values())+[iid])
                    value={**dict(old),**value}; write_idea(value); return self.respond(200,value)
                if method=="DELETE":
                    with storage.db() as c: c.execute("DELETE FROM ideas WHERE id=?",(iid,))
                    target=storage.DATA/"ideas"/(iid+".md")
                    if target.exists(): target.unlink()
                    return self.respond(200,{"ok":True})
            if path=="/api/settings" and method=="PATCH":
                value=self.body(); require(set(value)<={"focus","auto_sync","interval_minutes"},"不支持的设置")
                if "focus" in value: require(isinstance(value["focus"],list) and len(value["focus"])<=8 and all(isinstance(t,str) and t in TOPIC_IDS for t in value["focus"]),"无效关注方向")
                if "auto_sync" in value: require(type(value["auto_sync"]) is bool,"自动更新必须为布尔值")
                if "interval_minutes" in value: require(type(value["interval_minutes"]) is int and 60<=value["interval_minutes"]<=1440,"间隔应为 60—1440 分钟")
                with storage.db() as c:
                    for k,v in value.items(): c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)",(k,json.dumps(v,ensure_ascii=False)))
                return self.respond(200,storage.settings())
            if path.startswith("/api/sources/") and method=="PATCH":
                sid=path[len("/api/sources/"):]; value=self.body()
                require(sid in {s["id"] for s in SOURCES if s["collector"]!="manual"},"该来源仅支持手动访问")
                require(set(value)=={"enabled"} and type(value["enabled"]) is bool,"无效源设置")
                with storage.db() as c: c.execute("UPDATE sources SET enabled=? WHERE id=?",(int(value["enabled"]),sid))
                return self.respond(200,{"ok":True})
            if path=="/api/session" and method=="POST":
                value=self.body(); day=value.get("day",""); step=value.get("step",0)
                require(isinstance(day,str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}",day) is not None,"无效日期")
                require(type(step) is int and 0<=step<=3,"无效进度")
                with storage.db() as c: c.execute("INSERT OR REPLACE INTO sessions(day,step) VALUES (?,?)",(day,step))
                return self.respond(200,{"day":day,"step":step})
            if path=="/api/export" and method=="GET":
                output=io.BytesIO()
                with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as z:
                    items=storage.all_items()
                    with storage.db() as c: ideas=[dict(r) for r in c.execute("SELECT * FROM ideas")]
                    z.writestr("research-library.json",json.dumps({"exported":storage.now(),"items":items,"ideas":ideas,"settings":storage.settings(),"zotero_annotations":[r for item in items for r in integration_sync.annotations(item["id"])]},ensure_ascii=False,indent=2))
                    z.writestr("reading-evidence.json",json.dumps(deep_read.export_snapshot(),ensure_ascii=False,indent=2))
                    z.writestr("reading-queue.json",json.dumps(reading_queue.export_snapshot(),ensure_ascii=False,indent=2))
                    z.writestr("frontier-states.json",json.dumps(frontier.snapshot_states(),ensure_ascii=False,indent=2))
                    for item in items:
                        if item["notes"] or item["saved"]: z.writestr("notes/"+re.sub(r"[^a-zA-Z0-9_.-]","-",item["id"])+".md",storage.markdown(item))
                    for idea in ideas: z.writestr("ideas/"+idea["id"]+".md",idea_markdown(idea))
                return self.respond(200,output.getvalue(),"application/zip","research-radar-backup.zip")
            if method=="GET" and not path.startswith("/api/"):
                if path=='/pair':path='/pair.html'
                target=(PUBLIC/(path.lstrip("/") or "index.html")).resolve()
                if PUBLIC.resolve() not in target.parents or not target.is_file(): return self.respond(404,"Not found","text/plain")
                ctype=mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if ctype.startswith("text/") or ctype=="application/javascript": ctype+="; charset=utf-8"
                return self.respond(200,target.read_bytes(),ctype)
            return self.respond(404,{"error":"接口不存在"})
        except ValidationError as exc: self.respond(400,{"error":str(exc)})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception as exc:
            print("Request error:",repr(exc),flush=True)
            self.respond(500,{"error":"操作未完成，请查看本地服务日志"})
def scheduler():
    while True:
        try:
            prefs=storage.settings()
            if prefs["auto_sync"] and not collectors.state()["running"]:
                due=False
                for s in storage.source_states():
                    if not s["enabled"] or s["collector"]=="manual": continue
                    try: age=(datetime.now(timezone.utc)-datetime.fromisoformat(s["last_attempt"])).total_seconds() if s["last_attempt"] else float("inf")
                    except ValueError: age=float("inf")
                    if age>=prefs["interval_minutes"]*60: due=True
                if due: collectors.start_sync()
        except Exception as exc: print("Scheduler:",repr(exc),flush=True)
        time.sleep(30)
def main():
    p=argparse.ArgumentParser(description="Embodied Research Radar")
    p.add_argument("--port",type=int,default=8765); p.add_argument("--no-auto-sync",action="store_true")
    p.add_argument("--lan",action="store_true",help="Allow LAN access with a private access code")
    args=p.parse_args(); storage.init(); deep_read.init();reading_queue.init()
    with storage.db() as c:c.execute("UPDATE reading_jobs SET status='error',message='上次读取因服务重启中断，请重试' WHERE status='running'")
    server=ThreadingHTTPServer(("0.0.0.0" if args.lan else "127.0.0.1",args.port),Handler)
    addresses=local_ipv4() if args.lan else ["127.0.0.1"]
    server.allowed_hosts=[host+":"+str(args.port) for host in addresses+["localhost",connection.local_hostname()]]
    server.access=Access() if args.lan else None
    signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
    if not args.no_auto_sync: threading.Thread(target=scheduler,daemon=True).start()
    queue_stop=threading.Event();queue_owner=uuid.uuid4().hex
    threading.Thread(target=reading_queue.worker,args=(queue_stop,queue_owner),daemon=True).start()
    print("Research Radar ready: http://127.0.0.1:"+str(args.port),flush=True)
    if args.lan:
        connection.advertise(args.port)
        for address in addresses:
            if address!="127.0.0.1" and not address.startswith("198.18."):
                print("Mobile: http://"+address+":"+str(args.port),flush=True)
        print("Pair iPhone: http://127.0.0.1:"+str(args.port)+"/pair",flush=True)
        print("Access code file: "+str(storage.DATA/'access-code.txt'),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nResearch Radar stopped. Data: "+str(storage.DATA),flush=True)
    finally:
        queue_stop.set();reading_queue.release_owner(queue_owner)
        connection.stop();server.server_close()
if __name__=="__main__": main()
