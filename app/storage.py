import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .catalog import SEEDS, SOURCES
ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.environ.get("RADAR_DATA_DIR",str(ROOT/"data")))
DB=DATA/"radar.sqlite3"
def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
@contextmanager
def db():
    DATA.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(str(DB),timeout=20); conn.row_factory=sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally: conn.close()
FIELDS=["title","title_zh","summary","authors","url","pdf_url","code_url","source_id","kind","published","updated","topics","curated","analysis","source_revision"]
def init():
    with db() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS items(
        id TEXT PRIMARY KEY,title TEXT NOT NULL,title_zh TEXT DEFAULT '',
        summary TEXT DEFAULT '',authors TEXT DEFAULT '',url TEXT NOT NULL,
        pdf_url TEXT DEFAULT '',code_url TEXT DEFAULT '',source_id TEXT NOT NULL,
        kind TEXT NOT NULL,published TEXT NOT NULL,updated TEXT NOT NULL,
        discovered TEXT NOT NULL,topics TEXT NOT NULL,curated INTEGER DEFAULT 0,
        analysis TEXT DEFAULT '{}',saved INTEGER DEFAULT 0,reading TEXT DEFAULT 'unread',
        notes TEXT DEFAULT '',note_level TEXT DEFAULT '摘要筛选',note_updated TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,item_id TEXT NOT NULL REFERENCES items(id),at TEXT NOT NULL,description TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ideas(id TEXT PRIMARY KEY,title TEXT NOT NULL,topic TEXT NOT NULL,status TEXT NOT NULL,observation TEXT DEFAULT '',evidence TEXT DEFAULT '',hypothesis TEXT DEFAULT '',experiment TEXT DEFAULT '',item_id TEXT,created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,enabled INTEGER NOT NULL,last_attempt TEXT,last_success TEXT,error TEXT DEFAULT '',count INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(day TEXT PRIMARY KEY,step INTEGER DEFAULT 0);
        """)
        if 'source_revision' not in {r['name'] for r in c.execute('PRAGMA table_info(items)')}:c.execute("ALTER TABLE items ADD COLUMN source_revision TEXT DEFAULT ''")
        for s in SOURCES: c.execute("INSERT OR IGNORE INTO sources(id,enabled) VALUES (?,?)",(s["id"],int(s["enabled"])))
        for k,v in {"focus":["vla","imitation","data"],"daily_minutes":30,"auto_sync":True,"interval_minutes":180}.items():
            c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)",(k,json.dumps(v,ensure_ascii=False)))
    for s in SEEDS:
        url="https://arxiv.org/abs/"+s["id"].split(":")[1]
        upsert({"id":s["id"],"title":s["title"],"title_zh":s["title_zh"],"summary":s["summary"],"authors":s["authors"],"url":url,"pdf_url":url.replace("/abs/","/pdf/"),"code_url":s["code"],"source_id":"foundation","kind":"paper","published":s["date"],"updated":s["date"],"topics":s["topics"],"curated":1,"analysis":{k:s[k] for k in ["problem","method","evidence","limitations","question"]}},initial=True)
def upsert(item,initial=False):
    value={"title_zh":"","summary":"","authors":"","pdf_url":"","code_url":"","curated":0,"analysis":{},"topics":[],"source_revision":"",**item}
    for field in ["topics","analysis"]: value[field]=json.dumps(value[field],ensure_ascii=False)
    with db() as c:
        old=c.execute("SELECT * FROM items WHERE id=?",(value["id"],)).fetchone()
        if not old:
            c.execute("INSERT INTO items(id,"+",".join(FIELDS)+",discovered) VALUES ("+",".join("?" for _ in range(len(FIELDS)+2))+")",[value["id"]]+[value[k] for k in FIELDS]+[now()])
            c.execute("INSERT INTO events(item_id,at,description) VALUES (?,?,?)",(value["id"],now(),"基础阅读卡已加入" if initial else "首次采集"))
            return "new"
        if initial: return "unchanged"
        if 'source_revision' not in item:value['source_revision']=old['source_revision']
        if old["code_url"] and not value["code_url"]: value["code_url"]=old["code_url"]
        changed=any(old[k]!=value[k] for k in ["title","updated","code_url","source_revision"]) or (not old["curated"] and old["summary"]!=value["summary"])
        mutable=[k for k in FIELDS if k not in ["analysis","title_zh","curated"]]
        if old["curated"]: mutable=[k for k in mutable if k not in ["summary","topics","source_id"]]
        c.execute("UPDATE items SET "+",".join(k+"=?" for k in mutable)+" WHERE id=?",[value[k] for k in mutable]+[value["id"]])
        if changed: c.execute("INSERT INTO events(item_id,at,description) VALUES (?,?,?)",(value["id"],now(),"来源元数据或版本更新"))
        return "updated" if changed else "unchanged"
def decode(row):
    x=dict(row); x["topics"]=json.loads(x["topics"]); x["analysis"]=json.loads(x["analysis"])
    x["saved"]=bool(x["saved"]); x["curated"]=bool(x["curated"])
    return x
def settings():
    with db() as c: return {r["key"]:json.loads(r["value"]) for r in c.execute("SELECT * FROM settings")}
def all_items():
    with db() as c: return [decode(r) for r in c.execute("SELECT * FROM items ORDER BY updated DESC,published DESC")]
def get_item(item_id):
    with db() as c:
        r=c.execute("SELECT * FROM items WHERE id=?",(item_id,)).fetchone()
        if not r: return None
        item=decode(r)
        item["events"]=[dict(e) for e in c.execute("SELECT at,description FROM events WHERE item_id=? ORDER BY id DESC LIMIT 15",(item_id,))]
        return item
def source_states():
    with db() as c: rows={r["id"]:dict(r) for r in c.execute("SELECT * FROM sources")}
    return [{**s,**rows[s["id"]],"enabled":bool(rows[s["id"]]["enabled"])} for s in SOURCES]
def markdown(item):
    parts=["# "+(item["title_zh"] or item["title"]),"",item["title"],"","- 来源："+item["url"],"- 发表时间："+item["published"],"- 分析程度："+item["note_level"],"- 阅读状态："+item["reading"],"","## 摘要或导读","",item["summary"]]
    for k,label in [("problem","研究问题"),("method","方法机制"),("evidence","证据核查"),("limitations","局限"),("question","候选问题（待验证）")]:
        if item["analysis"].get(k): parts+=["","## "+label,"",item["analysis"][k]]
    parts+=["","## 我的精读笔记","",item["notes"] or "尚未填写。",""]
    from . import integration_sync
    evidence=integration_sync.annotations(item['id'])
    if evidence:
        parts+=['','## Zotero 阅读证据','']
        for row in evidence:
            parts+=['第 '+row['page']+' 页 · '+row['source'],'',row['quote'],'',row['comment'],'']
    return "\n".join(parts)
def write_note(item):
    folder=DATA/"notes"; folder.mkdir(parents=True,exist_ok=True)
    filename=re.sub(r"[^a-zA-Z0-9_.-]","-",item["id"])+".md"
    (folder/filename).write_text(markdown(item),encoding="utf-8")
