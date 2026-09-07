"""Telegram delivery with durable acknowledgements, daily heartbeat and migration."""
from __future__ import annotations
import argparse, hashlib, json, os, re, time, unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BKK=ZoneInfo('Asia/Bangkok')

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)

def load(path):
    if not Path(path).exists():return {'events':{},'heartbeats':{}}
    state=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(state,dict) or not isinstance(state.get('events'),dict):raise RuntimeError('Invalid receipt ledger; refusing to reset deduplication')
    state.setdefault('heartbeats',{});return state

def fingerprint(event):
    return hashlib.sha256(json.dumps({k:event.get(k) for k in ('title','start_at','end_at','mode','certificate','credits','registration_url')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]

def deliver(key,text,state,path,sender,*,kind,event=None):
    bucket=state.setdefault('heartbeats' if kind=='heartbeat' else 'events',{})
    fp=fingerprint(event) if event else hashlib.sha256(text.encode()).hexdigest()[:24]
    old=bucket.get(key,{})
    if old.get('fingerprint')==fp and old.get('message_id'):return False
    response=sender(text)
    message=response.get('result',{})
    if not response.get('ok') or not isinstance(message.get('message_id'),int):
        raise RuntimeError('Telegram did not acknowledge message; delivery receipt not recorded')
    record={'fingerprint':fp,'message_id':message['message_id'],'telegram_date':message.get('date'),'acknowledged_at':datetime.now(timezone.utc).isoformat(),'kind':kind}
    if event:record['event']=event
    bucket[key]=record;write(path,state)
    print('Telegram acknowledged',kind,'message_id='+str(message['message_id']))
    return True

def sender_from_env():
    token=os.environ.get('TELEGRAM_BOT_TOKEN'); chat=os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:raise RuntimeError('Telegram credentials missing; notifications are NOT enabled')
    def send(text):
        req=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',data=json.dumps({'chat_id':chat,'text':text,'disable_web_page_preview':True}).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
        except Exception as exc:
            raise RuntimeError('Telegram request failed: '+type(exc).__name__) from None
    return send

def status_text(result,new_count):
    d=datetime.fromisoformat(result['created_at']).astimezone(BKK)
    health=result['health'].upper();icon='✅' if health=='OK' else '⚠️'
    return f"{icon} MEDICAL EVENT RADAR · {d:%d %b %H:%M} ICT\n{health} · {new_count} new/updated alerts\nSources {result['sources_ok']}/{result['sources_total']} · {result['pages_checked']} pages checked\n"+('Scan complete; each event has its own link.' if health=='OK' else 'Some coverage could not be verified; zero matches does not mean no events exist.')

def event_text(event,kind='event'):
    start=datetime.fromisoformat(event['start_at']).astimezone(BKK);end=datetime.fromisoformat(event['end_at']).astimezone(BKK) if event.get('end_at') else None
    when=f'{start:%d %b %Y %H:%M}'
    if end:when+='–'+(f'{end:%H:%M}' if end.date()==start.date() else f'{end:%d %b %H:%M}')
    certificate='Not stated' if event['certificate']=='Not stated' else event['certificate']
    return '\n'.join(['🔄 CORRECTION / UPDATE' if kind=='update' else '🩺 FREE MEDICAL EVENT',event['title'][:190],f"{when} ICT · {event['mode']} · {event['language'].upper()}",f"🎓 {certificate}",f"CME/CPD: {event['credits']}",event['registration_url']])

def title_key(text):return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()

def legacy_kind(event,legacy):
    matches=[r for r in legacy.values() if isinstance(r,dict) and (title_key(r.get('title',''))==title_key(event['title']) or r.get('url')==event['registration_url'])]
    if not matches:return 'event'
    latest=max(matches,key=lambda r:r.get('notified_at',''))
    try:
        same=datetime.fromisoformat(latest['event_start'])==datetime.fromisoformat(event['start_at'])
    except (KeyError,ValueError):same=False
    return 'legacy-seen' if same else 'update'

def main():
    p=argparse.ArgumentParser();p.add_argument('--result',default='data/verified_radar/latest.json');p.add_argument('--receipts',default='data/verified_radar/receipts.json');p.add_argument('--failure');p.add_argument('--guard',action='store_true');args=p.parse_args()
    path=Path(args.receipts);state=load(path);today=datetime.now(BKK).date().isoformat()
    if args.guard:
        fresh=state.get('last_run',{}).get('date')==today and state.get('last_run',{}).get('health')!='failed'
        print('skip='+str(fresh).lower());return
    send=sender_from_env()
    if args.failure:
        run=os.environ.get('GITHUB_RUN_ID','manual')
        deliver('failure-'+run,'⚠️ MEDICAL EVENT RADAR FAILED\nThe scan or delivery did not complete. No all-clear is being claimed.\nhttps://github.com/'+os.environ.get('GITHUB_REPOSITORY','Enksodsoon/general-pathology-research-digest')+'/actions/runs/'+run,state,path,send,kind='heartbeat')
        return
    result=json.loads(Path(args.result).read_text(encoding='utf-8'))
    age=datetime.now(timezone.utc)-datetime.fromisoformat(result['created_at'])
    if age.total_seconds()>7200:raise RuntimeError('Refusing stale scan payload')
    legacy_path=Path('data/event_scout_state.json');legacy=json.loads(legacy_path.read_text()) if legacy_path.exists() else {}
    sent=0
    for event in result['events']:
        if datetime.fromisoformat(event['start_at'])<=datetime.now(timezone.utc):continue
        kind=legacy_kind(event,legacy)
        old=state['events'].get(event['id'])
        if not old and kind=='legacy-seen':continue
        if old and old.get('fingerprint')==fingerprint(event):continue
        prior=[r for r in state['events'].values() if r.get('event',{}).get('source_url')==event['source_url'] and title_key(r.get('event',{}).get('title',''))==title_key(event['title'])]
        if old or prior:kind='update'
        if sent>=20:break
        if deliver(event['id'],event_text(event,kind),state,path,send,kind=kind,event=event):sent+=1;time.sleep(1.1)
    run=os.environ.get('GITHUB_RUN_ID',today)
    deliver('status-'+run,status_text(result,sent),state,path,send,kind='heartbeat')
    state['last_run']={'date':today,'health':result['health'],'new_alerts':sent,'completed_at':datetime.now(timezone.utc).isoformat(),'run_id':run}
    write(path,state)
    print('Delivery complete:',sent,'event messages and one status message acknowledged')

if __name__=='__main__':main()
