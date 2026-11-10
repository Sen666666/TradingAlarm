"""Predeclared fixed-permit precision report; no execution calls."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;V=O.parent/'cash_dividend_402_scenario_v2/report_coverage_overlay';target=pd.read_csv(O/'ADJUDICATED_24.csv');ids=set(target.round_id)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def metrics(g):
 c=g[g.status.isin(['SCENARIO_CLOSED_NOT_FACT','COMPLETE_CONDITIONAL_STOCK_ROUND','CORE_ONLY_CLOSED_ALGEBRAIC'])];p=c.net_pnl;r=c.net_return_on_buy_cash
 return {'permits':len(g),'closed':len(c),'wins':int((p>0).sum()),'losses':int((p<0).sum()),'zero':int((p==0).sum()),'win_rate':float((p>0).mean()) if len(c) else None,'mean_return_on_buy_cash':float(r.mean()) if len(c) else None,'median_return_on_buy_cash':float(r.median()) if len(c) else None,'mean_pnl':float(p.mean()) if len(c) else None,'unknown':int(g.status.str.contains('UNKNOWN').sum()),'censored':int(g.status.str.contains('CENSORED').sum()),'nofill':int(g.status.str.contains('NOFILL').sum()),'status_counts':g.status.value_counts().to_dict()}
seal=json.loads((O/'REPORT_DEFINITIONS_SEAL.json').read_text());assert sha(Path(__file__))==seal['code_sha256']
a=pd.read_csv(O/'full/ROUNDS.csv');assert len(a)==96;new=a[a.cash_variant=='PRECISE_PUBLIC_CASH'];comparison=pd.read_csv(O/'full/CASH_ENDPOINT_COMPARISON.csv');merged={};before={}
for mode,g in new.groupby('mode'):
 b=pd.read_csv(V/(mode+'_FIXED_PERMITS.csv'));assert b[b.round_id.isin(ids)].status.str.contains('UNKNOWN').all() and len(g)==24;before[mode]=metrics(b)
 g=g.copy();g['round_id']=g.original_round_id;g['report_cohort']='RECOVERED_24_DOCUMENTED_PRECISE_NET80';z=pd.concat([b[~b.round_id.isin(ids)],g],ignore_index=True);assert len(z)==2432 and z.round_id.nunique()==2432;merged[mode]=z
closed=['SCENARIO_CLOSED_NOT_FACT','COMPLETE_CONDITIONAL_STOCK_ROUND','CORE_ONLY_CLOSED_ALGEBRAIC'];x=merged['FULL_CORE_PLUS_ADD'].set_index('round_id');y=merged['CORE_ONLY'].set_index('round_id');common=sorted(set(x[x.status.isin(closed)].index)&set(y[y.status.isin(closed)].index));x=x.loc[common];y=y.loc[common]
pairs=pd.DataFrame({'round_id':common,'full_pnl':x.net_pnl.values,'core_pnl':y.net_pnl.values,'full_minus_core':(x.net_pnl-y.net_pnl).values})
summary={'scope':'Fixed original2432; one24-permit precise dividend source-coordinate scenario. Not official ex-price, PIT, actual tax, reselection or account result.','prior_fixed':before,'new24_by_cash_and_mode':{variant:{mode:metrics(g) for mode,g in group.groupby('mode')} for variant,group in a.groupby('cash_variant')},'after24_fixed':{mode:metrics(g) for mode,g in merged.items()},'common_closed':{'count':len(common),'full':metrics(x),'core':metrics(y),'core_win_full_loss':int(((pairs.core_pnl>0)&(pairs.full_pnl<0)).sum()),'core_loss_full_win':int(((pairs.core_pnl<0)&(pairs.full_pnl>0)).sum())},'precision_diagnostic':{'case_mode_pairs':len(comparison),'actions_identical_count':int(comparison.actions_identical.sum()),'profit_signs_identical_count':int(comparison.profit_signs_identical.sum()),'min_post_event_abs_mark':float(comparison.post_event_min_abs_mark.min()),'min_mark_exceeds_own_cash_delta_count':int(comparison.min_mark_exceeds_cash_delta.fillna(False).sum()),'no_mark_cases':int(comparison.post_event_min_abs_mark.isna().sum()),'cash_delta_abs_max_each_own_inventory':float(comparison.net80_cash_delta.abs().max()),'meanings':'Cash differences are not a priori path-PnL bounds. Equality of observed complete actions permits exact PnL-delta reconciliation for those pairs only.'}}
fm=summary['after24_fixed']['FULL_CORE_PLUS_ADD'];n=fm['closed']+fm['unknown']+fm['censored'];summary['full_extreme_bounds_only_fixed_known_NET80_scenario']={'denominator_excludes_nofill':n,'lower':fm['wins']/n,'upper':(fm['wins']+fm['unknown']+fm['censored'])/n,'not_actual_strategy_bound':True}
d=O/'report';d.mkdir(exist_ok=False)
for mode,z in merged.items():z.to_csv(d/(mode+'_FIXED_PERMITS.csv'),index=False)
pairs.to_csv(d/'COMMON_CLOSED_PAIRS.csv',index=False);save(d/'SUMMARY.json',summary);save(d/'OUTPUT_HASHES.json',{p.name:sha(p) for p in d.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'});print(json.dumps(summary,ensure_ascii=False,indent=2))
