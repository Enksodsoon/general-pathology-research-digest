"""Readiness tests derived from the production diagnostics; no live credentials."""
import importlib, importlib.util, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
import pytest
from event_scout import verified_scan as scan, verified_notify as notify
NOW=datetime(2026,9,7,5,tzinfo=timezone.utc)

def reliability():
    assert importlib.util.find_spec('event_scout.verified_reliability'), 'Recovery implementation missing'
    return importlib.import_module('event_scout.verified_reliability')

def event(i='one'):
    return {'id':i,'title':'Clinical webinar '+i,'source_url':'https://medical.example/event/'+i,'registration_url':'https://medical.example/register/'+i,'start_at':'2026-10-10T12:00:00+00:00','end_at':'2026-10-10T13:00:00+00:00','mode':'Online','language':'en','certificate':'Not stated','credits':'Not stated','fee':'Free attendance','verified_at':NOW.isoformat()}

def test_google_empty_filtered_results_are_not_transport_failure(monkeypatch):
    rss='<rss><channel><title>Google News</title><item><title>General hospital news</title><link>https://medical.example/news</link></item></channel></rss>'
    monkeypatch.setattr(scan,'fetch',lambda u:(rss,u))
    rows,d=scan.discover({'id':'g','kind':'search','engine':'google_news','query':'medical webinar','url':'https://news.google.com/rss/search','language':'en'},NOW)
    assert not rows and d['status']=='ok'
    assert d.get('search_outcome')=='no-relevant-results'

def test_degraded_run_does_not_disable_recovery(tmp_path,monkeypatch,capsys):
    p=tmp_path/'r.json'
    p.write_text(json.dumps({'events':{},'last_run':{'date':datetime.now(notify.BKK).date().isoformat(),'health':'degraded','completed_at':(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat()}}))
    monkeypatch.setattr(sys,'argv',['notify','--guard','--receipts',str(p)])
    notify.main()
    assert 'skip=false' in capsys.readouterr().out

def test_empty_complete_scan_can_be_healthy():
    m=reliability()
    d=[{'id':x,'language':x,'status':'ok','kind':'search','candidates':0} for x in ('en','th','ja')]
    h=m.assess_health(d,[],[])
    assert h['health']=='ok' and h['verification']=='no-matches'

def test_nonempty_fetch_is_not_proof_of_parsed_events():
    m=reliability();d=[{'id':x,'language':x,'status':'ok'} for x in ('en','th','ja')]
    assert m.assess_health(d,[{'status':'error','error':'parser failure'}],[])['health']=='degraded'

def test_deterministic_exclusions_are_counted_not_hidden():
    m=reliability();d=[{'id':x,'language':x,'status':'ok'} for x in ('en','th','ja')]
    h=m.assess_health(d,[{'status':'rejected','reasons':['past-event']},{'status':'error','error':'403'}],[])
    assert h['page_errors']==1 and h['rejected_count']==1

def test_retry_timeout_but_never_bypass_forbidden():
    m=reliability();assert m.is_transient(URLError(TimeoutError()))
    assert not m.is_transient(HTTPError('https://medical.example',403,'Forbidden',{},None))
    assert not m.is_transient(ValueError('access-challenge'))

def test_url_encoding_does_not_generate_duplicate_fingerprint():
    a=event();b=dict(a,start_at='2026-10-10T14:00:00+02:00',end_at='2026-10-10T15:00:00+02:00')
    a['registration_url']='https://medical.example/register?a=https%3A%2F%2Fexample.org%2F'
    b['registration_url']='https://medical.example/register?a=https://example.org/'
    assert notify.fingerprint(a)==notify.fingerprint(b)

def test_transient_link_check_fallback_does_not_change_event_fingerprint():
    a=event();b=dict(a,registration_url=a['source_url'],registration_status='direct registration could not be checked')
    assert notify.fingerprint(a)==notify.fingerprint(b)

def test_real_schedule_change_changes_fingerprint():
    a=event();b=dict(a,start_at='2026-10-11T12:00:00+00:00')
    assert notify.fingerprint(a)!=notify.fingerprint(b)

def test_future_dated_scan_payload_rejected():
    with pytest.raises(ValueError):reliability().validate_scan_age((NOW+timedelta(hours=1)).isoformat(),NOW)

def test_stale_scan_payload_rejected():
    with pytest.raises(ValueError):reliability().validate_scan_age((NOW-timedelta(hours=3)).isoformat(),NOW)

def test_current_payload_accepted():
    reliability().validate_scan_age(NOW.isoformat(),NOW)

def test_notification_backlog_retained_but_requires_reverification():
    m=reliability();state={};a=event()
    updated=m.merge_backlog(state,[a],NOW)
    assert a['id'] in updated
    later=m.merge_backlog(updated,[],NOW+timedelta(days=1))
    assert a['id'] in later and later[a['id']]['event']['verified_at']==NOW.isoformat()

def test_past_backlog_pruned():
    m=reliability();old=event();old['start_at']='2026-09-01T12:00:00+00:00'
    assert not m.merge_backlog({},[old],NOW)

def test_fresh_guard_requires_real_heartbeat():
    m=reliability();state={'last_run':{'date':'2026-09-07','health':'ok','completed_at':NOW.isoformat()}}
    assert m.should_run(state,NOW,'recovery')

def test_healthy_acknowledged_guard_skips_duplicate():
    m=reliability();state={'last_run':{'date':'2026-09-07','health':'ok','completed_at':NOW.isoformat(),'run_id':'r'},'heartbeats':{'status-r':{'message_id':55}}}
    assert not m.should_run(state,NOW+timedelta(hours=3),'recovery')

def test_previous_day_healthy_run_does_not_skip_today():
    m=reliability();state={'last_run':{'date':'2026-09-06','health':'ok','completed_at':(NOW-timedelta(days=1)).isoformat(),'run_id':'r'},'heartbeats':{'status-r':{'message_id':55}}}
    assert m.should_run(state,NOW,'primary')

def test_recovery_throttled_but_not_disabled():
    m=reliability();state={'last_run':{'date':'2026-09-07','health':'degraded','completed_at':NOW.isoformat(),'run_id':'r'},'heartbeats':{'status-r':{'message_id':55}}}
    assert not m.should_run(state,NOW+timedelta(minutes=10),'recovery')
    assert m.should_run(state,NOW+timedelta(hours=3),'recovery')

def test_untrusted_cross_host_source_metadata_not_inherited(monkeypatch):
    seen=[]
    monkeypatch.setattr(scan,'fetch',lambda u:('<main></main>',u))
    monkeypatch.setattr(scan,'extract',lambda html,url,info,now:(seen.append(info) or [],[]))
    scan.verify({'url':'https://unrelated.example/event','origin_host':'trusted.example','timezone':'Asia/Tokyo','medical':True,'language':'ja','discovered_by':'source'},NOW,[])
    assert seen[0]['timezone']=='' and seen[0]['medical'] is False

def test_acknowledgement_before_disk_write_is_not_left_in_memory_on_failure(tmp_path,monkeypatch):
    state={'events':{},'heartbeats':{}}
    monkeypatch.setattr(notify,'write',lambda *a:(_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):notify.deliver('e','hello',state,tmp_path/'r',lambda t:{'ok':True,'result':{'message_id':1}},kind='event',event=event())
    assert 'e' not in state['events']

def test_boolean_is_not_valid_telegram_message_id(tmp_path):
    with pytest.raises(RuntimeError):notify.deliver('e','hello',{'events':{}},tmp_path/'r',lambda t:{'ok':True,'result':{'message_id':True}},kind='event',event=event())

def test_regression_check_runs_without_production_secrets():
    workflow=Path('.github/workflows/radar-reliability-check.yml').read_text()
    assert 'TELEGRAM_BOT_TOKEN' not in workflow
