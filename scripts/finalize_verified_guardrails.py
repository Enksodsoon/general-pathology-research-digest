"""One-time idempotent repair; production modules contain the resulting code."""
from pathlib import Path
import json
p=Path('event_scout/verified_extract.py');s=p.read_text(encoding='utf-8')
s=s.replace("GENERIC = {'events',", "GENERIC = {'conferences events','conferences and events','event calendar','events and educational opportunities','seminar calendar','events',")
s=s.replace("for tag in soup.select('head,script,style,nav,header,footer,aside,noscript,template,.tribe-related-events,.related-posts,[class*=\"cookie\"],[id*=\"cookie\"]'): tag.decompose()", "for header in soup.select('header'):\n        if header.find_parent(['main','article']) is not None and header.find('h1') is not None:\n            header.unwrap()\n    for tag in soup.select('head,script,style,nav,header,footer,aside,noscript,template,.tribe-related-events,.related-posts,[class*=\"cookie\"],[id*=\"cookie\"]'): tag.decompose()") if 'for header in soup.select' not in s else s
s=s.replace("root=soup.select_one('.tribe-events-single') or soup.select_one('main') or soup.select_one('article') or soup.select_one('[role=\"main\"]') or soup", "root=soup.select_one('.tribe-events-single') or soup.select_one('main') or soup.select_one('[role=\"main\"]') or soup.select_one('#main') or soup.select_one('article') or soup")
s=s.replace("prefix=unicodedata.normalize('NFKC',part.get_text(' ',strip=True))", "prefix=unicodedata.normalize('NFKC',heading.get_text(' ',strip=True)+' '+part.get_text(' ',strip=True))")
s=s.replace("    lang=source.get('language','')", "    if re.search(r'no (?:cme|cpd) credits|(?:cme|cpd) credits? (?:is |are )?not (?:available|offered|provided)',lower): credits='Not offered'\n    elif re.search(r'(?:application|applied|pending).{0,60}(?:cme|cpd)|(?:cme|cpd).{0,60}(?:pending|applied)',lower): credits='Application pending; not confirmed accredited'\n    lang=source.get('language','')") if 'Application pending; not confirmed accredited' not in s else s
s=s.replace('参加費無料|受講料無料|会費無料', '参加費無料|受講料無料|会費無料|参加は無料') if '参加は無料' not in s else s
p.write_text(s,encoding='utf-8')
p=Path('event_scout/verified_scan.py');s=p.read_text(encoding='utf-8')
s=s.replace("normalized=clean_url(href)", "normalized=urlsplit(clean_url(href))._replace(fragment='').geturl()")
s=s.replace("group=groups[host]; first=group[:3];rest=group[3:]", "group=sorted(groups[host],key=lambda r: -(5 if r.get('adapter') else 4 if re.search(r'/event/|/event-listings/',r['url']) else 2 if re.search(r'free|無料|ฟรี',r.get('label',''),re.I) else 0)); first=group[:3];rest=group[3:]")
s=s.replace("key=lambda e:(e['start_at'],e['title'])", "key=lambda e:(datetime.fromisoformat(e['start_at']),e['title'])")
p.write_text(s,encoding='utf-8')
p=Path('config/verified_sources.json');c=json.loads(p.read_text(encoding='utf-8'))
for source in c['sources']:
    if source.get('kind')=='search':
        source['engine']='google_news'
        source['max_links']=2
        source['query']=source['query'].replace('{year}','').replace('{thai_year}','').strip()
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ('README.md','docs/MEDICAL_EVENT_RADAR.md'):
    p=Path(name)
    if p.exists():
        text=p.read_text(encoding='utf-8').replace('using Bing RSS and Google News RSS','using Google News RSS').replace('across Bing RSS and Google News RSS','using Google News RSS')
        if 'Bing RSS is no longer scheduled' not in text:text+='\nBing RSS is no longer scheduled: repeated live checks returned unrelated results. The optional adapter remains for tests; active discovery uses the configured Google News queries and institutional feeds.\n'
        p.write_text(text,encoding='utf-8')
