"""Independent narrow Q0 adapter audit, no historical simulation."""
import pathlib,copy,json,contextlib,io,ast,collections,hashlib
P=pathlib.Path(__file__).resolve().parent if '__file__' in globals() else pathlib.Path('mainline_m7_downturn_q0_split_v3').resolve()
source=(P/'synthetic_q0.py').read_text();source=source[:source.index("e.save(P/'SYNTHETIC_QA.json'")]
scope={'__file__':str(P/'synthetic_q0.py'),'__name__':'repeat_author'}
with contextlib.redirect_stdout(io.StringIO()):exec(compile(source,'author_repeat','exec'),scope)
e=scope['e'];fixture=scope['fixture'];D=scope['D'];sid=e.SID;dt=scope['dt'];record=scope['record'];checks=[]
def ok(n,v=True):
 assert v,n
 checks.append(n)
ok('author_tests_repeated',scope['out']['result']=='PASS')
facts=e.read(e.FACT_PATH);ev=facts[0];ok('fact_artifact_hash',e.sha(e.FACT_PATH)==e.FACT_SHA)
for p,h in ev['evidence_hashes'].items():ok('evidence_hash_'+pathlib.Path(p).name,e.sha(pathlib.Path(p))==h)
z=e.pd.read_parquet(ev['signal_path']);a=z.loc[e.RECORD_DATE];b=z.loc[e.EX_DATE]
res=D(str(a.adjustment_factor))*D(str(a.raw_close))*D(ev['split_ratio'])/(D(str(a.raw_close))-D(ev['d_source']))/D(str(b.adjustment_factor))-1
ok('independent_factor_formula',abs(res)<D('1e-11') and str(a.raw_close)=='286.0')
ok('independent_source_continuity',tuple(e.m7.m3.lineage(a))==tuple(e.m7.m3.lineage(b))==tuple(ev['source_lineage']))
terms=[r for r in e.read(pathlib.Path(ev['local_action_path']))['events'] if r['effective_date']==e.EX_DATE]
ok('local_action_terms',len(terms)==1 and D(terms[0]['split_ratio'])==D('1.30') and D(terms[0]['cash_per_old_share'])==D('2.50'))
# Additional scope edge cases, all expected Blocked rather than assert or silent no-op.
def reject(n,mutate):
 x=fixture();mutate(x)
 try:x.economic_preflight(dt,[])
 except e.Blocked:ok(n)
 else:raise AssertionError(n)
reject('consumed_ticket_blocked',lambda x:x.tickets[sid].update(status='CONSUMED'))
reject('zero_active_round_blocked',lambda x:x.active.update({sid:{'lots':[]}}))
reject('zero_claim_blocked',lambda x:x.claims.update({(sid,dt):{'amount':D(0)}}))
reject('missing_reviewed_event_blocked',lambda x:x.d.events.clear())
x=fixture();x.claims[(sid,dt)]={'amount':D(0)};before=copy.deepcopy(x.snapshots)
try:x.register_pay(record)
except e.Blocked:ok('record_claim_guard_before_registration',x.snapshots==before)
else:raise AssertionError('claim guard')
# Additional invalid numeric encodings at each location must be Blocked.
for location in ['ticket','observed','event_old','event_new']:
 for value in ['sNaN',{},[],True]:
  def mutate(x,location=location,value=value):
   if location=='ticket':x.tickets[sid]['current_factor']=value
   elif location=='observed':
    zz=x.d.z(sid,dt).to_dict();zz['adjustment_factor']=value;x.d.z=lambda s,d:zz
   else:x.d.events[(sid,dt)]['factor_old' if location=='event_old' else 'factor_new']=value
  reject('independent_invalid_'+location+'_'+str(value),mutate)
# Corrupt inherited behavior must be caught by new postconditions.
original=e.m7.Engine.economic_preflight
for label in ['cash','ticket']:
 def corrupt(self,d,pending):
  original(self,d,pending)
  if label=='cash':self.cash+=D(1)
  else:self.tickets[sid]['nav0']+=D(1)
 e.m7.Engine.economic_preflight=corrupt
 reject('postcondition_'+label,lambda x:None)
e.m7.Engine.economic_preflight=original
# Actual atomic catch after successful bridge+accrual restores factor/date/equity.
tree=ast.parse(e.source);assigns=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)]
lists={}
for n in assigns:
 if isinstance(n.targets[0],ast.Name) and n.targets[0].id in ['keys','logs'] and isinstance(n.value,ast.List):lists[n.targets[0].id]=ast.literal_eval(n.value)
for n in ast.walk(tree):
 if isinstance(n,ast.AugAssign) and isinstance(n.target,ast.Name) and n.target.id in lists:lists[n.target.id]+=ast.literal_eval(n.value)
class Atomic(e.Engine):
 def exit_open(self,*a):pass
 def alloc_open(self,*a):pass
 def close(self,*a):raise e.Blocked('AFTER_Q0_BRIDGE_TEST')
 def scan_restored_targets(self,*a):return []
x=fixture();x.__class__=Atomic
for name in lists['keys']:
 if not hasattr(x,name):setattr(x,name,0 if name=='seq' else set() if name in ['_donor_sectors','_probe_receiver_sectors'] else {})
for name in lists['logs']:
 if not hasattr(x,name):setattr(x,name,[])
x.blockers=[];x.d.cal=e.pd.DatetimeIndex([record,dt]);x.d.days=[dt];before={k:copy.deepcopy(getattr(x,k)) for k in lists['keys']+lists['logs']}
with contextlib.redirect_stdout(io.StringIO()):e.run_loop(x,False)
ok('actual_atomic_rollback',all(getattr(x,k)==v for k,v in before.items()) and len(x.blockers)==1)
# Check prefix gating only, without writing/reexporting any historical outputs.
oldexport=e.m7.Engine.export;oldcheck=e.check_prefix;calls=[]
e.m7.Engine.export=lambda self,p:None;e.check_prefix=lambda p:calls.append(pathlib.Path(p).name)
x=fixture();x.export(P/'once_20241031');x.export(P/'checkpoint_20241009');x.export(P/'checkpoint_20241008')
ok('checkpoint_only_prefix_gate',calls==['checkpoint_20241008']);e.m7.Engine.export=oldexport;e.check_prefix=oldcheck
prefix=P.parent/'mainline_m7_downturn_extension_design_v1/checkpoint_20241008'
for name in e.FAMILIES:
 aa=e.read(prefix/(name+'.json'));bb=e.read(e.BASE/'once_20241008'/(name+'.json'))
 ok('existing_actual_prefix_'+name,aa==bb or name=='AVAILABILITY_EVENTS' and collections.Counter(json.dumps(q,sort_keys=True) for q in aa)==collections.Counter(json.dumps(q,sort_keys=True) for q in bb))
ok('unchanged_alpha_and_atomic',e.self_check()['atomic_loop_source_identical'] and all(e.self_check()['economic_method_identity'].values()))
out=dict(result='PASS',total=len(checks),checks=checks,author_tests_repeated=scope['out']['total'],engine_sha256=e.sha(P/'engine.py'),contract_sha256=e.sha(P/'CONTRACT.md'),fact_sha256=e.sha(e.FACT_PATH),factor_relative_residual=str(res),history_run=False,official_notice_review='Existing reviewed official PDF hash independently verified; dates and terms are bound by frozen fact artifact. PDF text was not independently re-extracted in this audit.')
print(json.dumps(out))
