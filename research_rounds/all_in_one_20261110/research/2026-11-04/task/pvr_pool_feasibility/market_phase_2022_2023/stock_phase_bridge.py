"""Basis-independent actual stock wealth per complete market leg, no PnL oracle."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
import pandas as pd
import analyze_phase as A
O=A.O;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SM={x['symbol']:x for x in A.read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
META=A.read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
frames={}
def price(sid,d):
 if sid not in frames:
  r=SM[sid];p=Path(r['refs']['facts']);assert A.sha(p)==r['output_sha256'][str(p)];A.SRC[str(p)]=A.sha(p);frames[sid]=pd.read_parquet(p,columns=['raw_close'])
 f=frames[sid];idx=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert idx>=0
 return D(str(f.iloc[idx].raw_close))
def main():
 legs=A.read(O/'HS300_ALL_LEGS.json');periods=A.read(O/'ALL_PERIODS.json');outputs={};bridges=[]
 for label,conf in A.CONFIG.items():
  b=A.book(conf['native']/'B.json.gz');snap={r['at'][:10]:r for r in A.stream(conf['native']/'daily.jsonl.gz')}
  output=[]
  for leg in legs:
   left,right=leg['left'],leg['right'];before=snap.get(left,dict(positions={},inventory='0',nav='1000000'));after=snap[right]
   oldvalue={sid:D(q)*price(sid,left)for sid,q in before['positions'].items()if q};newvalue={sid:D(q)*price(sid,right)for sid,q in after['positions'].items()if q}
   assert abs(sum(oldvalue.values(),D(0))-D(before['inventory']))<D('.000001')and abs(sum(newvalue.values(),D(0))-D(after['inventory']))<D('.000001')
   flow=defaultdict(lambda:D(0));fees=defaultdict(lambda:D(0));buys=defaultdict(lambda:D(0));sells=defaultdict(lambda:D(0));div=defaultdict(lambda:D(0));buycount=Counter();sellcount=Counter();reason=defaultdict(Counter)
   prior_bought={t['security_id']for t in b['trades']if t['side']=='buy'and t['at'][:10]<=left}
   for t in b['trades']:
    if not left<t['at'][:10]<=right:continue
    sid=t['security_id'];fee=D(t['fees_cny']);gross=D(t['gross_cny']);fees[sid]+=fee
    if t['side']=='buy':flow[sid]-=gross+fee;buys[sid]+=gross+fee;buycount[sid]+=1
    else:flow[sid]+=gross-fee;sells[sid]+=gross-fee;sellcount[sid]+=1;reason[sid][t['reason']]+=1
   for r in b['audit']:
    if r['kind']=='dividend_accrual':
     z=r['receivable']
     if left<z['ex_at'][:10]<=right:div[z['security_id']]+=D(z['net_local'])
   stocks=set(oldvalue)|set(newvalue)|set(flow)|set(div);rows=[]
   for sid in stocks:
    net=flow[sid]+newvalue.get(sid,D(0))-oldvalue.get(sid,D(0))+div[sid]
    cohort='carried_stock_at_start_may_have_new_adds'if sid in oldvalue else'previously_bought_but_flat_reentry'if buys[sid]and sid in prior_bought else'new_stock_foothold'if buys[sid]else'no_start_inventory_or_new_buy'
    rows.append(dict(policy=label,leg=leg['id'],left=left,right=right,sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],sector=META[sid]['sector_id'],
     start_inventory=oldvalue.get(sid,D(0)),end_inventory=newvalue.get(sid,D(0)),net_trade_cash=flow[sid],recognized_dividend=div[sid],net_PnL=net,
     actual_buy_cash=buys[sid],actual_sell_net=sells[sid],actual_fees=fees[sid],buy_fills=buycount[sid],sell_fills=sellcount[sid],exit_reasons=dict(reason[sid]),cohort=cohort,
     attribution_unit='whole-stock wealth change inside leg, not lifetime layer return or delete-trade counterfactual'))
   rows.sort(key=lambda x:(x['net_PnL'],x['sid']));actual=sum((r['net_PnL']for r in rows),D(0));expected=D(after['nav'])-D(before['nav']);assert abs(actual-expected)<D('.000001')
   cohorts={}
   for c in sorted({r['cohort']for r in rows}):
    rr=[r for r in rows if r['cohort']==c];cohorts[c]=dict(stocks=len(rr),net_PnL=sum((r['net_PnL']for r in rr),D(0)),actual_buy_cash=sum((r['actual_buy_cash']for r in rr),D(0)),start_inventory=sum((r['start_inventory']for r in rr),D(0)),end_inventory=sum((r['end_inventory']for r in rr),D(0)))
   bridges.append(dict(policy=label,leg=leg['id'],net_PnL=actual,expected_NAV_change=expected,residual=actual-expected,all_stocks=len(rows),cohorts=cohorts))
   output.extend(rows)
  outputs[label]=output
 A.save('ALL_PHASE_STOCK_WEALTH.json',outputs);A.save('PHASE_STOCK_WEALTH_BRIDGES.json',bridges)
 A.SRC[str(Path(__file__))]=A.sha(__file__);A.save('STOCK_PHASE_SOURCE_SHA256.json',A.SRC)
 A.save('STOCK_PHASE_GATE.json',dict(passed=True,stock_period_cohorts_not_layer_cost_reset=True,whole_stock_cash_dividend_inventory_bridge=True,policies=2,legs=len(legs),all_period_PnL_equal_NAV_change=True,new_policy_events=0))
 for r in bridges:
  if r['policy']=='NO60':print(r['leg'],r['net_PnL'],r['cohorts'],flush=True)
if __name__=='__main__':main()
