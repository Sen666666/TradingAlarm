"""Source/seed/proxy-preview tests only. No OPEN account event or economic path."""
import copy,json,sys,time,traceback
from decimal import Decimal as D
from pathlib import Path
import pandas as pd
import inputs as I
import conditional_engine as E
J=I.J

def preview(r,i,at):
 r.market.set_phase(at,'OPEN');sid=i['sid'];f=r.facts.factor(sid,at);w=r.market.window(sid,at,'buy',1)
 if w is None:return dict(result='UNKNOWN_NO_PROXY_WINDOW')
 x,why=J.LR.preview(i,w.raw_open,f,w.quantity,w.fees)
 if why:return dict(result=why,open=w.raw_open,guard=i['guard_floor']/f)
 floor=i['I_floor']/f;q=J.LR.maximum_quantity(x['rule'],x['maxq'],lambda n:E.nominal_risk(n,x['price'],floor,x['schedule'],i['quote'].par_value)<=i['risk_budget'])
 if not q:return dict(result='NO_MINIMUM_I_RISK',open=w.raw_open,guard=i['guard_floor']/f)
 assert q<=i['cap']and D(q)*x['price']<=i['budget']and E.nominal_risk(q,x['price'],floor,w.fees,i['quote'].par_value)<=i['risk_budget']
 return dict(result='PASS_PREVIEW_NOT_FUNDING_OR_FILL',open=w.raw_open,price=x['price'],guard=i['guard_floor']/f,I_floor=floor,maxq_before_budget_route=q,capacity=w.capacity_shares,frozen_q=i['cap'],risk=E.nominal_risk(q,x['price'],floor,w.fees,i['quote'].par_value),risk_budget=i['risk_budget'],gross_budget=i['budget'])

def main():
 st=time.monotonic();data=I.load();rows=[];tests={};prefix=[]
 for case in data['cases']:
  pair=[]
  for arm in E.ARMS:
   shared,rec,cp,states,ir=I.single(data,case['sid']);r=E.Runner(shared,rec,cp,states,ir,case,arm);r.warm(data['calendar']);row=E.seed_plan(r);a=r.account
   for i in a.pending:
    assert i['role']=='mobile'and i['budget']==a.current_nav*D('.02')and i['risk_budget']==a.current_nav*D('.0025')
    assert i['kind']==('probe_mobile'if arm==E.ARMS[1]else'add')
    at=i['clock'].earliest_execution_at;v=preview(r,i,at);row['first_OPEN_preview']=v
    # Frozen CP guard remains even though sizing floor is I.
    fac=r.facts.factor(case['sid'],at);guard=i['guard_floor']/fac;inside=(i['I_floor']/fac+guard)/2
    if guard>i['I_floor']/fac:
     x,why=J.LR.preview(i,inside,fac,r.market.quantity(case['sid'],at),r.market.fees(case['sid'],at));assert x is None and why=='open_at_or_below_protection'
    # Poison current+future HLCV and derived valid-volume masks, leave OPEN.
    m=r.market;sid=case['sid'];oldarr=m.arr[sid];poison={k:(v.copy()if hasattr(v,'copy')else v)for k,v in oldarr.items()};day=pd.Timestamp(at.date()).value//86400000000000;p=__import__('numpy').searchsorted(poison['days'],day)
    for k in ('high','low','close','volume','valid'):poison[k][p:]=False if k=='valid'else 99999999
    for k in ('good','positive'):poison[k]=poison[k][poison[k]<p]
    m.arr={sid:poison}
    try:assert I.canon(preview(r,i,at))==I.canon(v)
    finally:m.arr={sid:oldarr}
    for method,args in [('row',(sid,at)),('floor',(sid,at,'I')),('packet',(at,'I'))]:
     try:getattr(r.facts,method)(*args)
     except AssertionError:pass
     else:raise AssertionError(('OPEN future facts permitted',method))
   if not a.pending:row['first_OPEN_preview']={'result':'SIGNAL_MINIMUM_NO_INTENT'}
   assert not a.trades and not a.positions and not a.buys and not a.layers
   pair.append(row);rows.append(row)
  x,y=pair;assert x['intents'][0]['cap']==y['intents'][0]['cap']if x['intents']and y['intents']else not x['intents']and not y['intents']
  prefix.append(dict(round_id=case['round_id'],original_epoch=case['original_initial_trade']['epoch'],recomputed_watch=x['global_watch'],seed_core_epoch=x['core_epoch'],original_roles=x['original_seed_roles'],suppressed_core=len(x['seed_suppressed']),both_arms_same_frozen_size=True))
  print('SEED_PASS',case['round_id'],case['name'],x['first_OPEN_preview']['result'],flush=True)
 # Stock-wide cost book tests: proportional sale, dividends not credited, split no cost mutation.
 class F:
  def __init__(self):self.journal=[];self.positions={'x':1};self.q=0
  def quantity(self,s):return self.q
 f=F();b=E.RemainingCost();f.journal=[dict(kind='real_buy_fill',sid='x',shares=100,price=D(10),fees=D(5))];f.q=100;b.sync(f);assert b.cost==1005
 f.journal.append(dict(kind='dividend_paid',sid='x',amount=500));b.sync(f);assert b.cost==1005
 f.journal.append(dict(kind='real_sell_fill',sid='x',shares=40,price=D(20),fees=D(5)));f.q=60;b.sync(f);assert b.cost==603
 f.journal.append(dict(kind='actual_split',sid='x',ratio=D(2)));f.q=120;b.sync(f);assert b.cost==603
 f.journal.append(dict(kind='real_sell_fill',sid='x',shares=120,price=D(20),fees=D(5)));f.q=0;b.sync(f);assert b.cost==0
 tests.update(guard_uses_frozen_CP_not_I=True,signal_2pct_and_025pct=True,OPEN_shrink_only=True,OPEN_HLCV_poison_invariance=True,OPEN_current_fact_APIs_blocked=True,cost_buyfees_prorata_sale_dividend_excluded_split=True,seed_market_qualification_matches_original=True,seed_watch_epoch_matches_original=True,seed_CORE_conditioning_explicit=True,no_financial_paths=True,account_OPEN_events=0,trade_fills=0)
 I.save('SOURCE_FREEZE_PRECHECK.json',I.SOURCES);I.save('NATIVE_DIFF_PRECHECK.json',E.DIFFS);I.save('SEED_PRECHECK.json',rows);I.save('SEED_EPOCH_PREFIX_CHECK.json',prefix);I.save('PRECHECK.json',dict(passed=True,seconds=time.monotonic()-st,tests=tests,seed_previews=len(rows),economic_paths=0,remaining='Independent source review and supplemental synthetic callback/state tests before economic execution.'))
 print('PRECHECK_PASS',time.monotonic()-st,flush=True)
if __name__=='__main__':
 try:main()
 except BaseException:
  p=I.O/'PRECHECK_FAILURE_02.txt';p.write_text(traceback.format_exc());raise
