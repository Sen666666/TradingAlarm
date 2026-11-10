"""Original-cohort diagnostic only; no deletion PnL or account prediction."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent.parent/'task';S={}
def bind(p):p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p):
 with gzip.open(bind(p),'rt')as h:return list(map(json.loads,h))
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def group(rows):
 return dict(events=len(rows),stocks=len({r['sid']for r in rows}),original_cost=sum((D(r['original_cost'])for r in rows),D(0)),
  original_cutoff_net=sum((D(r['original_cutoff_net'])for r in rows),D(0)),
  original_cutoff_positive=sum(D(r['original_cutoff_net'])>0 for r in rows),
  original_cutoff_negative=sum(D(r['original_cutoff_net'])<0 for r in rows),
  by_role=dict(Counter(r['role']for r in rows)),by_original_action=dict(Counter(r['original_action']for r in rows)))
start=time.monotonic();bind(__file__)
with bind(O/'PRICE_FEATURES.pkl').open('rb')as h:features=pickle.load(h)
sources={
 'long':dict(daily=T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/daily.jsonl.gz',
  layers=T/'risk_constraints/continuation2024_finance/analysis/2022_2024/PVR_NO_CONFIRMED60/LAYERS.json',
  actions=T/'loss_correction/continuation2024_layers/PVR_NO60-ENTRY_ACTIONS.json'),
 'strong':dict(daily=T/'pvr_pool_feasibility/runs/2025_26/pair/daily.jsonl.gz',
  layers=T/'loss_correction/pvr_no60_2025_26/analysis/2025_26/PVR_NO60/LAYERS.json',
  actions=T/'loss_correction/pvr_no60_2025_26/PVR_NO60-ENTRY_ACTIONS.json')}
rows=[]
for window,paths in sources.items():
 daily={r['at'][:10]:r for r in gz(paths['daily'])};layers=read(paths['layers']);actions={r['layer']:r for r in read(paths['actions'])}
 assert len(layers)==(2265 if window=='long' else 1171)
 for r in layers:
  sd=r['signal_day'];sid=r['sid'];dt=pd.Timestamp(sd);held=bool(daily[sd]['positions'].get(sid,0));f=features[sid]
  known=dt in f.index and bool(f.loc[dt,'bb20_cross_known']);cross=bool(f.loc[dt,'bb20_cross'])if known else None
  kept=held or known and cross
  rows.append(dict(window=window,layer=r['layer'],sid=sid,name=r['name'],industry=r['industry'],role=r['role'],
   signal_day=sd,opened=r['opened'],original_action=actions[r['layer']]['action'],actual_signal_CLOSE_held=held,
   BB_known=known,BB_cross=cross,plugin_would_accept_on_original_state=bool(kept),
   original_cost=r['cost'],original_cutoff_net=r['net'],original_open=bool(r['qty']),
   original_tail30_label=D(r['net'])>=D('.3')*D(r['cost']),
   cutoff_scope='Original3year end2024 or original strong end2026Jun; not a new policy return'))
groups={}
for w in ['long','strong']:
 sets={'all':[r for r in rows if r['window']==w]}
 for y in (['2022','2023','2024']if w=='long'else['2025','2026']):sets[y]=[r for r in sets['all']if r['signal_day'][:4]==y]
 if w=='long':
  sets['after_924']=[r for r in sets['all']if r['signal_day']>='2024-09-24']
  sets['strict_Oct9_new_fill']=[r for r in sets['all']if r['opened'][:10]>='2024-10-09']
 else:sets['semiconductor_2026H1']=[r for r in sets['all']if r['industry']=='半导体' and r['opened'][:10]>='2026-01-01']
 for name,rs in sets.items():
  groups[w+'_'+name]={}
  for status,ss in [('all',rs),('held_ADD_unchanged',[r for r in rs if r['actual_signal_CLOSE_held']]),
                    ('flat_kept',[r for r in rs if not r['actual_signal_CLOSE_held']and r['plugin_would_accept_on_original_state']]),
                    ('flat_filtered',[r for r in rs if not r['actual_signal_CLOSE_held']and not r['plugin_would_accept_on_original_state']]),
                    ('old_tail30',[r for r in rs if r['original_tail30_label']]),
                    ('old_tail30_filtered',[r for r in rs if r['original_tail30_label']and not r['plugin_would_accept_on_original_state']])]:
   groups[w+'_'+name][status]=group(ss)
save('ALL3436_ORIGINAL_ENTRY_BB_ASSOCIATION.json',rows);save('ORIGINAL_ENTRY_BB_COHORT_SUMMARY.json',groups)
save('ORIGINAL_ENTRY_BB_SCOPE.json',dict(events=3436,new_accounts=0,new_financial_paths=0,seconds=time.monotonic()-start,
  scope='Original actual filled layer cohort and original signal CLOSE state only; filtered cohort net is not avoidable loss, new policy return, or expected cash rerouting',
  tail='>=30% original lifecycle net/cost evaluation label only, not a gate; original cutoff includes later years and is not period wealth',
  modules_unchanged='Held ADD accepted without lookup; no signal/entry/exit/quantity or original account mutation'))
save('ORIGINAL_ENTRY_BB_SOURCE_SHA256.json',S)
print(json.dumps({k:v for k,v in groups.items()if k in ['long_all','strong_all','strong_semiconductor_2026H1','long_strict_Oct9_new_fill']},ensure_ascii=False,indent=2,default=str))
