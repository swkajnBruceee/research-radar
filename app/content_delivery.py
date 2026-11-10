"""Authenticated clients report a fully saved public package, separate from login."""
import json
import re
import uuid
from . import storage

def init(c):
    c.execute('CREATE TABLE IF NOT EXISTS content_receipts(device_id TEXT PRIMARY KEY,version TEXT NOT NULL,documents TEXT NOT NULL,received_at TEXT NOT NULL)')

def acknowledge(value,manifest):
    if not isinstance(value,dict) or set(value)!={'device_id','version','documents'}:raise ValueError('内容保存确认字段无效')
    try:device=str(uuid.UUID(value['device_id']))
    except (ValueError,TypeError,AttributeError):raise ValueError('客户端标识无效')
    version=value['version'];documents=value['documents']
    if not isinstance(version,str) or not re.fullmatch(r'[a-f0-9]{64}',version):raise ValueError('内容版本无效')
    if not isinstance(documents,dict) or len(documents)>5000 or any(not isinstance(k,str) or not 1<=len(k)<=250 or not isinstance(v,str) or not re.fullmatch(r'[a-f0-9]{64}',v) for k,v in documents.items()):raise ValueError('文档保存清单无效')
    with storage.db() as c:
        init(c)
        stamp=storage.now()
        c.execute('INSERT OR REPLACE INTO content_receipts VALUES (?,?,?,?)',(device,version,json.dumps(documents,sort_keys=True),stamp))
    return {'received_at':stamp,'version':version,'count':len(documents),
            'current':version==manifest['version'] and documents==manifest['documents'],
            'notice':'客户端报告内容已保存；此确认不代表用户已经阅读。'}

def status(device_id,manifest):
    try:device=str(uuid.UUID(device_id))
    except (ValueError,TypeError,AttributeError):raise ValueError('客户端标识无效')
    with storage.db() as c:
        init(c);row=c.execute('SELECT * FROM content_receipts WHERE device_id=?',(device,)).fetchone()
    if not row:return {'received':False,'current':False,'count':0,'latest_count':manifest['count']}
    return {'received':True,'current':row['version']==manifest['version'] and json.loads(row['documents'])==manifest['documents'],
            'version':row['version'],'received_at':row['received_at'],'count':len(json.loads(row['documents'])),'latest_count':manifest['count']}
