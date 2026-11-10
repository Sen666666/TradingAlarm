"""Observed development-window tail-capture baseline; no strategy import/replay."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING
from collections import defaultdict,Counter
import json,csv,hashlib
O=Path(__file__).resolve().parent;R=O.parent/'mainline_m7_cash_batch_design_v6/once_20260630';Z=D(0);A='2024-11-06'
def read(n):return json.loads((R/(n+'.json')).read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def sm(rs,k):return sum((D(r.get(k,0)) for r in rs),Z)
def quant(arr,p):
 arr=sorted(D(x) for x in arr)
 if not arr:return None
 pos=D(len(arr)-1)*D(p);i=int(pos);frac=pos-i;return arr[i]+(arr[min(i+1,len(arr)-1)]-arr[i])*frac
orders=read('ORDERS');ats=read('ATTEMPTS');led=read('DAY_LEDGER');caps=read('CAPITAL_LOTS');E=led[-1]['day'];byrid=defaultdict(list)
for o in orders:byrid[o['round_id']].append(o)
endnets={c['round_id']:c['round_net'] for c in caps if c['day']==E};rr=[]
for a in ats:
 os=byrid[a['id']];seed=next(o for o in os if o['side']=='BUY_SEED');assert seed['signal_day']==a['signal_day'] and seed['day']==a['seed_day']
 slip=sum((abs(D(o['price'])-D(o['price'])/(D('1.0005') if o['side'].startswith('BUY') else D('.9995')))*o['qty'] for o in os),Z)
 rr.append(dict(opportunity_key=a['sid']+'|'+a['signal_day'],round_id=a['id'],sid=a['sid'],name=seed['name'],sector51=a['sector51'],original_signal_date=a['signal_day'],birth_type=a['birth_type'],actual_seed_OPEN=a['seed_day'],seed_capital_role=seed['capital_role'],seed_all_in=-D(seed['cash_delta']),add_count=a['add_count'],exit_day=a.get('exit_day'),open_at_cutoff=bool(a['final_qty']),final_qty=a['final_qty'],marked_net_pnl=D(a['marked_net_pnl']),net_liquidation_pnl=D(endnets[a['id']]) if a['final_qty'] else D(a['marked_net_pnl']),fees=D(a['fees']),model_slippage=slip,fill_price_plus_div_pnl=D(a['marked_net_pnl'])+D(a['fees']),raw_price_plus_div_pnl=D(a['marked_net_pnl'])+D(a['fees'])+slip))
assert len({r['opportunity_key'] for r in rr})==len(rr)
assert sm(rr,'marked_net_pnl')==D(led[-1]['NAV'])-D(1200000)
cohorts={
 'FULL_OBSERVED_WINDOW':rr,
 'SEPT_STARTUP_SEED_OPEN_0923_0930':[r for r in rr if '2024-09-23'<=r['actual_seed_OPEN']<='2024-09-30'],
 'PV_SEED_OPEN_1023_1029':[r for r in rr if r['sector51']=='光伏风电设备' and '2024-10-23'<=r['actual_seed_OPEN']<='2024-10-29'],
 'NEW_SEED_OPEN_FROM_1107':[r for r in rr if r['actual_seed_OPEN']>'2024-11-06']}
summ=[];ranked=[];openrows=[];cohortrows=[]
for name,rs in cohorts.items():
 closed=[r for r in rs if not r['open_at_cutoff']];op=[r for r in rs if r['open_at_cutoff']];win=sorted([r for r in closed if r['marked_net_pnl']>0],key=lambda r:r['marked_net_pnl'],reverse=True);loss=[r for r in closed if r['marked_net_pnl']<0];npos=len(win);ngross=sm(win,'marked_net_pnl');lossabs=-sm(loss,'marked_net_pnl');net=sm(closed,'marked_net_pnl');topdecile_n=int((D(npos)*D('.1')).to_integral_value(rounding=ROUND_CEILING));topdec=sm(win[:topdecile_n],'marked_net_pnl')
 result=dict(cohort=name,definition={'FULL_OBSERVED_WINDOW':'All actual seeded rounds, 2024-09-02 through certified 2025-01-20.','SEPT_STARTUP_SEED_OPEN_0923_0930':'Actual first seed OPEN dates 2024-09-23 through 2024-09-30 inclusive, all sectors.','PV_SEED_OPEN_1023_1029':'Actual first seed OPEN dates 2024-10-23 through 2024-10-29 inclusive, sector51 光伏风电设备 only.','NEW_SEED_OPEN_FROM_1107':'Actual first seed OPEN >=2024-11-07, identical to existing 954 new-round attribution after 11/6.'}[name],total_rounds=len(rs),closed_rounds=len(closed),open_rounds=len(op),all_marked_net=sm(rs,'marked_net_pnl'),closed_net=net,open_marked_net=sm(op,'marked_net_pnl'),open_liquidation_net=sm(op,'net_liquidation_pnl'),positive_closed_rounds=npos,negative_closed_rounds=len(loss),zero_closed_rounds=sum(r['marked_net_pnl']==0 for r in closed),gross_positive_pnl=ngross,gross_negative_cost=lossabs,top10pct_positive_count=topdecile_n,top10pct_positive_contribution=topdec,top10pct_share_positive_pct=topdec/ngross*100 if ngross else None,top10pct_share_closed_net_pct=topdec/net*100 if net>0 else None,top5_positive_count=min(5,npos),top5_positive_contribution=sm(win[:5],'marked_net_pnl'),top5_share_positive_pct=sm(win[:5],'marked_net_pnl')/ngross*100 if ngross else None,top10_positive_count=min(10,npos),top10_positive_contribution=sm(win[:10],'marked_net_pnl'),top10_share_positive_pct=sm(win[:10],'marked_net_pnl')/ngross*100 if ngross else None,positive_closed_p50=quant([r['marked_net_pnl'] for r in win],'.5'),positive_closed_p90=quant([r['marked_net_pnl'] for r in win],'.9'),positive_closed_p95=quant([r['marked_net_pnl'] for r in win],'.95'),negative_closed_fees=sm(loss,'fees'),negative_closed_model_slippage=sm(loss,'model_slippage'),negative_closed_fee_share_loss_pct=sm(loss,'fees')/lossabs*100 if lossabs else None,negative_closed_fee_plus_slippage_share_loss_pct=(sm(loss,'fees')+sm(loss,'model_slippage'))/lossabs*100 if lossabs else None,negative_closed_fill_price_plus_div_pnl=sm(loss,'fill_price_plus_div_pnl'),negative_closed_raw_price_plus_div_pnl=sm(loss,'raw_price_plus_div_pnl'),negative_closed_nonnegative_raw_price_count=sum(r['raw_price_plus_div_pnl']>=0 for r in loss),negative_closed_nonnegative_raw_price_net=sm([r for r in loss if r['raw_price_plus_div_pnl']>=0],'marked_net_pnl'))
 summ.append(result)
 for rank,r in enumerate(win,1):ranked.append(dict(cohort=name,positive_rank=rank,in_top10pct_positive=rank<=topdecile_n,**r))
 for r in op:openrows.append(dict(cohort=name,**r))
 for r in rs:cohortrows.append(dict(cohort=name,**r))
# Optional literal interpretation of "after Nov 7", explicitly separate from the four main cohorts.
strict=[r for r in rr if r['actual_seed_OPEN']>'2024-11-07'];save('DATE_SCOPE_NOTE',dict(primary_new_cohort='>=2024-11-07; 954 rounds',strict_after_1107_rounds=len(strict),strict_after_1107_marked_net=sm(strict,'marked_net_pnl'),nov7_seed_rounds=sum(r['actual_seed_OPEN']=='2024-11-07' for r in rr),nov7_seed_whole_round_net=sm([r for r in rr if r['actual_seed_OPEN']=='2024-11-07'],'marked_net_pnl'),warning='The 954-round primary cohort uses November 7 inclusive, consistent with 11/6 NAV anchoring. Strictly after November 7 is not the same population.'))
meta=dict(label='OBSERVED_DEVELOPMENT_WINDOW_BASELINE',certified_through=E,initial_cash=D(1200000),actual_cash_NAV=led[-1]['NAV'],actual_net_liquidation_NAV=led[-1]['net_liquidation_NAV'],planned_directory_end='2026-06-30 is not certified end',positive_decile_definition='ceil(10% * count of strictly profitable CLOSED rounds), sorted by final actual realized net PnL descending; not 10% of all rounds.',percentile_definition='Linear interpolation at (n-1)*p on positive CLOSED round net PnL.',cohort_overlap='The four cohorts overlap. Never add their PnL or tail contributions together. Open rounds are excluded from closed winner/loss distributions and listed separately.',net_share_convention='Top-decile/closed-net shown only when closed net > 0; gross-positive denominator is always the meaningful winner capture fraction.',fees_definition='Actual modeled fees already charged in round cashflow. Modeled 5bp slippage is separately added back only for decomposition, never a second deduction.',not_entry_information='Observed rank, quantiles, no-ADD status and later net profit are evaluation labels only, never entry predictors.',opportunity_key='sid|original_signal_date, verified unique for baseline. Actual seed OPEN is a separate execution field.',same_window_rule='Future candidate comparison must stop at common certified frontier, use actual cash NAV with same facts/costs/capital constraints, and disclose unmatched baseline and candidate opportunities.',parameters_selected='Retrospective development window; sealing these metrics for a next experiment does not make this unseen or out of sample.')
for n,x in [('BASELINE_SUMMARY',summ),('CLOSED_POSITIVE_RANKING',ranked),('OPEN_AT_CUTOFF',openrows),('COHORT_OPPORTUNITY_MEMBERSHIP',cohortrows),('ALL_OPPORTUNITIES',rr),('BASELINE_DEFINITIONS',meta)]:save(n,x)
save('SOURCE_HASHES',{str(R/(n+'.json')):hashlib.sha256((R/(n+'.json')).read_bytes()).hexdigest() for n in ['ORDERS','ATTEMPTS','DAY_LEDGER','CAPITAL_LOTS']})
print(json.dumps(summ,ensure_ascii=False,default=str))
