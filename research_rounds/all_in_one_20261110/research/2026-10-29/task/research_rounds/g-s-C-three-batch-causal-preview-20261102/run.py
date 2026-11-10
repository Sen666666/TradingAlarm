"""Three fixed pure planning diagnostics. No account/market events or order submission."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import sys,json,pickle,copy,hashlib,inspect,ast,time,traceback
HERE=Path(__file__).resolve().parent;W=HERE.parent;R=W/'g-s-C-month-continuation-20261102';sys.path.insert(0,str(R));import month_runtime as M
import c_selector as C
B=C.B;J=C.J;Z=D(0);DATES=('2025-07-08','2025-07-22','2025-07-29');SOURCE_READS={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):M.E.IO.write_json(HERE/n,x,encoder=M.E.encode)
def load(mode):
 p=R/'runs'/('2025_26-'+mode)/'2025-07-31-CLOSE.pkl';side=M.read(p.with_suffix('.provenance.json'));assert sha(p)==side['checkpoint_sha256'];r=pickle.loads(p.read_bytes());assert r.binding()==side['binding'];SOURCE_READS[str(p)]=sha(p);return r
def loop_copy():
 src=inspect.getsource(B.solve_B);tree=ast.parse(src);count=0
 for n in ast.walk(tree):
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ds' for t in n.targets) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='sorted':
   assert ast.unparse(n.value)=='sorted(ds, key=lambda d: (d[\'priority\'], d[\'sid\']))';n.value=ast.Call(func=ast.Name(id='list',ctx=ast.Load()),args=[ast.Name(id='ds',ctx=ast.Load())],keywords=[]);count+=1
 assert count==1;tree.body[0].name='solve_queue_only';ast.fix_missing_locations(tree);ns=dict(B.__dict__);ns['__name__']='isolated_queue_only_diagnostic';exec(compile(tree,str(HERE/'run.py')+'::one_assignment_queue_patch','exec'),ns)
 save('ISOLATED_FUNCTION_IDENTITY.json',dict(original_selector=str(Path(B.__file__).resolve()),original_sha256=sha(B.__file__),diagnostic_wrapper_sha256=sha(__file__),changed_assignments=count,original_source=src,patched_AST=ast.dump(tree,include_attributes=False),financial_authority=False))
 return ns['solve_queue_only']
def context_breakdown(s,ds,Q,Dmap,costs):
 old=defaultdict(lambda:Z)
 for z in s['lots']:
  q=D(z['qty']);mark=D(z['mark']);floor=D(z['floor']);cost=costs[z['id']];principal=q*max(Z,min(mark,cost)-floor);profit=q*max(Z,mark-max(cost,floor));line=q*max(Z,mark-floor);assert principal+profit==line
  old['principal']+=principal;old['profit_giveback']+=profit;old['line_risk']+=line;old['actual_snapshot_risk']+=D(z['risk']);old['execution_lock_excess']+=D(z['risk'])-line
 prior_reserve=sum((D(Q.get(d['sid'],0))*max(Z,D(d['mark'])*(1+J.SLIP)-D(d['floor'])) for d in ds),Z)
 prior_mark=sum((D(Q.get(d['sid'],0))*max(Z,D(d['mark'])-D(d['floor'])) for d in ds),Z)
 plan=B.make_plan(s,ds,Q,Dmap)
 return dict(old=dict(old),prefix_new_reserve_risk=prior_reserve,prefix_new_post_conditional_fill_risk=prior_mark,projected_old_risk_release=sum((D(p['risk_release']) for p in plan['rows']),Z),donor_plan=plan,actual_risk_released=0,actual_sale_cash_released=0)
def first_unit(s,ds,Qpre,Dstart,d,qty,costs):
 test=dict(Qpre);test[d['sid']]=qty;base=B.evaluate(s,ds,test,Dstart);groups=defaultdict(list)
 for z in s['lots']:
  if z['role']=='mobile' and z.get('B_donor_eligible') and z['sid']!=d['sid'] and not Qpre.get(z['sid'],0) and tuple(z['rank_key'])>tuple(d['priority']):groups[z['sid']].append(z)
 weak=sorted(groups,key=lambda sid:tuple(groups[sid][0]['rank_key']),reverse=True);stats=Counter();sets=Counter();n=0;first=None;last=None
 def check(Dmap):
  nonlocal n,first,last
  out=B.evaluate(s,ds,test,Dmap);n+=1;last=out;stats.update(out['validation']['violations']);sets[tuple(out['validation']['violations'])]+=1
  if out['validation']['ok'] and first is None:first=out
  return out['validation']['ok']
 if not check(Dstart):
  prefix=dict(Dstart)
  for sid in weak:
   lots=groups[sid];stocktotal=sum(z['qty'] for z in s['lots'] if z['sid']==sid);values=B.sell_totals(lots,prefix.get(sid,0),stocktotal)
   for q in values:
    dd=dict(prefix);dd[sid]=q
    if check(dd):break
   if first:break
   if values:prefix[sid]=values[-1]
  
 return dict(sid=d['sid'],tested_total_quantity=qty,original_initial_min=d['quantity']['buy_minimum'],original_step=d['quantity']['buy_step'],original_max=d['max_q'],base_exact=base,first_legal_with_original_donor_path=first,last_original_path_test=last,tests=n,violation_occurrences=dict(stats),violation_sets=[dict(violations=list(k),count=v) for k,v in sets.items()],admissible_weaker_donor_stocks=weak,prefix_breakdown=context_breakdown(s,ds,Qpre,Dstart,costs),scope='original deterministic cumulative donor path, not all possible subsets; all releases hypothetical only')
def main():
 started=time.perf_counter();M.guard();contract_sha=sha(HERE/'CONTRACT.txt');solve_queue=loop_copy();summary=[]
 for mode in ('C10','C_BATCH20'):
  r=load(mode);costs={lid:D(m['unit_cost']) for lid,m in r.account.capital_meta.items()};saved={p['at'][:10]:p for p in r.results}
  for day in DATES:
   label=mode+'-'+day;row=saved[day];v=r.trusted[row['certificate']['trusted_id']];before=J.digest(v);save('INPUT-'+label+'.json',dict(trusted=v,saved_certificate=row['certificate'],saved_result=row['projection'],contract_sha256=contract_sha));t=time.perf_counter();orig=r._solve(copy.deepcopy(v['snapshot']),copy.deepcopy(v['demands']),copy.deepcopy(v['evidence']),v['budget_before'])
   assert J.digest(orig)==row['certificate']['projection_hash'];assert J.digest(orig)==J.digest(row['projection']);assert before==J.digest(v)
   ss,dd,audit=C.transform(v['snapshot'],v['demands'],v['evidence']);ordered=sorted(dd,key=lambda d:(d['priority'],d['sid']));Q={d['sid']:0 for d in ordered};Dmap={};prefix=[]
   for tr,d in zip(orig['trace'],ordered):
    assert tr['sid']==d['sid'];prefix.append(dict(sid=d['sid'],before_positive_Q={s:q for s,q in Q.items() if q},before_D=dict(Dmap),demand=d,original_trace=tr));Q[d['sid']]=tr['q']
    if 'D' in tr:Dmap=dict(tr['D'])
   assert len(prefix)==len(ordered) and Q==orig['Q'] and Dmap==orig['D'];save('BASELINE-'+label+'.json',dict(exact_complete_digest=True,seconds=time.perf_counter()-t,result=orig,prefixes=prefix,sorted_complete_demands=ordered,transformed_snapshot=ss,rank_binding=audit));print('BASELINE_EXACT',label,len(dd),'seconds',round(time.perf_counter()-t,3),flush=True)
   entry=dict(mode=mode,day=day,original_exact=True,candidates=len(dd),original_Q=orig['Q'],original_D=orig['D'])
   if mode=='C10':
    target=lambda d:d['sid']=='688425.SH' if day=='2025-07-29' else d['sector']=='URFI881268'
    actual_targets=[d['sid'] for d in ordered if target(d)];assert actual_targets,'fixed case absent; no invented eligibility'
    identity=solve_queue(copy.deepcopy(ss),copy.deepcopy(ordered));assert identity['Q']==orig['Q'] and identity['D']==orig['D'] and identity['trace']==orig['trace'] and identity['validation']==orig['validation'];queue=[d for d in ordered if target(d)]+[d for d in ordered if not target(d)];t=time.perf_counter();changed=solve_queue(copy.deepcopy(ss),copy.deepcopy(queue));assert changed['validation']['ok'];assert J.digest(v)==before
    assert {d['sid']:d for d in queue}=={d['sid']:d for d in ordered}
    allchanges=[dict(sid=s,before=orig['Q'][s],after=changed['Q'][s]) for s in orig['Q'] if orig['Q'][s]!=changed['Q'][s]]
    save('QUEUE_ONLY-'+label+'.json',dict(contract_sha256=contract_sha,identity_original_order_exact=True,targets=actual_targets,original_full_order=[d['sid'] for d in ordered],diagnostic_full_order=[d['sid'] for d in queue],financial_fields_and_comparative_rank_keys_identical=True,result=changed,all_Q_changes=allchanges,all_D_before=orig['D'],all_D_after=changed['D'],seconds=time.perf_counter()-t,account_events=0,submit_allowed=False))
    probes=[]
    for p in prefix:
     d=p['demand']
     if not target(d):continue
     q0={s:0 for s in orig['Q']};q0.update(p['before_positive_Q']);probe=first_unit(ss,ordered,q0,p['before_D'],d,d['quantity']['buy_minimum'],costs);probe['original_accepted_q']=orig['Q'][d['sid']]
     if p['original_trace']['q']>=d['max_q']:probe['next_increment']='original_max_target_already_filled_no_extra_authorization'
     elif p['original_trace']['q']:
      probe['next_increment']=first_unit(ss,ordered,q0,p['original_trace']['D'],d,p['original_trace']['q']+d['quantity']['buy_step'],costs)
     probes.append(probe)
    save('FIXED_PREFIX_UNITS-'+label+'.json',probes);entry.update(queue_targets=actual_targets,queue_Q_changes=allchanges,queue_D=changed['D'],queue_validation_passed=True,unit_probes=len(probes));print('DIAGNOSTIC_DONE',label,'Qchanges',len(allchanges),'probes',len(probes),flush=True)
   summary.append(entry)
 save('SUMMARY.json',dict(rows=summary,seconds=time.perf_counter()-started,financial_events=0,account_progression=0,ranking_diagnostic='queue only; comparative rank/donor eligibility unchanged'));save('SOURCE_INPUT_CHECKS.json',dict(source_reads=SOURCE_READS,source_policy_guard_passed=True,contract_sha256=contract_sha,original_source_untouched=True));print('ALL_DONE',round(time.perf_counter()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as exc:save('ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),financial_events=0));raise
