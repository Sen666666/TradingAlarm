import json,csv,statistics
from pathlib import Path
m=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
r=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
recs=json.loads((m/'tech-finite-compound-20261026/data/core-v3/manifest.json').read_text())['series']
tech={x['series_id'] for x in recs if x['kind']=='stock'}
assert len(tech)==407
d=list(csv.DictReader((r/'selection_entry_diagnosis_v1/ALL_FIRST_ENTRIES.csv').open()))
d=[x for x in d if x['account']=='PVR']
print('N all',len(d),'tech407',len(tech),'sectors',sorted({x['sector'] for x in d if x['sid'] in tech}))
def st(rows):
 c=[x for x in rows if x['closed']=='True'];p=[float(x['round_pnl']) for x in c];w=[x for x in p if x>0];l=[x for x in p if x<0];mw=statistics.mean(w) if w else None;ml=-statistics.mean(l) if l else None
 return {'n':len(rows),'closed':len(c),'wins':len(w),'loss':len(l),'open':len(rows)-len(c),'wr':len(w)/len(c) if c else None,'meanwin':mw,'meanloss':ml,'payoff':mw/ml if mw and ml else None,'net':sum(p),'tail30':sum(float(x['round_return_on_cumulative_cost'])>=.3 for x in c)}
for win,rs in [('all',d),('2024on',[x for x in d if x['entry_day']>='2024-01-01'])]+[(y,[x for x in d if x['entry_day'].startswith(y)]) for y in ['2022','2023','2024','2025','2026']]:
 print(win,json.dumps({'all':st(rs),'tech407':st([x for x in rs if x['sid'] in tech]),'nontech':st([x for x in rs if x['sid'] not in tech])}))
print('FIRST_STOCK',next(x for x in recs if x['kind']=='stock'))
