"""Acknowledged Telegram delivery, durable backlog and bounded daily recovery."""
from __future__ import annotations
import argparse, copy, hashlib, json, os, re, time, unicodedata
import urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .verified_reliability import event_fingerprint, canonical_url, aware, should_run, validate_scan_age, merge_backlog
BKK=ZoneInfo('Asia/Bangkok')

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    tmp.replace(path)

def load(path):
    if not Path(path).exists():return {'events':{},'heartbeats':{}}
    state=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(state,dict) or not isinstance(state.get('events'),dict):raise RuntimeError('Invalid receipt ledger; refusing to reset deduplication')
    if not isinstance(state.get('heartbeats',{}),dict):raise RuntimeError('Invalid heartbeat ledger')
    state.setdefault('heartbeats',{});return state

def fingerprint(event):return event_fingerprint(event)

def deliver(key,text,state,path,sender,*,kind,event=None):
    bucket_name='heartbeats' if kind=='heartbeat' else 'events'
    bucket=state.setdefault(bucket_name,{})
    fp=fingerprint(event) if event else hashlib.sha256(text.encode()).hexdigest()[:24]
    old=bucket.get(key,{})
    same_target=(not event or canonical_url(old.get('event',{}).get('registration_target',''))==canonical_url(event.get('registration_target','')))
    if old.get('fingerprint')==fp and type(old.get('message_id')) is int and same_target:return False
    response=sender(text)
    message=response.get('result',{}) if isinstance(response,dict) else {}
    if not isinstance(response,dict) or not response.get('ok') or type(message.get('message_id')) is not int or message['message_id']<=0:
        raise RuntimeError('Telegram did not acknowledge message; no successful receipt recorded')
    record={'fingerprint':fp,'message_id':message['message_id'],'telegram_date':message.get('date'),'acknowledged_at':datetime.now(timezone.utc).isoformat(),'kind':kind}
    if event:record['event']=event
    proposed=copy.deepcopy(state);proposed[bucket_name][key]=record
    write(path,proposed)
    state.clear();state.update(proposed)
    print('Telegram acknowledged',kind,'message_id='+str(message['message_id']),flush=True)
    return True

def sender_from_env():
    token=os.environ.get('TELEGRAM_BOT_TOKEN');chat=os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:raise RuntimeError('Telegram credentials missing; notifications are NOT enabled')
    def send(text):
        if len(text)>4000:raise ValueError('Telegram message exceeds safe length')
        for attempt in range(3):
            req=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',data=json.dumps({'chat_id':chat,'text':text,'disable_web_page_preview':True}).encode(),headers={'Content-Type':'application/json'},method='POST')
            try:
                with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
            except urllib.error.HTTPError as exc:
                # Retry only explicit rate-limit rejection, not ambiguous network
                # failures that may already have delivered the message.
                if exc.code==429 and attempt<2:
                    try:delay=int(json.loads(exc.read(10000)).get('parameters',{}).get('retry_after',2))
                    except (ValueError,TypeError):delay=2
                    if delay<=30:time.sleep(max(1,delay));continue
                raise RuntimeError('Telegram HTTP '+str(exc.code)) from None
            except Exception as exc:raise RuntimeError('Telegram request failed: '+type(exc).__name__) from None
        raise RuntimeError('Telegram rate-limit retry exhausted')
    return send

def status_text(result,new_count):
    d=datetime.fromisoformat(result['created_at']).astimezone(BKK)
    health=result['health'].upper();icon='✅' if health=='OK' else '⚠️'
    text=f"{icon} MEDICAL EVENT RADAR · {d:%d %b %H:%M} ICT\n{health} · {new_count} new/updated alerts\nSources {result['sources_ok']}/{result['sources_total']} · {result['pages_checked']} pages checked"
    if result.get('delivery_errors'):text+='\nDelivery failures: '+str(result['delivery_errors'])+'; retained for retry.'
    elif health!='OK':text+='\nSome coverage could not be verified; zero matches does not mean no events exist.'
    elif not new_count:text+='\nNo new verified events; the scan completed.'
    else:text+='\nEach event has its own registration/event link.'
    if result.get('pending_count'):text+='\nQueued for recheck: '+str(result['pending_count'])
    return text

def event_text(event,kind='event'):
    start=aware(event['start_at']).astimezone(BKK);end=aware(event['end_at']).astimezone(BKK) if event.get('end_at') else None
    when=f'{start:%d %b %Y %H:%M}'
    if end:when+='–'+(f'{end:%H:%M}' if end.date()==start.date() else f'{end:%d %b %H:%M}')
    lines=['🔄 CORRECTION / UPDATE' if kind=='update' else '🩺 FREE MEDICAL EVENT',event['title'][:190],f"{when} ICT · {event['mode']} · {event['language'].upper()}",f"🎓 {event['certificate']}",f"CME/CPD: {event['credits']}"]
    if event.get('registration_deadline'):lines.append('Register by: '+event['registration_deadline'])
    lines.append(event['registration_url'])
    return '\n'.join(lines)

def title_key(text):return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()

def legacy_kind(event,legacy):
    matches=[r for r in legacy.values() if isinstance(r,dict) and (title_key(r.get('title',''))==title_key(event['title']) or canonical_url(r.get('url',''))==canonical_url(event['registration_url']))]
    if not matches:return 'event'
    latest=max(matches,key=lambda r:r.get('notified_at',''))
    try:same=aware(latest['event_start'])==aware(event['start_at'])
    except (KeyError,ValueError):same=False
    return 'legacy-seen' if same else 'update'

def prior_receipt(event,state):
    exact=state['events'].get(event['id'])
    if exact:return exact
    for row in state['events'].values():
        old=row.get('event',{})
        if title_key(old.get('title',''))==title_key(event['title']) and canonical_url(old.get('source_url',''))==canonical_url(event['source_url']):return row
    return None

def main():
    p=argparse.ArgumentParser();p.add_argument('--result',default='data/verified_radar/latest.json');p.add_argument('--receipts',default='data/verified_radar/receipts.json');p.add_argument('--failure');p.add_argument('--guard',action='store_true');p.add_argument('--begin',action='store_true');p.add_argument('--stage',default='recovery');args=p.parse_args()
    path=Path(args.receipts);state=load(path);now=datetime.now(timezone.utc);today=now.astimezone(BKK).date().isoformat()
    if args.guard:
        print('skip='+str(not should_run(state,now,args.stage)).lower());return
    if args.begin:
        counts=state.setdefault('daily_attempts',{});counts[today]=counts.get(today,0)+1
        state['daily_attempts']={k:v for k,v in counts.items() if k>=str(now.astimezone(BKK).year)+'-01-01'}
        write(path,state);return
    send=sender_from_env();run=os.environ.get('GITHUB_RUN_ID',today)
    if args.failure:
        deliver('failure-'+run,'⚠️ MEDICAL EVENT RADAR FAILED\nThe scan or delivery did not complete. Recovery remains enabled.\nhttps://github.com/'+os.environ.get('GITHUB_REPOSITORY','Enksodsoon/general-pathology-research-digest')+'/actions/runs/'+run,state,path,send,kind='heartbeat')
        state['last_run']={'date':today,'health':'failed','completed_at':now.isoformat(),'run_id':run};write(path,state);return
    result=json.loads(Path(args.result).read_text(encoding='utf-8'));validate_scan_age(result['created_at'],now)
    legacy_path=Path('data/event_scout_state.json');legacy=json.loads(legacy_path.read_text()) if legacy_path.exists() else {}
    queue_path=Path(args.result).parent/'backlog.json'
    queue=json.loads(queue_path.read_text()) if queue_path.exists() else {}
    queue=merge_backlog(queue,result['events'],now);write(queue_path,queue)
    sent=0;errors=[]
    # Freshly reverified events only. Older queue records are never sent blind.
    for event in result['events']:
        if aware(event['start_at'])<=now:queue.pop(event['id'],None);continue
        kind=legacy_kind(event,legacy);old=prior_receipt(event,state)
        if old:
            previous=old.get('event',{})
            target_changed=bool(previous.get('registration_target') and event.get('registration_target') and canonical_url(previous['registration_target'])!=canonical_url(event['registration_target']))
            if fingerprint(previous)==fingerprint(event) and not target_changed:
                queue.pop(event['id'],None);continue
            kind='update'
        elif kind=='legacy-seen':queue.pop(event['id'],None);continue
        if sent>=20:continue
        try:
            if deliver(event['id'],event_text(event,kind),state,path,send,kind=kind,event=event):sent+=1
            queue.pop(event['id'],None);write(queue_path,queue);time.sleep(1.1)
        except Exception as exc:
            errors.append({'event_id':event['id'],'error':type(exc).__name__})
            print('Event delivery failed; queued:',event['id'],type(exc).__name__,flush=True)
    write(queue_path,queue)
    result['delivery_errors']=len(errors);result['pending_count']=len(queue)
    if errors:result['health']='failed'
    deliver('status-'+run,status_text(result,sent),state,path,send,kind='heartbeat')
    state['last_run']={'date':today,'health':result['health'],'new_alerts':sent,'pending_count':len(queue),'delivery_errors':len(errors),'completed_at':datetime.now(timezone.utc).isoformat(),'run_id':run,'trigger':os.environ.get('GITHUB_EVENT_NAME','local')}
    write(path,state)
    write(Path(args.result).parent/'delivery.json',{'run_id':run,'sent':sent,'errors':errors,'pending':len(queue),'status_acknowledged':True})
    print('Delivery complete:',sent,'event messages and one status message acknowledged',flush=True)
    if errors:raise SystemExit(1)

if __name__=='__main__':main()
