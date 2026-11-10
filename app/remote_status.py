"""Credential-free, short-lived status shared with the local pairing page."""
import json
import os
import re
import time
from . import storage

URL_PATTERN = r'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com'


def valid_url(value):
    return isinstance(value, str) and re.fullmatch(URL_PATTERN, value) is not None


def write(state, url='', message=''):
    value = {'state': state, 'url': url if valid_url(url) else '',
             'updated_at': time.time(), 'temporary': True, 'message': message}
    storage.DATA.mkdir(parents=True, exist_ok=True)
    path = storage.DATA / 'remote-access.json'
    temporary = path.with_suffix('.tmp')
    fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False)
    temporary.replace(path)
    return value


def read():
    try:
        value = json.loads((storage.DATA / 'remote-access.json').read_text())
        age = time.time() - float(value['updated_at'])
        if not 0 <= age < 90:
            return {'state': 'offline', 'url': '', 'temporary': True,
                    'message': '公网通道未运行，请在 Mac 上检查服务。'}
        return {'state': value['state'], 'url': value['url'] if valid_url(value.get('url')) else '',
                'temporary': True, 'message': str(value.get('message', ''))[:300]}
    except (OSError, ValueError, KeyError, TypeError):
        return {'state': 'offline', 'url': '', 'temporary': True, 'message': '尚未开启公网通道。'}
