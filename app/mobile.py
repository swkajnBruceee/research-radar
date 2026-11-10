"""Idempotent mobile edits with atomic optimistic concurrency checks."""
import json
import re
from . import storage, frontier

class Conflict(Exception):
    def __init__(self,current): self.current=current

def commit(body,validate_idea):
    command=body.get('id','');kind=body.get('kind');target=body.get('target','');base=body.get('base',{});changes=body.get('changes',{})
    if not isinstance(command,str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}',command):raise ValueError('无效的手机操作标识')
    if kind not in ['item','idea','idea-delete','frontier'] or not isinstance(target,str) or len(target)>300 or not isinstance(base,dict) or not isinstance(changes,dict):raise ValueError('手机同步格式无效')
    item_allowed={'saved','reading','notes','note_level'}
    idea_allowed={'title','topic','status','observation','evidence','hypothesis','experiment','item_id'}
    if kind=='item':
        if not set(changes)<=item_allowed:raise ValueError('不支持的文献字段')
        if 'saved' in changes and type(changes['saved']) is not bool:raise ValueError('收藏格式无效')
        if 'reading' in changes and changes['reading'] not in ['unread','reading','read']:raise ValueError('阅读状态无效')
        if 'note_level' in changes and changes['note_level'] not in ['摘要筛选','全文分析','代码核查']:raise ValueError('分析程度无效')
        if 'notes' in changes and (not isinstance(changes['notes'],str) or len(changes['notes'])>60000):raise ValueError('笔记最多 60000 字符')
    elif kind=='frontier':
        if set(changes)!={'status'} or not isinstance(changes['status'],str) or changes['status'] not in frontier.STATUSES:raise ValueError('无效的进展处理状态')
        if set(base)!={'status','version_signature'}:raise ValueError('进展同步需要原状态与版本')
    elif not set(changes)<=idea_allowed:raise ValueError('不支持的选题字段')
    with storage.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS mobile_receipts(id TEXT PRIMARY KEY,body TEXT NOT NULL,result TEXT NOT NULL)')
        frontier.init(c)
        c.commit();c.execute('BEGIN IMMEDIATE')
        encoded=json.dumps(body,sort_keys=True,ensure_ascii=False)
        receipt=c.execute('SELECT body,result FROM mobile_receipts WHERE id=?',(command,)).fetchone()
        if receipt:
            if receipt['body']!=encoded:raise ValueError('操作标识已被其他内容使用')
            return json.loads(receipt['result'])
        table='items' if kind in ['item','frontier'] else 'ideas'
        old=c.execute('SELECT * FROM '+table+' WHERE id=?',(target,)).fetchone()
        current=storage.decode(old) if old and kind in ['item','frontier'] else dict(old) if old else {}
        if kind=='frontier':
            if not current or current.get('curated'):raise ValueError('该条目不是可处理的新进展')
            previous=c.execute('SELECT * FROM frontier_states WHERE id=?',(target,)).fetchone()
            current=frontier.current(current,previous)
            if current['version_signature']!=base['version_signature'] or (current['status']!=base['status'] and current['status']!=changes['status']):raise Conflict(current)
            current['status']=changes['status']
            c.execute('INSERT OR REPLACE INTO frontier_states VALUES (?,?,?,?)',(target,current['version_signature'],current['status'],storage.now()))
        elif kind=='item':
            if not current:raise Conflict({})
            for field,value in changes.items():
                if field not in base or (current.get(field)!=base[field] and current.get(field)!=value):raise Conflict(current)
            updated={**changes,'note_updated':storage.now()}
            c.execute('UPDATE items SET '+','.join(k+'=?' for k in updated)+' WHERE id=?',list(updated.values())+[target])
            current=storage.decode(c.execute('SELECT * FROM items WHERE id=?',(target,)).fetchone())
        elif kind=='idea':
            if not re.fullmatch(r'[a-zA-Z0-9-]{16,64}',target):raise ValueError('选题标识无效')
            if current:
                if base.get('exists') is False:raise Conflict(current)
                for field,value in changes.items():
                    if field not in base or (current.get(field)!=base[field] and current.get(field)!=value):raise Conflict(current)
            elif base.get('exists') is not False:raise Conflict({})
            value=validate_idea({**current,**changes})
            stamp=storage.now();current={**value,'id':target,'created':current.get('created',stamp),'updated':stamp}
            c.execute('INSERT OR REPLACE INTO ideas('+','.join(current)+') VALUES ('+','.join('?' for _ in current)+')',list(current.values()))
        elif current:
            if any(current.get(k)!=base.get(k) for k in idea_allowed):raise Conflict(current)
            c.execute('DELETE FROM ideas WHERE id=?',(target,));current={}
        result={'ok':True,'record':current}
        c.execute('INSERT INTO mobile_receipts VALUES (?,?,?)',(command,encoded,json.dumps(result,ensure_ascii=False)))
    if kind=='item':storage.write_note(current)
    return result
