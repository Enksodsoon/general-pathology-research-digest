"""Bounded public Google News URL resolution, no proxy or challenge bypass.

Public redirect protocol documented by SSujitX/google-news-url-decoder (MIT).
This implementation uses bounded HTTP calls and validates every publisher URL.
"""
import base64
import json
import re
import threading
import time
import urllib.request
from urllib.parse import urlsplit, urlencode
from bs4 import BeautifulSoup

_LOCK = threading.Lock()


def parse_rpc(text, safe_url):
    for line in text.splitlines():
        try:
            values = json.loads(line)
        except ValueError:
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, list) or len(value) < 3 or value[1] != 'Fbv4je':
                continue
            try:
                result = json.loads(value[2])
                candidate = result[1]
            except (ValueError, TypeError, IndexError):
                continue
            if result[0] == 'garturlres' and isinstance(candidate, str) and safe_url(candidate):
                return candidate
    raise ValueError('Google News response has no safe publisher URL')


def resolve(url, fetch, safe_url):
    p = urlsplit(url)
    if p.hostname != 'news.google.com' or not re.fullmatch(r'/(?:rss/)?(?:articles|read)/[A-Za-z0-9_-]+', p.path):
        raise ValueError('Not a public Google News article URL')
    token = p.path.rsplit('/', 1)[-1]
    try:
        data = base64.urlsafe_b64decode(token + '=' * (-len(token) % 4))
        match = re.search(rb'https?://[\x21-\x7e]+', data)
        if match:
            original = match.group().decode('ascii')
            if safe_url(original):
                return original
    except (ValueError, UnicodeDecodeError):
        pass
    with _LOCK:
        time.sleep(1)
        markup, final = fetch(url)
        if urlsplit(final).hostname != 'news.google.com' and safe_url(final):
            return final
        node = BeautifulSoup(markup, 'html.parser').select_one('[data-n-a-sg][data-n-a-ts]')
        if node is None:
            raise ValueError('Google News redirect metadata unavailable')
        sig, ts = node['data-n-a-sg'], node['data-n-a-ts']
        if not str(ts).isdigit():
            raise ValueError('Invalid public redirect timestamp')
        context = [['X','X',['X','X'],None,None,1,1,'US:en',None,1,None,None,None,None,None,0,1], 'X','X',1,[1,1,1],1,1,None,0,0,None,0]
        arguments = ['garturlreq', context, token, int(ts), sig]
        body = urlencode({'f.req':json.dumps([[['Fbv4je',json.dumps(arguments),None,'generic']]])}).encode()
        req = urllib.request.Request('https://news.google.com/_/DotsSplashUi/data/batchexecute', data=body, headers={'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8','User-Agent':'MedicalEventRadar/2.0'}, method='POST')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=12) as response:
            raw = response.read(250001)
            if len(raw) > 250000:
                raise ValueError('Google News response too large')
        return parse_rpc(raw.decode('utf-8'), safe_url)
