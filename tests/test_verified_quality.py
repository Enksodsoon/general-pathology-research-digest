"""Regressions exposed by actual organizer pages and delivery failure paths."""
import base64, importlib, json
from datetime import datetime, timezone
import pytest
NOW=datetime(2026,9,7,3,tzinfo=timezone.utc)

def module(name):return importlib.import_module('event_scout.'+name)

def test_html_entities_in_schema_match_heading():
    schema={'@type':'Event','name':'Cancer Survivorship &#8211; Live Webinar','startDate':'2026-10-14T12:00:00-04:00','offers':{'price':'0'}}
    html='<script type="application/ld+json">'+json.dumps(schema)+'</script><main><h1>Cancer Survivorship – Live Webinar</h1><p>Free online webinar</p><a href="https://learn.unclcn.org/">Register to Attend in our Learning Portal</a></main>'
    rows,_=module('verified_extract').extract(html,'https://unclineberger.org/unclcn/event/10142026/',{'timezone':'America/New_York','language':'en','medical':True},NOW)
    assert rows and rows[0]['start_at']=='2026-10-14T12:00:00-04:00'

def test_irrelevant_search_does_not_consume_budget(monkeypatch):
    m=module('verified_scan');rss='<rss><channel><item><title>The Counting Game</title><link>https://games.example/play</link></item></channel></rss>'
    monkeypatch.setattr(m,'fetch',lambda u:(rss,u))
    rows,diag=m.discover({'id':'bing-th','kind':'search','query':'medical webinar','url':'https://www.bing.com/search','language':'th'},NOW)
    assert rows==[] and diag['status']=='degraded'

def test_series_adapter_kept_only_on_root(monkeypatch):
    m=module('verified_scan');url='https://www.ncc.go.jp/series.html'
    monkeypatch.setattr(m,'fetch',lambda u:('<main><h1>NCC</h1><a href="https://zoom.us/webinar/register/one">Webinar registration</a></main>',u))
    rows,_=m.discover({'id':'ncc','url':url,'language':'ja','adapter':'ncc_series'},NOW)
    assert rows[0]['url']==url and rows[0]['adapter']=='ncc_series'
    assert all('adapter' not in r for r in rows if r['url']!=url)

def test_nav_does_not_displace_event_page(monkeypatch):
    m=module('verified_scan');url='https://med.example/events/'
    html='<header>'+''.join(f'<a href="https://other{i}.example/webinar">webinars</a>' for i in range(80))+'</header><main><a href="/event/topic">Clinical webinar</a></main>'
    monkeypatch.setattr(m,'fetch',lambda u:(html,u))
    rows,_=m.discover({'id':'society','url':url,'language':'en','max_links':3},NOW)
    assert [r['url'] for r in rows]==[url,'https://med.example/event/topic']

def test_thai_free_registration():
    html='<main><h1>อบรมแพทย์</h1><p>วันที่ 20 กันยายน 2569 เวลา 09.00-12.00 น.</p><p>อบรมแพทย์ ออนไลน์ ลงทะเบียนฟรี</p><a href="/register/topic">ลงทะเบียน</a></main>'
    rows,_=module('verified_extract').extract(html,'https://med.example/event/topic',{'timezone':'Asia/Bangkok','language':'th','medical':True},NOW)
    assert rows

def test_official_event_api_uses_individual_urls(monkeypatch):
    m=module('verified_scan');url='https://unclineberger.org/unclcn/wp-json/tribe/events/v1/events?start_date=2026-09-07'
    monkeypatch.setattr(m,'fetch',lambda u:(json.dumps({'events':[{'url':'https://unclineberger.org/unclcn/event/10142026/','title':'Cancer Survivorship webinar'}]}),u))
    rows,_=m.discover({'id':'UNC-API','url':url,'kind':'tribe','language':'en'},NOW)
    assert len(rows)==1 and rows[0]['url'].endswith('/10142026/')

def test_google_news_original_url_without_network():
    original='https://medical.example/events/free-webinar';token=base64.urlsafe_b64encode(b'\x08\x13\x22'+bytes([len(original)])+original.encode()+b'\xd2\x01\x00').decode().rstrip('=')
    def no_fetch(_):raise AssertionError('No network necessary')
    assert module('verified_news').resolve('https://news.google.com/rss/articles/'+token,no_fetch,lambda u:u.startswith('https://medical.example/'))==original

def test_google_news_wrong_host_rejected():
    with pytest.raises(ValueError):module('verified_news').resolve('https://attacker.example/read/abc',lambda u:('',u),lambda u:True)

def test_google_rpc_only_returns_safe_url():
    m=module('verified_news');rpc=")]}'\n\n"+json.dumps([["wrb.fr","Fbv4je",json.dumps(['garturlres','https://medical.example/event']),None]])
    assert m.parse_rpc(rpc,lambda u:u=='https://medical.example/event')=='https://medical.example/event'
    with pytest.raises(ValueError):m.parse_rpc(rpc,lambda u:False)

def test_updated_event_generates_new_receipt(tmp_path):
    m=module('verified_notify');state={'events':{},'heartbeats':{}};calls=[]
    def send(text):calls.append(text);return {'ok':True,'result':{'message_id':len(calls)}}
    m.deliver('x','a',state,tmp_path/'r.json',send,kind='event',event={'title':'Event','start_at':'2026-09-09T10:00:00+00:00'})
    assert m.deliver('x','b',state,tmp_path/'r.json',send,kind='update',event={'title':'Event','start_at':'2026-09-10T10:00:00+00:00'})
    assert len(calls)==2

def test_legacy_wrong_date_is_corrected():
    e={'title':'Medical webinar','start_at':'2026-09-09T16:00:00+09:00','registration_url':'https://zoom.us/webinar/register/a'}
    old={'x':{'title':'Medical webinar','event_start':'2027-04-21T10:00:00+09:00','url':e['registration_url'],'notified_at':'2026-08-31'}}
    assert module('verified_notify').legacy_kind(e,old)=='update'

def test_legacy_same_event_not_resent():
    e={'title':'Medical webinar','start_at':'2026-09-09T16:00:00+09:00','registration_url':'https://zoom.us/webinar/register/a'}
    old={'x':{'title':e['title'],'event_start':e['start_at'],'url':e['registration_url'],'notified_at':'2026-08-31'}}
    assert module('verified_notify').legacy_kind(e,old)=='legacy-seen'

def test_missing_telegram_credentials_fail(monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False);monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    with pytest.raises(RuntimeError):module('verified_notify').sender_from_env()

def test_ok_without_message_id_not_delivery(tmp_path):
    m=module('verified_notify');state={'events':{},'heartbeats':{}}
    with pytest.raises(RuntimeError):m.deliver('x','hello',state,tmp_path/'r.json',lambda t:{'ok':True},kind='event',event={'title':'X'})
    assert not state['events']

def test_corrupt_state_is_not_reset(tmp_path):
    p=tmp_path/'r.json';p.write_text('{invalid')
    with pytest.raises(ValueError):module('verified_notify').load(p)

def test_dns_private_target_rejected(monkeypatch):
    m=module('verified_scan');monkeypatch.setattr(m.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('10.0.0.1',443))])
    with pytest.raises(ValueError):m.check_dns('https://medical.example/event')

def test_source_timeout_reported(monkeypatch):
    m=module('verified_scan')
    def fail(_):raise TimeoutError('test')
    monkeypatch.setattr(m,'fetch',fail)
    rows,diag=m.discover({'id':'test','url':'https://medical.example/events','language':'en'},NOW)
    assert not rows and diag['status']=='error'

def test_closed_registration_target_rejected(monkeypatch):
    m=module('verified_scan');page='<main><h1>Medical webinar</h1><p>September 24, 2026 17:00 UTC</p><p>Free online webinar</p><a href="https://forms.example/register/one">Register</a></main>'
    monkeypatch.setattr(m,'fetch',lambda u:('No longer accepting responses',u) if 'forms.example' in u else (page,u))
    rows,diag=m.verify({'url':'https://medical.example/event','discovered_by':'test','timezone':'UTC','language':'en','medical':True},NOW,[])
    assert not rows and 'registration-target-closed' in diag['reasons']
