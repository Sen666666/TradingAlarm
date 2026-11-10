"""Bounded read-only 87 account-day audit; no strategy/provider/private fee import.
Native saved money reader reused unchanged. Expected fees use ONLY original
FeeSchedule on once flag-scaled components, multiplier=1, actual order accrual.
"""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
from collections import defaultdict,Counter
import importlib.util,json,bisect,sys
O=Path(__file__).resolve().parent; W=O.parent
S=W/'independent_review/trend_confirmation_full_ledger_v1/generic_saved_finance_reader.py'
spec=importlib.util.spec_from_file_location('robust87_saved_reader',S);R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
FP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py')
sys.path.insert(0,str(FP.parent));sp=importlib.util.spec_from_file_location('robust87_original_fee_engine_only',FP);F=importlib.util.module_from_spec(sp);sys.modules[sp.name]=F;sp.loader.exec_module(F)
RULEP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=R.read(RULEP)
R.SRC[str(FP)]=R.sha(FP);R.SRC[str(FP.parent/'sector_stock_admission.py')]=R.sha(FP.parent/'sector_stock_admission.py')
Z=D(0);EPS=D('.000001')
CONFIG={'MA63_G05':D('.05'),'MA63_G20':D('.20'),'MA62_G10':D('.10'),'MA64_G10':D('.10'),'MA63_G10_TECH':D('.10'),'NO60_C15':None,'MA63_G10_C15':D('.10')}
CASES=[('cost1','legacy9',9,D(1)),('cost1','fresh_DOWN_technical6',6,D(1)),('cost15','fresh_DOWN_technical6',6,D('1.5'))]
fee_cache={}
def dated(v,day):
 xs=[x for x in v if x['from']<=day and(x.get('to')is None or day<x['to'])];assert len(xs)==1;return xs[0]
def fee_schedule(sid,day,mult):
 venue=dated(rules['venue_versions'][sid],day)['venue'];obj=dated(rules['fee_versions'][venue],day)['schedule'];key=(obj['schedule_id'],mult)
 if key not in fee_cache:
  cs=tuple(F.FeeComponent(**x)for x in obj['components'])
  scaled=tuple(replace(c,rate=D(c.rate)*(mult if c.stress_rate else 1),minimum_local=D(c.minimum_local)*(mult if c.stress_minimum else 1),maximum_local=None if c.maximum_local is None else D(c.maximum_local)*(mult if c.stress_maximum else 1),stress_rate=False,stress_minimum=False,stress_maximum=False)for c in cs)
  fee_cache[key]=F.FeeSchedule(obj['schedule_id'],scaled)
 return fee_cache[key]
def pending_qty(book,cut):
 p={}
 for e in book['audit'][:cut]:
  if e['kind']=='reserve':p[e['order_id']]=int(e['target_shares'])
  elif e['kind']=='release_buy':p.pop(e['order_id'])
  elif e['kind']=='fill'and e['receipt']['side']=='buy':p[e['order_id']]=int(e['share_cap_remaining'])
  elif e['kind']in ('split','split_fraction_floor_proxy'):assert not p,'No pending-CA rewrite added'
 return p

def money(book,layers,cut,at,slip):
 p=R.prefix(book,cut);quant=defaultdict(int)
 for lid,q in p['q'].items():quant[layers[lid]['sid']]+=q
 inv=sum((D(q)*R.mark(sid,at)for sid,q in quant.items()if q),Z)
 gross=sum((x['gross']for x in p['pending'].values()),Z)
 drag=sum((x['fee']+x['gross']*slip/(1+slip)for x in p['pending'].values()),Z)
 return p,dict(NAV=p['cash']+p['divincome']+inv,inventory=inv,pending_gross=gross,pending_drag=drag)

def fee_and_price(book,mult):
 histories=defaultdict(list);states={};counts=Counter();examples=[]
 for idx,e in enumerate(book['audit']):
  if e['kind']!='fill':continue
  t=e['receipt'];oid=e['order_id'];sid=t['security_id'];day=t['at'][:10];side=t['side'];q=int(t['shares']);gross=D(t['gross_cny']);fee=D(t['fees_cny']);sch=fee_schedule(sid,day,mult);assert sch.schedule_id==e['fee_schedule']
  par=rules['security_metadata'][sid].get('par_value');par=None if par is None else D(par);paid,accrued=states.setdefault(oid,({},{}))
  expected=sch.incremental(side,gross,paid,accrued,1,shares=q,par_value=par)
  assert expected=={k:D(v)for k,v in e['fee_components'].items()},('original engine exact component mismatch',sid,t['at'],expected,e['fee_components'])
  assert sum(expected.values(),Z)==fee
  R.near(D(e['price'])*q*D(e['fx_rate']),gross,'actual execution principal');assert D(e['fx_rate'])==1
  op=R.mark(sid,t['at']);assert op==D(e['raw_open'])
  slip=D('.0005')*mult;px=op*(1+slip if side=='buy'else 1-slip);assert px==D(e['price']),('actual side execution slip',sid,side)
  for k,v in expected.items():paid[k]=paid.get(k,Z)+v
  for k,v in sch.rate_accrual(side,gross,1,shares=q,par_value=par).items():accrued[k]=accrued.get(k,Z)+v
  histories[oid].append((idx+1,dict(paid),dict(accrued)));counts[side]+=1;counts['fee_components']+=len(expected)
  if mult==D('1.5')and len(examples)<3 or(mult==D('1.5')and side=='sell'and not any(x['side']=='sell'for x in examples)):
   examples.append(dict(sid=sid,at=t['at'],side=side,qty=q,raw_open=str(op),execution_price=str(px),gross=str(gross),actual_fee=str(fee),exact_components={k:str(v)for k,v in expected.items()}))
 def expected_fee(oid,cut,sid,at,side,q,price):
  prior=[x for x in histories[oid]if x[0]<=cut];paid,accrued=(prior[-1][1],prior[-1][2])if prior else ({},{})
  par=rules['security_metadata'][sid].get('par_value');par=None if par is None else D(par)
  return sum(fee_schedule(sid,at[:10],mult).incremental(side,D(q)*price,paid,accrued,1,shares=q,par_value=par).values(),Z)
 return expected_fee,dict(counts),examples

report={};total_days=atomic_snapshots=0;stress_examples=[]
for family,name,n,mult in CASES:
 out=W/'market_gross_robustness_v1'/f'small87-{family}-v2'/name
 start=R.read(out/'STARTED.json');done=R.read(out/'SMALL_RESULT.json');assert done['passed']and done['closes_each']==n and not done['full']
 ds=R.rows(out/'pair/daily.jsonl.gz');bs=R.rows(out/'pair/balances.jsonl.gz');arms=start['arms'];assert len(ds)==n*len(arms)
 family_report={};slip=D('.0005')*mult
 for arm in arms:
  assert arm in CONFIG;alpha=CONFIG[arm];book=R.book(out/'pair'/(arm+'.json.gz'));daily=[r for r in ds if r['account']==arm];assert len(daily)==n
  assert D(done['arms'][arm]['cost_multiplier'])==mult and D(done['arms'][arm]['NAV'])==D(book['ending_NAV'])
  layers={x['id']:x for x in book['layers']};times=[];last=R.ts(daily[0]['at'])-R.pd.Timedelta(days=10000)
  for e in book['audit']:
   at=e.get('at')or e.get('receipt',{}).get('at')or e.get('receivable',{}).get('ex_at');cur=R.ts(at)if at else last;assert cur>=last;times.append(cur);last=cur
  for d in daily:
   cut=bisect.bisect_right(times,R.ts(d['at']));p,m=money(book,layers,cut,d['at'],slip);quant=defaultdict(int)
   for lid,q in p['q'].items():quant[layers[lid]['sid']]+=q
   assert {sid:q for sid,q in quant.items()if q}==d['positions'];R.near(m['NAV'],d['nav'],'daily native NAV');R.near(m['inventory'],d['inventory'],'daily raw inventory')
   R.near(p['cash']+p['divincome'],sum((D(d[k])for k in ('available','order_reserved','sale_receivable','dividend_receivable')),Z),'cash+AR liquid bridge');R.near(p['fees'],d['fees_cny'],'cumulative fee once')
  for b in bs:
   if b['account']==arm:
    for k in ('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):R.near(b[k],0,k)
  R.near(book['ending_NAV'],daily[-1]['nav'],'terminal wealth');R.near(book['ending_cash'],daily[-1]['available'],'ending cash available');expected_fee,fee_scope,fx=fee_and_price(book,mult)
  if family=='cost15':stress_examples+=fx
  totals=Counter();last_pre=last_reserve=None
  if alpha is not None:
   events=R.rows(out/'pair'/(arm+'-gross-admission-events.jsonl.gz'))
   for e in events:
    kind=e['kind'];cut=int(e['native_audit_count']);assert cut<=len(book['audit'])and D(e['alpha'])==alpha
    if kind=='route':
     if e['info']['state']=='DOWN'and D(e['inventory'])+D(e['pending_gross'])>alpha*(D(e['NAV'])-D(e['pending_drag']))+EPS:
      assert e['selected_q']==0;totals['passive_overcap_zero_new_q']+=1
     continue
    p,m=money(book,layers,cut,e['at'],slip)
    for k,v in m.items():R.near(v,e[k],('actual native prefix',family,name,arm,kind,k))
    qmap=pending_qty(book,cut);assert len(e['orders'])==len(p['pending'])
    for sid,o in e['orders'].items():
     native=p['pending'][o['order_id']];assert native['sid']==sid and qmap[o['order_id']]==o['qty'];R.near(native['gross'],o['gross'],'real remainder gross');R.near(native['fee'],o['fee'],'real remainder fee');R.near(native['fee']+native['gross']*slip/(1+slip),o['drag'],'pending fee/slip once')
    assert e['native_trade_count']==sum(x['kind']=='fill'for x in book['audit'][:cut]);state=e['info']['state'];totals[kind]+=1
    if kind=='reserve_pre':
     q=int(e['q']);px=D(e['execution_price']);mark=R.mark(e['sid'],e['at']);fee=D(e['fee']);R.near(mark,e['mark'],'reserve mark');R.near(fee,expected_fee('',cut,e['sid'],e['at'],'buy',q,px),'reference reserve fee')
     gross=m['inventory']+m['pending_gross']+D(q)*px;nav=m['NAV']-m['pending_drag']-fee-D(q)*max(Z,px-mark);R.near(gross,e['projected_gross'],'reserve principal numerator');R.near(nav,e['projected_NAV'],'reserve fee/slip denominator')
     assert e['allowed']==(state!='UNKNOWN'and(state!='DOWN'or(nav>0 and gross<=alpha*nav+EPS)));assert e['allowed']and q>0;last_reserve=dict(e=e,cut=cut,m=dict(m),gross=gross,nav=nav)
     if state=='DOWN':totals['positive_DOWN_reserve']+=1
    elif kind=='reserve_post':
     pre=last_reserve;assert pre and pre['e']['sid']==e['sid']and pre['e']['q']==e['q'];native=next(x for x in book['audit'][pre['cut']:cut]if x['kind']=='reserve'and x['order_id']==e['order_id']);R.near(native['fee_reserved_cny'],pre['e']['fee'],'actual native reserve fee');R.near(native['gross_budget_cny'],D(e['q'])*D(pre['e']['execution_price']),'native reserved principal');R.near(m['NAV'],pre['m']['NAV'],'reservation not expense');R.near(m['inventory']+m['pending_gross'],pre['gross'],'postreserve principal');R.near(m['NAV']-m['pending_drag'],pre['nav'],'reserve fee/slip once')
    elif kind=='fill_pre':
     order=e['orders'][e['sid']];px=D(e['execution_price']);mark=R.mark(e['sid'],e['at']);R.near(mark,e['mark'],'fill mark');bound=min(order['qty'],int(D(order['gross'])/px));assert bound==e['q_bound'];fullfee=D(e['fullfee_bound']);R.near(fullfee,expected_fee(order['order_id'],cut,e['sid'],e['at'],'buy',bound,px),'reference accrued fullremaining fee')
     drag=max(D(order['gross'])*slip/(1+slip),D(bound)*max(Z,px-mark));nav=m['NAV']-(m['pending_drag']-D(order['drag']))-(max(D(order['fee']),fullfee)+drag);gross=m['inventory']+m['pending_gross'];R.near(nav,e['projected_NAV'],'only current pending cost forecast replaced');R.near(gross,e['projected_gross'],'full current remainder once');assert e['allowed']==(state!='UNKNOWN'and(state!='DOWN'or(nav>0 and gross<=alpha*nav+EPS)));last_pre=dict(e=e,cut=cut,m=dict(m),cash=p['cash'],gross=gross,nav=nav)
    elif kind=='fill_post':
     pre=last_pre;assert pre and pre['e']['sid']==e['sid']and pre['e']['allowed'];actual=book['trades'][int(e['native_trade_count'])-1];assert actual['side']=='buy'and actual['security_id']==e['sid']and actual['shares']==e['actual_shares'];gross=D(actual['gross_cny']);fee=D(actual['fees_cny']);q=int(actual['shares']);mark=R.mark(e['sid'],e['at']);R.near(gross,e['actual_gross'],'real fill gross');R.near(fee,e['actual_fee'],'real fill fee');R.near(m['inventory']-pre['m']['inventory'],D(q)*mark,'real fill quantity to inventory');R.near(p['cash']-pre['cash'],-gross-fee,'real cash debit once');R.near(m['NAV'],pre['m']['NAV']-fee-(gross-D(q)*mark),'fee and slip NAV once');releases=sum((D(x['gross_released'])for x in book['audit'][pre['cut']:cut]if x['kind']=='release_buy'),Z);R.near(m['pending_gross'],pre['m']['pending_gross']-gross-releases,'actual principal removed/residual kept to ACK')
     if q==pre['e']['q_bound']:R.near(fee,pre['e']['fullfee_bound'],'actual fullremaining receipt fee');totals['actual_full_remaining_buy']+=1
     else:totals['actual_partial_buy']+=1
     if state=='DOWN':totals['positive_DOWN_actual_fill']+=1
    elif kind=='fill_cancelled':assert last_pre and not last_pre['e']['allowed'];totals['cancel_ACK_path']+=1
    else:raise AssertionError(kind)
    if state=='DOWN'and kind in ('reserve_post','fill_post'):assert m['inventory']+m['pending_gross']<=alpha*(m['NAV']-m['pending_drag'])+EPS
   atomic_snapshots+=sum(totals[k]for k in ('reserve_pre','reserve_post','fill_pre','fill_post','fill_cancelled'))
  total_days+=n;family_report[arm]=dict(daily_money_bridges=n,end_NAV=book['ending_NAV'],actual_fee_CNY=daily[-1]['fees_cny'],actual_trade_count=len(book['trades']),expected_fee_and_execution_price=dict(fee_scope),atomic_snapshot_counts=dict(totals),actual_CA_events=sum(x['kind']in ('split','split_fraction_floor_proxy')for x in book['audit']))
  if arm=='MA63_G10_TECH':
   old=W/'market_gross_admission_native_v1/small-long-v1'/name;gold=R.book(old/'pair/D_GROSS10.json.gz')
   for k in ('trades','layers','decisions','ending_NAV','ending_cash'):assert book[k]==gold[k],('cost1 control original identity',name,k)
   def norm(v):
    if isinstance(v,dict):return{k:('D_GROSS10'if k=='account'else norm(x))for k,x in v.items()}
    if isinstance(v,list):return[norm(x)for x in v]
    return v.replace('MA63_G10_TECH|','D_GROSS10|')if isinstance(v,str)else v
   assert [norm(x)for x in daily]==[x for x in R.rows(old/'pair/daily.jsonl.gz')if x['account']=='D_GROSS10'];family_report[arm]['original_same_start_finance_quantity_trades_fees_signals_identity']='EXACT_ONLY_LABEL_BUDGET_PREFIX_NORMALIZED_IN_DAILY'
 assert all(R.sha(p)==h for p,h in start['sources'].items());report[family+':'+name]=family_report
assert total_days==87
logic={}
for name in ('ACTUAL_SMALL87_COST1_CLOCK_REVIEW.json','ACTUAL_SMALL87_COST15_CLOCK_REVIEW.json','SMALL87_FINAL_PREPARATION_REVIEW.json','SMALL87_CANONICAL_FIX_SOURCE_SUPPLEMENT.json'):
 p=W/'market_gross_robustness_logic_review_v1'/name
 if p.exists():logic[str(p)]=R.sha(p)
result=dict(status='PASS_SMALL87_NATIVE_FINANCE_ATOMIC_ACTUAL_COST15_AND_CONTROL_ONLY',account_daily_bridges=total_days,actual_atomic_snapshots=atomic_snapshots,cases=report,expected_fee_method='Original unchanged FeeSchedule; scale only original stress flags of components once, set flags false, original incremental/rate_accrual multiplier1; match actual per-order paid/accrual, no private compatibility import or second money engine.',actual_stress_examples=stress_examples,limits=['This is a technical small gate, NOT full economic authorization or strategy success.','Cost1.5 is native flagged cost stress; stamp_duty and current5CNY brokerage minimum are not multiplied; not blanket fees/PnL times1.5.','No60_C15 is an actual new original native account, not historical fee or PnL rescaling.','No new native partial fixture; actual partial scope reported only.','Legacy passive overcap permitted, cap checked only on positive new conditional reserves/fills.','Original B1 full account and archived D10 full account are not rerun or merged.','MA/provider/source clocks reuse separately audited logic receipts; no indicators or accounts executed by reviewer.'],source_sha256=R.SRC,logic_receipts=logic,reader_sha256=R.sha(S),checker_sha256=R.sha(__file__),new_accounts=0,full_economic_run_authorized=False)
dest=O/'FINAL_SMALL87_FINANCE_ATOMIC_COST_CONTROL_REVIEW.json';assert not dest.exists();dest.write_text(json.dumps(result,indent=2)+'\n');print('PASS',R.sha(dest), 'days',total_days,'atomic',atomic_snapshots);print(json.dumps(report))
