"""Only C is new; validated A/B and no-action C cases are immutable aliases."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import Counter
import ast,sys,json,csv,gzip,time,hashlib,bisect,importlib.util
import pandas as pd

T=time.monotonic();O=Path(__file__).resolve().parent;P=O.parent/'old-side-exit-all69-20261030';F=O.parent/'old-warning-recovery-timing-20261030';PREV=O.parent/'down-event-transfer-local-20261030/study.py';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S=R/'s-entry-mechanism-audit-20261029';Z=D(0);ONE=D(1)
stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
sp=importlib.util.spec_from_file_location('single_recovery_same_helpers',S/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
for p,h in read(F/'TIMING_FREEZE.json')['sha256'].items():assert sha(p)==h,p
mo=list(csv.DictReader((P/'FROZEN_69_CYCLES.csv').open()));rr=list(csv.DictReader((F/'recovery-with-old-loss-timing.csv').open()));rec={x['cycle_id']:x for x in rr};AB=list(csv.DictReader((P/'full/unit-ledgers.csv').open()));ab={(x['cycle_id'],int(x['cost']),x['arm']):x for x in AB};assert len(mo)==69 and sum(bool(x['policy_IQ']) for x in rr)==35
sourceB={}
with gzip.open(P/'full/audit.json.gz','rt') as f:
 for x in json.load(f):
  if x['arm']=='B':sourceB[x['cycle_id'],x['cost']]=x
firstharm=min((x for x in rr if x['old_exit_group']=='harm20' and x['policy_IQ']),key=lambda x:(x['sold_at'],x['cycle_id']))['cycle_id'];firstbenefit=min((x for x in rr if x['old_exit_group']=='benefit37' and x['policy_IQ']),key=lambda x:(x['sold_at'],x['cycle_id']))['cycle_id'];targets=['605118.SH|2024-01-02','301486.SZ|2024-03-27','688143.SH|2026-06-03'];samples=list(dict.fromkeys([firstharm,firstbenefit]+targets))
files=[O/'PROTOCOL.txt',Path(__file__),PREV,P/'FROZEN_69_CYCLES.csv',P/'full/unit-ledgers.csv',P/'full/audit.json.gz',P/'full/local-equity.parquet',F/'TIMING_FREEZE.json',F/'recovery-with-old-loss-timing.csv',S/'market-cache.parquet',O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv']
if stage=='sample':save(O/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),mother_cycle_ids=[e['cycle_id'] for e in mo],samples=samples,sha256={str(p):sha(p) for p in files},new_policy_signal_cases=35,aliases=34))
identity=read(O/'INPUT_IDENTITY.json');assert identity['mother_cycle_ids']==[e['cycle_id'] for e in mo]
for p,h in identity['sha256'].items():assert sha(p)==h,p
events=mo if stage=='full' else [x for x in mo if x['cycle_id'] in samples];ids={x['old'] for x in events};_,m,_,_=H.context(ids,False);cache=pd.read_parquet(S/'market-cache.parquet');cc={(x.symbol,str(x.date.date())):x for x in cache.itertuples(index=False)};days=sorted(set(k[1] for k in cc))
original=read(R/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json');cp={x['at'][:10]:x for x in original['audit_log'] if x['kind']=='risk_checkpoint'};bc=pd.read_parquet(P/'full/local-equity.parquet');prior=list(csv.DictReader((O.parent/'act-loss-facts-20261030/actual-holding-close-paths.csv').open()))
prior_by={e['cycle_id']:[x for x in prior if x['cycle_id']==e['cycle_id']] for e in mo};hq={(x['cycle_id'],x['day']):int(x['shares']) for x in prior};checks=Counter();maxres=Z
names={'near','consume','marks_at','snapshot'};tree=ast.parse(PREV.read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert {n.name for n in nodes}==names;exec(compile(ast.Module(body=nodes,type_ignores=[]),str(PREV),'exec'),globals())
def risk(v):
 peak=v[0];dd=Z
 for x in v:peak=max(peak,x);dd=max(dd,ONE-x/peak)
 return min(v)/v[0]-ONE,dd
results=[];curves=[];audits=[];loadsec=time.monotonic()-T
for j,e0 in enumerate(events):
 key=e0['cycle_id'];s=e0['old'];r=rec.get(key);signal=r['policy_IQ'] if r else None
 for cost in [1,2]:
  b=ab[key,cost,'B'];out=dict(b);out['arm']='C';out.update(recovery_signal=signal or None,recovery_status='alias_no_warning' if e0['triggered']=='False' else 'alias_no_recovery',recovery_order_count=0,recovery_buy_at=None,recovery_buy_qty=0,recovery_buy_gross=Z,recovery_buy_fee=Z,recovery_sell_fee=Z,recovery_extra_fees=Z,closed_sale_cash=None,buy_spend=Z,original_A_qty_at_buy=None,qty_ratio_to_original_A=None,signal_price_change_since_sale=None,execution_price_change_since_sale=None,qty_reference_raw_cash=None,qty_loss_slippage=None,qty_loss_buy_fee=None,qty_loss_lot=None,qty_loss_order_or_capacity=None,source_AB_reused=True)
  if not signal:results.append(out);continue
  old=sourceB[key,cost];sales=[x for x in old['fills'] if x['side']=='sell'];assert len(sales)==1;sale=sales[0];sold=stamp(sale['at']);Snet=D(sale['net']);starts=[x['receivable'] for x in old['audit'] if x['kind']=='dividend_accrual'];assert all(x.get('paid_at') is None for x in starts)
  settlements=[x for x in old['audit'] if x['kind']=='settle' and not x['settlement']['debit']];assert len(settlements)==1 and D(settlements[0]['settlement']['cny_amount'])==Snet;cash_at=stamp(settlements[0]['at']);sig=H.at(signal,dt(15,10));end=H.at(e0['original_exit'][:10],dt(15,10));request=stamp(r['original_exit_request']);opbuy=m.sessions['A'][bisect.bisect_right(m.sessions['A'],sig)];assert sold<sig<request and opbuy<stamp(e0['original_exit']) and cash_at<=sig
  initial=Snet+sum((D(x['net_local']) for x in starts),Z);near(initial,D(b['final_equity']));a=H.L.SectorAccount(initial_cash=initial,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);a.available=Snet
  for x in starts:a.accrue_dividend(event_id=x['event_id'],sid=s,currency=x['currency'],net_local=D(x['net_local']),ex_at=stamp(x['ex_at']),paid_at=None,source_id=x['source_id'],entitlement_basis=x['entitlement_basis'])
  e=dict(e0);e['new']=s;st=dict(a=a,arm='C',cost=cost,q={},flow=Snet,div=Z,cursor=0,fee_state={},fees=Z,slippage=Z,I0=initial,snapshots=[],fills=[],requests=[],buy_spend=Z,new_initial_qty=0,maxres=Z);status='await_signal';target=0;buy_at=None;buygross=buyfee=sellfee=Z;order_count=0;frozenfloor=D(str(cc[s,signal].i_floor));snapshot(st,e,sold,'sold_cash')
  for day in days[days.index(str(sold.date())):bisect.bisect_right(days,str(end.date()))]:
   op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
   if op>sold:
    for act in m.actions.get(s,[]):
     if act['effective_date']==day:H.action(a,m,s,act)
    H.pay(a,m,op)
    if s in a.exits:
     w=m.window(s,op,'sell',cost)
     if w:a.fill_exit(s,w)
    if s in a.buys:
     assert op==opbuy and order_count==1;w=m.window(s,op,'buy',cost);target=a.buys[s].remaining_shares
     if w is None or not w.buy_allowed:status='failed_market_window'
     elif w.raw_open<=frozenfloor/D(str(cc[s,day].factor)):status='failed_frozen_support'
     else:
      f=a.fill_buy(s,w);status='filled' if f and f.shares==target else 'partial_filled' if f else 'failed_budget_quantity';buy_at=f.at if f else None
     if s in a.buys:a.cancel_buy(s)
    H.pay(a,m,op);snapshot(st,e,op,'open')
   H.pay(a,m,cl)
   if a.quantity(s) and s not in a.exits:
    row=cc[s,day];assert pd.notna(row.i_target)
    if not bool(row.i_target) or not cp[day]['on']:
     q=m.quote(s,cl);assert q is not None;a.request_exit(q,H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date()));st['requests'].append(dict(at=cl,reason='ACT' if not cp[day]['on'] else 'I_structure'))
   if cl==sig:
    assert order_count==0 and not a.positions and a.available==Snet;row=cc[s,day];assert row.i_buy and row.Q and row.i_target and cp[day]['on'];quote=m.quote(s,cl);assert quote is not None
    ok,why=a.reserve_budget(quote=quote,clock=H.A.Clock(cl,opbuy,cl.date()),gross_budget_cny=Snet,candidate_id=key+'|first_frozen_IQ_recovery');order_count=1;status='reserved' if ok else 'failed_reservation:'+str(why)
   snapshot(st,e,cl,'close')
  final=st['snapshots'][-1];assert final['at']==end and st['buy_spend']<=Snet and order_count==1
  fills=[x for x in st['fills'] if x['side']=='buy'];sells=[x for x in st['fills'] if x['side']=='sell'];assert len(fills)<=1
  basis=D(b['initial_actual_cost']);prefix=[basis]+[basis+D(x['nav_mark_pnl']) for x in prior_by[key] if x['day']<=e0['date']];bx=bc[(bc['cycle_id']==key)&(bc['cost']==cost)&(bc['arm']=='B')];bx=bx[(pd.to_datetime(bx['at'])>H.at(e0['date'],dt(15,10)))&(pd.to_datetime(bx['at'])<=sold)];prefix.extend(D(x) for x in bx['nav']);near(prefix[-1],initial);v=prefix+[x['nav'] for x in st['snapshots'][1:]];mn,dd=risk(v);sellsfee=sum((x['fees'] for x in sells),Z);buyfee=sum((x['fees'] for x in fills),Z);buygross=sum((x['gross'] for x in fills),Z);postvalues=[D(b['trigger_equity'])]+[D(x) for x in bx['nav']]+[x['nav'] for x in st['snapshots'][1:]];postmin,postdd=risk(postvalues);ccrows=[x for x in st['snapshots'] if x['phase']=='close'];pheld=int(b['holding_close_observations']);fullnet=final['nav']-basis
  out.update(final_equity=final['nav'],full_cycle_net=fullnet,full_cycle_return=fullnet/basis,post_trigger_pnl=final['nav']-D(b['trigger_equity']),fees_after_trigger=D(b['fees_after_trigger'])+st['fees'],full_fees=D(b['full_fees'])+st['fees'],dividend=st['div'],final_shares=a.quantity(s),terminal_claim=final['claim'],min_full_cycle_return=mn,max_full_cycle_DD=dd,min_post_trigger_return=postmin,max_post_trigger_DD=postdd,holding_close_observations=pheld+sum(x['inventory']>0 for x in ccrows),cash_close_after_trigger=sum(x['inventory']==0 for x in ccrows),status='single_recovery',recovery_status=status,recovery_order_count=order_count,recovery_buy_at=buy_at,recovery_buy_qty=st['new_initial_qty'],recovery_buy_gross=buygross,recovery_buy_fee=buyfee,recovery_sell_fee=sellsfee,recovery_extra_fees=st['fees'],closed_sale_cash=Snet,buy_spend=st['buy_spend'],last_recovery_sell=sells[-1]['at'] if sells else None,estimated_terminal_liquidation_fee=final['estimated_liquidation_fee'],estimated_terminal_slippage=final['estimated_liquidation_slippage'])
  anchor=D(sale['raw_open'])*D(str(cc[s,str(sold.date())].factor));out['signal_price_change_since_sale']=D(str(cc[s,signal].close))/anchor-ONE
  if fills:
   f=fills[0];day=str(f['at'].date());aq=hq[key,day];rawref=Snet/f['raw_open'];after_slip=Snet/f['price'];afterfee=(Snet-f['fees'])/f['price'];lot=m.quantity(s,f['at']).buy_floor(int(afterfee));out.update(original_A_qty_at_buy=aq,qty_ratio_to_original_A=D(f['shares'])/D(aq),execution_price_change_since_sale=f['raw_open']*D(str(cc[s,day].factor))/anchor-ONE,qty_reference_raw_cash=rawref,qty_loss_slippage=rawref-after_slip,qty_loss_buy_fee=after_slip-afterfee,qty_loss_lot=afterfee-D(lot),qty_loss_order_or_capacity=D(lot)-D(f['shares']));near(out['qty_loss_slippage']+out['qty_loss_buy_fee']+out['qty_loss_lot']+out['qty_loss_order_or_capacity'],rawref-D(f['shares']),8);checks['quantity_accounting']+=1
  results.append(out);curves.extend(st['snapshots']);audits.append(dict(cycle_id=key,cost=cost,original_sold_cash_source=sale,old_claims=starts,new_fills=st['fills'],audit=a.audit_log));maxres=max(maxres,st['maxres']);checks['closed_cash_recovery']+=1
 if stage=='sample' or (j+1)%16==0:print(json.dumps(dict(stage=stage,cycles=j+1,total=len(events),seconds=time.monotonic()-T)),flush=True)
 if time.monotonic()-T+float(identity.get('sample_seconds',0) if stage=='full' else 0)>300:raise TimeoutError('300s cumulative C-only budget')
export(dest/'C-unit-ledgers.csv',results);export(dest/'all-ABC-ledgers.csv',[r for r in AB if r['cycle_id'] in {e['cycle_id'] for e in events}]+results);pd.DataFrame(H.encoded(curves)).to_parquet(dest/'C-equity.parquet',index=False)
with gzip.open(dest/'C-audit.json.gz','wt') as f:json.dump(H.encoded(audits),f,ensure_ascii=False,allow_nan=False)
if stage=='full':
 sm=pd.read_csv(O/'sample/C-unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost']);fu=pd.read_csv(dest/'C-unit-ledgers.csv',dtype=str).fillna('').set_index(['cycle_id','cost']);pd.testing.assert_frame_equal(sm,fu.loc[sm.index],check_exact=True)
for p,h in identity['sha256'].items():assert sha(p)==h,p
elapsed=time.monotonic()-T;save(dest/'VERIFICATION.json',dict(passed=True,stage=stage,mother_cycles=len(events),C_rows=len(results),new_recovery_paths=checks['closed_cash_recovery'],AB_replays=0,max_NAV_residual=maxres,checks=dict(checks),sample_full_equal=stage=='full',load_seconds=loadsec,seconds=elapsed,source_AB_immutable=True,no_external_money=True,no_second_signal=True))
if stage=='sample':identity['sample_seconds']=elapsed;save(O/'INPUT_IDENTITY.json',identity)
print(json.dumps(dict(stage=stage,complete=True,C_rows=len(results),seconds=elapsed)),flush=True)
