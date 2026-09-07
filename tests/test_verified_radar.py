import importlib, importlib.util, json
from datetime import datetime, timezone
import pytest
NOW = datetime(2026,9,7,3,tzinfo=timezone.utc)

def module(name):
    spec=importlib.util.find_spec('event_scout.'+name)
    assert spec is not None, 'Verified radar implementation is missing'
    return importlib.import_module('event_scout.'+name)

def parse(body, *, title='Clinical medical webinar', zone='UTC', lang='en', url='https://medical.example/event/topic', schema=None):
    script='<script type="application/ld+json">'+json.dumps(schema)+'</script>' if schema else ''
    html=script+'<header>2027年4月21日 10:00 - 17:00 Tokyo exhibition</header><main><article><h1>'+title+'</h1>'+body+'</article></main>'
    return module('verified_extract').extract(html,url,{'language':lang,'timezone':zone,'medical':True},NOW)

def test_header_date_cannot_become_webinar_date():
    rows,_=parse('<p>2026年9月9日(水) 16:00 - 17:00</p><p>参加費無料 オンライン</p><a href="https://zoom.us/webinar/register/correct">申し込む</a>',title='医療機器セキュリティセミナー',zone='Asia/Tokyo',lang='ja')
    assert len(rows)==1
    assert rows[0]['start_at']=='2026-09-09T16:00:00+09:00'

def test_date_before_heading_is_retained():
    html='<header>2027年4月21日 10:00 - 17:00</header><main><div class="body"><p>2026年9月9日(水) 16:00 - 17:00</p><p>無料</p><h1>医療セミナー</h1><p>Zoomウェビナー</p><a href="https://zoom.us/webinar/register/abc">申し込む</a></div></main>'
    rows,_=module('verified_extract').extract(html,'https://medtecjapan.com/medtecwebinar/5992/',{'timezone':'Asia/Tokyo','language':'ja','medical':True},NOW)
    assert rows and rows[0]['start_at'].startswith('2026-09-09')

def test_unrelated_schema_ignored():
    rows,_=parse('<p>September 24, 2026, 17:00 - 18:30 CEST</p><p>Free online webinar</p><a href="https://medical.example/register/topic">Register</a>',schema={'@type':'Event','name':'Unrelated Trade Show','startDate':'2027-04-21T10:00:00+09:00'})
    assert rows[0]['start_at']=='2026-09-24T17:00:00+02:00'

def test_no_timezone_is_not_assumed_utc():
    rows,reasons=parse('<p>September 24, 2026 17:00</p><p>Free online webinar</p><a href="/register/topic">Register</a>',zone='')
    assert not rows
    assert 'date-or-timezone-unverified' in reasons

@pytest.mark.parametrize('body',[
 '<p>September 24, 2026 17:00 UTC</p><p>Online webinar. Free brochure. Registration fee USD 50.</p>',
 '<p>September 24, 2026 17:00 UTC</p><p>Online webinar. Free for members only.</p>',
 '<p>September 24, 2026 17:00 UTC</p><p>Free online webinar. Registration closed.</p>',
 '<p>September 1, 2026 17:00 UTC</p><p>Free online webinar.</p>',
 '<p>September 24, 2026 17:00 UTC</p><p>Free clinical seminar in Tokyo. In-person only.</p>',
 '<p>September 24, 2026 17:00 UTC</p><p>Online seminar; free certificate. Admission USD 20.</p>',
])
def test_rejects_ineligible(body):
    rows,_=parse(body+'<a href="/register/topic">Register</a>')
    assert not rows

def test_certificate_not_inferred_from_cme():
    rows,_=parse('<p>September 24, 2026 17:00 UTC</p><p>Free online webinar, 1.5 CME credits.</p><a href="/register/topic">Register</a>')
    assert rows[0]['certificate']=='Not stated'
    assert 'CME' in rows[0]['credits']

def test_certificate_conditions_kept_separate():
    rows,_=parse('<p>September 24, 2026 17:00 UTC</p><p>Free online webinar. Certificate of attendance available after evaluation. CME is available for members only.</p><a href="/register/topic">Register</a>')
    assert rows and 'condition' in rows[0]['certificate'].lower()

def test_fullwidth_japanese_time():
    rows,_=parse('<p>2026年9月16日(水)17：30～18：00</p><p>参加費無料 オンライン</p><a href="/register/topic">申し込む</a>',zone='Asia/Tokyo',lang='ja')
    assert rows and rows[0]['start_at']=='2026-09-16T17:30:00+09:00'

def test_thai_buddhist_date():
    rows,_=parse('<p>วันที่ 20 กันยายน 2569 เวลา 09.00-12.00 น.</p><p>อบรมแพทย์ ไม่มีค่าใช้จ่าย ณ กรุงเทพ ประเทศไทย รับเกียรติบัตรหลังทำแบบประเมิน</p><a href="/register/topic">ลงทะเบียน</a>',zone='Asia/Bangkok',lang='th',title='สัมมนาแพทย์')
    assert rows and rows[0]['start_at']=='2026-09-20T09:00:00+07:00'
    assert rows[0]['mode']=='Thailand onsite'

def test_registration_not_zoom_test_or_newsletter():
    rows,_=parse('<p>September 24, 2026 17:00 UTC</p><p>Free online webinar</p><a href="https://zoom.us/test">Test</a><a href="/newsletter/register">Register newsletter</a><a href="https://zoom.us/webinar/register/real">Register</a>')
    assert rows[0]['registration_url']=='https://zoom.us/webinar/register/real'

def test_generic_learning_portal_uses_specific_event_page():
    rows,_=parse('<p>September 24, 2026 17:00 UTC</p><p>Free online webinar</p><a href="https://learn.unclcn.org/">Register to attend in our Learning Portal</a>')
    assert rows[0]['registration_url']=='https://medical.example/event/topic'

def test_schema_offset_preserved():
    rows,_=parse('<p>Free online webinar</p><a href="/register/topic">Register</a>',schema={'@type':'Event','name':'Clinical medical webinar','startDate':'2026-10-14T12:00:00-04:00','endDate':'2026-10-14T13:00:00-04:00','isAccessibleForFree':True})
    assert rows and rows[0]['start_at']=='2026-10-14T12:00:00-04:00'

def test_index_rejected_without_event_scoping():
    rows,_=parse('<p>September 24, 2026 17:00 UTC Free online webinar</p><a href="/register/topic">Register</a>',title='Upcoming events')
    assert not rows

def test_failed_send_does_not_create_delivery_receipt(tmp_path):
    m=module('verified_notify');state={'events':{},'heartbeats':{}}
    with pytest.raises(RuntimeError):
        m.deliver('id','hello',state,tmp_path/'receipts.json',lambda _: {'ok':False},kind='event',event={'title':'test'})
    assert not state['events']

def test_success_receipt_and_retry_dedup(tmp_path):
    m=module('verified_notify'); state={'events':{},'heartbeats':{}}; calls=[]
    def sender(text):
        calls.append(text);return {'ok':True,'result':{'message_id':123,'date':1780000000}}
    assert m.deliver('id','hello',state,tmp_path/'receipts.json',sender,kind='event',event={'title':'test'})
    assert not m.deliver('id','hello',state,tmp_path/'receipts.json',sender,kind='event',event={'title':'test'})
    assert len(calls)==1 and state['events']['id']['message_id']==123

def test_status_message_distinguishes_degraded_from_empty():
    text=module('verified_notify').status_text({'health':'degraded','events':[],'sources_ok':12,'sources_total':20,'pages_checked':52,'created_at':NOW.isoformat()},0)
    assert 'DEGRADED' in text and '0 new' in text and '12/20' in text

def test_host_balance_prevents_one_source_starvation():
    rows=[{'url':f'https://a.example/event/{i}','language':'en'} for i in range(50)]+[{'url':f'https://b.example/event/{i}','language':'th'} for i in range(10)]+[{'url':f'https://c.example/event/{i}','language':'ja'} for i in range(10)]
    chosen=module('verified_scan').balanced(rows,6,0)
    assert {r['language'] for r in chosen}=={'en','th','ja'}

def test_no_public_network_targets_local_addresses():
    m=module('verified_scan')
    for u in ['file:///etc/passwd','http://127.0.0.1/','http://169.254.169.254/','http://localhost/','https://user:pass@medical.example/']:
        assert not m.safe_url(u)

def test_ncc_series_shared_schedule_split_into_individual_events():
    html='<main><h1>地域連携Webセミナー</h1><h2>がん緩和ケア支持療法セミナー</h2><p>2026年7月～2027年1月 第3水曜日17：30～18：00 対象：医療従事者（会費無料）形式：Zoomウェビナー</p><h4>第2回 2026年9月16日（水曜日）</h4><p>『がん患者の浮腫のケア』</p><p><a href="https://zoom.us/webinar/register/one">参加登録</a></p><h4>第3回 2026年10月21日（水曜日）</h4><p>『がん疼痛への対応』</p><p><a href="https://zoom.us/webinar/register/two">参加登録</a></p></main>'
    rows,_=module('verified_extract').extract(html,'https://www.ncc.go.jp/series',{'timezone':'Asia/Tokyo','language':'ja','medical':True,'adapter':'ncc_series'},NOW)
    assert len(rows)==2 and {r['start_at'][:10] for r in rows}=={'2026-09-16','2026-10-21'}
    assert rows[0]['registration_url'].endswith('/one')

def test_conflicting_schema_date_rejected():
    rows,reasons=parse('<p>September 24, 2026 17:00 UTC Free online webinar</p><a href="/register/topic">Register</a>',schema={'@type':'Event','name':'Clinical medical webinar','startDate':'2027-04-21T10:00:00+09:00'})
    assert not rows and 'conflicting-event-dates' in reasons

def test_registration_deadline_is_not_event_date():
    rows,_=parse('<p>Register by September 10, 2026 17:00 UTC</p><p>Event September 24, 2026 17:00 UTC</p><p>Free online webinar</p><a href="/register/topic">Register</a>')
    assert rows and rows[0]['start_at'].startswith('2026-09-24')

def test_free_webinar_brochure_does_not_prove_free_attendance():
    rows,_=parse('<p>September 24, 2026 17:00 UTC</p><p>Online education. Download a free webinar brochure.</p><a href="/register/topic">Register</a>')
    assert not rows
