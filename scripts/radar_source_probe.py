"""Read-only endpoint diagnostics; no credentials or registrations."""
import json, concurrent.futures, time, urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
from event_scout.verified_scan import fetch
URLS=[
 'https://kcmh.chulalongkornhospital.go.th/feed/',
 'https://kcmh.chulalongkornhospital.go.th/wp-json/wp/v2/poster?per_page=20',
 'https://kcmh.chulalongkornhospital.go.th/poster/',
 'https://www.md.chula.ac.th/',
 'https://pr.moph.go.th/',
 'https://ddc.moph.go.th/',
 'https://ddc.moph.go.th/training.php',
 'https://www.dmsc.moph.go.th/',
 'https://www.cdc.gov/coca/hcp/trainings/index.html',
 'https://icimagingsociety.org.uk/events-archive/',
]
def probe(url):
    started=time.monotonic()
    try:
        text,final=fetch(url);soup=BeautifulSoup(text,'html.parser')
        for t in soup.select('script,style,nav,header,footer'):t.decompose()
        return {'url':url,'final_url':final,'status':'ok','bytes':len(text),'title':(soup.title.get_text() if soup.title else '')[:150],'sample':soup.get_text(' ',strip=True)[:350],'links':[{'url':a.get('href'),'text':a.get_text(' ',strip=True)[:100]} for a in soup.select('a[href]') if any(w in str(a).lower() for w in ('rss','feed','poster','อบรม','ประชุม','training','seminar','webinar'))][:12],'seconds':round(time.monotonic()-started,2)}
    except Exception as exc:return {'url':url,'status':'error','error':type(exc).__name__+': '+str(exc)[:200]}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(probe,URLS))
out=Path('repair_evidence/reliability');out.mkdir(parents=True,exist_ok=True)
(out/'source_probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for r in rows:print(r['url'],r['status'],r.get('error',''))
