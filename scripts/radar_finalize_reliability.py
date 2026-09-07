"""Small isolated corrections after the live fallback diagnostic test."""
from pathlib import Path
p=Path('event_scout/verified_scan.py');s=p.read_text(encoding='utf-8')
assert 'attempts.append(result)' in s
s=s.replace('attempts.append(result)','attempts.append(dict(result))')
p.write_text(s,encoding='utf-8')
p=Path('event_scout/verified_reliability.py');s=p.read_text(encoding='utf-8')
s=s.replace("today=now.astimezone(BKK).date().isoformat()\n    last=state.get('last_run',{})", "today=now.astimezone(BKK).date().isoformat()\n    if state.get('daily_attempts',{}).get(today,0)>=3:return False\n    last=state.get('last_run',{})")
p.write_text(s,encoding='utf-8')
