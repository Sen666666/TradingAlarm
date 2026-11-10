import adapter as M
from pathlib import Path
import sys,time,signal,traceback,shutil,json,gzip
O=M.O
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def at(r):return r.get('at',r.get('receipt',{}).get('at',r.get('receivable',{}).get('ex_at','')))
def identity(r,name,ref,refname,end,full=False):
 ds=[M.N.encoded(x) for x in r.daily if x['account']==name and str(x['at'])[:10]<=end]
 old=[x for x in rows(ref/'daily.jsonl.gz') if x['account']==refname and x['at'][:10]<=end]
 for x in ds:x['account']=refname
 assert ds==old,('daily identity',name,len(ds),len(old),next((i for i,(a,b) in enumerate(zip(ds,old)) if a!=b),None))
 a=r.accounts[name];op=ref/f'{refname}.json';rr=M.read(op) if op.exists() else obj(ref/f'{refname}.json.gz')
 for field in ['trades','decisions','audit']:
  target=[x for x in rr[field] if at(x)[:10]<=end];new=[x for x in M.N.encoded(getattr(a,'audit_log' if field=='audit' else field)) if at(x)[:10]<=end];assert new==target,(name,field)
 if full:assert M.N.encoded(a.layers)==rr['layers'],(name,'layers')
 return dict(passed=True,daily_rows=len(ds),trades=sum(at(x)[:10]<=end for x in M.N.encoded(a.trades)),decisions=sum(at(x)[:10]<=end for x in M.N.encoded(a.decisions)),audit=sum(at(x)[:10]<=end for x in M.N.encoded(a.audit_log)),complete=full)

def main():
 sec,stage=sys.argv[1:3];assert sec in ['TECH','DRUG'] and stage in ['gate','postgate','cachegate','prefix','full','repair-prefix','repair-full'];short=stage in ['gate','postgate','cachegate'];repair=stage.startswith('repair-');prefix=stage in ['prefix','repair-prefix']
 prior=M.read(O/'COMPUTE_TIME.json') if (O/'COMPUTE_TIME.json').exists() else dict(seconds=0,stages=[])
 left=min(300,600-prior['seconds']);assert left>0;t=time.monotonic();root=O/sec/stage;root.mkdir(parents=True,exist_ok=False)
 shutil.copyfile(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json')
 status='started';r=None;signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('frozen 300s stage / 600s total compute budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  assert M.read(O/'REPAIRED_TEST_RESULTS.json')['passed']
  freeze=M.read(O/'FREEZE.json');assert all(M.sha(p)==h for p,h in freeze['sha256'].items())
  if stage!='gate':assert M.read(O/sec/'gate/GATE.json')['passed']
  if stage in ['full','repair-full']:
   for s in ['TECH','DRUG']:assert M.read(O/s/'prefix/GATE.json')['passed']
  cut='2025-12-31' if prefix else None;end='2024-03-13' if short else cut if cut else '2026-10-27'
  policies=['ADD'] if repair else ['L0'] if stage=='cachegate' else ['L0','OFF','ADD'] if stage in ['gate','postgate'] else ['L0','ADD'];stresses=['delay1'] if repair else ['base'] if stage in ['prefix','cachegate'] else ['base','cost2','delay1']
  r=M.Pilot(sec,root,cut,stresses,policies)
  if short:
   for a in r.accounts.values():a.verify_index=True
  if stage in ['full','repair-full']:r.record_risk=True
  init=time.monotonic()-t;print(dict(sector=sec,stage=stage,initialized_seconds=init,paths=len(r.accounts),budget=left),flush=True)
  t1=time.monotonic();r.run(end);sim=time.monotonic()-t1;M.dump(r,root/'results')
  if short:
   receipts=[]
   if stage in ['gate','postgate']:
    for s in stresses:receipts.append(identity(r,'OFF_'+s,root/'results','L0_'+s,end))
   if stage=='postgate':
    for name in ['L0_base','L0_cost2','L0_delay1','ADD_base','ADD_cost2']:receipts.append(identity(r,name,O/sec/'gate/results',name,end))
   if sec=='TECH':receipts.append(identity(r,'L0_base',M.RR/'lot-risk-allocation-20261029/results','L0',end))
   M.save(root/'GATE.json',dict(passed=True,identities=receipts,actual_fragment_ops={k:a.ops for k,a in r.accounts.items() if a.add_enabled},elapsed_simulation=sim,closes_per_path=len(r.daily)/len(r.accounts),estimate_6_full_sim_seconds=sim/(len(r.daily)/len(r.accounts))*681*6/len(r.accounts),initialization=init,read_only_row_lookup_original_checks=r.row_cache_checks))
  elif prefix:M.save(root/'GATE.json',dict(passed=True,physical_cutoff=cut,paths=policies,price_facts_actions_CP_H1_physically_truncated=True,drug_PVR_recomputed_prefix_exact=True,rows=len(r.daily),simulation_seconds=sim))
  elif stage=='repair-full':
   receipts=[identity(r,'ADD_delay1',O/sec/'repair-prefix/results','ADD_delay1','2025-12-31')]
   M.save(root/'GATE.json',dict(passed=True,identities=receipts,rows=len(r.daily),simulation_seconds=sim,only_fixes_preapproved_single_use_wait_credit=True))
  else:
   receipts=[identity(r,p+'_base',O/sec/'prefix/results',p+'_base','2025-12-31') for p in ['L0','ADD']]
   if sec=='TECH':receipts.append(identity(r,'L0_base',M.RR/'lot-risk-allocation-20261029/results','L0','2026-10-27',True))
   M.save(root/'GATE.json',dict(passed=True,identities=receipts,rows=len(r.daily),simulation_seconds=sim))
  assert all(M.sha(p)==h for p,h in freeze['sha256'].items());status='complete'
 except BaseException as e:
  status='failed';M.save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()))
  if r is not None and not (root/'results').exists():M.dump(r,root/'failed-results')
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;prior=M.read(O/'COMPUTE_TIME.json') if (O/'COMPUTE_TIME.json').exists() else dict(seconds=0,stages=[]);prior['seconds']+=elapsed;prior['stages'].append(dict(sector=sec,stage=stage,status=status,seconds=elapsed));M.save(O/'COMPUTE_TIME.json',prior);M.save(root/'TIMING.json',dict(status=status,seconds=elapsed,total_seconds=prior['seconds']));print(dict(sector=sec,stage=stage,status=status,seconds=elapsed,total=prior['seconds']),flush=True)
if __name__=='__main__':main()
