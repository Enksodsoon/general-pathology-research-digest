"""Event-scoped extraction. Search snippets are never eligibility evidence."""
from __future__ import annotations
import hashlib, html as html_lib, json, re, unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

GENERIC = {'conferences events','conferences and events','event calendar','events and educational opportunities','seminar calendar','events','upcoming events','webinars','free webinars','seminars','event listings','past webinars','ウェビナー','無料聴講ウェビナー','過去のウェビナー','オンデマンドウェビナー','イベント一覧'}
MONTHS = {v:i for i,names in enumerate(('January Jan','February Feb','March Mar','April Apr','May','June Jun','July Jul','August Aug','September Sep Sept','October Oct','November Nov','December Dec'),1) for v in names.lower().split()}
THAI = {v:i for i,names in enumerate(('มกราคม ม.ค.','กุมภาพันธ์ ก.พ.','มีนาคม มี.ค.','เมษายน เม.ย.','พฤษภาคม พ.ค.','มิถุนายน มิ.ย.','กรกฎาคม ก.ค.','สิงหาคม ส.ค.','กันยายน ก.ย.','ตุลาคม ต.ค.','พฤศจิกายน พ.ย.','ธันวาคม ธ.ค.'),1) for v in names.split()}
ZONES={'UTC':'UTC','GMT':'UTC','ICT':'Asia/Bangkok','JST':'Asia/Tokyo','BST':'Europe/London','CEST':'Europe/Berlin','CET':'Europe/Berlin','ET':'America/New_York','EDT':'America/New_York','EST':'America/New_York','PT':'America/Los_Angeles','PDT':'America/Los_Angeles','PST':'America/Los_Angeles'}
CLOSED=r'registration (?:is |has )?closed|registrations closed|sold out|event (?:has )?ended|no longer accepting responses|ปิดรับ(?:สมัคร|ลงทะเบียน|การลงทะเบียน)|เต็มแล้ว|受付終了|申込終了|募集終了|満席'
REG=r'register|registration|book now|sign up|ลงทะเบียน|สมัคร|申し込|申込|参加登録'

def norm(s):
    return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',html_lib.unescape(str(s))).casefold()).strip()

def clean_url(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.startswith('utm_') and k not in ('fbclid','gclid')]),p.fragment))

def stamp(value,zone=''):
    if not value or not re.search(r'\d[T ]\d',str(value)): return None
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if d.tzinfo is None:
            if not zone: return None
            d=d.replace(tzinfo=ZoneInfo(zone))
        return d
    except (ValueError,KeyError): return None

def dates(text,zone=''):
    """Require date and clock to be adjacent, never bridge a second date."""
    s=unicodedata.normalize('NFKC',text).translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))
    patterns=[
        (r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日','jp'),
        (r'(\d{1,2})\s*('+ '|'.join(map(re.escape,THAI))+r')\s*(?:พ.ศ.\s*)?(25\d{2}|20\d{2})','th'),
        (r'\b('+ '|'.join(MONTHS)+r')\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(20\d{2})','en'),
        (r'\b(\d{1,2})(?:st|nd|rd|th)?\s+('+ '|'.join(MONTHS)+r')\s*,?\s*(20\d{2})','uk'),
        (r'\b(20\d{2})-(\d{2})-(\d{2})','iso')]
    found=[]
    for pattern,kind in patterns:
        for match in re.finditer(pattern,s,re.I):
            prefix=s[max(0,s.rfind('\n',0,match.start())):match.start()]
            if re.search(r'deadline|register by|registration closes|posted|published|สมัครภายใน|締切|申込期限',prefix,re.I):continue
            tail=s[match.end():match.end()+110]
            clock=re.match(r'[^\d]{0,45}(\d{1,2})[:.](\d{2})\s*(AM|PM)?(?:\s*[-–—~〜～至]\s*(\d{1,2})[:.](\d{2})\s*(AM|PM)?)?',tail,re.I)
            if not clock: continue
            a,b,c=match.groups()
            if kind in ('jp','iso'): y,mo,day=int(a),int(b),int(c)
            elif kind=='th': y,mo,day=int(c),THAI[b],int(a); y=y-543 if y>2400 else y
            elif kind=='en': y,mo,day=int(c),MONTHS[b.lower()] if b.lower() in MONTHS else MONTHS[a.lower()],int(b)
            else: y,mo,day=int(c),MONTHS[b.lower()],int(a)
            tm=clock.groups(); hh,mi=int(tm[0]),int(tm[1]); am=tm[2] or tm[5]
            if am: hh=hh%12+(12 if am.lower()=='pm' else 0)
            tzmatch=re.search(r'\b(CEST|CET|UTC|GMT|ICT|JST|BST|EDT|EST|PDT|PST|ET|PT)\b',tail[clock.end():clock.end()+40],re.I)
            tz=ZONES.get(tzmatch.group().upper(),zone) if tzmatch else zone
            if not tz: continue
            try:
                start=datetime(y,mo,day,hh,mi,tzinfo=ZoneInfo(tz)); end=None
                if tm[3]:
                    eh=int(tm[3]); ea=tm[5] or tm[2]
                    if ea: eh=eh%12+(12 if ea.lower()=='pm' else 0)
                    end=start.replace(hour=eh,minute=int(tm[4]))
                    if end<=start: end+=timedelta(days=1)
                found.append((match.start(),start,end,s[match.start():match.end()+clock.end()]))
            except (ValueError,KeyError): continue
    return sorted(found,key=lambda x:x[0])

def schema_events(value):
    if isinstance(value,dict):
        types=value.get('@type',[]);types=types if isinstance(types,list) else [types]
        if any(str(t).endswith('Event') for t in types): yield value
        for v in value.values(): yield from schema_events(v)
    elif isinstance(value,list):
        for v in value: yield from schema_events(v)

def extract(html,url,source,now):
    soup=BeautifulSoup(html,'html.parser'); schemas=[]
    if source.get('adapter')=='ncc_series': return ncc_series(soup,url,source,now)
    for script in soup.select('script[type="application/ld+json"]'):
        try: schemas.extend(schema_events(json.loads(script.get_text())))
        except (ValueError,TypeError): pass
    for header in soup.select('header'):
        if header.find_parent(['main','article']) is not None and header.find('h1') is not None:
            header.unwrap()
    for tag in soup.select('head,script,style,nav,header,footer,aside,noscript,template,.tribe-related-events,.related-posts,[class*="cookie"],[id*="cookie"]'): tag.decompose()
    root=soup.select_one('.tribe-events-single') or soup.select_one('main') or soup.select_one('[role="main"]') or soup.select_one('#main') or soup.select_one('article') or soup
    headings=[h for h in root.select('h1') if h.get_text(' ',strip=True)]
    heading=headings[-1] if headings else None
    title=heading.get_text(' ',strip=True) if heading else ''
    if not title: return [],['missing-event-heading']
    if norm(title) in GENERIC: return [],['generic-index']
    # Main/article DOM boundary removes all sitewide dates, including repeated banners.
    text=unicodedata.normalize('NFKC',root.get_text('\n',strip=True))[:35000]
    lower=text.casefold(); topic=norm(title)
    candidates=[e for e in schemas if norm(e.get('name','')) and (norm(e['name']) in topic or topic in norm(e['name']))]
    if len(candidates)>1: return [],['multiple-event-schemas']
    event=candidates[0] if candidates else {}
    zone=source.get('timezone',''); start=stamp(event.get('startDate'),zone);end=stamp(event.get('endDate'),zone)
    date_evidence='schema.org Event matched to title' if start else ''
    visible=dates(text,zone)
    if start and visible:
        pos=text.find(unicodedata.normalize('NFKC',title))
        nearest=min(visible,key=lambda d:abs(d[0]-max(0,pos)))
        if nearest[1].date()!=start.date():return [],['conflicting-event-dates']
    if start is None and visible:
        # Closest date to the event H1; never use a site's global header.
        pos=text.find(unicodedata.normalize('NFKC',title))
        best=min(visible,key=lambda d:abs(d[0]-max(0,pos)))
        _,start,end,date_evidence=best
    if start is None: return [],['date-or-timezone-unverified']
    if start<=now: return [],['past-event']
    if start>now+timedelta(days=365): return [],['outside-lookahead']
    if re.search(CLOSED,lower): return [],['registration-closed']
    if any(x in str(event.get('eventStatus','')).lower() for x in ('cancelled','postponed')): return [],['cancelled-or-postponed']
    online=bool(re.search(r'online|virtual|webinar|zoom|teams|ออนไลน์|オンライン|ウェビナー|ライブ配信',lower)) or 'Online' in str(event.get('eventAttendanceMode',''))
    if re.search(r'in.person only|on.site only|onsite only',lower):online=False
    thailand=bool(re.search(r'thailand|ประเทศไทย|กรุงเทพ|เชียงใหม่|ขอนแก่น|สงขลา',lower))
    if not online and not thailand: return [],['not-online-or-thailand']
    offers=event.get('offers',[]); offers=offers if isinstance(offers,list) else [offers]
    prices=[]
    for o in offers:
        if isinstance(o,dict):
            try: prices.append(float(o['price']))
            except (KeyError,ValueError,TypeError): pass
    # Attendance restrictions are distinct from restrictions on credit/certificates.
    restricted=re.search(r'free for members|members (?:attend )?free|members.only (?:event|webinar)|เฉพาะสมาชิก|会員限定|会員のみ',lower)
    paid=re.search(r'(?:registration|admission|attendance|course|ticket) fee.{0,25}?(?:usd|thb|jpy|[$฿¥£€])\s*[1-9]|ค่าลงทะเบียน.{0,25}?[1-9][\d,]*\s*บาท|(?:参加費|受講料).{0,15}?[1-9][\d,]*円',lower)
    if restricted or paid or any(p>0 for p in prices): return [],['paid-or-restricted-attendance']
    free=bool(re.search(r'free (?:registration|admission|attendance|online (?:medical )?webinar|webinar|seminar|to attend)(?!\s+(?:brochure|preview|materials|recording))|(?:registration|attendance) (?:is )?free|free of charge|no (?:registration )?(?:cost|fee)|price:\s*free|cost:\s*free|เข้าร่วมฟรี|สมัครฟรี|ลงทะเบียนฟรี|ไม่มีค่าใช้จ่าย|ไม่เสียค่า(?:ใช้จ่าย|ลงทะเบียน)|参加費無料|受講料無料|会費無料|参加は無料|(?m:^\s*(?:free|無料)\s*$)',lower))
    if not (free or 0 in prices or event.get('isAccessibleForFree') is True): return [],['free-attendance-unverified']
    relevant=source.get('medical') or re.search(r'medic|clinical|health|pathology|oncolog|cancer|nurs|physician|patient|แพทย์|สุขภาพ|เวช|医療|医学|臨床|看護|がん',lower)
    if not relevant: return [],['medical-relevance-unverified']
    links=[]
    for a in root.select('a[href]'):
        href=urljoin(url,a['href']); anchor=a.get_text(' ',strip=True); p=urlsplit(href)
        if p.scheme not in ('http','https') or p.username or not p.hostname: continue
        if re.search(r'newsletter|interest-with|privacy|terms|zoom\.us/test|/setup|/login$|/signup$|calendar',href+' '+anchor,re.I): continue
        if re.search(REG,anchor,re.I):
            direct=bool(re.search(r'/webinar/register/|forms\.gle/|/forms/d/|registration|/register/.+|redirectUrl=',href,re.I))
            links.append((3 if direct else 1,href))
    link=max(links,default=(0,url),key=lambda x:x[0])[1]
    if urlsplit(link).path in ('','/') or re.search(r'/events/?$|/webinars/?$',urlsplit(link).path): link=url
    if not links and not offers and not root.select('form'): return [],['registration-action-unverified']
    cert='Not stated';credits='Not stated'
    if re.search(r'certificate of (?:attendance|participation|completion)|attendance certificate|download.{0,30}certificate|เกียรติบัตร|ประกาศนียบัตร|受講証明書|修了証',lower):
        cert='Available; attendance/evaluation conditions may apply'
    if re.search(r'no (?:attendance )?certificate|certificate.{0,8}not (?:available|provided)|ไม่มีเกียรติบัตร|発行しません',lower):cert='Not offered'
    if re.search(r'cme.{0,10}credit|\d(?:\.\d+)?\s*(?:european )?cme|ecmec|cpd.{0,10}(?:point|credit)|คะแนน\s*cme|認定単位',lower):credits='CME/CPD offered; eligibility must be checked'
    if re.search(r'(?:cme|credit|certificate).{0,65}members? only|certificate.{0,35}(?:fee|paid)|有料.{0,15}(?:証明書|修了証)',lower):
        credits='Restricted/conditional; not confirmed free'
        if cert!='Not stated':cert='Conditional; fee/membership rules apply'
    if re.search(r'no (?:cme|cpd) credits|(?:cme|cpd) credits? (?:is |are )?not (?:available|offered|provided)',lower): credits='Not offered'
    elif re.search(r'(?:application|applied|pending).{0,60}(?:cme|cpd)|(?:cme|cpd).{0,60}(?:pending|applied)',lower): credits='Application pending; not confirmed accredited'
    lang=source.get('language','')
    if re.search(r'[ก-๙]',title):lang='th'
    elif re.search(r'[ぁ-ヿ一-龥]',title):lang='ja'
    if lang not in ('en','th','ja'): return [],['language-unverified']
    event_id=hashlib.sha256((norm(title)+'|'+start.astimezone(timezone.utc).isoformat()).encode()).hexdigest()[:24]
    row={'id':event_id,'title':title,'source_url':clean_url(url),'registration_url':clean_url(link),'start_at':start.isoformat(),'end_at':end.isoformat() if end else None,'mode':'Online' if online else 'Thailand onsite','language':lang,'certificate':cert,'credits':credits,'fee':'Free attendance','date_evidence':date_evidence,'verified_at':now.isoformat(),'registration_status':'Organizer provides registration; not submitted'}
    return [row],[]


def ncc_series(soup,url,source,now):
    """NCC explicitly supplies a common clock/free policy for its dated sessions."""
    heading=next((h for h in soup.select('h2') if 'がん緩和ケア支持療法セミナー' in h.get_text()),None)
    if heading is None:return [],['ncc-series-layout-changed']
    nodes=[]
    for node in heading.next_siblings:
        if getattr(node,'name',None)=='h2':break
        nodes.append(node)
    markup=''.join(map(str,nodes));part=BeautifulSoup(markup,'html.parser')
    prefix=unicodedata.normalize('NFKC',heading.get_text(' ',strip=True)+' '+part.get_text(' ',strip=True))
    clock=re.search(r'(\d{1,2}:\d{2})\s*[~〜～–-]\s*(\d{1,2}:\d{2})',prefix)
    if not clock or not re.search('会費無料|参加費無料',prefix):return [],['ncc-series-policy-unverified']
    events=[];reasons=[]
    for h in part.select('h4'):
        date=re.search(r'20\d{2}年\d{1,2}月\d{1,2}日',h.get_text())
        if not date:continue
        bits=[]
        for sibling in h.next_siblings:
            if getattr(sibling,'name',None) in ('h2','h3','h4'):break
            bits.append(str(sibling))
        block=BeautifulSoup(''.join(bits),'html.parser')
        topic=re.search(r'『([^』]+)』',block.get_text(' ',strip=True))
        link=block.select_one('a[href*="/webinar/register/"]')
        if not topic or not link:continue
        topic=topic.group(1)
        card='<main><h1>'+html_lib.escape(topic)+'</h1><p>'+date.group()+' '+clock.group(1)+'-'+clock.group(2)+'</p><p>会費無料 Zoomウェビナー</p><a href="'+html_lib.escape(link['href'],quote=True)+'">参加登録</a></main>'
        info=dict(source);info.pop('adapter',None)
        rows,why=extract(card,url,info,now)
        for row in rows:row['date_evidence']='NCC dated session plus explicit shared series clock'
        events.extend(rows);reasons.extend(why)
    return events,([] if events else reasons or ['ncc-no-eligible-sessions'])
