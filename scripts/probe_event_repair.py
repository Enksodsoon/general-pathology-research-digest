"""Read-only network/DOM probe; does not send notifications."""
import concurrent.futures, json, pathlib, urllib.request
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from event_scout.parsing import parse_event_page
from event_scout.models import SearchHit
URLS = [
'https://medtecjapan.com/medtecwebinar/5992/',
'https://icimagingsociety.org.uk/events/free-webinar-msk-imaging-update/',
'https://www.cirse.org/online/cirse-webinars/artificial-intelligence-and-robotic-innovations-in-non-oncological-interventional-radiology/',
'https://unclineberger.org/unclcn/event/10142026/',
'https://unclineberger.org/unclcn/events/',
'https://www.ncc.go.jp/jp/ncch/division/support/physician_referral_service/web_seminar/index.html',
'https://cimjournal.com/home-conference/',
'https://www.bing.com/search?q=free+medical+webinar+2026&format=rss',
'https://www.who.int/news-room/events',
'https://www.amed.go.jp/news/event.html']
def probe(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (compatible; MedicalEventRadar/2.0)'})
        with urllib.request.urlopen(req, timeout=15) as r:
            html=r.read(2000000).decode('utf-8', errors='replace')
        soup=BeautifulSoup(html,'html.parser')
        headings=[{'tag':h.name,'text':h.get_text(' ',strip=True)[:220], 'parent':str(h.parent)[:180]} for h in soup.select('h1,h2')][:12]
        regions={s:len(soup.select(s)) for s in ['main','article','.entry-content','.tribe-events-single','.c-section--webinar','[role=main]']}
        schemas=[s.get_text()[:3200] for s in soup.select('script[type="application/ld+json"]')][:2]
        baseline=parse_event_page(SearchHit('probe',url,'','probe','probe','en'),html,datetime.now(timezone.utc))
        for tag in soup.select('script,style,nav,header,footer,noscript'): tag.decompose()
        text=soup.get_text('\n',strip=True)
        return {'url':url,'headings':headings,'regions':regions,'schemas':schemas,'visible':text[:10500],'baseline':baseline.to_dict(),'links':[{'text':a.get_text(' ',strip=True)[:120],'url':a.get('href')} for a in soup.select('a[href]') if any(w in str(a).lower() for w in ['register','webinar','event','seminar','ลงทะเบียน','申し込'])][:45]}
    except Exception as e: return {'url':url,'error':type(e).__name__+': '+str(e)[:200]}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(probe,URLS))
out=pathlib.Path('repair_evidence'); out.mkdir(exist_ok=True)
(out/'probe.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
for row in rows: print(row['url'],row.get('error',row.get('baseline',{}).get('start_at')))
