"""Bounded pre-registered cap ablation. No account window beyond September23."""
from pathlib import Path
import ast,copy,json,sys,hashlib,argparse
sys.dont_write_bytecode=True
import engine as m
O=Path(__file__).resolve().parent;REF=O.parent/'mainline_candidate_v1';D=m.D;ZERO=D(0)
FAMILIES=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','RETRY_TICKETS','INFORMATION_CONFIRMATIONS','TRANSFERS','FUNDING_REQUESTS','ADD_FLOOR_RISK','OPEN_SECTOR_EXPOSURE','TICKET_STATE','TRANSFER_PLAN_AT_END']
def seal_ast():
 orig=ast.parse((REF/'engine.py').read_text());new=ast.parse((O/'engine.py').read_text());flag=[x for x in new.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='UNCAP_ADD' for t in x.targets)];assert len(flag)==1;new.body.remove(flag[0]);changed=[]
 class Reduce(ast.NodeTransformer):
  def visit_IfExp(self,node):
   if isinstance(node.test,ast.Name) and node.test.id=='UNCAP_ADD':changed.append(dict(line=node.lineno,uncapped=ast.unparse(node.body),original=ast.unparse(node.orelse)));return node.orelse
   return self.generic_visit(node)
 norm=Reduce().visit(new);assert len(changed)==3 and ast.dump(orig,include_attributes=False)==ast.dump(norm,include_attributes=False)
 origcls=next(n for n in orig.body if isinstance(n,ast.ClassDef) and n.name=='Engine');newcls=next(n for n in ast.parse((O/'engine.py').read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Engine');methods={n.name:ast.dump(n,include_attributes=False) for n in origcls.body if isinstance(n,ast.FunctionDef)};changedmethods=[n.name for n in newcls.body if isinstance(n,ast.FunctionDef) and methods[n.name]!=ast.dump(n,include_attributes=False)];assert changedmethods==['noncash','alloc_open','close']
 out=dict(result='PASS',sole_changed_methods=changedmethods,three_expression_locations=changed,entire_module_identical_after_flag_reduction=True,reference_engine_sha256=m.sha(REF/'engine.py'),engine_sha256=m.sha(O/'engine.py'),contract_sha256=m.sha(O/'FROZEN_CONTRACT_DRAFT.md'),unchanged_methods=[n for n in methods if n not in changedmethods]);m.save(O/'AST_IDENTITY_QA.json',out);return out

def synthetic():
 ns={'__name__':'ablation_synthetic'};exec(compile((REF/'synthetic_m.py').read_text(),str(REF/'synthetic_m.py'),'exec'),ns);m.UNCAP_ADD=False;original=ns['run']();checks=[]
 setup=ns['setup'];plan=ns['plan'];proof=ns['proof'];Stub=ns['Stub'];attempt=ns['attempt'];cp=ns['cp'];dt=ns['dt'];prev=ns['prev']
 for mode,expected in [(False,100),(True,2000)]:
  m.UNCAP_ADD=mode;e,a=setup();a['plan']=plan('b',2000);proof(e,a);e.alloc_open(dt,[]);assert len(e.orders)==1 and e.orders[0]['qty']==expected and a['add_count']==1 and a['cp'] is None;checks.append(f'OPEN_both_size_layers_mode_{mode}_{expected}')
 m.UNCAP_ADD=True
 class CloseTest(m.Engine):
  def attribute(self,*args):pass
  def plan_transfers(self,*args):self.transfer_plan=[]
 e=CloseTest(Stub());a=attempt('b',100);a['cp']=cp();e.active['b']=a;e.archive[a['id']]=a;e.close(dt,prev);assert a['plan']['planned_q']==2300 and a['information_pending'];checks.append('CLOSE_uncapped_2pct_budget')
 e,a=setup();r=plan('b',2000);nav=e.nav(dt,'raw_open');sv={'b':e.qvalue(a,dt,'raw_open')}
 for field in ['raw_close','raw_open']:assert e.demand([r],dt,field,nav,sv)[1][0]['q']==2000
 checks.append('same_noncash_flow_CLOSE_and_OPEN_demand')
 e,a=setup();r=plan('b',2000);r['capacity']=300;assert e.noncash(r,dt,'raw_open',nav,sv)['q']==300;checks.append('capacity_retained')
 e,a=setup();a['plan']=plan('b',100);proof(e,a);e.alloc_open(dt,[]);assert e.orders[0]['qty']==100;checks.append('OPEN_never_expands_CLOSE')
 e,a=setup(q=200);e.d.prices['b']=D(100);r=plan('b',200);r['budget']=D(15000);a['plan']=r;proof(e,a);e.alloc_open(dt,[]);assert e.orders[0]['qty']==100;checks.append('gap_still_shrinks')
 e,a=setup();e.cash=D(100);a['plan']=plan('b',2000);proof(e,a);e.alloc_open(dt,[]);assert not e.orders and not a['cp']['consumed'] and a['confirmed_history'];checks.append('cash_legal_failure_keeps_CP_and_confirmation')
 e,a=setup();a['cashflow']=D(-2000);r=plan('b',2000);assert e.noncash(r,dt,'raw_open',e.nav(dt,'raw_open'),{'b':D(1000)})['q']==0;checks.append('positive_net_gate_unchanged')
 e,a=setup();a['plan']=plan('b',2000);proof(e,a);a['exit']='TRIAL_SECTOR_FALSE';e.exit_open(dt);e.alloc_open(dt,[]);assert not e.active and not a['confirmed_history'];checks.append('protection_exit_precedes_ADD')
 e,a=setup(q=4700);r=plan('b',5000);a['plan']=r;proof(e,a);e.alloc_open(dt,[]);assert not e.orders;checks.append('round4pct_legal_remainder_below_minimum')
 e,a=setup();observed=Observer(e.d);observed.active=copy.deepcopy(e.active);observed.archive={x['id']:x for x in observed.active.values()};a['plan']=plan('b',2000);proof(e,a);oa=observed.active['b'];oa['plan']=plan('b',2000);proof(observed,oa);e.alloc_open(dt,[]);observed.alloc_open(dt,[]);assert e.orders==observed.orders and e.cash==observed.cash and len(observed.add_context)==1;checks.append('Observer_delegate_has_identical_account_and_order')
 m.UNCAP_ADD=False;out=dict(result='PASS',original_suite=original,additional_checks=checks,check_count=original['check_count']+len(checks),historical_account_not_run=True);m.save(O/'SYNTHETIC_QA.json',out);return out

class Observer(m.Engine):
 """Pure recording override delegates unchanged order and does not change any account state."""
 def __init__(self,data):super().__init__(data);self.add_context=[]
 def order(self,a,d,side,q,p,reason,**kw):
  if side=='BUY_ADD':
   s=a['sid'];raw=m.dec(self.d.z(s,d)['raw_open']);oldq=self.quantity(a)-q;factor=a['factor'];cp=a['cp'];fl=max(a['ifloor'],cp['floor']);sellp=fl/factor*(1-m.SLIP);bf=self.d.fee(s,d,q,p,'buy');cost=q*p+bf;sf=self.d.fee(s,d,q,sellp,'sell');loss=cost-(q*sellp-sf);old_net=self.net(a,d,'raw_open')-q*raw*(1-m.SLIP)+self.d.fee(s,d,oldq+q,raw*(1-m.SLIP),'sell')-self.d.fee(s,d,oldq,raw*(1-m.SLIP),'sell');pre_nav=self.nav(d,'raw_open')-q*raw;whole_fee=self.d.fee(s,d,oldq+q,sellp,'sell');whole=a['cashflow']+a['dividend']-cost+(oldq+q)*sellp-whole_fee
   assert old_net==D(kw['open_net'])
   self.add_context.append(dict(day=m.day(d),sid=s,round_id=a['id'],order_seq=len(self.orders)+1,cp_id=cp['id'],old_qty=oldq,add_qty=q,pre_add_close_net=kw['close_net'],pre_add_open_net=str(old_net),raw_open=str(raw),buy_price=str(p),buy_slippage=str(q*(p-raw)),buy_fee=str(bf),buy_all_in=str(cost),I_signal=str(a['ifloor']),CP_signal=str(cp['floor']),factor=str(factor),known_protection_raw=str(fl/factor),hypothetical_sell_price=str(sellp),new_layer_sell_fee=str(sf),new_layer_floor_loss=str(loss),whole_round_combined_sell_fee=str(whole_fee),whole_round_floor_net_after_ADD=str(whole),whole_round_floor_loss_after_ADD=str(max(ZERO,-whole)),pre_add_actual_NAV=str(pre_nav),original_round_nav0=str(a['nav0']),layer_loss_pct_initial_principal=str(100*loss/m.INITIAL),layer_loss_pct_pre_add_NAV=str(100*loss/pre_nav),add_cost_pct_pre_add_NAV=str(100*cost/pre_nav),whole_floor_loss_pct_NAV=str(100*max(ZERO,-whole)/pre_nav),loss_exceeds_old_profit=loss>old_net,old_lot_protections=[dict(lot_id=l['id'],qty=l['q'],kind=l['kind'],protection_signal=str(a['ifloor'] if l['kind']=='SEED' else l['floor'])) for l in a['lots'] if l['id']!=kw['lot_id']],not_maximum_loss=True,not_stop_fill_guarantee=True))
  return super().order(a,d,side,q,p,reason,**kw)

def run():
 static=seal_ast();assert m.read(O/'SYNTHETIC_QA.json')['result']=='PASS'
 approval=m.read(O/'CONTRACT_APPROVAL.json');assert approval['approved'] and approval['engine_sha256']==m.sha(O/'engine.py') and approval['runner_sha256']==m.sha(Path(__file__)) and approval['contract_sha256']==m.sha(O/'FROZEN_CONTRACT_DRAFT.md')
 assert not (O/'RUN_STARTED.json').exists();m.save(O/'RUN_STARTED.json',dict(end='2024-09-23',start='2024-09-02',new_arm_execution_count_allowed=1))
 data=m.Data(end='2024-09-23');assert len(data.days)==14;data.evidence.to_csv(O/'ALL50_MAINLINE_EVIDENCE.csv',index=False);source=dict(data.hashes);m.save(O/'FROZEN_INPUTS.json',source)
 refsource=m.read(REF/'checkpoint_20240923/SOURCE_HASHES.json');common=set(source)&set(refsource);assert all(source[p]==refsource[p] for p in common)
 missing=set(refsource)-set(source);future_paths=set()
 def collect_paths(obj):
  if isinstance(obj,dict):
   for k,v in obj.items():
    if isinstance(k,str) and k.startswith('/'):future_paths.add(k)
    collect_paths(v)
  elif isinstance(obj,list):
   for v in obj:collect_paths(v)
  elif isinstance(obj,str) and obj.startswith('/'):future_paths.add(obj)
 event_files=[m.b.E/'cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json',O.parent/'continuous_candidate_v1/EXTRA_REVIEWED_EQUITY_EVENTS_V2.json',m.BASE/'ADDITIONAL_REVIEWED_EVENTS.json',O.parent/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_603083_V1.json']
 for event_file in event_files:
  for event in m.read(event_file):
   if event['ex_date']>'2024-09-23':collect_paths(event)
 strategy_paths={str(REF/'engine.py'),str(REF/'FROZEN_CONTRACT_DRAFT.md')};assert missing<=strategy_paths|future_paths,('UNEXPLAINED_SOURCE_OMISSION',sorted(missing-strategy_paths-future_paths))
 m.save(O/'SOURCE_GROUP_QA.json',dict(result='PASS',common_identical=len(common),reference_strategy_paths_only=sorted(missing&strategy_paths),out_of_window_equity_evidence_only=sorted(missing-strategy_paths),shared_Data_object_both_modes=True,source_hashes_sha256=m.sha(O/'FROZEN_INPUTS.json')))
 m.UNCAP_ADD=False;baseline=m.Engine(data).run(False);assert not baseline.blockers and len(baseline.ledger)==14;baseline.export(O/'capped_replay_20240923');counts={}
 for fam in FAMILIES:
  ours=m.read(O/'capped_replay_20240923'/(fam+'.json'));prior=m.read(REF/'checkpoint_20240923'/(fam+'.json'));assert ours==prior,('PREFIX_MISMATCH',fam);counts[fam]=len(ours)
 m.save(O/'PREFIX_REPLAY_QA.json',dict(result='PASS',days=14,exact_families=counts));print('PREFIX_17_FAMILIES_PASS '+json.dumps(counts),flush=True)
 m.UNCAP_ADD=True;m.save(O/'NEW_ARM_STARTED.json',dict(end='2024-09-23',mode='only_remove_ADD_share_cap'));new=Observer(data).run(False);assert len(new.ledger)==14 and not new.blockers;new.export(O/'uncapped_once_20240923');m.save(O/'ADD_CONTEXT.json',new.add_context);m.pd.DataFrame(new.add_context).to_csv(O/'ADD_CONTEXT.csv',index=False);assert data.hashes==source
 out=dict(result='PASS',days=14,orders=len(new.orders),adds=len(new.add_context),last=new.ledger[-1],source_hashes_identical_between_arms=True,only_one_uncapped_execution=True);m.save(O/'RUN_STATUS.json',out);print('UNCAPPED_DONE '+json.dumps(out),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',required=True,choices=['prepare','run']);a=ap.parse_args()
 if a.mode=='prepare':print(json.dumps(dict(ast=seal_ast(),synthetic=synthetic()),default=str))
 else:run()
