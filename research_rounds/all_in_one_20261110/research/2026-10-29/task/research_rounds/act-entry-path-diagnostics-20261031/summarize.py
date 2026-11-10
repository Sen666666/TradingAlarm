from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,time
import pandas as pd,numpy as np
P=Path(__file__).resolve().parent;T=time.monotonic();rs=list(csv.DictReader((P/'CYCLE_PATH_FACTS.csv').open()));out=[];qs=[];groups=[];legacy=[]
def num(r,k):return float(r[k]) if r.get(k) not in ['',None] else None
def quant(z,k):
 a=[num(r,k) for r in z if num(r,k) is not None];return {str(p):float(np.quantile(a,p)) if a else None for p in [0,.1,.25,.5,.75,.9,1]}
for sec in ['TECH','DRUG']:
 z=[r for r in rs if r['sector']==sec];closed=[r for r in z if r['closed']=='True'];loss=[r for r in closed if D(r['final_net_pnl'])<0];win=[r for r in closed if D(r['final_net_pnl'])>0];tails=[r for r in z if r['final_group']=='tail_profit_30pct'];opens=[r for r in z if r['closed']!='True']
 a=dict(sector=sec,cycles=len(z),closed=len(closed),open=len(opens),stocks=len({r['symbol'] for r in z}),profit_count=len(win),loss_count=len(loss),closed_profit=sum((D(r['final_net_pnl']) for r in win),D(0)),closed_loss=sum((D(r['final_net_pnl']) for r in loss),D(0)),open_pnl=sum((D(r['final_net_pnl']) for r in opens),D(0)),tail_count=len(tails),tail_pnl=sum((D(r['final_net_pnl']) for r in tails),D(0)),unknown_count=sum(int(r['unknown_count'])>0 for r in z),unknown_rows=sum(int(r['unknown_count']) for r in z),loss_MAE_vs_first_positive=dict(Counter(r['MAE_vs_first_positive'] for r in loss)),tail_MAE_vs_first_positive=dict(Counter(r['MAE_vs_first_positive'] for r in tails)),loss_first_positive=sum(bool(r['first_positive_close']) for r in loss),loss_after_plus10=sum(r['loss_after10_NAV']=='True' for r in loss),tail_back_to_negative=sum(bool(r['first_negative_after_positive']) for r in tails),all_back_to_negative=sum(bool(r['first_negative_after_positive']) for r in z),tail_worst_cost_loss=sorted(tails,key=lambda r:num(r,'MAE_close'))[:3])
 for scope,g in [('all',z),('closed_loss',loss),('tail_profit_30pct',tails),('other_closed_profit',[r for r in win if r not in tails]),('open',opens)]:
  groups.append(dict(sector=sec,group=scope,count=len(g),negative_close_observed=sum(num(r,'MAE_close')<0 for r in g),first_positive_then_negative=sum(bool(r['first_negative_after_positive']) for r in g),MAE_stage=dict(Counter(r['MAE_vs_first_positive'] for r in g)),quantiles={k:quant(g,k) for k in ['MAE_close','MFE_close','MAE_including_actual_exit','initial_floor_distance','max_drawdown_from_prior_positive_peak','longest_recorded_below_cost_run']}))
 out.append(a)
for r in rs:
 if r['sector']=='TECH':
  legacy.append(dict(cycle_id=r['cycle_id'],name=r['name'],old=r['legacy_loss_after10'],new=r['loss_after10_NAV'],old_NAV_MFE_difference=r['old_NAV_MFE_difference']))
sameepoch=Counter((r['sector'],r['economic_epoch']) for r in rs if r['economic_epoch']);overlaps=[]
for i,a in enumerate(rs):
 for b in rs[i+1:]:
  if a['sector']==b['sector'] and a['symbol']==b['symbol'] and max(a['entry_at'],b['entry_at'])<min(a['endpoint'],b['endpoint']):overlaps.append((a['cycle_id'],b['cycle_id']))
assert not overlaps
s=dict(sectors=out,groups=groups,legacy_disagreements=[x for x in legacy if x['old']!=x['new']],legacy_nav_max_residual=max(abs(float(x['old_NAV_MFE_difference'])) for x in legacy),same_market_epochs_with_multiple_cycles=[dict(sector=k[0],epoch=k[1],cycles=v) for k,v in sameepoch.items() if v>1],overlapping_positions=overlaps,summary_seconds=time.monotonic()-T)
(P/'SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,default=str));pd.DataFrame(legacy).to_csv(P/'LEGACY_PLUS10_RECONCILIATION.csv',index=False)
print(json.dumps(s,ensure_ascii=False,indent=2,default=str))
