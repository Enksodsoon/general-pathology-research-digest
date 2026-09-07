"""End-to-end state/notification regressions with simulated Telegram responses."""
import copy,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from event_scout import verified_scan as scan,verified_notify as notify,verified_reliability as reliability


def sample(i):
    start=datetime.now(timezone.utc)+timedelta(days=10)
    return {'id':str(i),'title':'Clinical webinar '+str(i),'source_url':'https://medical.example/event/'+str(i),'registration_url':'https://medical.example/register/'+str(i),'start_at':start.isoformat(),'end_at':(start+timedelta(hours=1)).isoformat(),'mode':'Online','language':'en','certificate':'Not stated','credits':'Not stated','fee':'Free attendance','verified_at':datetime.now(timezone.utc).isoformat()}

def payload(events):
    return {'created_at':datetime.now(timezone.utc).isoformat(),'health':'ok','sources_ok':3,'sources_total':3,'pages_checked':3,'events':events}

def test_fallback_diagnostics_are_serializable(monkeypatch):
    source={'id':'official','url':'https://blocked.example/','language':'th','fallbacks':[{'url':'https://alternative.example/'}]}
    def discover(s,now):
        if 'blocked' in s['url']:return [],{'id':'official','status':'error','error':'403','language':'th'}
        return [{'url':s['url']}],{'id':'official','status':'ok','language':'th','candidates':1}
    monkeypatch.setattr(scan,'_discover_once',discover)
    rows,d=scan.discover(source,datetime.now(timezone.utc))
    assert rows and d['fallback_used'] and d['status']=='degraded'
    assert len(json.loads(json.dumps(d))['attempts'])==2

def test_daily_failure_limit_applies_without_heartbeat():
    now=datetime.now(timezone.utc);today=now.astimezone(notify.BKK).date().isoformat()
    state={'daily_attempts':{today:3},'last_run':{'date':today,'health':'failed'}}
    assert not reliability.should_run(state,now,'recovery')
    assert reliability.should_run(state,now,'manual')

def test_previous_fingerprint_format_does_not_resend(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);e=sample('one');now=datetime.now(timezone.utc)
    (tmp_path/'result.json').write_text(json.dumps(payload([e])))
    (tmp_path/'receipts.json').write_text(json.dumps({'events':{e['id']:{'fingerprint':'old-format','message_id':50,'event':e}},'heartbeats':{}}))
    messages=[]
    def send(text):messages.append(text);return {'ok':True,'result':{'message_id':100+len(messages)}}
    monkeypatch.setattr(notify,'sender_from_env',lambda:send)
    monkeypatch.setattr(sys,'argv',['notify','--result','result.json','--receipts','receipts.json'])
    monkeypatch.setenv('GITHUB_RUN_ID','test-migration')
    notify.main()
    assert len(messages)==1 and '0 new/updated' in messages[0]
    assert not json.loads((tmp_path/'backlog.json').read_text())

def test_partial_failure_retries_only_failed_event(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);events=[sample('one'),sample('two')]
    Path('result.json').write_text(json.dumps(payload(events)));messages=[]
    def first(text):
        messages.append(text)
        if 'Clinical webinar two' in text:raise RuntimeError('simulated rejection')
        return {'ok':True,'result':{'message_id':len(messages)+10}}
    monkeypatch.setattr(notify,'sender_from_env',lambda:first)
    monkeypatch.setattr(notify.time,'sleep',lambda n:None)
    monkeypatch.setattr(sys,'argv',['notify','--result','result.json','--receipts','receipts.json'])
    monkeypatch.setenv('GITHUB_RUN_ID','first')
    with pytest.raises(SystemExit):notify.main()
    assert set(json.loads(Path('backlog.json').read_text()))=={'two'}
    again=[]
    def second(text):again.append(text);return {'ok':True,'result':{'message_id':len(again)+30}}
    monkeypatch.setattr(notify,'sender_from_env',lambda:second)
    monkeypatch.setenv('GITHUB_RUN_ID','second')
    notify.main()
    assert len(again)==2 and 'Clinical webinar two' in again[0]
    assert not json.loads(Path('backlog.json').read_text())

def test_backlog_not_in_fresh_scan_is_not_sent(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);e=sample('stale')
    Path('backlog.json').write_text(json.dumps({e['id']:{'event':e,'first_seen':e['verified_at'],'last_seen':e['verified_at']}}))
    Path('result.json').write_text(json.dumps(payload([])));sent=[]
    monkeypatch.setattr(notify,'sender_from_env',lambda:lambda text:(sent.append(text) or {'ok':True,'result':{'message_id':100}}))
    monkeypatch.setattr(sys,'argv',['notify','--result','result.json','--receipts','receipts.json'])
    notify.main()
    assert len(sent)==1 and 'Clinical webinar stale' not in sent[0]
    assert 'stale' in json.loads(Path('backlog.json').read_text())

def test_actual_registration_target_change_sends_update(tmp_path):
    state={'events':{},'heartbeats':{}};e=sample('one');e['registration_target']=e['registration_url'];texts=[]
    def send(text):texts.append(text);return {'ok':True,'result':{'message_id':len(texts)}}
    assert notify.deliver('one','first',state,tmp_path/'r',send,kind='event',event=e)
    changed=dict(e,registration_target='https://medical.example/register/new',registration_url='https://medical.example/register/new')
    assert notify.deliver('one','changed',state,tmp_path/'r',send,kind='update',event=changed)
    assert len(texts)==2

def test_production_guard_record_attempt_and_artifact_contract():
    text=Path('.github/workflows/daily-medical-events.yml').read_text()
    assert '--begin' in text and '--guard' in text
    assert 'workflow_run:' in text and 'Daily Digest' in text
    assert '17 3,6,9 * * *' in text
    assert '043fb46d1a93c77aae656e7c1c64a875d1fc6a0a' in text
    assert text.index('Upload durable run evidence') < text.index('Persist reports and acknowledged receipts')

def test_readonly_regressions_have_no_notification_secrets():
    for name in ('event-radar-repair-check.yml','radar-reliability-check.yml'):
        assert 'secrets.TELEGRAM' not in Path('.github/workflows',name).read_text()
