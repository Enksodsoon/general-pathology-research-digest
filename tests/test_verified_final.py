import json
from datetime import datetime, timezone
from event_scout.verified_extract import extract
NOW=datetime(2026,9,7,3,tzinfo=timezone.utc)
SOURCE={'language':'en','timezone':'UTC','medical':True}

def page(title,body):return '<main><h1>'+title+'</h1>'+body+'</main>'

def test_conference_index_cannot_be_one_event():
    rows,_=extract(page('Conferences & Events','<p>October 18, 2026 08:00 ICT</p><p>Free online webinar</p><a href="/conference/old">Register</a>'),'https://medical.example/index',SOURCE,NOW)
    assert not rows

def test_ncc_clock_in_section_heading():
    html=page('地域連携Webセミナー','<h2>がん緩和ケア支持療法セミナー（2026年7月～2027年1月 第3水曜日17：30～18：00）</h2><p>会費無料 Zoomウェビナー</p><h4>第2回 2026年9月16日</h4><p>『がん患者の浮腫のケア』</p><a href="https://zoom.us/webinar/register/a">参加登録</a>')
    rows,_=extract(html,'https://www.ncc.go.jp/series',{'timezone':'Asia/Tokyo','language':'ja','medical':True,'adapter':'ncc_series'},NOW)
    assert rows and rows[0]['start_at']=='2026-09-16T17:30:00+09:00'

def test_article_header_title_kept():
    html='<header><h1>Hospital navigation</h1></header><main><article><header><h1>Clinical medical webinar</h1></header><p>September 24, 2026 17:00 UTC</p><p>Free online webinar</p><a href="/register/topic">Register</a></article></main>'
    rows,_=extract(html,'https://hospital.example/event',SOURCE,NOW)
    assert rows and rows[0]['title']=='Clinical medical webinar'

def test_cme_denied_not_offered():
    rows,_=extract(page('Clinical medical webinar','<p>September 24, 2026 17:00 UTC</p><p>Free online webinar. No CME credits will be awarded.</p><a href="/register/topic">Register</a>'),'https://medical.example/event',SOURCE,NOW)
    assert rows and rows[0]['credits']=='Not offered'

def test_cme_pending_not_accredited():
    rows,_=extract(page('Clinical medical webinar','<p>September 24, 2026 17:00 UTC</p><p>Free online webinar. Application for CME credits is pending.</p><a href="/register/topic">Register</a>'),'https://medical.example/event',SOURCE,NOW)
    assert rows and 'pending' in rows[0]['credits'].lower()
