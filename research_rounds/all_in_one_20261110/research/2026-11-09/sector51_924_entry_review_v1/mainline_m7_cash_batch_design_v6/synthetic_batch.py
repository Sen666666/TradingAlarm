from pathlib import Path
import importlib.util,sys,types,json,copy,difflib,hashlib
P=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('v5batchqa',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
static=e.self_check();ok('all_v4_execution_and_cash_methods_identical');ok('only_exactscope_and_evidence_container_loader_changes')
oldloop=e.run_loop;sentinel=object();calls=[]
try:
 e.run_loop=lambda x,cp:(calls.append((x,cp)),sentinel)[1];instance=e.Engine.__new__(e.Engine);ok('Engine_run_routes_local_v6_loop',instance.run(False) is sentinel and calls==[(instance,False)])
finally:e.run_loop=oldloop
oldread=e.read
try:
 e.read=lambda p: {'approved':False} if Path(p).name=='CONTRACT_APPROVAL.json' else oldread(p)
 try:e.authorized_run()
 except AssertionError:ok('no_run_without_explicit_approval')
 else:raise AssertionError('unapproved run allowed')
finally:e.read=oldread
records=e.manifest()['events'];results=[]
for ev in records:
 sid=ev['sid'];dt=e.pd.Timestamp(ev['ex_date']);raw=e.pd.read_parquet(ev['signal_path'])
 if not isinstance(raw.index,e.pd.DatetimeIndex):raw=raw.set_index('date' if 'date' in raw else 'trade_date')
 data=types.SimpleNamespace(end=e.pd.Timestamp('2026-06-30'),actions={sid:e.read(Path(ev['local_action_path']))},raw={sid:raw},events={},admission=[],sid_sector={sid:'fixture'})
 def checked(p,h):assert e.sha(Path(p))==h
 e.admit_cash(data,ev,checked,e.ALLOWED);ok('actual_source_bridge_'+sid,(sid,dt) in data.events and len(data.admission)==1)
 x=e.Engine(data);x.register_pay(e.pd.Timestamp(ev['record_date']));x.accrue(dt);x.register_pay(e.pd.Timestamp(ev['pay_date']));ok('Q0_cash_zero_'+sid,x.cash==e.D(1200000) and x.receivable==0 and not x.claims)
 x=e.Engine(data);q=200;rid=sid+'|synthetic';a=dict(sid=sid,id=rid,lots=[dict(q=q)],dividend=e.D(0));x.active[sid]=a;x.archive[rid]=a;x.register_pay(e.pd.Timestamp(ev['record_date']));x.active.clear();x.accrue(dt);entitlement=e.D(q)*e.D(ev['d_cash'])*e.D('.8');ok('record_holdings_accrue_'+sid,x.receivable==entitlement and x.cash==e.D(1200000) and a['dividend']==entitlement);x.register_pay(e.pd.Timestamp(ev['pay_date']));ok('documented_pay_once_'+sid,x.receivable==0 and x.cash==e.D(1200000)+entitlement);x.register_pay(e.pd.Timestamp(ev['pay_date']));ok('no_double_payment_'+sid,x.cash==e.D(1200000)+entitlement)
 try:e.admit_cash(data,ev,checked,e.ALLOWED)
 except AssertionError:ok('duplicate_event_rejected_'+sid)
 else:raise AssertionError('duplicate')
 results.append(dict(sid=sid,ex_date=ev['ex_date'],d_source=ev['d_source'],d_cash=ev['d_cash'],d_ref=ev.get('d_ref'),actual200share_NET80=str(entitlement),record_date=ev['record_date'],pay_date=ev['pay_date'],evidence=ev['primary_evidence']['kind']))
example=next(r for r in records if r['sid']=='600157.SH');ok('600157_three_distinct_quantities',example['d_source']=='0.0056' and example['d_cash']=='0.00556' and example['d_ref']=='0.00551');ok('600157_200share_entitlement_not_sourcecash',next(r for r in results if r['sid']=='600157.SH')['actual200share_NET80']=='0.889600')
bad=copy.deepcopy(example);bad['d_cash']='0.0056'
try:e.validate_primary(bad)
except AssertionError:ok('gross_not_replaced_with_source_rounding')
else:raise AssertionError('cash rounding')
bad=copy.deepcopy(example);bad['pay_date']=bad['record_date']
try:e.validate_primary(bad)
except AssertionError:ok('guessed_payment_rejected')
else:raise AssertionError('date')
ok('no_factor_only_runtime_fallback',e.manifest()['q0_factor_only_enabled'] is False)
ok('actual_cash_loader_methods_preserved',e.Engine.accrue is e.v.Engine.accrue and e.Engine.register_pay is e.v.Engine.register_pay)

# Explicit fact-pair validation, no epsilon or cash-model changes.
def rejects_pair(ev):
 try:return not e.cash_pair_allowed(ev)
 except (AssertionError,ValueError,KeyError):return True
for sid in ['688016.SH','688548.SH']:
 ev=next(x for x in records if x['sid']==sid)
 ok('exact_upward_pair_'+sid,e.cash_pair_allowed(ev))
 for k,val in [('d_cash',str(e.D(ev['d_cash'])+e.D('.000001'))),('d_source',str(e.D(ev['d_source'])-e.D('.000001'))),('d_ref','0'),('sid','999999.SH'),('ex_date','2024-11-12')]:
  bad=copy.deepcopy(ev);bad[k]=val;ok('modified_pair_rejected_'+sid+'_'+k,rejects_pair(bad))
 bad=copy.deepcopy(ev);bad['primary_evidence']['sha256']='0'*64;ok('primary_hash_rejected_'+sid,rejects_pair(bad))
 bad=copy.deepcopy(ev);bad['primary_evidence']['record']['F012N']=999;ok('primary_record_rejected_'+sid,rejects_pair(bad))
 for val in ['-1','NaN','Infinity','-Infinity']:
  bad=copy.deepcopy(ev);bad['d_cash']=val;ok('bad_cash_rejected_'+sid+'_'+val,rejects_pair(bad))
 for val in ['0','-1','NaN','Infinity']:
  bad=copy.deepcopy(ev);bad['d_source']=val;ok('bad_source_rejected_'+sid+'_'+val,rejects_pair(bad))
 evrow=next(x for x in results if x['sid']==sid);ok('exact_NET80_not_source_capped_'+sid,e.D(evrow['actual200share_NET80'])==e.D(200)*e.D(ev['d_cash'])*e.D('.8'))
equal=next(x for x in records if x['d_cash']==x['d_source']);ok('original_equal_case_allowed',e.cash_pair_allowed(equal));ok('original_lower_case_allowed',e.cash_pair_allowed(example))
bad=copy.deepcopy(equal);bad['d_cash']=str(e.D(equal['d_source'])+e.D('.00000000001'));ok('unknown_tiny_positive_difference_rejected',rejects_pair(bad))
# Verified baseline source snapshots only; no historical simulation or writes.
nov7,base=e.validate_nov7();oldsave=e.save
try:
 e.save=lambda *a,**k:None;e.check_nov7(base);ok('actual_certified_Nov7_32family_prefix_validator')
finally:e.save=oldsave
ok('Nov7_family_set_nonvacuous',len(nov7['comparison_families'])==32 and len(set(nov7['comparison_families']))==32)
ok('both_checkpoint_dates',"['2024-11-06','2024-11-07']" in e.source)

qa=dict(result='PASS',total=len(checks),checks=checks,events=results,history_run=False,engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),manifest_sha256=e.sha(P/'EXACT_CASH_BATCH_MANIFEST.json'))
e.save(P/'STATIC_QA.json',static);e.save(P/'SYNTHETIC_QA.json',qa);(P/'CASH_LOADER_PATCH.diff').write_text(''.join(difflib.unified_diff(e.loader_source.splitlines(True),e.batch_loader_source.splitlines(True),fromfile='approved_cash_loader',tofile='v6_exact63_primary_container')));print(json.dumps({k:qa[k] for k in ['result','total','history_run','engine_sha256','contract_sha256','manifest_sha256']}))
