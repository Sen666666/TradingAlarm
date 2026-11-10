"""Pure synthetic Budget/route fixtures. No native Account/Market/Runner init."""
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import asdict,is_dataclass,replace
from decimal import Decimal as D
from datetime import datetime
import sys,json,copy,hashlib,time,traceback
R=Path(__file__).resolve().parent;F=R.parent/'funding';S=R.parent/'saved_batches';begun=time.monotonic();sys.dont_write_bytecode=True;sys.path.insert(0,str(F))
import confirmed_adapter as C
assert C.sha(F/'confirmed_adapter.py')=='66ac96d10722ae49c0910c08a11e22cdd567159cf1e2b63c6b6142fbf5f025bd'
J,LR=C.J,C.LR;SID='688469.SH';SEC='FIXTURE_INDUSTRY';DAY='2026-06-29';AT=datetime.fromisoformat('2026-06-30T09:30:00+08:00');DEC=datetime.fromisoformat(DAY+'T15:10:00+08:00');BAR=J.ordinal(DAY);EP=(0,9);results=[];synthetic_budgets=0
raw=json.loads((S/'PREVIEWS_2026-06-30.json').read_text());template=next(x for x in raw if x['sid']==SID and x['role']=='core');lookup=json.loads((S/'CORE_CP_LOOKUP_2026-06-30.json').read_text());original_cp=lookup[SID]['trace'];qr=LR.L.QuantityRule(**template['preview']['rule']);fs0=template['preview']['schedule'];fs=LR.L.FeeSchedule(fs0['schedule_id'],tuple(LR.L.FeeComponent(**x)for x in fs0['components']))
def canon(v):
 if is_dataclass(v):return canon(asdict(v))
 if isinstance(v,dict):return {str(k):canon(x)for k,x in sorted(v.items(),key=lambda z:str(z[0]))}
 if isinstance(v,(list,tuple)):return [canon(x)for x in v]
 if isinstance(v,set):return sorted((canon(x)for x in v),key=str)
 if isinstance(v,D):return str(v)
 return v
def state(b):return canon(b.__dict__)
def snap(a):return state(a.budget),copy.deepcopy(a.core_epoch),a.available
class View:
 def __init__(self,b):self.budget=b;self.label='SYNTHETIC';self.current_nav=D(1000000);self.available=D(str(b.cash));self.core_epoch={};self.buys={};self.exits={};self._budget_sync_pending=False;self.pool_syncs=0
 def quantity(self,sid):return sum(x.qty for x in self.budget.lots if x.stock==sid)
 def pools_from_model(self):self.pool_syncs+=1

def rebalance(b):b.cash=1e6-sum(x.qty*b.prices[x.stock]for x in b.lots)
def lot(b,name,sector,capital,risk=0,pool='confirmed',attempt='other-attempt'):
 p=100.;qty=capital/p;b.prices[name]=p;b.lots.append(J.V.Lot(name,name,sector,'OLD_EPISODE',pool,qty,p,p-risk/qty if qty else p,'core',attempt));rebalance(b)
def freeze(i,b,cp):
 s=b.sectors[SEC];f=dict(policy=C.POLICY,account='SYNTHETIC',sid=SID,signal_day=DAY,epoch=list(i['epoch']),sector=SEC,industry_episode=s.episode,industry_attempt=s.attempt,industry_level=s.level,source_segment=0,i_target=True,i_buy=True,e0_target=True,G1_ready=True,G1_grade=4.,ACT_on=True,canonical_receipt=copy.deepcopy(cp));f['receipt_sha256']=C.digest(cp)if cp is not None else None;f['proof_sha256']=C.digest(f);i['_confirmed_core_cp']=f

def rehash(i):
 f=i['_confirmed_core_cp'];f['receipt_sha256']=C.digest(f['canonical_receipt'])if f['canonical_receipt']is not None else None;f.pop('proof_sha256',None);f['proof_sha256']=C.digest(f)
def fixture(mode='probe_risk',level=1,rule=None):
 global synthetic_budgets
 b=C.ConfirmedCoreBudget(True);synthetic_budgets+=1;b.start(SEC,'FIXTURE_E0',BAR-20);s=b.sectors[SEC];s.active=True;s.level=level;s.started=BAR-10;s.attempt='FIXTURE_ATTEMPT';s.status='confirmed'if level==1 else'expanded'if level==2 else'probe'
 if mode=='probe_risk':lot(b,'PROBE_OTHER','OTHER',4900,4900,'probe')
 elif mode=='sector_capital':lot(b,'SECTOR_OLD',SEC,19000,0)
 elif mode=='small_probe':lot(b,'SECTOR_OLD',SEC,17000,0)
 elif mode=='none':pass
 else:raise ValueError(mode)
 a=View(b);run=C.Runner.__new__(C.Runner);run.core_confirmed_mode='ON';run.sector_by_sid={SID:SEC};run.core_proof_log=[];run.core_confirmed_log=[]
 rule=rule or qr;quote=NS(raw_price=D('10.15'),quantity=rule,fees=fs,par_value=D(1));i=dict(sid=SID,clock=NS(decision_at=DEC,earliest_execution_at=AT),quote=quote,kind='core',role='core',floor=D('6.87'),epoch=EP,weight=1.,reason='I_early_core',score=80,rank=0,CP1_id=None,CP1_trace=None)
 LR.resize_core(i,D(1000000),D(1));assert not i['size_reject'];x,why=LR.preview(i,D('10.14'),D(1),rule,fs);assert why is None;x['known_open']=D('10.14');freeze(i,b,original_cp);return run,a,i,x

def call(r,a,i,x):return C.Runner.route(r,a,i,x,AT)
def savecase(name,**extra):results.append(dict(name=name,passed=True,**extra));assert time.monotonic()-begun<60

def denied(name,change,expect=None):
 r,a,i,x=fixture();change(r,a,i,x);before=snap(a);res,why=call(r,a,i,x);assert res is None,(name,res,why);assert snap(a)==before,(name,'failed route mutated synthetic state')
 if expect:
  log=r.core_confirmed_log;assert log and log[-1]['fallback_reason']==expect,(name,log)
 savecase(name,original_reason=why,fallback_reason=r.core_confirmed_log[-1]['fallback_reason']if r.core_confirmed_log else None)

try:
 # Both allowed failure origins, levels, and actual dated grids.
 mainrule=LR.L.QuantityRule(**next(x['preview']['rule']for x in raw if x.get('preview')and x['preview']['rule']['buy_step']==100))
 for mode in ['probe_risk','sector_capital']:
  for level in [1,2]:
   for label,rule in [('STAR200step1',qr),('MAIN100step100',mainrule)]:
    r,a,i,x=fixture(mode,level,rule);ep=copy.deepcopy(a.core_epoch);before_resources=a.budget.resources();res,why=call(r,a,i,x);assert res and res[1]=='confirmed'and why is None;qty=res[0];assert qty>=rule.buy_minimum and rule.buy_floor(qty)==qty and qty<=x['maxq'];o=a.budget.orders[i['budget_order']];assert o.role=='core'and o.pool=='confirmed'and o.floor==float(x['floor']);assert o.__class__ is C.A.P.MOD.Order;assert i['kind']=='core'and i['floor']==D('6.87')and i['CP1_id']==original_cp['receipt_id'];assert original_cp['receipt_id']in a.budget.consumed and a.core_epoch==ep;assert LR.protection_risk(qty,x['price'],x['floor'],x['schedule'],i['quote'].par_value)<=i['risk_budget'];assert C.TYPED_REQUEST.__globals__['Order']is C.A.P.MOD.Order
    savecase('confirmed_success_'+mode+'_L'+str(level)+'_'+label,qty=qty,preview_maxq=x['maxq'],CORE_epoch_unconsumed_at_reserve=True)
 # Original probe success must remain the original smaller quantity, no CP consume.
 r,a,i,x=fixture('small_probe');ar=copy.deepcopy(a);ar.budget.__class__=C.A.NoConfirmed60Budget;ii=copy.deepcopy(i);expected=C.A.P.ROUTES[True](r,ar,ii,x,AT);actual=call(r,a,i,x);assert actual==expected and actual[0][1]=='probe'and 0<actual[0][0]<x['maxq'];assert state(a.budget)==state(ar.budget)and not r.core_confirmed_log and original_cp['receipt_id']not in a.budget.consumed
 savecase('successful_small_probe_never_expanded_or_consumes_CP',qty=actual[0][0],confirmed_possible_preview_cap=x['maxq'])
 denied('no_CP',lambda r,a,i,x:freeze(i,a.budget,None),'no_frozen_signal_CP')
 denied('corrupt_proof_hash',lambda r,a,i,x:i['_confirmed_core_cp'].__setitem__('proof_sha256','bad'),'frozen_CP_hash_mismatch')
 def proofchange(field,value):
  def change(r,a,i,x):i['_confirmed_core_cp'][field]=value;rehash(i)
  return change
 for name,field,value,reason in [('wrong_signal_day','signal_day','2026-06-28','frozen_CORE_clock_or_epoch_mismatch'),('wrong_CORE_source','source_segment',3,'CORE_source_epoch_mismatch'),('original_I_off','i_target',False,'original_CORE_qualification_not_frozen'),('original_I_buy_off','i_buy',False,'original_CORE_qualification_not_frozen'),('not_G1_warm','G1_grade',1,'original_CORE_qualification_not_frozen'),('ACT_off','ACT_on',False,'original_CORE_qualification_not_frozen'),('wrong_frozen_sector','sector','OTHER','frozen_industry_episode_or_attempt_mismatch')]:denied(name,proofchange(field,value),reason)
 def cpchange(field,value):
  def change(r,a,i,x):i['_confirmed_core_cp']['canonical_receipt'][field]=value;rehash(i)
  return change
 for name,field,value,reason in [('wrong_CP_stock','canonical_series','000001.SZ','canonical_CP_identity_or_unknown'),('stale_CP_day','confirmed_day','2026-06-28','canonical_CP_identity_or_unknown'),('unknown_CP','trace_unknown',['missing'],'canonical_CP_identity_or_unknown'),('cross_source_CP','source_segment','2','CP_source_or_scale_mismatch'),('wrong_CP_scale','scale_id','FAKE','CP_source_or_scale_mismatch'),('future_CP_formation','formation_end_inclusive','2026-07-01','CP_formation_after_signal')]:denied(name,cpchange(field,value),reason)
 denied('cross_industry_attempt_after_freeze',lambda r,a,i,x:setattr(a.budget.sectors[SEC],'attempt','NEW_ATTEMPT'),'frozen_industry_episode_or_attempt_mismatch')
 denied('cross_industry_episode_after_freeze',lambda r,a,i,x:setattr(a.budget.sectors[SEC],'episode','NEW_EPISODE'),'frozen_industry_episode_or_attempt_mismatch')
 denied('already_consumed_CP',lambda r,a,i,x:a.budget.consumed.add(original_cp['receipt_id']),'CP_invalid_or_consumed')
 denied('CORE_epoch_locked_across_pools',lambda r,a,i,x:a.core_epoch.__setitem__(SID,EP),'core_epoch_locked')
 denied('industry_level0',lambda r,a,i,x:setattr(a.budget.sectors[SEC],'level',0),'industry_not_confirmed')
 denied('industry_expand_disabled',lambda r,a,i,x:setattr(a.budget,'expand',False),'industry_not_confirmed')
 for status in ['open','cancel_pending']:
  def blocked(r,a,i,x,status=status):
   o=C.A.P.MOD.Order('BLOCK','OTHER_STOCK',SEC,'FIXTURE_E0','probe',100,10,9,0,status,attempt='FIXTURE_ATTEMPT');a.budget.orders['BLOCK']=o
  denied('same_attempt_'+status+'_blocks_migration',blocked,'same_attempt_probe_order_blocks_migration')
 # Retained numeric vetoes: the original combined failure set excludes fallback.
 def cashlow(r,a,i,x):lot(a.budget,'CASH_OCCUPIED','OTHER2',895000,0);a.available=D(str(a.budget.cash))
 denied('cash10_reserve_not_released',cashlow)
 def poolfull(r,a,i,x):a.budget.lots=[];a.budget.prices={};lot(a.budget,'FULL_PROBE','OTHER',99000,0,'probe');a.available=D(str(a.budget.cash))
 denied('probe_pool10_veto_is_not_rescued',poolfull)
 def sectorrisk(r,a,i,x):lot(a.budget,'SECTOR_RISK',SEC,19000,9900);a.available=D(str(a.budget.cash))
 denied('all_pool_sector1_risk_not_relaxed',sectorrisk)
 def stockfull(r,a,i,x):a.budget.prices[SID]=10.14;a.budget.lots.append(J.V.Lot('HELD',SID,SEC,'OLD','confirmed',10000,10.14,10.14));rebalance(a.budget);a.available=D(str(a.budget.cash))
 denied('stock10_or_flat_not_relaxed',stockfull)
 # Direct typed request invalidity: failed calls leave complete synthetic budget byte-value state intact.
 for case in ['epoch','token_used','token_wrong_attempt','token_wrong_episode','token_wrong_stock','token_future','not_typed_core','cash','sector_capital','sector_risk']:
  r,a,i,x=fixture();b=a.budget;s=b.sectors[SEC];token=J.V.Evidence(original_cp['receipt_id'],SEC,'stock_cp1','21',BAR-5,BAR,BAR,s.episode,SID,s.attempt);kwargs=dict(probe_request=False,role='core',typed_core_confirmed=True,core_epoch_locked=False)
  if case=='epoch':kwargs['core_epoch_locked']=True
  if case=='token_used':b.consumed.add(token.event_id)
  if case=='token_wrong_attempt':token=replace(token,attempt='OTHER')
  if case=='token_wrong_episode':token=replace(token,epoch='OTHER')
  if case=='token_wrong_stock':token=replace(token,stock='OTHER')
  if case=='token_future':token=replace(token,confirmed_time=BAR+1)
  if case=='not_typed_core':kwargs['role']='mobile'
  if case=='cash':b.cash=10.
  if case=='sector_capital':lot(b,'SECTOR_TOO_BIG',SEC,100000,0)
  if case=='sector_risk':lot(b,'SECTOR_TOO_RISKY',SEC,19000,9900)
  before=state(b);q=qr.buy_minimum;f=LR.fees(q,x['price'],x['schedule'],'buy',D(1));res=b.request('DIRECT',SID,SEC,q,float(x['price']),float(x['floor']),token,BAR,float(f/D(q)),order_expiry_bar=J.ordinal(AT.date()),**kwargs);assert res!='reserved'and state(b)==before,(case,res)
  savecase('typed_request_failed_atomic_'+case,result=res)
 # Failed CORE token check cannot steal the original Mobile fallback receipt.
 r,a,i,x=fixture();i['_confirmed_core_cp']['proof_sha256']='bad';before=state(a.budget);res,_=call(r,a,i,x);assert res is None and state(a.budget)==before;mi=copy.deepcopy(i);mi.update(role='mobile',kind='add',reason='fresh_CP1_mobile',CP1_id=original_cp['receipt_id'],CP1_trace=copy.deepcopy(original_cp),floor=D(str(original_cp['original_candidate'])),budget=D(20000),cap=1900);mx,why=LR.preview(mi,D('10.14'),D(1),qr,fs);assert why is None;mx['known_open']=D('10.14');res,why=call(r,a,mi,mx);assert res and why is None and mi['CP1_id']in a.budget.consumed
 savecase('failed_CORE_preserves_original_Mobile_fallback',pool=res[1],qty=res[0])
 # Newly committed CORE token cannot finance a second Mobile reservation.
 r,a,i,x=fixture();res,why=call(r,a,i,x);assert res and original_cp['receipt_id']in a.budget.consumed;mi=copy.deepcopy(i);mi.update(role='mobile',kind='add',CP1_trace=copy.deepcopy(original_cp));before=state(a.budget);second,reason=call(r,a,mi,x);assert second is None and reason=='no_fresh_stock_CP1'and state(a.budget)==before
 savecase('reserved_CORE_blocks_cross_role_same_CP_without_reuse')
 # Original Mobile route and request behavior unchanged for representative states.
 for mode in ['probe_risk','sector_capital','small_probe','none']:
  r,a,i,x=fixture(mode);i.update(role='mobile',kind='add',CP1_id=original_cp['receipt_id'],CP1_trace=copy.deepcopy(original_cp));ar=copy.deepcopy(a);ar.budget.__class__=C.A.NoConfirmed60Budget;ii=copy.deepcopy(i);one=C.A.P.ROUTES[True](r,ar,ii,x,AT);two=call(r,a,i,x);assert one==two and state(a.budget)==state(ar.budget)
  savecase('original_Mobile_route_exact_'+mode)
 # Confirm no removed 60%/3% gates are resurrected: valid old occupancy spread over sectors.
 r,a,i,x=fixture();
 for k in range(4):lot(a.budget,'OLD_CONF_'+str(k),'IND_'+str(k),175000,9000)
 a.available=D(str(a.budget.cash));assert a.budget.resources('confirmed')[0]>.60*a.budget.nav and a.budget.resources()[1]>.03*a.budget.nav;res,why=call(r,a,i,x);assert res and res[1]=='confirmed'
 savecase('No60_no_confirmed60_or_account3_gate',prior_confirmed_capital=700000,prior_global_nominal_risk=40900)
 # Original inherited native sources, not a fake implementation, own epoch-on-fill/T+1/FIFO.
 assert 'core_epoch[sid]=meta[\'epoch\']'in Path(J.BP.__file__).read_text();assert C.Runner.opening is J.Runner.opening
 result={'passed':True,'scope':'Independent synthetic budget/request and bare Runner.__new__ route fixtures only; no native __init__, Account, Market, financial fills, price marks or PnL.','fixture_count':len(results),'cases':results,'synthetic_budget_objects':synthetic_budgets,'native_Account_or_Runner_init_or_Market_constructions':0,'native_fill_paths':0,'prefix_or_portfolio_run_admitted':False,'not_covered_by_pure_fixtures':['Actual fill epoch/T+1/FIFO/CA remains original inherited engine; native prefix and saved-batch audits required.','Full account ACT and resource feedback/economic value untested.'],'adapter_sha256':C.sha(F/'confirmed_adapter.py'),'source_freeze_sha256':C.sha(F/'SOURCE_FREEZE.json'),'fixture_source_sha256':C.sha(__file__),'saved_rules_and_CP_reuse_sha256':{str(p.resolve()):C.sha(p)for p in[S/'PREVIEWS_2026-06-30.json',S/'CORE_CP_LOOKUP_2026-06-30.json']},'seconds_including_import':time.monotonic()-begun};(R/'PURE_TYPED_CONTRACT_FIXTURES.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in['cases','saved_rules_and_CP_reuse_sha256']},ensure_ascii=False))
except BaseException as e:
 (R/'PURE_TYPED_CONTRACT_FAILURE.json').write_text(json.dumps({'passed':False,'completed_cases':results,'error':str(e),'traceback':traceback.format_exc(),'seconds':time.monotonic()-begun,'adapter_sha256':C.sha(F/'confirmed_adapter.py')},ensure_ascii=False,indent=2)+'\n');raise
