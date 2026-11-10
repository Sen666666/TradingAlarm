"""Bounded unchanged No60 checkpoint restoration; read-only target observers.

No new strategy, no account output/checkpoint, no parameter or holding changes.
"""
from pathlib import Path
from datetime import datetime,time as dt
from types import SimpleNamespace as NS
import copy,gzip,hashlib,inspect,json,sys,textwrap,time,traceback

OUT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0,str(BASE))
import native_adapter as A
P=A.P;N=A.N;J=A.J;L=A.L;IO=A.IO;S=A.S
ROOT=BASE/'runs/2025_26'
FUNNEL=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/loss_correction/no60_behavior_v1/PVR_NO60-SEMICONDUCTOR_FUNNEL.json')
DATES={'300666.SZ':['2026-02-06','2026-02-09','2026-02-12','2026-02-25','2026-05-25','2026-06-25','2026-06-29'],
 '301611.SZ':['2026-02-10','2026-05-13','2026-06-24','2026-06-29'],
 '603061.SH':['2026-05-11','2026-05-12','2026-05-20','2026-06-24','2026-06-29']}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 (OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def stream(n):
 with gzip.open(ROOT/'pair'/n,'rt')as f:return [json.loads(x)for x in f]
def exact(a,b,name):
 assert P.digest(a)==P.digest(b),(name,P.digest(a),P.digest(b))

def main():
 began=time.monotonic();funnel=read(FUNNEL)
 targets=[x for x in funnel['all_market_receipts'] if x['signal_day'] in DATES.get(x['sid'],[])]
 assert len(targets)==16
 save('TARGET_RECEIPTS_SOURCE.json',targets)
 targetmap={(x['next_saved_OPEN'],x['sid']):x for x in targets if x['category']=='opening_rejected_raw_merged_constraints'}
 assert len(targetmap)==15
 frozen=read(ROOT/'RUN_METADATA.json')['source_freeze']
 assert all(Path(p).is_file() and sha(p)==h for p,h in frozen.items()),'original frozen source/input changed'
 sources=dict(frozen);sources[str(FUNNEL)]=sha(FUNNEL);sources[str(Path(__file__))]=sha(__file__)
 for cp in ['2025-12-31','2026-03-31']:
  for ext in ['pkl','json','provenance.json']:
   p=ROOT/f'checkpoint-{cp}.{ext}';sources[str(p)]=sha(p)
 save('SOURCE_SHA256.json',sources)
 funding_original=stream('funding.jsonl.gz');daily_original=stream('daily.jsonl.gz');balances_original=stream('balances.jsonl.gz')
 with gzip.open(ROOT/'pair/B.json.gz','rt')as f:old=json.load(f)
 N.configure_scores();print('scores loaded',time.monotonic()-began,flush=True)
 old_o=S.O
 try:S.O=OUT;shared,receipts,cpdata,states,ir,identity=S.inputs('2025_26')
 finally:S.O=old_o
 gate=read(A.W/'pvr-slot1-native-readiness-20261101/PREFLIGHT_GATE.json')
 exact(S.canonical_identity(identity),gate['input_identities']['2025_26'],'input identity')
 print('inputs loaded',time.monotonic()-began,flush=True)
 captured=[];preopens={};identities=[]
 def capture_preopen(rr,a,at):
  if (str(at.date()),'300666.SZ') in targetmap or any(day==str(at.date())for day,sid in targetmap):
   preopens[str(at)]=dict(state=P.snapshot(a).view(),same_open_protection_sells=[x for x in a.trades if str(x.get('at'))==str(at) and str(x.get('side')).lower()=='sell'])
 def wanted(i,at):
  target=targetmap.get((str(at.date()),i['sid']))
  return target if target and i['role']=='mobile' and i.get('CP1_id')==target['receipt']else None
 def capture_pre(rr,a,i,x,at):
  target=wanted(i,at)
  if not target:return
  state=P.snapshot(a);state.remove_confirmed60=True
  ci=copy.deepcopy(i);ci['_preview']=copy.deepcopy(x);ci['_preview_failure']=None
  captured.append(dict(target=target,at=at,state=state,intent=ci,
   earlier_same_open_funding=copy.deepcopy([z for z in rr.funding if z['at']==at]),
   same_open_protection_sells=copy.deepcopy([z for z in a.trades if z.get('at')==at and str(z.get('side')).lower()=='sell'])))
 def capture_post(rr,a,i,x,at,route,why):
  if not wanted(i,at):return
  z=captured[-1];assert z['intent']['CP1_id']==i['CP1_id']
  z['native_route_result']=copy.deepcopy(route);z['native_route_reason']=why
 # Read-only hooks, identical native body after removing exactly these lines.
 source=textwrap.dedent(inspect.getsource(J.Runner.opening));derived=source
 inserts=[(' a.settle_due(at);a.sync(at);funded=[];done=set()', '\n capture_preopen(self,a,at)'),
          ('  route,why=self.route(a,i,x,at)',None)]
 needle=inserts[0][0];assert derived.count(needle)==1
 derived=derived.replace(needle,needle+inserts[0][1])
 needle=inserts[1][0];assert derived.count(needle)==1
 derived=derived.replace(needle,'  capture_pre(self,a,i,x,at)\n'+needle+'\n  capture_post(self,a,i,x,at,route,why)')
 assert derived.replace(inserts[0][1],'').replace('  capture_pre(self,a,i,x,at)\n','').replace('\n  capture_post(self,a,i,x,at,route,why)','')==source
 (OUT/'opening_readonly_observers.py').write_text(derived)
 env=dict(J.__dict__,capture_preopen=capture_preopen,capture_pre=capture_pre,capture_post=capture_post)
 exec(compile(derived,str(OUT/'opening_readonly_observers.py'),'exec'),env);observed_open=env['opening']
 for cp,finish in [('2025-12-31','2026-02-26'),('2026-03-31','2026-06-30')]:
  assert time.monotonic()-began<360,'360 second restoration budget exhausted'
  r=A.Runner(shared,receipts,**S.kwargs(cpdata,states,ir));r.source_freeze=dict(frozen)
  with IO.atomic_runner_outputs(r,L,OUT,canonicalize=J.W.canon):after=r.restore(ROOT/f'checkpoint-{cp}.pkl')
  assert str(after)[:10]==cp
  end=J.M.N.iso(finish+'T09:30:00+08:00');start=J.M.N.iso(J.START+'T15:10:00+08:00')
  cutoffs={x for x in r.market.cutoffs if start<=x<=end};opens={x for x in r.market.sessions['A']if start<=x<=end}
  acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ)for d in r.actions_by_date}
  events=sorted(cutoffs|opens|{x for x in acts if start<=x<=end})
  J.M.E.risk_policy.RECOVERY=J.pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:finish]
  replay=[];n0=len(r.accounts['B'].trades)
  for at in events:
   if at<=after:continue
   assert time.monotonic()-began<360,'360 second restoration budget exhausted'
   for a in r.accounts.values():a.settle_due(at)
   r._actions(at)
   for a in r.accounts.values():r._payments(a,at)
   if at in opens:
    for a in r.accounts.values():observed_open(r,a,at)
   if at in cutoffs:r.planning(at)
   replay.append(dict(at=at,OPEN=at in opens,CLOSE=at in cutoffs))
  a=r.accounts['B'];canon=J.W.canon
  exact(canon(r.funding),[x for x in funding_original if J.M.N.iso(x['at'].replace(' ','T'))<=end],'whole funding prefix '+cp)
  exact(canon(a.trades),old['trades'][:len(a.trades)],'whole trade prefix '+cp)
  exact(canon(a.journal),old['journal'][:len(a.journal)],'whole journal prefix '+cp)
  exact(canon(r.daily),[x for x in daily_original if J.M.N.iso(x['at'].replace(' ','T'))<=end],'whole daily prefix '+cp)
  exact(canon(r.balance_audit),[x for x in balances_original if J.M.N.iso(x['at'].replace(' ','T'))<=end],'whole balance prefix '+cp)
  identities.append(dict(checkpoint=cp,end=end,passed=True,events=len(replay),opens=sum(x['OPEN']for x in replay),closes=sum(x['CLOSE']for x in replay),restored_original_fills=len(a.trades)-n0,
   full_prefix_records=dict(funding=len(r.funding),trades=len(a.trades),journal=len(a.journal),daily=len(r.daily),balances=len(r.balance_audit)),seconds=time.monotonic()-began))
  save('RESTORE_IDENTITY.json',identities);save('REPLAY_EVENTS_'+cp+'.json',replay)
  print('exact restored',cp,'to',finish,'captured',len(captured),'seconds',time.monotonic()-began,flush=True)
 assert len(captured)==15
 # Persist exact source snapshots before any private diagnostic evaluation.
 save('PREOPEN_EXACT_STATE.json',preopens)
 raw=[]
 for z in captured:
  raw.append(dict(target=z['target'],at=z['at'],state=z['state'].view(),intent=P.B.intent_view(z['intent']),native_route_result=z['native_route_result'],native_route_reason=z['native_route_reason'],earlier_same_open_funding=z['earlier_same_open_funding'],same_open_protection_sells=z['same_open_protection_sells']))
 save('PRE_CANDIDATE_EXACT_STATE.json',raw)
 # Same native route, read-only per-pool hook in a PRIVATE copy of exact state.
 pool_records=[]
 def observe_pool(a,i,x,at,pool,q,allowed):
  b=a.budget;sector=b.sector_by_sid[i['sid']];s=b.sectors[sector];minq=x['rule'].buy_minimum
  fee=float(J.LR.fees(minq,x['price'],x['schedule'],'buy',i['quote'].par_value));pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values()if o.status in ['open','cancel_pending'])
  nav=b.nav-pending_fees-fee;pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);reserve=b.resources()[2]
  cap=minq*float(x['price']);risk=minq*max(0.,float(x['price']-x['floor']));frac=.02 if pool=='probe'else(.02,.1,.2)[s.level]
  failures=allowed(minq,True);allcodes=['cash_or_original_reserve','pool_capital','probe_risk','sector_capital','sector_risk','stock_capital']
  each_max={code:J.LR.maximum_quantity(x['rule'],x['maxq'],lambda qty,c=code:c not in allowed(qty,True))for code in allcodes if code!='pool_capital' or pool=='probe'}
  pool_records.append(dict(pool=pool,maximum_legal_quantity=q,minimum_quantity=minq,minimum_failures_code_order=failures,
   first_evaluated_failing_predicate=failures[0]if failures else None,independent_max_quantity_by_constraint=each_max,
   minimum_capital=cap,minimum_fee=fee,minimum_stop_risk=risk,minimum_protection_risk_including_fees=str(J.LR.protection_risk(minq,x['price'],x['floor'],x['schedule'],i['quote'].par_value)),
   nav_after_pending_and_minimum_fee=nav,decision_nav=a.current_nav,budget_cash=b.cash,reserved_cash=reserve,available=a.available,
   original_ten_percent_cash_reserve=a.current_nav*J.D('.1'),available_minus_original_reserve=a.available-a.current_nav*J.D('.1'),budget_cash_minus_reserved=b.cash-reserve,
   spendable_admission=min(float(a.available-a.current_nav*J.D('.1')),b.cash-reserve),minimum_cash_shortfall=max(0,cap+fee-min(float(a.available-a.current_nav*J.D('.1')),b.cash-reserve)),
   pool_capital=pc,pool_risk=pr,sector_capital=sc,sector_risk=sr,sector_fraction=frac,
   sector_capital_headroom=frac*nav-sc,sector_risk_headroom=.01*nav-sr,probe_risk_headroom=.005*nav-pr if pool=='probe'else None,
   held_quantity=a.quantity(i['sid']),sector_level=s.level,sector_status=s.status))
 diagnostic=P.NEW_ROUTE
 needle='   q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)'
 assert diagnostic.count(needle)==1
 diagnostic=diagnostic.replace(needle,needle+'\n   observe_pool(a,i,x,at,pool,q,allowed)')
 assert diagnostic.replace('\n   observe_pool(a,i,x,at,pool,q,allowed)','')==P.NEW_ROUTE
 (OUT/'private_route_readonly_observer.py').write_text(diagnostic)
 env=dict(J.__dict__,observe_pool=observe_pool);exec(compile(diagnostic,str(OUT/'private_route_readonly_observer.py'),'exec'),env)
 output=[]
 for z in captured:
  pool_records.clear();b=copy.deepcopy(z['state']);b.remove_confirmed60=True;b.context='read_only_original_reject';b.phase='evaluation';a=P.AccountView(b);i=copy.deepcopy(z['intent']);x=i['_preview']
  route,why=env['route'](NS(sector_by_sid=b.sector_by_sid),a,i,x,z['at'])
  assert route is None and why==z['native_route_reason']
  assert all(v['maximum_legal_quantity']==0 for v in pool_records)
  holdings={}
  for lot in b.lots:
   h=holdings.setdefault(lot.stock,dict(sid=lot.stock,sector=lot.sector,quantity=0,capital=0,risk=0,lots=[]));h['quantity']+=lot.qty;h['capital']+=lot.qty*b.prices[lot.stock];h['risk']+=lot.qty*max(0,b.prices[lot.stock]-lot.floor);h['lots'].append(lot)
  live_orders=[o for o in b.orders.values()if o.qty>0 and o.status in ['open','cancel_pending']]
  view=P.B.intent_view(i)
  output.append(dict(sid=i['sid'],name=z['target']['name'],signal_day=z['target']['signal_day'],receipt=i['CP1_id'],opening=z['at'],native_result=why,
   actual_earliest_route_branch='all_available_routes_have_zero_legal_quantity; Contract.request never called',request_reached=False,
   original_rank=i['rank'],frozen_budget=i['budget'],dated_rule=x['rule'],preview_maxq=x['maxq'],preview_minq=x['minq'],open_raw=x['known_open'],open_execution_price=x['price'],open_floor=x['floor'],
   candidate_preview=view['preview'],pools=copy.deepcopy(pool_records),migration_observation=b.migrations,
   prior_same_open_funding=z['earlier_same_open_funding'],live_reserved_orders=live_orders,same_open_protection_sells=z['same_open_protection_sells'],
   holdings=sorted(holdings.values(),key=lambda h:-h['capital']),
   smaller_same_signal_upper_bound_cannot_make_minimum_feasible=True))
 save('ALL15_OPEN_FUNDING_RESPONSIBILITY.json',output)
 save('COMPLETION.json',dict(passed=True,captured_original_open_rejects=15,close_sizing_receipts=1,all16_receipts_saved=True,
  original_policy_only=True,new_strategy_paths=0,new_account_outputs=0,source_unchanged=all(sha(p)==h for p,h in sources.items()),
  seconds=time.monotonic()-began,restoration_wallclock_budget_seconds=360))
 assert all(sha(p)==h for p,h in sources.items())
 print('DONE',time.monotonic()-began,flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:
  save('FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),new_strategy_paths=0));raise
