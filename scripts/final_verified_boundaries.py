"""Apply narrowly tested article and session boundary corrections."""
from pathlib import Path
p=Path('event_scout/verified_extract.py');s=p.read_text(encoding='utf-8')
old="    # Main/article DOM boundary removes all sitewide dates, including repeated banners.\n    text=unicodedata.normalize('NFKC',root.get_text('\\n',strip=True))[:35000]"
new="""    # Fee, format and registration evidence must belong to this article, not a neighboring post.
    article=heading.find_parent('article') if heading else None
    if article is not None: root=article
    body=root.select_one('.entry-content') or root.select_one('.post-entry')
    if body is not None: root=body
    for extra in root.select('.post-pagination,.post-navigation,.related-posts,.tribe-related-events'):
        extra.decompose()
    text=unicodedata.normalize('NFKC',title+'\\n'+root.get_text('\\n',strip=True))[:35000]"""
if old in s:s=s.replace(old,new)
s=s.replace("online=bool(re.search(r'online|virtual|webinar|zoom|teams|ออนไลน์|オンライン|ウェビナー|ライブ配信',lower))", "online=bool(re.search(r'online|virtual|webinar|zoom|teams|ออนไลน์|オンライン|ウェビナー|ライブ配信',re.sub(r'(?i)register online|online registration|registration online|ลงทะเบียนออนไลน์|ลงทะเบียนผ่านระบบออนไลน์|オンライン申込', '', lower)))")
s=s.replace("topic=re.search(r'『([^』]+)』',block.get_text(' ',strip=True))", "topic=re.search(r'『([^』]+)』',h.get_text(' ',strip=True)+' '+block.get_text(' ',strip=True))")
s=s.replace('thailand|ประเทศไทย', 'thailand|bangkok|ประเทศไทย') if 'thailand|bangkok' not in s else s
s=s.replace("r'cme.{0,10}credit|", "r'ce\\s+credits[\\s:]*cme|cme.{0,10}credit|")
p.write_text(s,encoding='utf-8')
p=Path('event_scout/verified_scan.py');s=p.read_text(encoding='utf-8')
s=s.replace("events,reasons=extract(html,final,info,now)\n        for event in events:", "events,reasons=extract(html,final,info,now)\n        verified=[]\n        for event in events:")
s=s.replace("return [],{'url':url,'status':'rejected','reasons':['registration-target-closed']}", "reasons.append('registration-target-closed')\n                        continue")
s=s.replace("event['discovered_by']=candidate['discovered_by']\n        return events,", "event['discovered_by']=candidate['discovered_by']\n            verified.append(event)\n        events=verified\n        return events,")
p.write_text(s,encoding='utf-8')
