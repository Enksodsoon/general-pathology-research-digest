"""Pure recovery, health and queue rules shared by scheduled and manual runs."""
from __future__ import annotations
import copy, hashlib, json, socket, ssl
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo
BKK=ZoneInfo('Asia/Bangkok')

def aware(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone is required')
    return d.astimezone(timezone.utc)

def canonical_url(value):
    p=urlsplit(value or '')
    query=sorted((k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid'))
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',urlencode(query),'')).rstrip('/')

def event_fingerprint(event):
    # Delivery-link fallbacks do not change the underlying event. Genuine target
    # changes are compared separately when both targets were recorded explicitly.
    data={k:event.get(k) for k in ('title','source_url','start_at','end_at','mode','certificate','credits')}
    for k in ('start_at','end_at'):
        if data[k]:data[k]=aware(data[k]).isoformat()
    if data['source_url']:data['source_url']=canonical_url(data['source_url'])
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:24]

def is_transient(exc):
    if isinstance(exc,HTTPError):return exc.code in (408,425,429,500,502,503,504)
    if isinstance(exc,URLError):return is_transient(exc.reason)
    if isinstance(exc,ssl.SSLError):return False
    return isinstance(exc,(TimeoutError,socket.timeout,ConnectionError,socket.gaierror)) or (isinstance(exc,str) and 'timed out' in exc.lower())

def validate_scan_age(created_at,now):
    age=(now-aware(created_at)).total_seconds()
    if age < -120 or age > 7200:raise ValueError('Refusing stale or future-dated scan payload')

def assess_health(sources,pages,events):
    ok=sum(d.get('status')=='ok' for d in sources)
    langs={lang:sum(d.get('status')=='ok' and d.get('language')==lang for d in sources) for lang in ('en','th','ja')}
    errors=sum(d.get('status')=='error' for d in pages)
    rejected=sum(d.get('status')=='rejected' for d in pages)
    if not ok:health='failed'
    elif ok<len(sources) or errors or not all(langs.values()):health='degraded'
    else:health='ok'
    return {'health':health,'sources_ok':ok,'sources_total':len(sources),'language_sources_ok':langs,'page_errors':errors,'rejected_count':rejected,'verification':'matches' if events else 'no-matches','source_warnings':[d.get('id') for d in sources if d.get('status')!='ok']}

def should_run(state,now,stage='recovery'):
    if stage=='manual':return True
    today=now.astimezone(BKK).date().isoformat()
    if state.get('daily_attempts',{}).get(today,0)>=3:return False
    last=state.get('last_run',{})
    if last.get('date')!=today:return True
    heart=state.get('heartbeats',{}).get('status-'+str(last.get('run_id','')), {})
    if type(heart.get('message_id')) is not int or heart['message_id']<=0:return True
    try:elapsed=(now-aware(last['completed_at'])).total_seconds()
    except (KeyError,ValueError,TypeError):return True
    if elapsed<0:return True
    if last.get('health')=='ok' and not last.get('pending_count') and not last.get('delivery_errors'):return False
    if elapsed<7200:return False
    attempts=state.get('daily_attempts',{}).get(today,0)
    return attempts<3

def merge_backlog(state,events,now):
    pending=copy.deepcopy(state)
    for e in events:
        try:
            if aware(e['start_at'])<=now:continue
        except (KeyError,ValueError,TypeError):continue
        previous=pending.get(e['id'],{})
        pending[e['id']]={'event':copy.deepcopy(e),'first_seen':previous.get('first_seen',now.isoformat()),'last_seen':now.isoformat()}
    for key,row in list(pending.items()):
        try:
            expired=aware(row['event']['start_at'])<=now or aware(row['last_seen'])<now-timedelta(days=30)
        except (KeyError,ValueError,TypeError):expired=True
        if expired:pending.pop(key,None)
    return pending
