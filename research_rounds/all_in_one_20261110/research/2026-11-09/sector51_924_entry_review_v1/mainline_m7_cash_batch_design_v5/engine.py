"""Exact19-event cash batch; existing M7/v4 execution unchanged. Review only."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,re
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;BASE=O.parent/'mainline_m7_november_boundary_design_v4'
sp=importlib.util.spec_from_file_location('cash_batch_v4',BASE/'engine.py');v=importlib.util.module_from_spec(sp);sys.modules[sp.name]=v;sp.loader.exec_module(v)
D=v.D;dec=v.dec;pd=v.pd;read=v.read;save=v.save;sha=v.sha;day=v.day;Blocked=v.Blocked;v4=v.v4
MANIFEST_SHA='bb3372d35635a030b65d48593c057bf65010d6f2f3c227436d16e7479301dff7'
def manifest():
 assert sha(O/'EXACT_CASH_BATCH_MANIFEST.json')==MANIFEST_SHA,'BATCH_MANIFEST_DRIFT'
 m=read(O/'EXACT_CASH_BATCH_MANIFEST.json');assert sha(BASE/'engine.py')==m['base_engine_sha256'] and sha(BASE/'CONTRACT.md')==m['base_contract_sha256']
 rows=m['events'];assert len(rows)==19 and len({(r['sid'],r['ex_date']) for r in rows})==19
 assert m['q0_factor_only_enabled'] is False and m['cash_model']=='UNCHANGED_NET80'
 return m
ALLOWED={(r['sid'],r['ex_date'],r['economic_event_id_candidate']) for r in manifest()['events']}
def validate_primary(ev):
 p=ev['primary_evidence'];path=Path(p['path']);assert sha(path)==p['sha256'],'PRIMARY_SOURCE_DRIFT'
 if p['kind']=='ISSUER_PDF':
  assert ev['sid']=='300760.SZ' and path.read_bytes().startswith(b'%PDF');return
 assert p['kind']=='OFFICIAL_CNINFO_RAW'
 raw=read(path);assert raw['sid']==ev['sid'] and raw['requested_code']==ev['sid'][:6] and raw['params']['scode']==ev['sid'][:6] and raw.get('target_ex_date',ev['ex_date'])==ev['ex_date'] and raw['endpoint']=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139' and raw['transport']['status_code']==200
 records=[r for r in raw['raw']['records'] if r.get('F020D')==ev['ex_date']];assert len(records)==1
 r=records[0];assert r==p['record'] and r['F006D']==ev['disclosure_date'] and r['F018D']==ev['record_date'] and r['F023D']==ev['pay_date']
 assert r['F006D']<=r['F018D']<r['F020D']<=r['F023D']
 amounts=re.findall(r'10派([0-9.]+)元',r['F007V']);assert len(amounts)==1 and dec(amounts[0])/10==dec(r['F012N'])/10==dec(ev['d_cash'])
 assert r.get('F010N') in [None,0] and r.get('F011N') in [None,0] and not any(w in r['F007V'] for w in ['送','转增','配股'])
# Economic/date/lineage/factor body identical to approved loader. Only exact scope and evidence-container validation differ.
loader_source=v.loader_source
old_scope="assert '2024-10-11'<=ev['ex_date']<='2024-10-31' and ev['event_type']=='PURE_CASH'"
new_scope="assert '2024-11-01'<=ev['ex_date']<='2024-12-31' and ev['event_type']=='PURE_CASH' and (s,ev['ex_date'],ev['economic_event_id_candidate']) in ALLOWED"
old_evidence=" assert ev.get('notice',{}).get('pdf_path')\n paths[ev['notice']['pdf_path']]=ev['notice']['pdf_sha256']"
new_evidence=" validate_primary(ev)\n primary=ev['primary_evidence'];paths[primary['path']]=primary['sha256']"
assert loader_source.count(old_scope)==1 and loader_source.count(old_evidence)==1
batch_loader_source=loader_source.replace(old_scope,new_scope).replace(old_evidence,new_evidence)
exec(compile(batch_loader_source,'CASH_BATCH_EXACT_SCOPE_PRIMARY_CONTAINER_ONLY','exec'),globals())
class Data(v.Data):
 def __init__(self,end=v.b.END):
  m=manifest();super().__init__(end)
  def checked(p,h):assert sha(Path(p))==h,('BATCH_SOURCE_DRIFT',p);self.hashes[str(p)]=h
  for ev in m['events']:
   if (ev['sid'],pd.Timestamp(ev['ex_date'])) in self.events:
    assert ev['sid']=='300760.SZ';old=self.events[(ev['sid'],pd.Timestamp(ev['ex_date']))]
    for k in ['record_date','ex_date','pay_date','d_cash','d_source','d_ref','factor_old','factor_new']:assert old[k]==ev[k],('INHERITED_EVENT_MISMATCH',k)
    continue
   admit_cash(self,ev,checked,ALLOWED)
  for n in ['engine.py','CONTRACT.md','EXACT_CASH_BATCH_MANIFEST.json']:self.hashes[str(O/n)]=sha(O/n)
def check_prefix(path):
 m=v.validate_inputs();v.b.require_exact((p.stem for p in Path(path).glob('*.json')),m['required_json_families'],'NOV6_PREFIX_FAMILY_SET');checks={}
 for n in m['comparison_families']:
  a=read(Path(path)/(n+'.json'));z=read(v.BASE/'once_20260630'/(n+'.json'));same=a==z
  if n=='AVAILABILITY_EVENTS':same=collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in z)
  assert same,('NOV6_PREFIX_MISMATCH',n);checks[n]='PASS'
 save(O/'PREFIX_QA_20241106.json',dict(result='PASS',families=checks,excluded_inventory=m['excluded_inventory'],sealed_future_failure_diagnostics=m['failure_diagnostics']))
class Engine(v.Engine):
 def run(self,checkpoint=True):return run_loop(self,checkpoint)
 def export(self,path):
  v.b.v6.v5.v4.v3.m7.Engine.export(self,path)
  if Path(path).name=='checkpoint_20241106':assert not self.paused_new_requests and not self.execution_boundary_log;check_prefix(path)
  if self.paused_new_requests or self.execution_boundary_log:
   save(Path(path)/'PAUSED_NEW_REQUESTS.json',self.paused_new_requests);save(Path(path)/'EXECUTION_BOUNDARY_LOG.json',self.execution_boundary_log)
   save(Path(path)/'OUTPUT_HASHES.json',{p.name:sha(p) for p in Path(path).iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
source=v.source
exec(compile(source,'UNCHANGED_V4_ATOMIC_LOOP_NEW_OUTPUT_DIRECTORY','exec'),globals())
def self_check():
 manifest();v.self_check();assert batch_loader_source.replace(new_scope,old_scope).replace(new_evidence,old_evidence)==loader_source
 names=[n for n in dir(v.Engine) if not n.startswith('__') and callable(getattr(v.Engine,n)) and n not in ['export','run']];assert all(getattr(Engine,n) is getattr(v.Engine,n) for n in names)
 assert source==v.source
 return dict(result='PASS',history_run=False,unchanged_economic_execution_methods=names,only_loader_changes=['exact19NovDec_event_scope','hash_bound_genuinePDF_or_officialCNINFO_JSON_evidence_container'],cash_methods_identical=all(getattr(Engine,n) is getattr(v.Engine,n) for n in ['accrue','register_pay','economic_preflight','alloc_open','exit_open','close']),q0_factor_only_runtime_enabled=False)
def authorized_run():
 approval=read(O/'CONTRACT_APPROVAL.json');assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md') and approval['manifest_sha256']==MANIFEST_SHA
 qa=read(O/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==sha(O/'engine.py') and qa['contract_sha256']==sha(O/'CONTRACT.md') and qa['manifest_sha256']==MANIFEST_SHA
 assert not (O/'RUN_STARTED.json').exists(),'ONE_RUN_ONLY'
 self_check();data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md'),manifest_sha256=MANIFEST_SHA))
 save(O/'RUN_STARTED.json',dict(time=str(pd.Timestamp.now(tz='UTC')),planned_end=v.b.END))
 eng=Engine(data).run();eng.export(O/'once_20260630')
 status=dict(days=len(eng.ledger),orders=len(eng.orders),blockers=eng.blockers,last=eng.ledger[-1] if eng.ledger else None,prefix_1106_pass=(O/'PREFIX_QA_20241106.json').exists(),planned_end=v.b.END,completed_horizon=bool(eng.ledger and eng.ledger[-1]['day']==v.b.END and not eng.blockers))
 save(O/'RUN_STATUS.json',status);return status
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],default='check');args=ap.parse_args()
 if args.mode=='check':print(json.dumps(self_check()))
 else:print(json.dumps(authorized_run()))
