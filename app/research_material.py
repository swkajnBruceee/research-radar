"""Capture complete official release notes/model cards as versioned public evidence.

Only configured publishers are accepted. Links and code are never executed.
"""
import hashlib
import json
import re
from urllib.parse import urlparse,unquote,quote
from . import storage
from .catalog import SOURCES

def release_revision(data):
    # GitHub does not consistently expose a release-level updated_at. Hash the
    # complete notes, not publication date or mutable asset download counters.
    return 'notes:'+hashlib.sha256(json.dumps({k:data.get(k) for k in ['tag_name','name','body']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def supported(item):
    if not item:return False
    item=dict(item);url=urlparse(item['url'])
    if url.scheme!='https' or url.username or url.password or url.port not in [None,443] or url.fragment:return False
    if item['kind']=='paper':return url.hostname=='arxiv.org' and bool(re.fullmatch(r'arxiv:\d{4}\.\d{4,5}',item['id'])) and bool(re.fullmatch('/abs/'+re.escape(item['id'].split(':')[1])+r'(?:v[1-9]\d*)?',url.path))
    source=next((s for s in SOURCES if s['id']==item['source_id']),{})
    if item['kind']=='release' and source.get('collector')=='github':
        prefix='/'+source['repo']+'/releases/tag/'
        return url.hostname=='github.com' and unquote(url.path).startswith(prefix) and item['id']=='github:'+source['repo']+':'+unquote(url.path)[len(prefix):]
    if item['kind']=='model' and source.get('collector')=='huggingface':
        return url.hostname=='huggingface.co' and bool(re.fullmatch(r'/lerobot/[A-Za-z0-9_.-]+/?',url.path)) and item['id']=='hf:'+url.path.strip('/')
    if item['kind']=='dataset' and source.get('collector')=='huggingface-datasets':
        return url.hostname=='huggingface.co' and bool(re.fullmatch(r'/datasets/lerobot/[A-Za-z0-9_.-]+/?',url.path)) and item['id']=='hf-dataset:'+url.path.strip('/').removeprefix('datasets/')
    return item['kind']=='industry' and source.get('collector')=='pi' and url.hostname in ['www.pi.website','pi.website','www.physicalintelligence.company']

def html_rows(raw):
    from .deep_read import ArticleParser
    class OfficialPageParser(ArticleParser):
        def handle_starttag(self,tag,attrs):
            super().handle_starttag(tag,attrs)
            classes=dict(attrs).get('class','').split()
            if self.article is None and (tag in ['main','section'] or (tag=='div' and any(c in classes for c in ['prose','markdown-body','article-body','post-content']))):self.article=len(self.stack)
            if self.article is not None and not self.block and tag in ['li','pre','blockquote']:
                self.block={'tag':tag,'depth':len(self.stack),'parts':[],'anchor':next((a for a in reversed(self.anchors) if a),'')}
        def handle_endtag(self,tag):
            if self.block and tag in self.stack and len(self.stack)-self.stack[::-1].index(tag)==self.block['depth'] and not self.block['tag'].startswith('h'):
                text=re.sub(r'\s+',' ',' '.join(self.block['parts'])).strip()
                if text and len(text)<30:
                    self.passages.append({'text':text,'section':self.section,'location':self.section,'kind':self.block['tag'],'preserve_short':True});self.block=None
            super().handle_endtag(tag)
    parser=OfficialPageParser();parser.feed(raw.decode('utf-8','replace'))
    return parser.passages

def snapshot(item,verify=True):
    from . import collectors,deep_read
    item=dict(item)
    if not supported(item) or item['kind']=='paper':raise ValueError('仅准备已配置信息源的官方发布材料')
    parsed=urlparse(item['url']);source=next(s for s in SOURCES if s['id']==item['source_id'])
    url=item['url'];kind='markdown';commit=''
    if item['kind']=='release':
        tag=unquote(parsed.path).split('/releases/tag/',1)[1]
        raw=collectors.fetch('https://api.github.com/repos/'+source['repo']+'/releases/tags/'+quote(tag,safe=''))
        data=json.loads(raw)
        if data.get('draft') or data.get('prerelease') or unquote(data.get('html_url','')).rstrip('/')!=unquote(url).rstrip('/'):raise ValueError('官方发布标识与候选不符')
        revision=release_revision(data) if item.get('source_revision','').startswith('notes:') else (data.get('updated_at') or data.get('published_at') or '')
        text=(data.get('name') or data['tag_name'])+'\n\n'+(data.get('body') or '')
        rows=[{'text':p,'section':'官方发布说明','location':'官方发布说明','kind':'paragraph','preserve_short':True} for p in re.split(r'\n\s*\n',text) if p.strip()]
    elif item['kind'] in ['model','dataset']:
        model=parsed.path.strip('/');repo=model.removeprefix('datasets/')
        pinned=item.get('source_revision','')
        data={'sha':pinned} if re.fullmatch(r'[a-f0-9]{40,64}',pinned) else json.loads(collectors.fetch('https://huggingface.co/api/'+('datasets/' if item['kind']=='dataset' else 'models/')+repo))
        sha=data.get('sha','')
        if not re.fullmatch(r'[a-f0-9]{40,64}',sha):raise ValueError('模型卡没有可固定的提交版本')
        commit=sha
        raw=collectors.fetch('https://huggingface.co/'+model+'/raw/'+sha+'/README.md','text/plain')
        text=raw.decode('utf-8','replace');url='https://huggingface.co/'+model+'/blob/'+sha+'/README.md'
        revision=sha if re.fullmatch(r'[a-f0-9]{40,64}',item.get('source_revision','')) else (data.get('lastModified') or data.get('createdAt') or '')
        rows=[{'text':p,'section':'固定提交模型卡','location':'模型卡 '+sha[:12],'kind':'paragraph','preserve_short':True} for p in re.split(r'\n\s*\n',text) if p.strip()]
    else:
        raw=collectors.fetch(url,'text/html');rows=html_rows(raw);kind='html'
        text='\n\n'.join(p['text'] for p in rows);revision=hashlib.sha256(text.encode()).hexdigest()
    expected=item.get('source_revision','')
    if verify and expected and revision!=expected:raise deep_read.PreparationError('官方材料已更新，等待采集新版本后重新准备','source_revision',False)
    if len(text.strip())<100:raise deep_read.PreparationError('官方材料缺少足够正文；保留候选，不生成技术结论','no_text',False)
    return {'url':url,'format':kind,'raw':raw,'rows':rows,'revision':revision,'commit':commit,'text':text}

def obtain(item):
    from . import deep_read
    value=snapshot(item)
    passages=deep_read.prepare_passages(value['rows'],value['url'],value['format'])
    if not passages:raise ValueError('未提取到可引用的官方正文')
    content_hash=hashlib.sha256(value['raw']).hexdigest()
    digest=hashlib.sha256((value['url']+'|'+content_hash).encode()).hexdigest()
    folder=storage.DATA/'documents';folder.mkdir(exist_ok=True)
    path=folder/(content_hash+'.source.'+('html' if value['format']=='html' else 'json' if item['kind']=='release' else 'md'))
    if not path.exists():path.write_bytes(value['raw'])
    with storage.db() as c:
        c.execute('INSERT OR REPLACE INTO reading_documents(id,item_id,url,format,passages,fetched,raw_file,source_signature) VALUES (?,?,?,?,?,?,?,?)',
                  (digest,item['id'],value['url'],value['format'],json.dumps(passages,ensure_ascii=False),storage.now(),str(path.relative_to(storage.DATA)),deep_read.signature(item)))
    return digest
