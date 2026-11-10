from pathlib import Path
import json,sys,importlib.util,gzip,time,collections
from decimal import Decimal as D
import pandas as pd
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/s0-first-margin-20261029')
sp=importlib.util.spec_from_file_location('s0_rep',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;Z=D(0);t=time.monotonic()
def total(xs):return sum((D(str(x)) for x in xs),Z)
def dec(x):return D(str(x))
u=pd.read_parquet(O/'results/units.parquet');a=u[u.role.eq('first')];b=u[u.role.eq('second')];p=a.merge(b,on=['pair_id','cost'],suffixes=('_first','_second'),validate='one_to_one');assert len(p)==386
for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','nav','shares','inventory','dividend_receivable','market_value','invested_cost_sessions','estimated_liquidation_fee','estimated_exit_slippage']:
 for side in ['first','second']:p[k+'_'+side]=p[k+'_'+side].map(dec)
p['delta']=p.net_pnl_first-p.net_pnl_second;p['tail_first']=p.net_return_first.ge(.3).fillna(False);p['tail_second']=p.net_return_second.ge(.3).fillna(False);p['pair_tail']=p.tail_first|p.tail_second;p['marked_tail']=p.tail_first&p.shares_first.gt(0)|p.tail_second&p.shares_second.gt(0)
p['loss_saved']=p.net_pnl_second.map(lambda x:max(Z,-x))-p.net_pnl_first.map(lambda x:max(Z,-x));p['positive_added']=p.net_pnl_first.map(lambda x:max(Z,x))-p.net_pnl_second.map(lambda x:max(Z,x));assert all(p.delta.eq(p.loss_saved+p.positive_added))
p['held_session_difference']=p.held_close_sessions_first-p.held_close_sessions_second;p['duration_group']=p.held_session_difference.map(lambda x:'first_longer' if x>0 else 'first_shorter' if x<0 else 'equal');p['extra_fees']=p.buy_fees_first+p.sell_fees_first-p.buy_fees_second-p.sell_fees_second
metadata={x['symbol']:x for x in H.roster()};p['first_name']=p.symbol_first.map(lambda s:metadata[s]['name']);p['second_name']=p.symbol_second.map(lambda s:metadata[s]['name'])
slip=collections.defaultdict(lambda:Z);components=collections.defaultdict(lambda:Z);fills=[]
with gzip.open(O/'results/audit.jsonl.gz','rt') as f:
 for line in f:
  x=json.loads(line)
  for z in x['audit']:
   if z['kind']=='fill':
    r=z['receipt'];slip[(x['pair_id'],x['role'],x['cost'])]+=abs(D(z['price'])-D(z['raw_open']))*r['shares'];fills.append(dict(pair_id=x['pair_id'],role=x['role'],cost=x['cost'],**r,raw_open=z['raw_open'],price=z['price'],fee_components=z['fee_components']))
    for k,v in z['fee_components'].items():components[(x['role'],x['cost'],k)]+=D(v)
pd.DataFrame(fills).to_csv(O/'results/fills.csv',index=False);pd.DataFrame([dict(role=k[0],cost=k[1],component=k[2],amount=v) for k,v in components.items()]).to_csv(O/'results/fee-components.csv',index=False)
p['slippage_first']=[slip[(r.pair_id,'first',r.cost)] for r in p.itertuples()];p['slippage_second']=[slip[(r.pair_id,'second',r.cost)] for r in p.itertuples()]
summary={};curve=[];duration=[]
for cost in [1,2]:
 z=p[p.cost.eq(cost)];tail=z.pair_tail
 def side(role):
  v=z['net_pnl_'+role];pos=[x for x in v if x>0];neg=[x for x in v if x<0];up=total(pos);loss=-total(neg);filled=z['first_fill_'+role].notna();held=z['held_close_sessions_'+role]
  return dict(net_pnl=total(v),per_1m_unit=total(v)/len(z),mean_capital_return=total(v)/len(z)/S.B,positive_pnl=up,negative_loss=loss,positive_units=len(pos),negative_units=len(neg),zero_units=int(v.eq(0).sum()),payoff=(up/len(pos))/(loss/len(neg)) if pos and neg else None,profit_factor=up/loss if loss else None,win_fraction=len(pos)/len(z),filled=int(filled.sum()),no_fill=int((~filled).sum()),terminal_share_open=int(z['shares_'+role].gt(0).sum()),terminal_mark_value=total(z['market_value_'+role]),dividend_receivable=total(z['dividend_receivable_'+role]),initial_buy_cost=total(z['buy_gross_'+role]+z['buy_fees_'+role]),mean_actual_initial_cost_filled=total(z['buy_gross_'+role]+z['buy_fees_'+role])/int(filled.sum()),explicit_fees=total(z['buy_fees_'+role]+z['sell_fees_'+role]),slippage=total(z['slippage_'+role]),held_close_sessions=int(held.sum()),mean_held_close_sessions_all=float(held.mean()),mean_held_close_sessions_filled=float(held[filled].mean()),invested_cost_sessions=total(z['invested_cost_sessions_'+role]),terminal_estimated_liquidation_fee=total(z['estimated_liquidation_fee_'+role]),terminal_estimated_exit_slippage=total(z['estimated_exit_slippage_'+role]))
 ds=[]
 for group,g in z.groupby('duration_group'):
  row=dict(cost=cost,group=group,pairs=len(g),delta=total(g.delta),first_pnl=total(g.net_pnl_first),second_pnl=total(g.net_pnl_second));duration.append(row);ds.append(row)
 dt=total(z.delta);assert dt==total(z.loc[tail,'delta'])+total(z.loc[~tail,'delta']);assert sum((x['delta'] for x in ds),Z)==dt
 ordered=z.sort_values('delta',ascending=False);c1=c2=Z
 for rank,r in enumerate(ordered.itertuples(),1):c1+=r.net_pnl_first;c2+=r.net_pnl_second;curve.append(dict(cost=cost,rank_by_delta=rank,pair_id=r.pair_id,decision_day=r.decision_day_first,first=r.symbol_first,second=r.symbol_second,first_pnl=r.net_pnl_first,second_pnl=r.net_pnl_second,delta=r.delta,first_cumulative=c1,second_cumulative=c2,pair_tail=r.pair_tail))
 z.to_csv(O/f'results/paired-events-cost{cost}.csv',index=False);ordered.head(15).to_csv(O/f'results/top-positive-differences-cost{cost}.csv',index=False);ordered.tail(15).to_csv(O/f'results/top-negative-differences-cost{cost}.csv',index=False)
 summary[cost]=dict(pairs=len(z),first=side('first'),second=side('second'),delta=dt,per_1m_pair_delta=dt/len(z),loss_saved=total(z.loss_saved),positive_added=total(z.positive_added),pair_tail_count=int(tail.sum()),terminal_valued_pair_tail=int((tail&z.marked_tail).sum()),tail_delta=total(z.loc[tail,'delta']),ordinary_delta=total(z.loc[~tail,'delta']),first_pair_tail_contribution=total(z.loc[tail,'net_pnl_first']),second_pair_tail_contribution=total(z.loc[tail,'net_pnl_second']),extra_fees=total(z.extra_fees),extra_slippage=total(z.slippage_first-z.slippage_second),positive_delta_pairs=int(z.delta.gt(0).sum()),negative_delta_pairs=int(z.delta.lt(0).sum()),equal_delta_pairs=int(z.delta.eq(0).sum()),same_first_fill=int((z.first_fill_first.fillna('NONE')==z.first_fill_second.fillna('NONE')).sum()),one_side_no_fill=int((z.first_fill_first.isna()^z.first_fill_second.isna()).sum()),both_no_fill=int((z.first_fill_first.isna()&z.first_fill_second.isna()).sum()),duration_groups=ds,same_sector_pairs=int(z.same_sector_first.sum()),same_sector_delta=total(z.loc[z.same_sector_first,'delta']),cross_sector_delta=total(z.loc[~z.same_sector_first,'delta']),top5_positive_differences=total(ordered.head(5).delta),bottom5_differences=total(ordered.tail(5).delta))
pd.DataFrame(curve).to_csv(O/'results/continuous-contributions.csv',index=False);pd.DataFrame(duration).to_csv(O/'results/duration-decomposition.csv',index=False);S.save(O/'results/summary.json',summary)
ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(x)==h for x,h in ident.items())
S.save(O/'results/report-verification.json',dict(passed=True,all193_pairs_present_both_costs=True,saved_losses_plus_added_positive_equals_delta=True,tail_plus_ordinary_equals_delta=True,duration_groups_sum_to_delta=True,input_hashes_unchanged=len(ident),sample_and_full_verified=H.read(O/'results/verification.json')['passed'],seconds=time.monotonic()-t))
print(json.dumps(S.enc(summary),ensure_ascii=False,indent=2));print('report_seconds',time.monotonic()-t)
