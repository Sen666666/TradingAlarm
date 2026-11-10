"""Native economic identity, explicit repaired-baseline metadata, physical prefix."""
from pathlib import Path
import pickle,json,copy,hashlib
import jan_r0 as X
E=X.E;P=X.HERE;BASE=X.W/'g-s-C-two-day-finance-20261102/runs';DAYS=['2022-01-04','2022-01-05'];cache={}
def oldpath(mode,day,phase):
 root=BASE/('2022-'+mode)
 if mode=='C10' and day==DAYS[-1] and phase=='CLOSE':root=BASE/'2022-C10-recovered'
 return root/(day+'-'+phase+'.pkl')
def load(p):
 side=X.read(p.with_suffix('.provenance.json'));E.require(X.sha(p)==side['checkpoint_sha256'],'prefix bytes changed');r=pickle.loads(p.read_bytes());r.account.owner=r
 E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'actual prefix source/class changed');r.assert_observers();return r

def ctx(key):
 if key in cache:return cache[key]
 mode,kind=key;path=oldpath(mode,DAYS[-1],'CLOSE') if kind=='original' else (P/'runs'/mode if kind=='full' else P/'gates'/kind/mode)/(DAYS[-1]+'-CLOSE.pkl');r=load(path);ids={};sources=[r.source_binding()];proofs=[]
 for cid,c in r.authority.certificates.items():
  tag=mode+'|'+c['known_at'];ids[cid]='CERT|'+tag;v=r.trusted[c['trusted_id']];s,ds,e,bb=v['snapshot'],v['demands'],v['evidence'],v['budget_before'];res=next(z['projection'] for z in r.results if z['certificate']['certificate_id']==cid)
  E.require(cid==E.digest({k:z for k,z in c.items() if k!='certificate_id'}) and c['trusted_id']==E.digest(dict(s=s,ds=ds,e=e,bb=bb)) and c['snapshot_hash']==E.digest(s) and c['projection_hash']==E.digest(res),'raw certificate/trusted/projection hash')
  sources.append(c['source_binding'])
  if 'software_interface_repair' in e:E.require(e['software_interface_repair']['kind']=='non_donor_core_creation_rank_metadata' and e['software_interface_repair']['numeric_input_unchanged'] is True and e['software_interface_repair']['source_sha256']==X.sha(X.M.C.F.HERE/'provider_fix1.py'),'unknown provider repair metadata')
  ss,dd,au=X.R.M.C.transform(s,ds,e)
  for raw,logical in [(c['trusted_id'],'TRUSTED'),(E.digest(s),'SNAPSHOT'),(E.digest(ss),'RANKED_SNAPSHOT'),(E.digest(e),'EVIDENCE'),(c['projection_hash'],'PROJECTION')]:ids[raw]=logical+'|'+tag
  if E.digest(s)==E.digest(ss):ids[E.digest(s)]='SNAPSHOT|'+tag
  for k in ['result_id','base_B_result_id','base_private_B_result_id','budget_after_sha256']:
   if k in res:ids[res[k]]=k+'|'+tag
  proofs.append(dict(at=c['known_at'],trusted=v,ranked_snapshot=ss,ranked_demands=dd,projection=res))
 for source in sources:
  for f,h in source.items():
   if Path(f).is_file():E.require(X.sha(f)==h,'embedded original/current source hash changed')
 # Technical required-stage hashes are compared only for same-code physical
 # branches; reconstruct each exact preoptional body, never erase a residual.
 necessary=[]
 if kind!='original':
  root=P/'runs'/mode if kind=='full' else P/'gates'/kind/mode
  for day in DAYS:
   z=r if day==DAYS[-1] else load(root/(day+'-CLOSE.pkl'));op=X.read(root/(day+'-OPEN.json'));at=z.last_completed_event
   E.require(not z.results[-1]['projection']['D'],'prefix necessary proof expects no funding D')
   a=z.account;old=a.funding.goals;a.funding.goals=copy.deepcopy(op['account']['funding_coverage']['goals']);body=copy.deepcopy(dict(account=a.exported(at),f1={k:X.asdict(v) for k,v in z.f1.items()},f1seq=z.f1seq,cursor=z.cursor));a.funding.goals=old
   raw=z.close_stages[at.isoformat()]['necessary_digest'];E.require(E.digest(body)==raw,'necessary preoptional body not exact');ids[raw]='NECESSARY|'+mode+'|'+day;necessary.append(body)
 cache[key]=dict(ids=ids,sources=sources,proofs=proofs,necessary=necessary);return cache[key]

def norm(r,key,physical=False):
 c=ctx(key);x=dict(account=r.account.exported(r.last_completed_event),audit=r.account.audit_log,decisions=r.account.decisions,F1=r.f1,F1seq=r.f1seq,cursor=r.cursor,last_completed=r.last_completed_event,last_stock=r.last_stock_state,pending=r.account.pending,active=r.active,active_intents=getattr(r,'active_intents',None),authority=r.authority.__dict__,budget=r.budget.dumps() if r.budget else None,coverage=r.coverage.exported(),goals=r.goal_intents,busy=r._busy_goals,rank_bindings=r.rank_bindings,windows=r.windows,results=r.results,trusted_source_bodies=c['proofs'])
 if physical:x.update(lifecycle=r.lifecycle,events=r.events,event_ids=r.event_ids,close_stages=r.close_stages,transitions=r.transitions,no_subscription_actions=r.no_subscription_actions,risk=r.risk.__dict__,necessary_source_bodies=c['necessary'])
 raw=json.loads(json.dumps(x,default=E.encode));sourcehashes={E.digest(s) for s in c['sources']}
 def n(v,k=None):
  if k=='software_interface_repair':
   E.require(v['kind']=='non_donor_core_creation_rank_metadata' and v['numeric_input_unchanged'] is True,'unknown provider repair metadata');return {'verified_software_repair_metadata_only':True}
  if k=='source_binding' and isinstance(v,dict) and E.digest(v) in sourcehashes:return {'verified_current_or_original_source':True}
  if isinstance(v,dict):
   return {n(a):n(b,a) for a,b in v.items() if a not in ['software_interface_repair','input_manifest','input_sha256']}
  if isinstance(v,list):return [n(a) for a in v]
  if isinstance(v,str):
   if v.startswith('{"body"'):
    z=json.loads(v);E.require(z['state_id']==E.digest(z['body']),'raw budget state digest');b=n(z['body']);return dict(body=b,state_id=E.digest(b))
   for a,b in c['ids'].items():v=v.replace(a,b)
  return v
 return n(raw)

def main():
 records=[]
 for mode in ['C10','C_BATCH20']:
  for day in DAYS:
   for phase in ['OPEN','CLOSE']:
    off=load(P/'gates/off'/mode/(day+'-'+phase+'.pkl'));orig=load(oldpath(mode,day,phase));a,b=norm(off,(mode,'off')),norm(orig,(mode,'original'))
    if a!=b:X.save(P/('OFF-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(new=a,original=b));raise ValueError('OFF native economics differs '+mode+' '+day+' '+phase)
    full=load(P/'runs'/mode/(day+'-'+phase+'.pkl'));phys=load(P/'gates/physical'/mode/(day+'-'+phase+'.pkl'));a,b=norm(full,(mode,'full'),True),norm(phys,(mode,'physical'),True)
    if a!=b:X.save(P/('PHYSICAL-'+mode+'-'+day+'-'+phase+'-DIFF.json'),dict(full=a,physical=b));raise ValueError('physical complete prefix differs '+mode+' '+day+' '+phase)
    records.append(dict(mode=mode,day=day,phase=phase,off_original_native_state_orders_fills_QD_trusted_inputs_exact=True,full_physical_complete_state_and_R0_exact=True));print('PREFIX_PASS',mode,day,phase,flush=True)
 X.save(P/'TWO_DAY_GATE.json',dict(passed=True,records=records,runtime_sha256=X.sha(P/'jan_r0.py'),entry_sha256=X.sha(P/'run_january.py'),financial_events=0,cross_process_restart='Jan4 CLOSE checkpoint restored in new process beforeJan5',baseline_C10_technical_repair_history_preserved=True,normalization=['source/CID-derived hashes backed by raw trusted/snapshot/full projection body hash checks and comparison','known provider_fix1 software-only industry evidence metadata, no numeric change','OFF compares complete native account/audit/decisions/pending/F1/order/window/QD/underlying inputs, not old engineering exception/lifecycle narratives','physical compares complete same-code lifecycle/events/stages and R0 after exact necessary-stage hash reconstruction']))
 print('TWO_DAY_GATE_PASS',flush=True)
if __name__=='__main__':main()
