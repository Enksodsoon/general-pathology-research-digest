"""Bounded, multilingual discovery, event verification, and explicit scan health."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, ipaddress, json, os, re, socket, threading, time
import urllib.request, urllib.error
from xml.etree import ElementTree
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urljoin, urlencode
from bs4 import BeautifulSoup
from .verified_extract import extract, clean_url, norm, CLOSED

LIMIT=2500000
HOST_LOCKS=defaultdict(threading.Lock)

def safe_url(url):
    try:
        p=urlsplit(url); host=p.hostname
        if p.scheme not in ('http','https') or not host or p.username or p.password or p.port not in (None,80,443): return False
        if host in ('localhost','localhost.localdomain') or host.endswith(('.local','.internal','.localhost')): return False
        try: return ipaddress.ip_address(host).is_global
        except ValueError: return '.' in host
    except ValueError: return False

def check_dns(url):
    if not safe_url(url): raise ValueError('unsafe-url')
    p=urlsplit(url)
    for record in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(record[4][0]).is_global: raise ValueError('non-public-dns')

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        check_dns(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url):
    check_dns(url)
    with HOST_LOCKS[urlsplit(url).hostname]:
        req=urllib.request.Request(url,headers={'User-Agent':'MedicalEventRadar/2.0 (+https://github.com/Enksodsoon/general-pathology-research-digest)','Accept':'text/html,application/json,application/rss+xml,application/xml','Accept-Language':'en,th;q=0.9,ja;q=0.9'})
        with urllib.request.build_opener(SafeRedirect).open(req,timeout=12) as response:
            data=response.read(LIMIT+1)
            if len(data)>LIMIT: raise ValueError('page-too-large')
            typ=response.headers.get_content_type()
            if not any(t in typ for t in ('html','xml','json','text')): raise ValueError('unsupported-content-type')
            text=data.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
            if re.search(r'just a moment\.\.\.|verify you are human|unusual traffic',text[:15000],re.I): raise ValueError('access-challenge')
            return text,response.geturl()

def balanced(rows,limit,rotation=0):
    """Round-robin domains, then rotate deep queues; no single host fills the budget."""
    groups=defaultdict(list); seen=set()
    for r in rows:
        if r['url'] in seen:continue
        seen.add(r['url']); groups[urlsplit(r['url']).hostname].append(r)
    queues=[]
    for host in sorted(groups):
        group=sorted(groups[host],key=lambda r: -(5 if r.get('adapter') else 4 if re.search(r'/event/|/event-listings/',r['url']) else 2 if re.search(r'free|無料|ฟรี',r.get('label',''),re.I) else 0)); first=group[:3];rest=group[3:]
        if rest:
            shift=rotation%len(rest);rest=rest[shift:]+rest[:shift]
        queues.append(deque(first+rest))
    out=[]
    while queues and len(out)<limit:
        for q in queues:
            if q and len(out)<limit:out.append(q.popleft())
        queues=[q for q in queues if q]
    return out

def resolve_news(url):
    from .verified_news import resolve
    return resolve(url,fetch,safe_url)


def resolve_news(url):
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
            normalized=urlsplit(clean_url(href))._replace(fragment='').geturl()
            if normalized in seen:continue
            seen.add(normalized)
            row=dict(source,url=normalized,label=label,discovered_by=source['id'])
            if normalized!=clean_url(final):row.pop('adapter',None)
            if source.get('kind')=='search':row['timezone']='';row['medical']=False
            output.append(row)
        return output[:source.get('max_links',45)],{'id':source['id'],'language':source['language'],'url':url,'status':status,'candidates':len(output),'irrelevant_results_dropped':dropped,'decode_errors':decode_errors,'seconds':round(time.monotonic()-started,2)}
    except Exception as exc:
        return [],{'id':source['id'],'language':source['language'],'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:140]}


def verify(candidate,now,sources):
    url=candidate['url']
    try:
        html,final=fetch(url); info=dict(candidate)
        for s in sources:
            if s.get('kind')!='search' and urlsplit(s['url']).hostname==urlsplit(final).hostname:
                info.update(timezone=s.get('timezone',''),medical=s.get('medical',False),language=s['language']);break
        events,reasons=extract(html,final,info,now)
        for event in events:
            target=event['registration_url']
            if target!=event['source_url']:
                try:
                    registration,resolved=fetch(target)
                    visible=BeautifulSoup(registration,'html.parser').get_text(' ',strip=True)
                    if re.search(CLOSED,visible,re.I) or '/closedform' in resolved:
                        return [],{'url':url,'status':'rejected','reasons':['registration-target-closed']}
                    event['registration_status']='Registration link checked; availability may require login/JavaScript'
                except Exception:
                    event['registration_url']=event['source_url']
                    event['registration_status']='Use source event page; direct registration could not be checked'
            event['discovered_by']=candidate['discovered_by']
        return events,{'url':url,'status':'accepted' if events else 'rejected','reasons':reasons,'language':info['language']}
    except Exception as exc:
        return [],{'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:140],'language':candidate.get('language')}

def save_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

def scan(config,now):
    sources=config['sources']; diagnostic=[];candidates=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for rows,diag in pool.map(lambda s:discover(s,now),sources):candidates.extend(rows);diagnostic.append(diag)
    chosen=balanced(candidates,config.get('max_pages',180),now.toordinal()*7)
    events=[];pages=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for rows,diag in pool.map(lambda c:verify(c,now,sources),chosen):events.extend(rows);pages.append(diag)
    byid={e['id']:e for e in events};events=sorted(byid.values(),key=lambda e:(datetime.fromisoformat(e['start_at']),e['title']))
    ok=sum(d['status']=='ok' for d in diagnostic)
    language_ok={lang:sum(d['status']=='ok' and d['language']==lang for d in diagnostic) for lang in ('en','th','ja')}
    errors=sum(d['status']=='error' for d in pages)
    health='failed' if ok==0 else ('degraded' if ok<len(sources) or errors or not all(language_ok.values()) or not events else 'ok')
    return {'version':2,'created_at':now.isoformat(),'health':health,'sources_ok':ok,'sources_total':len(sources),'language_sources_ok':language_ok,'links_discovered':len({r['url'] for r in candidates}),'pages_checked':len(chosen),'page_errors':errors,'events':events,'sources':diagnostic,'pages':pages,'coverage_note':'Bounded scan; inaccessible, image-only, login-only or ambiguous events are not verified. Zero matches does not establish absence of events.'}

def report(result):
    lines=['# Free Medical Events — '+result['created_at'][:10],'',f"Scan health: **{result['health'].upper()}** · Sources {result['sources_ok']}/{result['sources_total']} · Pages checked {result['pages_checked']}",'',result['coverage_note'],'']
    for e in result['events']:
        d=datetime.fromisoformat(e['start_at']).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Bangkok'))
        lines.extend([f"## {e['title']}",f"{d:%d %b %Y %H:%M} ICT · {e['mode']} · {e['language'].upper()} · Free attendance",f"Certificate: {e['certificate']} | Credit: {e['credits']}",e['registration_url'],e['registration_status'],''])
    lines.extend(['## Source health','']+[f"- {d['id']}: {d['status']}"+(f" — {d['error']}" if 'error' in d else '') for d in result['sources']])
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='data/verified_radar');p.add_argument('--config',default='config/verified_sources.json');args=p.parse_args()
    config=json.loads(Path(args.config).read_text());now=datetime.now(timezone.utc);result=scan(config,now)
    out=Path(args.output);save_json(out/'latest.json',result);(out/'latest.md').write_text(report(result),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('events','sources','pages')},ensure_ascii=False))
    print('Verified events:',len(result['events']))
    if result['health']=='failed': raise SystemExit(2)

if __name__=='__main__':main()
