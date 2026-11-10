"""C_R and D use one frozen selection/resource policy and one verified local executor."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import Counter
import ast,sys,csv,json,gzip,time,hashlib,bisect,importlib.util
import pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S=R/'s-entry-mechanism-audit-20261029';PREV=O.parent/'down-event-transfer-local-20261030/study.py';Z=D(0);ONE=D(1)
stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('unified_use_verified_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
freeze=read(O/'SELECTION_FREEZE.json')
for p,h in freeze['sha256'].items():assert sha(p)==h,p
selection={(x['cycle_id'],x['arm']):x for x in csv.DictReader((O/'FROZEN_SELECTIONS.csv').open())};mother=list(csv.DictReader((P/'FROZEN_69_CYCLES.csv').open()));AB=list(csv.DictReader((P/'full/unit-ledgers.csv').open()));ab={(x['cycle_id'],int(x['cost']),x['arm']):x for x in AB};samples=freeze['sample_ids'];assert len(selection)==138 and len(mother)==69
files=[O/'PROTOCOL.txt',Path(__file__),O/'SELECTION_FREEZE.json',O/'INPUT_IDENTITY.json',PREV,P/'FROZEN_69_CYCLES.csv',P/'full/unit-ledgers.csv',P/'full/audit.json.gz',P/'full/local-equity.parquet',S/'market-cache.parquet',O.parent/'old-warning-single-recovery-20261030/full/C-unit-ledgers.csv',O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv']
if stage=='sample':save(O/'EXECUTION_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),mother_ids=[x['cycle_id'] for x in mother],sample_ids=samples,sha256={str(p):sha(p) for p in files}))
identity=read(O/'EXECUTION_IDENTITY.json');assert identity['mother_ids']==[x['cycle_id'] for x in mother]
for p,h in identity['sha256'].items():assert sha(p)==h,p
events=mother if stage=='full' else [x for x in mother if x['cycle_id'] in samples];ids={x['old'] for x in mother}|{x['new'] for x in selection.values() if x.get('new')};_,m,_,_=H.context(ids,False);cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};days=sorted({x[1] for x in cc});cp={x['at'][:10]:x for x in read(R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json')['audit_log'] if x['kind']=='risk_checkpoint'}
with gzip.open(P/'full/audit.json.gz','rt') as f:sourceB={(x['cycle_id'],x['cost']):x for x in json.load(f) if x['arm']=='B'}
bc=pd.read_parquet(P/'full/local-equity.parquet');prior=list(csv.DictReader((O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv').open()));prior_by={e['cycle_id']:[x for x in prior if x['cycle_id']==e['cycle_id']] for e in mother};hq={(x['cycle_id'],x['day']):int(x['shares']) for x in prior}
checks=Counter();maxres=Z;tree=ast.parse(PREV.read_text());names={'near','consume','marks_at','snapshot'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert {x.name for x in nodes}==names;exec(compile(ast.Module(body=nodes,type_ignores=[]),str(PREV),'exec'),globals())
def risk(v):
 peak=v[0];dd=Z
 for x in v:peak=max(peak,x);dd=max(dd,ONE-x/peak)
 return min(v)/v[0]-ONE,dd
results=[];curves=[];audits=[];loadsec=time.monotonic()-T
for j,e0 in enumerate(events):
 key=e0['cycle_id'];old=e0['old'];warn=e0['triggered']=='True'
 for arm in ['C_R','D']:
  chosen=selection[key,arm];signal=chosen.get('signal');n=chosen.get('new')
  for cost in [1,2]:
   b=ab[key,cost,'B'];out=dict(b);out.update(arm=arm,new=n or None,new_name=chosen.get('new_name'),signal=signal or None,new_status=chosen['status'],new_buy_at=None,new_buy_qty=0,new_buy_spend=Z,new_buy_gross=Z,new_fees=Z,initial_sale_cash=None,base_gross_cap=chosen.get('base_gross_cap'),actual_gross_budget=None,spent_fraction_of_sale=Z,original_old_qty_at_buy=None,old_qty_ratio=None,post_sale_inventory_yuan_observations=Z if warn else None,post_sale_cash_yuan_observations=None,order_count=0)
   if warn:
    oldsource=sourceB[key,cost];sale=next(x for x in oldsource['fills'] if x['side']=='sell');sold=stamp(sale['at']);Snet=D(sale['net']);end=H.at(e0['original_exit'][:10],dt(15,10));out['initial_sale_cash']=Snet;out['post_sale_cash_yuan_observations']=Snet*sum(H.at(day,dt(15,10))>sold and H.at(day,dt(15,10))<=end for day in days)
   if not signal:results.append(out);continue
   carries=[x['receivable'] for x in oldsource['audit'] if x['kind']=='dividend_accrual'];assert all(x.get('paid_at') is None for x in carries);cash_at=stamp(next(x['at'] for x in oldsource['audit'] if x['kind']=='settle' and not x['settlement']['debit']));sig=H.at(signal,dt(15,10));request=stamp(chosen['original_exit_request']);buyopen=m.sessions['A'][bisect.bisect_right(m.sessions['A'],sig)];assert sold<sig<request and buyopen<stamp(e0['original_exit']) and cash_at<=sig
   initial=Snet+sum((D(x['net_local']) for x in carries),Z);near(initial,D(b['final_equity']));a=H.L.SectorAccount(initial_cash=initial,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Snet
   for x in carries:a.accrue_dividend(event_id=x['event_id'],sid=old,currency=x['currency'],net_local=D(x['net_local']),ex_at=stamp(x['ex_at']),paid_at=None,source_id=x['source_id'],entitlement_basis=x['entitlement_basis'])
   e=dict(e0);e['new']=n;st=dict(a=a,arm='C',cost=cost,q={},flow=Snet,div=Z,cursor=0,fee_state={},fees=Z,slippage=Z,I0=initial,snapshots=[],fills=[],requests=[],buy_spend=Z,new_initial_qty=0,maxres=Z);status='await_signal';count=0;buy_at=None;budget=min(D(chosen['base_gross_cap']),Snet);floor=D(str(cc[n,signal].i_floor));snapshot(st,e,sold,'sold_cash')
   for day in days[days.index(str(sold.date())):bisect.bisect_right(days,str(end.date()))]:
    op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
    if op>sold:
     for action in m.actions.get(n,[]):
      if action['effective_date']==day:H.action(a,m,n,action)
     H.pay(a,m,op)
     if n in a.exits:
      w=m.window(n,op,'sell',cost)
      if w:a.fill_exit(n,w)
     if n in a.buys:
      assert op==buyopen and count==1;w=m.window(n,op,'buy',cost);target=a.buys[n].remaining_shares
      if w is None or not w.buy_allowed:status='failed_market_window'
      elif w.raw_open<=floor/D(str(cc[n,day].factor)):status='failed_frozen_support'
      else:
       f=a.fill_buy(n,w);status='filled' if f and f.shares==target else 'partial_filled' if f else 'failed_quantity_or_budget';buy_at=f.at if f else None
      if n in a.buys:a.cancel_buy(n)
     H.pay(a,m,op);snapshot(st,e,op,'open')
    H.pay(a,m,cl)
    if a.quantity(n) and n not in a.exits:
     row=cc[n,day];assert pd.notna(row.i_target)
     if not bool(row.i_target) or not cp[day]['on']:
      q=m.quote(n,cl);assert q is not None;a.request_exit(q,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(at=cl,reason='ACT' if not cp[day]['on'] else 'I_structure'))
    if cl==sig:
     assert count==0 and not a.positions and a.available==Snet;row=cc[n,day];assert row.i_buy and row.Q and row.i_target and cp[day]['on'];q=m.quote(n,cl);assert q is not None;ok,why=a.reserve_budget(quote=q,clock=H.A.Clock(cl,buyopen,cl.date()),gross_budget_cny=budget,candidate_id=key+'|'+arm+'|first_shared_resource');count=1;status='reserved' if ok else 'failed_reservation:'+str(why)
    snapshot(st,e,cl,'close')
   final=st['snapshots'][-1];assert final['at']==end and st['buy_spend']<=Snet and count==1
   buys=[x for x in st['fills'] if x['side']=='buy'];sells=[x for x in st['fills'] if x['side']=='sell'];assert len(buys)<=1
   basis=D(b['initial_actual_cost']);prefix=[basis]+[basis+D(x['nav_mark_pnl']) for x in prior_by[key] if x['day']<=e0['date']];bx=bc[(bc['cycle_id']==key)&(bc['cost']==cost)&(bc['arm']=='B')];bx=bx[(pd.to_datetime(bx['at'])>H.at(e0['date'],dt(15,10)))&(pd.to_datetime(bx['at'])<=sold)];prefix.extend(D(x) for x in bx['nav']);near(prefix[-1],initial);mn,dd=risk(prefix+[x['nav'] for x in st['snapshots'][1:]]);pmn,pdd=risk([D(b['trigger_equity'])]+[D(x) for x in bx['nav']]+[x['nav'] for x in st['snapshots'][1:]]);closes=[x for x in st['snapshots'] if x['phase']=='close']
   out.update(new_status=status,new_buy_at=buy_at,new_buy_qty=st['new_initial_qty'],new_buy_spend=st['buy_spend'],new_buy_gross=sum((x['gross'] for x in buys),Z),new_fees=st['fees'],new_slippage=st['slippage'],actual_gross_budget=budget,spent_fraction_of_sale=st['buy_spend']/Snet,order_count=count,final_equity=final['nav'],full_cycle_net=final['nav']-basis,full_cycle_return=(final['nav']-basis)/basis,post_trigger_pnl=final['nav']-D(b['trigger_equity']),fees_after_trigger=D(b['fees_after_trigger'])+st['fees'],full_fees=D(b['full_fees'])+st['fees'],dividend=st['div'],final_shares=a.quantity(n),terminal_claim=final['claim'],min_full_cycle_return=mn,max_full_cycle_DD=dd,min_post_trigger_return=pmn,max_post_trigger_DD=pdd,holding_close_observations=int(b['holding_close_observations'])+sum(x['inventory']>0 for x in closes),cash_close_after_trigger=sum(x['inventory']==0 for x in closes),estimated_terminal_liquidation_fee=final['estimated_liquidation_fee'],estimated_terminal_slippage=final['estimated_liquidation_slippage'],terminal_inventory=final['inventory'],terminal_cash=final['cash'],post_sale_inventory_yuan_observations=sum((x['inventory'] for x in closes),Z),post_sale_cash_yuan_observations=sum((x['nav']-x['inventory']-x['claim'] for x in closes),Z))
   if arm=='C_R' and buys:
    aq=hq[key,str(buys[0]['at'].date())];out.update(original_old_qty_at_buy=aq,old_qty_ratio=D(buys[0]['shares'])/D(aq))
   for x in st['snapshots']:x['arm']=arm
   results.append(out);curves.extend(st['snapshots']);audits.append(dict(cycle_id=key,arm=arm,cost=cost,source_B_sale=sale,old_carry_claims=carries,fills=st['fills'],requests=st['requests'],audit=a.audit_log));maxres=max(maxres,st['maxres']);checks['closed_sale_slice_no_external_money']+=1
 if stage=='sample' or (j+1)%16==0:print(json.dumps(dict(stage=stage,cycles=j+1,total=len(events),seconds=time.monotonic()-T)),flush=True)
 if time.monotonic()-T+float(identity.get('sample_seconds',0) if stage=='full' else 0)>295:raise TimeoutError('300s including frozen selection budget')
export(dest/'new-unit-ledgers.csv',results);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'equity.parquet',index=False)
with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(H.encoded(audits),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/new-unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);fu=pd.read_csv(dest/'new-unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost','arm']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,mother=len(events),rows=len(results),new_slice_paths=checks['closed_sale_slice_no_external_money'],source_ABC_paths_rerun=0,max_NAV_residual=maxres,checks=dict(checks),sample_full_equal=stage=='full',load_seconds=loadsec,seconds=elapsed,no_external_money=True,single_submitted_attempt=True,shared_resource_and_execution_function=True))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'EXECUTION_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,rows=len(results),seconds=elapsed)),flush=True)
