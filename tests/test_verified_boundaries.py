from datetime import datetime, timezone
from event_scout.verified_extract import extract
from event_scout import verified_scan
NOW = datetime(2026,9,7,tzinfo=timezone.utc)
SOURCE={'language':'en','timezone':'UTC','medical':True}

def test_neighbor_event_cannot_prove_free_attendance():
    html='<main><article><h1>Clinical conference</h1><div class="entry-content"><p>October 18, 2026 08:00 ICT</p><p>Onsite in Bangkok. Register online.</p><a href="/register/current">Register</a></div></article><div class="post-pagination"><p>Free online webinar</p><a href="/event/old">Register</a></div></main>'
    rows,why=extract(html,'https://medical.example/current',SOURCE,NOW)
    assert not rows and 'free-attendance-unverified' in why

def test_onsite_online_registration_is_not_online_attendance():
    html='<main><h1>Clinical conference</h1><p>October 18, 2026 08:00 ICT</p><p>Onsite Bangkok, free registration. Register online.</p><a href="/register/current">Register</a></main>'
    rows,_=extract(html,'https://medical.example/current',SOURCE,NOW)
    assert rows and rows[0]['mode']=='Thailand onsite'

def test_ncc_topic_in_same_heading_as_date():
    html='<main><h1>地域連携Webセミナー</h1><h2>がん緩和ケア支持療法セミナー（第3水曜日17：30～18：00）</h2><p>会費無料 Zoomウェビナー</p><h4>第2回 2026年9月16日<br>『がん患者の浮腫のケア』</h4><p><a href="https://zoom.us/webinar/register/a">参加登録</a></p></main>'
    rows,_=extract(html,'https://www.ncc.go.jp/series',{'timezone':'Asia/Tokyo','language':'ja','medical':True,'adapter':'ncc_series'},NOW)
    assert rows and rows[0]['start_at']=='2026-09-16T17:30:00+09:00'

def test_one_closed_series_session_does_not_discard_others(monkeypatch):
    events=[{'source_url':'https://medical.example/series','registration_url':'https://zoom.us/webinar/register/'+i} for i in ['closed','open']]
    monkeypatch.setattr(verified_scan,'extract',lambda *args:(events,[]))
    monkeypatch.setattr(verified_scan,'fetch',lambda u:('Registration closed' if u.endswith('closed') else 'Register',u))
    rows,_=verified_scan.verify({'url':'https://medical.example/series','language':'en','discovered_by':'test'},NOW,[])
    assert len(rows)==1 and rows[0]['registration_url'].endswith('open')

def test_credit_list_with_cme_detected():
    html='<main><h1>Clinical webinar</h1><p>September 24, 2026 17:00 UTC</p><p>Free online webinar</p><p>FREE CE credits: CME • NCPD • ACPE</p><a href="/register/current">Register</a></main>'
    rows,_=extract(html,'https://medical.example/current',SOURCE,NOW)
    assert rows and rows[0]['credits'].startswith('CME/CPD offered')
