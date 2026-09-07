"""One-time, idempotent migration on the repair branch; no notification access."""
from pathlib import Path
import json
p=Path('event_scout/verified_extract.py')
s=p.read_text(encoding='utf-8')
s=s.replace("unicodedata.normalize('NFKC',str(s))", "unicodedata.normalize('NFKC',html_lib.unescape(str(s)))")
s=s.replace('สล็อตออนไลน์', 'ลงทะเบียน'+'ฟรี')
assert "html_lib.unescape(str(s))" in s
p.write_text(s,encoding='utf-8')
p=Path('event_scout/verified_scan.py');s=p.read_text(encoding='utf-8')
a=s.index('def discover(');b=s.index('\ndef verify(',a)
# Replace only discovery; preserve the bounded network and verification layers.
s=s[:a]+r'''def resolve_news(url):
    from .verified_news import resolve
    return resolve(url,fetch,safe_url)


def discover(source,now):
    event_hint=r'webinar|seminar|conference|sympos|workshop|lecture|training|meeting|อบรม|ประชุม|สัมมนา|บรรยาย|セミナー|ウェビナー|研修|講演|学会'
    medical_hint=r'medic|clinical|health|physician|patient|patholog|oncolog|cancer|radiolog|imaging|surg|nurs|CME|CPD|แพทย์|เวช|สุขภาพ|พยาบาล|สาธารณสุข|医療|医学|臨床|がん|看護|医師|病院'
    started=time.monotonic(); url=source['url'].replace('{date}',now.date().isoformat()).replace('{year}',str(now.year)); rows=[]; dropped=0; status='ok'; decode_errors=0; raw_count=0
    if 'query' in source:
        q=source['query'].replace('{year}',str(now.year)).replace('{thai_year}',str(now.year+543))
        if source.get('engine')=='google_news':
            locales={'en':('en-US','US','US:en'),'th':('th','TH','TH:th'),'ja':('ja','JP','JP:ja')}
            hl,gl,ceid=locales[source['language']]
            url='https://news.google.com/rss/search?'+urlencode({'q':q+' when:30d','hl':hl,'gl':gl,'ceid':ceid})
        else:
            url='https://www.bing.com/search?'+urlencode({'q':q,'format':'rss','setlang':source['language'],'mkt':{'en':'en-US','th':'th-TH','ja':'ja-JP'}[source['language']]})
    try:
        html,final=fetch(url)
        if source.get('kind')=='search':
            rss=ElementTree.fromstring(html)
            if rss.find('channel') is None:raise ValueError('search-did-not-return-rss')
            for item in rss.findall('.//item'):
                raw_count+=1
                href=item.findtext('link') or '';label=item.findtext('title') or ''
                evidence=label+' '+BeautifulSoup(item.findtext('description') or '', 'html.parser').get_text(' ',strip=True)
                if not re.search(event_hint,evidence,re.I) or not re.search(medical_hint,evidence,re.I):
                    dropped+=1;continue
                if urlsplit(href).hostname=='news.google.com':
                    if len(rows)+decode_errors>=source.get('max_links',4):break
                    try:href=resolve_news(href)
                    except Exception:decode_errors+=1;continue
                rows.append((href,label))
            if (raw_count and not rows) or decode_errors:status='degraded'
        elif source.get('kind')=='tribe':
            payload=json.loads(html)
            for event in payload.get('events',[]):
                if isinstance(event,dict) and event.get('url'):rows.append((event['url'],event.get('title','')))
            if 'events' not in payload:raise ValueError('event-api-layout-changed')
        else:
            soup=BeautifulSoup(html,'html.parser')
            for tag in soup.select('head,nav,header,footer,aside,script,style'):tag.decompose()
            rows.append((final,''))
            if not source.get('adapter'):
                for a in soup.select('a[href]'):
                    href=urljoin(final,a['href']);label=a.get_text(' ',strip=True)
                    if re.search(event_hint+'|/event/|/events/|/event-listings/',href+' '+label,re.I):rows.append((href,label))
        output=[];seen=set()
        for href,label in rows:
            if not safe_url(href):continue
            if re.search(r'facebook\.com|instagram\.com|twitter\.com|youtube\.com|linkedin\.com|/privacy|/terms|/login|/tag/|/category/|\.pdf(?:$|\?)',href,re.I):continue
            normalized=clean_url(href)
            if normalized in seen:continue
            seen.add(normalized)
            row=dict(source,url=normalized,label=label,discovered_by=source['id'])
            if normalized!=clean_url(final):row.pop('adapter',None)
            if source.get('kind')=='search':row['timezone']='';row['medical']=False
            output.append(row)
        return output[:source.get('max_links',45)],{'id':source['id'],'language':source['language'],'url':url,'status':status,'candidates':len(output),'irrelevant_results_dropped':dropped,'decode_errors':decode_errors,'seconds':round(time.monotonic()-started,2)}
    except Exception as exc:
        return [],{'id':source['id'],'language':source['language'],'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:140]}

''' +s[b:]
p.write_text(s,encoding='utf-8')
p=Path('config/verified_sources.json');config=json.loads(p.read_text(encoding='utf-8'))
changes={'AMED':'https://www.amed.go.jp/form/event.php?f=event.html','NIH-VideoCast':'https://videocast.nih.gov/event-calendar','CDC-COCA':'https://www.cdc.gov/coca/hcp/trainings/index.html','Thai-CME':'https://ccme.or.th/'}
for source in config['sources']:
    if source['id'] in changes:source['url']=changes[source['id']]
    if source['id']=='AMED':source['max_links']=60
new=[{'id':'UNC-Event-API','kind':'tribe','url':'https://unclineberger.org/unclcn/wp-json/tribe/events/v1/events?start_date={date}&per_page=40','language':'en','timezone':'America/New_York','medical':True,'max_links':40},{'id':'Asahikawa-Medical','url':'https://www.asahikawa-med.ac.jp/hospital/event/','language':'ja','timezone':'Asia/Tokyo','medical':True},{'id':'Sapporo-Medical','url':'https://web.sapmed.ac.jp/jp/news/event/index.html','language':'ja','timezone':'Asia/Tokyo','medical':True}]
for language,queries in {'en':['free medical webinar','free healthcare seminar'],'th':['แพทย์ ฟรี อบรม','สัมมนา สุขภาพ ออนไลน์'],'ja':['医療 無料 セミナー','医学 ウェビナー 無料']}.items():
    for i,query in enumerate(queries,1):new.append({'id':f'news-{language}-{i}','kind':'search','engine':'google_news','url':'https://news.google.com/rss/search','query':query,'language':language,'timezone':'','medical':False,'max_links':4})
for row in new:
    if not any(s['id']==row['id'] for s in config['sources']):config['sources'].append(row)
p.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Applied event-scoping and multilingual discovery fixes; sources:',len(config['sources']))
