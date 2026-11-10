"""Post-run only. Baseline outcome labels never feed the consumer."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,math
import pandas as pd
O=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025');sys.path.insert(0,str(B/'code'))
from market_rules import market_identity_on,version_on
from sector_account import FeeSchedule,FeeComponent
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids']
r=pd.concat([pd.read_csv(O/x/'ROUNDS.csv',float_precision='round_trip') for x in ['baseline','economic']],ignore_index=True)
def sell_fee(sid,day,q,px):
 ident=market_identity_on(rules,sid,day,proxies);v=version_on(rules['fee_versions'][ident['venue']],day,proxies)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**z) for z in v['components']));par=D(str(rules['security_metadata'][sid]['par_value']))
 return sum(fs.incremental('sell',D(q)*px,{}, {},1,shares=q,par_value=par).values(),D(0))
for i,z in r[r.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')].iterrows():
 q=int(z.entry_q);px=D(str(z.exit_price));f=sell_fee(z.sid,z.exit_day,q,px);cost=D(q)*D(str(z.entry_price))+D(str(z.entry_fee));net=D(q)*px-f-cost
 r.loc[i,['core_net','core_return','core_sell_fee','core_buy_cash']]=[float(net),float(net/cost),float(f),float(cost)]
summary=[];tails=[]
for (w,arm),g in r.groupby(['window','arm']):
 c=g[g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];unknown=g.status.str.contains('UNKNOWN').sum();cens=g.status.str.contains('CENSORED').sum();nofill=g.status.str.contains('NOFILL').sum();assert len(g)==len(c)+unknown+cens+nofill
 for layer,pnl,ret in [('full','net_pnl','net_return_on_buy_cash'),('core','core_net','core_return')]:
  wins=c[c[pnl].gt(0)];loss=c[c[pnl].le(0)]
  summary.append(dict(window=w,arm=arm,layer=layer,selected=len(g),entered=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(c),unknown=int(unknown),censored=int(cens),nofill=int(nofill),unknown_over_selected=float(unknown/len(g)),wins=len(wins),losses=len(loss),win_rate=len(wins)/len(c) if len(c) else None,payoff_cny=wins[pnl].mean()/-loss[pnl].mean() if len(wins) and len(loss) and loss[pnl].mean()!=0 else None,payoff_return=wins[ret].mean()/-loss[ret].mean() if len(wins) and len(loss) and loss[ret].mean()!=0 else None,independent_stock_net_sum=c[pnl].sum(),mean_return=c[ret].mean(),tail_ge20=int(c[ret].ge(.2).sum()),tail_ge50=int(c[ret].ge(.5).sum()),not_account_return=True))
for w,g in r.groupby('window'):
 base=g[g.arm.eq('A_UNION_B')&g.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND')];new=g[g.arm.eq('RELATIVE_UP_PRIORITY')].set_index('event_id')
 for layer,pnl,ret in [('full','net_pnl','net_return_on_buy_cash'),('core','core_net','core_return')]:
  pos=base[base[pnl].gt(0)]
  sets=[('ge20',base[base[ret].ge(.2)]),('ge50',base[base[ret].ge(.5)])]
  for metric in [pnl,ret]:
   ranked=pos.sort_values([metric,'event_id'],ascending=[False,True])
   sets.extend([(metric+'_top10',ranked.head(10)),(metric+'_top10pct',ranked.head(math.ceil(len(pos)*.1)))])
  for label,cohort in sets:
   kept=new.reindex(cohort.event_id);closed=kept.status.eq('COMPLETE_CONDITIONAL_STOCK_ROUND');threshold=.2 if label=='ge20' else .5 if label=='ge50' else 0
   tails.append(dict(window=w,layer=layer,cohort=label,baseline_n=len(cohort),selected_retained=int(kept.arm.notna().sum()),completed_retained=int(closed.sum()),positive_retained=int((closed&kept[pnl].gt(0)).sum()),threshold_retained=int((closed&kept[ret].ge(threshold)).sum()) if threshold else None,selected_retention_fraction=kept.arm.notna().sum()/len(cohort) if len(cohort) else None))
r.to_csv(O/'CORE_AND_FULL_ROUNDS.csv',index=False);pd.DataFrame(summary).to_csv(O/'PERFORMANCE.csv',index=False);pd.DataFrame(tails).to_csv(O/'BASELINE_TAIL_RETENTION.csv',index=False)
# Same-event new lifecycle can differ; compare selection and complete status without imputing unknown.
b=r[r.arm.eq('A_UNION_B')].set_index('event_id');n=r[r.arm.eq('RELATIVE_UP_PRIORITY')].set_index('event_id')
b.add_prefix('baseline_').join(n.add_prefix('new_'),how='outer').to_csv(O/'EVENT_OUTCOME_COMPARISON.csv')
print('EVALUATED: independent conditional stock rounds, not account returns')
