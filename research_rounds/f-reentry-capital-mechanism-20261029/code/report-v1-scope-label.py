from pathlib import Path
import sys,json,gzip,time,importlib.util,collections
from decimal import Decimal as D
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/f-reentry-capital-mechanism-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029'
sp=importlib.util.spec_from_file_location('f_study_report',O/'code/study.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S)
Z=D(0);B=D(1000000);t=time.monotonic()
def total(xs):return sum((D(str(x)) for x in xs),Z)
def writecsv(path,rows):pd.DataFrame(S.slim(rows)).to_csv(path,index=False)
u=pd.read_parquet(O/'results/units.parquet');i=pd.read_parquet(E1/'results/units.parquet');i=i[i.variant.eq('I')]
p=u.merge(i,on=['event_id','cost'],suffixes=('_F','_I'),validate='one_to_one');assert len(p)==10698
for k in ['net_pnl','buy_fees','sell_fees','nav','dividend_receivable','market_value','shares','buy_gross','sell_gross']:
 for arm in ['F','I']:p[k+'_'+arm]=p[k+'_'+arm].map(lambda x:D(str(x)))
p['delta']=p.net_pnl_F-p.net_pnl_I;p['tail_I']=p.net_return.ge(.30);p['I_valued_open']=p.shares_I.gt(0);p['F_valued_open']=p.shares_F.gt(0)
p['extra_fees']=p.buy_fees_F+p.sell_fees_F-p.buy_fees_I-p.sell_fees_I;p['extra_slippage']=p.slippage.map(D)-p.control_slippage.map(D)
p['I_profit_lost']=p.net_pnl_I.map(lambda x:max(Z,x))-p.net_pnl_F.map(lambda x:max(Z,x));p['loss_saved']=p.net_pnl_I.map(lambda x:min(Z,x)).mul(-1)-p.net_pnl_F.map(lambda x:min(Z,x)).mul(-1)
assert all(abs(x)<=D('1e-15') for x in p.delta-p.loss_saved+p.I_profit_lost)
d=pd.read_parquet(O/'results/daily-paired.parquet');d.delta_increment=d.delta_increment.map(D);bucket=d.groupby(['cost','bucket']).delta_increment.agg(total).reset_index();bucket.to_csv(O/'results/daily-accounting-buckets.csv',index=False)
cycles=[];attempts=[];exits=[];raises=[];coverage=collections.Counter();fee_components=collections.defaultdict(lambda:Z);cyclemap={}
lookup={(r.event_id,r.cost):r for r in p.itertuples()}
with gzip.open(O/'results/audit.jsonl.gz','rt') as f:
 for line in f:
  a=json.loads(line);key=(a['event_id'],a['cost']);r=lookup[key];q=0;cur=None;seq=0;av=None;re=[];newlogs=[];cycle_start=len(cycles)
  for x in a['attempts']:attempts.append(dict(event_id=key[0],symbol=a['symbol'],cost=key[1],**x))
  for x in a['decisions']:
   (exits if x['kind']=='exit' else raises).append(dict(event_id=key[0],symbol=a['symbol'],cost=key[1],**x))
  for x in a['audit']:
   k=x['kind'];coverage[k]+=1
   if k=='fill':
    z=x['receipt'];qty=int(z['shares']);gr=D(z['gross_cny']);fee=D(z['fees_cny']);slip=abs(D(x['price'])-D(x['raw_open']))*qty
    if z['side']=='buy':
     if not q:
      seq+=1;cur=dict(event_id=key[0],symbol=a['symbol'],cost=key[1],cycle=seq,buy_at=z['at'],sell_at=None,buy_gross=Z,sell_gross=Z,fees=Z,slippage=Z,dividend=Z,closed=False)
     q+=qty;cur['buy_gross']+=gr
    else:q-=qty;cur['sell_gross']+=gr;cur['sell_at']=z['at']
    cur['fees']+=fee;cur['slippage']+=slip
    for name,v in x['fee_components'].items():fee_components[(key[1],name)]+=D(v)
    if not q:cur['closed']=True;cur['terminal_market_value']=Z;cur['net_pnl']=cur['sell_gross']+cur['dividend']-cur['buy_gross']-cur['fees'];cycles.append(cur);cur=None
   elif k in ['split','split_fraction_floor_proxy']:q=int(D(q)*D(x['ratio']))
   elif k=='dividend_accrual':
    assert cur is not None;cur['dividend']+=D(x['receivable']['net_local'])
  if cur:
   cur['terminal_market_value']=r.market_value_F;cur['net_pnl']=cur['sell_gross']+cur['dividend']+cur['terminal_market_value']-cur['buy_gross']-cur['fees'];cycles.append(cur)
  these=cycles[cycle_start:]
  assert abs(total(x['net_pnl'] for x in these)-r.net_pnl_F)<=D(str(r.precision_bound_F)),(key,'cycle accounting')
writecsv(O/'results/roundtrips.csv',cycles);writecsv(O/'results/attempts.csv',attempts);writecsv(O/'results/exit-decisions.csv',exits);writecsv(O/'results/protection-raises.csv',raises)
writecsv(O/'results/fee-components.csv',[dict(cost=k[0],component=k[1],amount=v) for k,v in fee_components.items()])
curve=[];summary={}
for cost in [1,2]:
 z=p[p.cost.eq(cost)].copy();tails=z.tail_I;Dtot=total(z.delta);ordinary=total(z.loc[~tails,'delta']);tail=total(z.loc[tails,'delta']);assert Dtot==ordinary+tail
 assert abs(total(bucket[bucket.cost.eq(cost)].delta_increment)-Dtot)<=D('1e-15')
 stockmeans=z.groupby('symbol_F').delta.agg(lambda x:total(x)/len(x));c=[x for x in cycles if x['cost']==cost];retry=[x for x in c if x['cycle']>1];closedretry=[x for x in retry if x['closed']];retryneg=[x for x in closedretry if x['net_pnl']<0]
 seq=z.sort_values('net_pnl_I',ascending=False);ic=fc=Z
 for rank,r in enumerate(seq.itertuples(),1):
  ic+=r.net_pnl_I;fc+=r.net_pnl_F;curve.append(dict(cost=cost,rank=rank,event_id=r.event_id,symbol=r.symbol_F,I=r.net_pnl_I,F=r.net_pnl_F,delta=r.delta,I_cumulative=ic,F_same_events_cumulative=fc,tail_I=r.tail_I,reentries=r.reentries,I_valued_open=r.I_valued_open,F_valued_open=r.F_valued_open))
 z.to_csv(O/f'results/paired-events-cost{cost}.csv',index=False)
 seq.head(30).to_csv(O/f'results/top-I-events-cost{cost}.csv',index=False)
 bucketmap={r.bucket:r.delta_increment for r in bucket[bucket.cost.eq(cost)].itertuples()}
 def side(arm):
  q=z['net_pnl_'+arm];pos=[x for x in q if x>0];neg=[x for x in q if x<0];up=total(pos);dn=-total(neg)
  return dict(pnl=total(q),positive_pnl=up,negative_loss=dn,positive_events=len(pos),negative_events=len(neg),payoff=(up/len(pos))/(dn/len(neg)) if pos and neg else None,profit_factor=up/dn if dn else None,win_fraction=len(pos)/len(q),shares_open=int(z['shares_'+arm].gt(0).sum()),unpaid_dividend=total(z['dividend_receivable_'+arm]))
 summary[cost]=dict(events=len(z),stocks=z.symbol_F.nunique(),I=side('I'),F=side('F'),delta=Dtot,per_1m_event_delta=Dtot/len(z),loss_saved=total(z.loss_saved),positive_pnl_foregone=total(z.I_profit_lost),tail_delta=tail,ordinary_delta=ordinary,tail_events=int(tails.sum()),I_tail_contribution=total(z.loc[tails,'net_pnl_I']),F_same_tail_contribution=total(z.loc[tails,'net_pnl_F']),tail_retention=total(z.loc[tails,'net_pnl_F'])/total(z.loc[tails,'net_pnl_I']),tail_realized_share_closed=int((tails&~z.I_valued_open).sum()),tail_terminal_valued_open=int((tails&z.I_valued_open).sum()),stock_equal_delta_per_1m=total(stockmeans)/len(stockmeans),total_F_entries=int(z.cycles.sum()),reentries=int(z.reentries.sum()),events_reentered=int(z.reentries.gt(0).sum()),max_entries_per_event=int(z.cycles.max()),retry_closed=len(closedretry),retry_closed_losses=len(retryneg),retry_closed_loss_amount=-total(x['net_pnl'] for x in retryneg),retry_all_pnl=total(x['net_pnl'] for x in retry),retry_fees=total(x['fees'] for x in retry),all_extra_fees=total(z.extra_fees),all_extra_slippage=total(z.extra_slippage),daily_accounting=bucketmap,idle_close_sessions=int(z.idle_close_sessions.sum()),idle_available_cash_sessions=total(z.idle_available_cash_sessions),held_close_sessions=int(z.held_close_sessions.sum()),all_attempts=sum(x['cost']==cost for x in attempts),unsuccessful_reservations=sum(x['cost']==cost and not x['accepted'] for x in attempts),terminal_estimated_liquidation_fee_F=total(z.estimated_liquidation_fee_F),terminal_estimated_liquidation_fee_I=total(z.estimated_liquidation_fee_I),terminal_estimated_exit_slippage_F=total(z.estimated_exit_slippage_F),terminal_estimated_exit_slippage_I=total(z.estimated_exit_slippage_I))
writecsv(O/'results/continuous-contributions.csv',curve)
S.save(O/'results/summary.json',summary)
S.save(O/'results/report-verification.json',dict(passed=True,all_cycle_pnls_sum_to_unit=True,all_saved_losses_minus_foregone_profit_equal_delta=True,all_daily_buckets_sum_to_delta=True,rows=len(p),roundtrips=len(cycles),attempts=len(attempts),audit_kind_counts=dict(coverage),seconds=time.monotonic()-t))
print(json.dumps(S.slim(summary),ensure_ascii=False,indent=2));print('report_seconds',time.monotonic()-t)
