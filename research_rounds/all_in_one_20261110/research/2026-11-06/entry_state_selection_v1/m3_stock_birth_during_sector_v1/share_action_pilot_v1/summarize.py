"""Report the preselected small share pilot without rerunning any path."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;BASE=O.parent/'cash_dividend_precision_24_v1/report'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def met(g):
 c=g[g.status.isin(['COMPLETE_CONDITIONAL_STOCK_ROUND','CORE_ONLY_CLOSED_ALGEBRAIC','SCENARIO_CLOSED_NOT_FACT'])];p=c.net_pnl;r=c.net_return_on_buy_cash
 return dict(permits=len(g),closed=len(c),wins=int((p>0).sum()),losses=int((p<0).sum()),zero=int((p==0).sum()),win_rate=float((p>0).mean()) if len(c) else None,mean_return_on_buy_cash=float(r.mean()) if len(c) else None,median_return_on_buy_cash=float(r.median()) if len(c) else None,unknown=int(g.status.str.contains('UNKNOWN').sum()),censored=int(g.status.str.contains('CENSORED').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),status_counts=g.status.value_counts().to_dict())
seal=json.loads((O/'REPORT_DEFINITIONS_SEAL.json').read_text());assert sha(Path(__file__))==seal['code_sha256'];a=pd.read_csv(O/'pilot/ROUNDS.csv');ids=set(pd.read_csv(O/'PILOT_TARGETS.csv').round_id);assert len(a)==2*len(ids)
merged={};before={}
for mode,g in a.groupby('mode'):
 z=pd.read_csv(BASE/(mode+'_FIXED_PERMITS.csv'));assert len(z)==2432 and z[z.round_id.isin(ids)].status.str.contains('UNKNOWN').all();before[mode]=met(z)
 g=g.copy();g['round_id']=g.original_round_id;g['report_cohort']='SMALL_SAME_DAY_TAX_EXEMPT_CAPITALIZATION_PILOT';z=pd.concat([z[~z.round_id.isin(ids)],g],ignore_index=True);assert z.round_id.nunique()==len(z)==2432;merged[mode]=z
closed=['COMPLETE_CONDITIONAL_STOCK_ROUND','CORE_ONLY_CLOSED_ALGEBRAIC','SCENARIO_CLOSED_NOT_FACT'];x=merged['FULL_CORE_PLUS_ADD'].set_index('round_id');y=merged['CORE_ONLY'].set_index('round_id');common=sorted(set(x[x.status.isin(closed)].index)&set(y[y.status.isin(closed)].index));x=x.loc[common];y=y.loc[common]
summary={'scope':'Small preselected same-day tradable, strictly integer, explicitly tax-exempt premium capitalization. Fixed original permits/source only, NET80 cash scenario. No other49/50 execution, no portfolio, PIT or strategy optimization.','pilot_ids':sorted(ids),'before':before,'pilot_by_mode':{m:met(g) for m,g in a.groupby('mode')},'fixed_after_pilot':{m:met(g) for m,g in merged.items()},'common_closed':{'n':len(common),'full':met(x),'core':met(y)},'others_in_original_share50_not_executed':50-len(ids),'basis':'Unchanged cash-precision24 strict fixed2432 report; only declared pilot rows replaced, all other rows retained.'}
out=O/'report';out.mkdir(exist_ok=False)
for m,z in merged.items():z.to_csv(out/(m+'_FIXED_PERMITS.csv'),index=False)
save(out/'SUMMARY.json',summary);save(out/'OUTPUT_HASHES.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps(summary,ensure_ascii=False,indent=2))
