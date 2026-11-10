from pathlib import Path
import json,sys,importlib.util,gzip,time,collections
from decimal import Decimal as D
import pandas as pd
import numpy as np
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-incremental-order-20261029');sp=importlib.util.spec_from_file_location('pvr_report',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;Z=D(0);t=time.monotonic()
def total(v):return sum((D(str(x)) for x in v),Z)
u=pd.read_parquet(O/'results/units.parquet');p=u[u.role.eq('pvr')].merge(u[u.role.eq('h1')],on=['pair_id','cost'],suffixes=('_pvr','_h1'),validate='one_to_one');assert len(p)==504
for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','nav','shares','market_value','dividend_receivable','invested_cost_sessions','estimated_liquidation_fee','estimated_exit_slippage']:
 for role in ['pvr','h1']:p[k+'_'+role]=p[k+'_'+role].map(D)
p['delta']=p.net_pnl_pvr-p.net_pnl_h1;p['tail_pvr']=p.net_return_pvr.ge(.3).fillna(False);p['tail_h1']=p.net_return_h1.ge(.3).fillna(False);p['pair_tail']=p.tail_pvr|p.tail_h1;p['marked_tail']=p.tail_pvr&p.shares_pvr.gt(0)|p.tail_h1&p.shares_h1.gt(0)
p['loss_saved']=p.net_pnl_h1.map(lambda x:max(Z,-x))-p.net_pnl_pvr.map(lambda x:max(Z,-x));p['positive_added']=p.net_pnl_pvr.map(lambda x:max(Z,x))-p.net_pnl_h1.map(lambda x:max(Z,x));assert all(p.delta.eq(p.loss_saved+p.positive_added))
p['held_diff']=p.held_close_sessions_pvr-p.held_close_sessions_h1;p['duration_group']=p.held_diff.map(lambda x:'PVR_longer' if x>0 else 'PVR_shorter' if x<0 else 'equal')
slips=collections.defaultdict(lambda:Z);components=collections.defaultdict(lambda:Z);fills=[]
with gzip.open(O/'results/audit.jsonl.gz','rt') as f:
 for line in f:
  x=json.loads(line)
  for a in x['audit']:
   if a['kind']!='fill':continue
   rr=a['receipt'];slips[(x['pair_id'],x['role'],x['cost'])]+=abs(D(a['price'])-D(a['raw_open']))*rr['shares'];fills.append(dict(pair_id=x['pair_id'],role=x['role'],cost=x['cost'],**rr,raw_open=a['raw_open'],price=a['price'],fee_components=a['fee_components']))
   for k,v in a['fee_components'].items():components[(x['role'],x['cost'],k)]+=D(v)
pd.DataFrame(fills).to_csv(O/'results/fills.csv',index=False);pd.DataFrame([dict(role=k[0],cost=k[1],component=k[2],amount=v) for k,v in components.items()]).to_csv(O/'results/fee-components.csv',index=False)
for role in ['pvr','h1']:p['slippage_'+role]=[slips[(x.pair_id,role,x.cost)] for x in p.itertuples()]
cov=H.read(O/'COVERAGE_BEFORE_RETURNS.json');allpairs=pd.read_parquet(O/'all-comparable-pairs.parquet');meta={x['symbol']:x for x in H.roster()}
p['PVR_name']=p.symbol_pvr.map(lambda s:meta[s]['name']);p['H1_name']=p.symbol_h1.map(lambda s:meta[s]['name']);summary={};curves=[];fillgroups=[];durations=[]
for cost in [1,2]:
 z=p[p.cost.eq(cost)];tail=z.pair_tail;dt=total(z.delta)
 def side(role):
  v=z['net_pnl_'+role];pos=[x for x in v if x>0];neg=[x for x in v if x<0];up=total(pos);loss=-total(neg);filled=z['first_fill_'+role].notna();held=z['held_close_sessions_'+role]
  return dict(net_pnl=total(v),per_1m_conflict_unit=total(v)/len(z),positive_pnl=up,negative_loss=loss,positive_units=len(pos),negative_units=len(neg),zero_units=int(v.eq(0).sum()),payoff=(up/len(pos))/(loss/len(neg)) if pos and neg else None,profit_factor=up/loss if loss else None,win_fraction=len(pos)/len(z),filled=int(filled.sum()),no_fill=int((~filled).sum()),terminal_share_open=int(z['shares_'+role].gt(0).sum()),terminal_mark_value=total(z['market_value_'+role]),dividend_receivable=total(z['dividend_receivable_'+role]),initial_buy_cost=total(z['buy_gross_'+role]+z['buy_fees_'+role]),explicit_fees=total(z['buy_fees_'+role]+z['sell_fees_'+role]),slippage=total(z['slippage_'+role]),mean_held_sessions_all=float(held.mean()),mean_held_sessions_filled=float(held[filled].mean()),invested_cost_sessions=total(z['invested_cost_sessions_'+role]),terminal_estimated_liquidation_fee=total(z['estimated_liquidation_fee_'+role]),terminal_estimated_exit_slippage=total(z['estimated_exit_slippage_'+role]))
 for (a,b),g in z.groupby([z.first_fill_pvr.notna(),z.first_fill_h1.notna()]):fillgroups.append(dict(cost=cost,PVR_filled=bool(a),H1_filled=bool(b),pairs=len(g),delta=total(g.delta)))
 ds=[]
 for group,g in z.groupby('duration_group'):
  r=dict(cost=cost,group=group,pairs=len(g),delta=total(g.delta),PVR_pnl=total(g.net_pnl_pvr),H1_pnl=total(g.net_pnl_h1));ds.append(r);durations.append(r)
 assert dt==total(z.loc[tail,'delta'])+total(z.loc[~tail,'delta']);assert dt==sum((r['delta'] for r in ds),Z)
 order=z.sort_values('delta',ascending=False);cp=ch=Z
 for rank,r in enumerate(order.itertuples(),1):
  cp+=r.net_pnl_pvr;ch+=r.net_pnl_h1;curves.append(dict(cost=cost,rank_by_delta=rank,pair_id=r.pair_id,date=r.decision_day_pvr,PVR=r.symbol_pvr,H1=r.symbol_h1,PVR_pnl=r.net_pnl_pvr,H1_pnl=r.net_pnl_h1,delta=r.delta,PVR_cumulative=cp,H1_cumulative=ch,pair_tail=r.pair_tail))
 z.to_csv(O/f'results/paired-conflicts-cost{cost}.csv',index=False);order.head(15).to_csv(O/f'results/top-positive-cost{cost}.csv',index=False);order.tail(15).to_csv(O/f'results/top-negative-cost{cost}.csv',index=False)
 # Same-choice pairs change no stock, hence incremental difference0; their absolute P&L is NOT assumed0.
 increments=allpairs[['pair_id','pair_kind']].merge(z[['pair_id','delta']],on='pair_id',how='left');increments.loc[increments.pair_kind.ne('conflict'),'delta']=Z;assert increments.delta.notna().all();assert total(increments.delta)==dt;increments.to_csv(O/f'results/all-comparable-increment-cost{cost}.csv',index=False)
 summary[cost]=dict(conflict_pairs=len(z),all_comparable_pairs=len(allpairs),same_choice_pairs=int(allpairs.pair_kind.eq('same_choice').sum()),PVR=side('pvr'),H1=side('h1'),delta=dt,per_1m_conflict_delta=dt/len(z),per_1m_all_comparable_increment=dt/len(allpairs),unmatched_events=cov['unmatched_E0_events'],unmatched_returns_not_imputed=True,loss_saved=total(z.loss_saved),positive_added=total(z.positive_added),tail_pairs=int(tail.sum()),marked_tail_pairs=int((tail&z.marked_tail).sum()),tail_delta=total(z.loc[tail,'delta']),ordinary_delta=total(z.loc[~tail,'delta']),PVR_tail_contribution=total(z.loc[tail,'net_pnl_pvr']),H1_tail_contribution=total(z.loc[tail,'net_pnl_h1']),extra_fees=total(z.buy_fees_pvr+z.sell_fees_pvr-z.buy_fees_h1-z.sell_fees_h1),extra_slippage=total(z.slippage_pvr-z.slippage_h1),positive_delta_pairs=int(z.delta.gt(0).sum()),negative_delta_pairs=int(z.delta.lt(0).sum()),equal_delta_pairs=int(z.delta.eq(0).sum()),duration_groups=ds,top5_positive_differences=total(order.head(5).delta),bottom5_differences=total(order.tail(5).delta))
pd.DataFrame(curves).to_csv(O/'results/continuous-contributions.csv',index=False);pd.DataFrame(fillgroups).to_csv(O/'results/fill-decomposition.csv',index=False);pd.DataFrame(durations).to_csv(O/'results/duration-decomposition.csv',index=False);S.save(O/'results/summary.json',summary)
# Feature identity against old computation is verification only, never candidate filtering.
a=pd.read_parquet(O/'risk-set.parquet');b=pd.read_parquet(S.ROOT/'research_rounds/cp1-incremental-mechanism-20261029/risk-set.parquet');b['date']=pd.to_datetime(b.date);joint=a.merge(b,on=['date','symbol'],suffixes=('_new','_old'));checks={k:bool(np.array_equal(joint[k+'_new'].to_numpy(),joint[k+'_old'].to_numpy())) for k in ['age','runup','scale','grade']};assert all(checks.values())
ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());S.save(O/'results/report-verification.json',dict(passed=True,tail_plus_ordinary_and_saved_loss_plus_positive_equal_delta=True,all_comparable_difference_zero_for_same_choice=True,unmatched_never_zero_filled=True,feature_identity_overlap=len(joint),feature_checks=checks,input_hashes_unchanged=len(ident),seconds=time.monotonic()-t))
print(json.dumps(S.enc(summary),ensure_ascii=False,indent=2));print('report_seconds',time.monotonic()-t)
