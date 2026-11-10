"""Portable, one-way research snapshots. No external account writes."""
import csv
import hashlib
import io
import json
import re
import zipfile
from . import storage
from .catalog import TOPICS

TOPIC_NAMES = {t['id']: t['name'] for t in TOPICS}
READING = {'unread': '未读', 'reading': '在读', 'read': '已读'}

def select_items(scope, item_id=None):
    if item_id:
        item = storage.get_item(item_id)
        if not item:
            raise ValueError('文献不存在')
        return [item]
    if scope not in {'selected', 'all'}:
        raise ValueError('无效的导出范围')
    items = storage.all_items()
    if scope == 'selected':
        return [x for x in items if x['saved'] or x['notes'] or x['reading'] != 'unread']
    return items

def single_line(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def ris(items):
    records = []
    for item in items:
        if item['kind'] != 'paper':
            continue
        lines = ['TY  - UNPB', 'ID  - ' + single_line(item['id']),
                 'TI  - ' + single_line(item['title']), 'UR  - ' + single_line(item['url'])]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', item['published']):
            lines += ['PY  - ' + item['published'][:4], 'DA  - ' + item['published'].replace('-', '/')]
        arxiv = re.fullmatch(r'arxiv:(\d{4}\.\d{4,5})', item['id'])
        if arxiv:
            lines += ['DO  - 10.48550/arXiv.' + arxiv.group(1), 'DB  - arXiv']
        authors = single_line(item['authors'])
        if re.search(r'\bet\s+al\.?', authors, re.I):
            lines.append('N1  - 作者信息不完整，请从原始论文核查：' + authors)
        elif authors:
            lines += ['AU  - ' + author.strip() for author in authors.split(',') if author.strip()]
        else:
            lines.append('N1  - 当前来源未提供作者列表，请从原始论文补全。')
        lines += ['KW  - ' + TOPIC_NAMES.get(t, t) for t in item['topics']]
        if item['summary']:
            lines.append(('N1  - 基础导读：' if item['curated'] else 'AB  - ') + single_line(item['summary']))
        if item['pdf_url']:
            lines.append('L1  - ' + single_line(item['pdf_url']))
        lines += ['N1  - 研究台标记：' + READING[item['reading']] + '；' + item['note_level'], 'ER  - ']
        records.append('\r\n'.join(lines))
    return ('\r\n\r\n'.join(records) + '\r\n').encode('utf-8')

def csv_bytes(headers, rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        # Keep source text from becoming formulas if this CSV is opened in a spreadsheet.
        values = [str(v or '') for v in row]
        writer.writerow(["'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    return output.getvalue().encode('utf-8-sig')

def file_id(kind, value):
    return kind + '-' + hashlib.sha256(value.encode('utf-8')).hexdigest()[:16] + '.md'

def label(value):
    return single_line(value).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]')

def idea_text(idea, items):
    text = '# ' + idea['title'] + '\n\n- 研究方向：' + TOPIC_NAMES.get(idea['topic'], idea['topic']) + '\n- 状态：' + idea['status'] + '\n'
    linked = next((x for x in items if x['id'] == idea['item_id']), None)
    if linked:
        text += '\n起点文献：[' + label(linked['title']) + '](../Papers/' + file_id('paper', linked['id']) + ')\n'
    elif idea['item_id']:
        original = storage.get_item(idea['item_id'])
        if original:
            text += '\n起点文献：' + original['url'] + '\n'
    for key, name in [('observation', '问题观察'), ('evidence', '证据与相关工作'), ('hypothesis', '待验证假设'), ('experiment', '最小验证实验')]:
        text += '\n## ' + name + '\n\n' + (idea[key] or '待补充') + '\n'
    return text

def bundle(target, items, ideas):
    if target not in {'notion', 'obsidian'}:
        raise ValueError('不支持的导出目标')
    output = io.BytesIO()
    stamp = storage.now()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        index = ['# 具身智能研究笔记', '', '导出时间：' + stamp, '',
                 '这是一次性快照，不会自动同步回研究台。个人笔记和候选假设保留原文。', '', '## 文献与笔记', '']
        for item in items:
            filename = 'Papers/' + file_id('paper', item['id'])
            text = storage.markdown(item)
            if target == 'obsidian':
                metadata = {'radar_id': item['id'], 'source': item['url'], 'reading': READING[item['reading']],
                            'analysis_level': item['note_level'], 'tags': ['radar/' + t for t in item['topics']]}
                text = '---\n' + '\n'.join(k + ': ' + json.dumps(v, ensure_ascii=False) for k, v in metadata.items()) + '\n---\n\n' + text
                text += '\n## 研究方向\n\n' + '\n'.join('[' + TOPIC_NAMES.get(t, t) + '](../Topics/' + t + '.md)' for t in item['topics'] if t in TOPIC_NAMES) + '\n'
            archive.writestr(filename, text)
            index.append('- [' + label(item['title_zh'] or item['title']) + '](' + filename + ')')
        index += ['', '## 选题', '']
        for idea in ideas:
            filename = 'Ideas/' + file_id('idea', idea['id'])
            archive.writestr(filename, idea_text(idea, items))
            index.append('- [' + label(idea['title']) + '](' + filename + ')')
        if target == 'notion':
            archive.writestr('papers.csv', csv_bytes(['标题', '原始标题', '稳定ID', '来源', '发表日期', '研究方向', '阅读状态', '分析程度', '我的笔记'],
                [[x['title_zh'] or x['title'], x['title'], x['id'], x['url'], x['published'], ', '.join(TOPIC_NAMES.get(t, t) for t in x['topics']), READING[x['reading']], x['note_level'], x['notes']] for x in items]))
            archive.writestr('ideas.csv', csv_bytes(['标题', '稳定ID', '研究方向', '状态', '问题观察', '证据与相关工作', '待验证假设', '最小实验', '关联文献ID'],
                [[x['title'], x['id'], TOPIC_NAMES.get(x['topic'], x['topic']), x['status'], x['observation'], x['evidence'], x['hypothesis'], x['experiment'], x['item_id']] for x in ideas]))
            instructions = '在 Notion 电脑端或网页端使用导入：papers.csv 与 ideas.csv 可导入为数据库；Papers、Ideas 中的 Markdown 可另行导入为页面。CSV 与页面不会自动建立关联，稳定ID用于后续核对。重复导入会新增记录，不是同步更新。建议先在空白页面导入少量内容。'
        else:
            for topic in TOPICS:
                lines = ['# ' + topic['name'], '', topic['description'], '', '## 带着问题阅读', ''] + ['- ' + q for q in topic['questions']] + ['', '## 关联内容', '']
                lines += ['- [' + label(x['title_zh'] or x['title']) + '](../Papers/' + file_id('paper', x['id']) + ')' for x in items if topic['id'] in x['topics']]
                lines += ['', '## 相关方向', ''] + ['- [' + TOPIC_NAMES[t] + '](' + t + '.md)' for t in topic['related']]
                archive.writestr('Topics/' + topic['id'] + '.md', '\n'.join(lines))
            instructions = '将 ZIP 解压到新的文件夹，在 Obsidian 中选择“打开文件夹作为仓库”。从 Home.md 开始，论文与研究方向通过相对链接关联。可将其用于自己的知识图谱；不会自动回写研究台。重新导出时建议解压到新目录，避免覆盖你在 Obsidian 中修改的内容。'
        archive.writestr('Home.md', '\n'.join(index))
        archive.writestr('使用说明.md', '# 导入说明\n\n' + instructions + '\n\n已导出 ' + str(len(items)) + ' 条内容与 ' + str(len(ideas)) + ' 个选题。文件不包含账号访问码或登录会话。\n')
    return output.getvalue()
