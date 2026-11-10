"""Reviewed explanations are separate from automatically collected paper metadata."""
import json
from . import storage

def build(items):
    catalog=json.loads((storage.ROOT/'content/technologies.json').read_text(encoding='utf-8'))
    for brief in catalog:
        sources={s['item_id'] for s in brief['sources']}
        candidates=[]
        for item in items:
            if item['id'] in sources or item['kind']!='paper':continue
            text=(item['title']+' '+item['summary']).lower()
            if any(word in text for word in brief['keywords']):candidates.append(item)
        brief['related_ids']=[i['id'] for i in sorted(candidates,key=lambda i:i['updated'],reverse=True)[:8]]
        brief['source_item_ids']=[s['item_id'] for s in brief['sources'] if any(i['id']==s['item_id'] for i in items)]
    return catalog
