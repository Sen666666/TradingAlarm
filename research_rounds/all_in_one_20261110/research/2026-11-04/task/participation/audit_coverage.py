import json, hashlib
from pathlib import Path
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/participation')
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/industry-evidence-ranking-readonly-v1')
C10=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/C10-account6-ablation-five-snapshots-v1-20261103/SUMMARY.json')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={str(p):sha(p) for p in [ROOT/'PROTOCOL.txt', ROOT/'audit_coverage.py', C10]+[BASE/f'{w}-FULL_TABLE_WITH_HISTORY.parquet' for w in ['2022','2023','OLD924','LOCAL2026']]}
cols=['day','sector','industry','global_F1_permit','F1_permit','F1_mature','I_entry_Q','canonical_CP1_Q','canonical_status','H1_rank_all_original_sectors']
result={}
for w in ['2022','2023','OLD924','LOCAL2026']:
 d=pd.read_parquet(BASE/f'{w}-FULL_TABLE_WITH_HISTORY.parquet',columns=cols)
 assert not d.duplicated(['day','sector']).any()
 assert d[['global_F1_permit','F1_permit','F1_mature']].notna().all().all()
 groups={}
 for name,mask in [('global_only',d.global_F1_permit&~d.F1_permit),('local_only',~d.global_F1_permit&d.F1_permit),('both',d.global_F1_permit&d.F1_permit),('neither',~d.global_F1_permit&~d.F1_permit)]:
  x=d[mask]
  groups[name]={'industry_observations':len(x),'distinct_days':x.day.nunique(),'distinct_industries':x.sector.nunique(),'I_entry_Q_stock_observations':int(x.I_entry_Q.sum()),'canonical_CP1_Q_stock_observations':None if w=='OLD924' else int(x.canonical_CP1_Q.sum())}
 assert sum(x['industry_observations'] for x in groups.values())==len(d)
 x=d[(~d.global_F1_permit)&d.F1_permit&d.F1_mature]
 result[w]={'from':d.day.min(),'to':d.day.max(),'industry_observations':len(d),'days':d.day.nunique(),'industries':d.sector.nunique(),'groups':groups,'local_mature_while_global_false':{'industry_observations':len(x),'distinct_days':x.day.nunique(),'distinct_industries':x.sector.nunique(),'I_entry_Q_stock_observations':int(x.I_entry_Q.sum()),'canonical_CP1_Q_stock_observations':None if w=='OLD924' else int(x.canonical_CP1_Q.sum())},'canonical_status':d.canonical_status.value_counts().to_dict()}
 if w=='LOCAL2026':
  x=d[d.industry.eq('半导体')];result[w]['semiconductor']={'observations':len(x),'global_permitted':int(x.global_F1_permit.sum()),'local_permitted':int(x.F1_permit.sum()),'local_mature_permitted':int((x.F1_permit&x.F1_mature).sum()),'canonical_CP1_Q_total':int(x.canonical_CP1_Q.sum()),'canonical_CP1_Q_local_permitted':int(x.loc[x.F1_permit,'canonical_CP1_Q'].sum()),'canonical_CP1_Q_local_mature_permitted':int(x.loc[x.F1_permit&x.F1_mature,'canonical_CP1_Q'].sum()),'first_local_mature_permitted':x.loc[x.F1_permit&x.F1_mature,'day'].min()}
a=json.loads(C10.read_text());static=[]
for c in a['cases']:
 static.append({'day':c['day'],'full_original_C_candidates':c['full_C_candidates'],'original_identity':c['original_mode_full_identity'],'modes':{k:{z:v[z] for z in ['Q_positive','D_positive','new_buy_gross','D_mark_gross','nominal_risk_pct','capital_pct']}for k,v in c['modes'].items()},'Q_changes':[{'sid':x['sid'],'old_Q':x['old_Q'],'new_Q':x['new_Q']}for x in c['Q_changes']],'focus':{k:{z:v[z]for z in ['name','old_Q','new_Q']}for k,v in c.get('focus',{}).items()}})
out={'scope':'new descriptive cross-window aggregation, zero account events, no price-return labels read','source_sha256':manifest,'coverage':result,'static_account6_recovered':static}
assert all(sha(Path(p))==h for p,h in manifest.items())
(ROOT/'RESULTS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps({'coverage':result,'static_brief':[{'day':s['day'],'old_capital':s['modes']['ORIGINAL_6']['capital_pct'],'no_AR6_capital':s['modes']['NO_AR6']['capital_pct'],'old_risk':s['modes']['ORIGINAL_6']['nominal_risk_pct'],'no_AR6_risk':s['modes']['NO_AR6']['nominal_risk_pct']}for s in static]},ensure_ascii=False,indent=2))
