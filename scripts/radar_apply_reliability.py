"""One-time migration, applied only on the isolated repair branch."""
from pathlib import Path
import json
p=Path('event_scout/verified_scan.py');s=p.read_text(encoding='utf-8')
assert 'def scan(config,now):' in s
s=s.replace('from .verified_extract import extract, clean_url, norm, CLOSED','from .verified_extract import extract, clean_url, norm, CLOSED\nfrom .verified_reliability import assess_health, is_transient, merge_backlog')
s=s.replace('def fetch(url):','def _fetch_once(url):',1).replace('open(req,timeout=12)','open(req,timeout=20)',1)
needle='\ndef balanced(rows,limit,rotation=0):'
wrapper='''
def fetch(url):
    for attempt in range(2):
        try:return _fetch_once(url)
        except Exception as exc:
            if attempt or not is_transient(exc):raise
            time.sleep(1.0)
    raise RuntimeError('Fetch retry exhausted')

'''
s=s.replace(needle,'\n'+wrapper+needle,1)
s=s.replace("group=sorted(groups[host],key=lambda r: -(5 if r.get('adapter')", "group=sorted(groups[host],key=lambda r: -(9 if r.get('pending') else 5 if r.get('adapter')")
duplicate="def resolve_news(url):\n    from .verified_news import resolve\n    return resolve(url,fetch,safe_url)\n\n\ndef resolve_news(url):\n    from .verified_news import resolve\n    return resolve(url,fetch,safe_url)"
s=s.replace(duplicate,"def resolve_news(url):\n    from .verified_news import resolve\n    return resolve(url,fetch,safe_url)")
s=s.replace('def discover(source,now):','def _discover_once(source,now):',1)
s=s.replace("for item in rss.findall('.//item'):","items=rss.findall('.//item')\n            if items and source.get('rotate_results',False):\n                shift=(now.toordinal()*3)%len(items); items=items[shift:]+items[:shift]\n            for item in items:")
s=s.replace("if (raw_count and not rows) or decode_errors:status='degraded'", "if decode_errors or (source.get('engine')!='google_news' and raw_count and not rows):status='degraded'")
s=s.replace("discovered_by=source['id'])", "discovered_by=source['id'],origin_host=urlsplit(final).hostname)")
s=s.replace("'candidates':len(output),'irrelevant_results_dropped'", "'candidates':len(output),'kind':source.get('kind','landing'),'search_outcome':('matches' if output else 'no-relevant-results') if source.get('kind')=='search' else 'not-applicable','raw_results':raw_count,'irrelevant_results_dropped'")
point='\ndef verify(candidate,now,sources):'
fallback='''
def discover(source,now):
    rows,diag=_discover_once(source,now)
    if diag['status']=='error' and source.get('fallbacks'):
        attempts=[dict(diag)]
        for fallback in source['fallbacks']:
            alternative=dict(source);alternative.pop('fallbacks',None);alternative.update(fallback)
            extra,result=_discover_once(alternative,now);attempts.append(result)
            if result['status']=='ok':
                # Different organizational pages are additional coverage, not an
                # equivalent replacement for an inaccessible original publisher.
                result.update(id=source['id'],status='degraded',fallback_used=True,primary_url=source['url'],fallback_note='Partial official alternative; original publisher remains unverified',attempts=attempts)
                return extra,result
        diag['attempts']=attempts
    return rows,diag

'''
s=s.replace(point,'\n'+fallback+point,1)
s=s.replace("html,final=fetch(url); info=dict(candidate)","html,final=fetch(url); info=dict(candidate)\n        origin=info.get('origin_host')\n        if origin and origin!=urlsplit(final).hostname:\n            info.update(timezone='',medical=False)\n        declared=(BeautifulSoup(html,'html.parser').html or {}).get('lang','').split('-')[0].lower()\n        if declared and declared not in ('en','th','ja'):info['language']=''")
s=s.replace("target=event['registration_url']", "target=event['registration_url']\n            event['registration_target']=target",1)
s=s.replace("sources=config['sources']; diagnostic=[];candidates=[]", "sources=config['sources']; diagnostic=[];candidates=[]\n    for row in config.get('_backlog',{}).values():\n        e=row.get('event',{});url=e.get('source_url','')\n        if not safe_url(url):continue\n        info=next((dict(s) for s in sources if s.get('kind')!='search' and urlsplit(s['url']).hostname==urlsplit(url).hostname),{})\n        info.update(url=url,discovered_by=info.get('id','pending-reverification'),language=info.get('language',e.get('language','')),pending=True)\n        candidates.append(info)")
a=s.index("    ok=sum(d['status']=='ok' for d in diagnostic)");b=s.index('\ndef report(result):',a)
s=s[:a]+'''    health=assess_health(diagnostic,pages,events)
    return {'version':3,'created_at':now.isoformat(),**health,'links_discovered':len({r['url'] for r in candidates}),'pages_checked':len(chosen),'events':events,'sources':diagnostic,'pages':pages,'coverage_note':'Bounded scan; inaccessible, image-only, login-only or ambiguous events are not verified. Official fallback pages provide partial alternative coverage, not equivalence. Zero matches does not establish absence of events.'}

'''+s[b:]
s=s.replace("config=json.loads(Path(args.config).read_text());now=datetime.now(timezone.utc);result=scan(config,now)", "config=json.loads(Path(args.config).read_text());now=datetime.now(timezone.utc)\n    queue_path=Path(args.output)/'backlog.json'\n    backlog=json.loads(queue_path.read_text()) if queue_path.exists() else {}\n    config['_backlog']=merge_backlog(backlog,[],now)\n    result=scan(config,now)\n    save_json(queue_path,merge_backlog(backlog,result['events'],now))")
s=s.replace("f\" — {d['error']}\" if 'error' in d else ''", "f\" — {d['error']}\" if 'error' in d else (' — '+d['fallback_note'] if d.get('fallback_used') else '')")
p.write_text(s,encoding='utf-8')
p=Path('event_scout/verified_notify.py');s=p.read_text(encoding='utf-8')
s=s.replace("if old.get('fingerprint')==fp and type(old.get('message_id')) is int:return False", "same_target=(not event or canonical_url(old.get('event',{}).get('registration_target',''))==canonical_url(event.get('registration_target','')))\n    if old.get('fingerprint')==fp and type(old.get('message_id')) is int and same_target:return False")
s=s.replace("if not response.get('ok') or type(message.get('message_id'))", "if not isinstance(response,dict) or not response.get('ok') or type(message.get('message_id'))")
p.write_text(s,encoding='utf-8')
p=Path('config/verified_sources.json');config=json.loads(p.read_text())
for source in config['sources']:
    if source['id']=='Chula-Hospital':
        source['fallbacks']=[{'url':'https://www.md.chula.ac.th/pr-news/','timezone':'Asia/Bangkok','language':'th','medical':True,'max_links':35}]
    if source['id']=='Thai-MOPH':
        source['fallbacks']=[{'url':'https://www.dmsc.moph.go.th/th/home','timezone':'Asia/Bangkok','language':'th','medical':True,'max_links':35}]
    if source.get('kind')=='search':source.update(rotate_results=True,max_links=3)
existing={r['id'] for r in config['sources']}
for source in [
 {'id':'Chula-Publisher-Discovery','kind':'search','engine':'google_news','url':'https://news.google.com/rss/search','query':'site:kcmh.chulalongkornhospital.go.th (อบรม OR ประชุม OR สัมมนา)','language':'th','timezone':'','medical':False,'max_links':3,'rotate_results':True},
 {'id':'MOPH-Publisher-Discovery','kind':'search','engine':'google_news','url':'https://news.google.com/rss/search','query':'site:moph.go.th (อบรม OR สัมมนา) (ฟรี OR ไม่มีค่าใช้จ่าย)','language':'th','timezone':'','medical':False,'max_links':3,'rotate_results':True}
]:
    if source['id'] not in existing:config['sources'].append(source)
config['max_pages']=220
p.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Applied recovery and source reliability patch')
