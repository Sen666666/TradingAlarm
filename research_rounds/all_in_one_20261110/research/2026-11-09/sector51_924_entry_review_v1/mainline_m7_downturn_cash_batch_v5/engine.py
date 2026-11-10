"""Frozen M7/v4 extension: exact manifest-bound ordinary cash batch only."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;BASE=ROOT/'mainline_m7_downturn_cash_v4'
sp=importlib.util.spec_from_file_location('v5_frozen_v4',BASE/'engine.py');v4=importlib.util.module_from_spec(sp);sys.modules[sp.name]=v4;sp.loader.exec_module(v4)
read=v4.read;save=v4.save;sha=v4.sha;day=v4.day;pd=v4.pd;Blocked=v4.Blocked;D=v4.D;dec=v4.dec
BASE_SHA='6b7c9c2dd8c8fccc27da99d67c47faf7cecac011e2863c1359b05b46b96fdb04'
assert sha(BASE/'engine.py')==BASE_SHA
MANIFEST_PATH=O/'REVIEWED_BATCH_MANIFEST.json'
MANIFEST_SHA='d72c66d16205b77e356276ecb7f1e541aa2dee5ad7f87e7bb1d0e018ff0d76d0'

def admit_cash(data,ev,checked,allowed):
 s=ev['sid'];dt=pd.Timestamp(ev['ex_date'])
 assert (s,ev['ex_date'],ev['economic_event_id_candidate']) in allowed
 assert '2024-10-11'<=ev['ex_date']<='2024-10-31' and ev['event_type']=='PURE_CASH'
 assert pd.Timestamp(ev['record_date'])<dt<=pd.Timestamp(ev['pay_date'])
 assert dec(ev['d_source']).is_finite() and dec(ev['d_source'])>0 and dec(ev['d_cash']).is_finite() and D(0)<=dec(ev['d_cash'])<=dec(ev['d_source'])
 paths=dict(ev.get('evidence_hashes',{}))
 for stem in ['source_fact','local_action','signal']:
  if ev.get(stem+'_path'):paths[ev[stem+'_path']]=ev[stem+'_sha256']
 assert ev.get('notice',{}).get('pdf_path')
 paths[ev['notice']['pdf_path']]=ev['notice']['pdf_sha256']
 for p,h in paths.items():checked(p,h)
 if dt>data.end:return
 assert (s,dt) not in data.events,('DUPLICATE_EVENT',s,dt)
 terms=[a for a in data.actions[s]['events'] if a['effective_date']==ev['ex_date']];assert len(terms)==1
 assert dec(terms[0]['split_ratio'])==1 and dec(terms[0]['cash_per_old_share'])==dec(ev['d_source'])
 z=data.raw[s];prev=z[z.index<dt].iloc[-1];cur=z.loc[dt]
 assert day(prev.name)==ev['record_date'] and v4.v3.m7.m3.valid(prev) and v4.v3.m7.m3.valid(cur)
 assert v4.v3.m7.m3.lineage(prev)==v4.v3.m7.m3.lineage(cur)
 fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);pc=dec(prev.raw_close)
 assert fo.is_finite() and fn.is_finite() and fo>0 and fn>0 and pc>dec(ev['d_source'])
 assert abs(fo*pc/(pc-dec(ev['d_source']))/fn-1)<D('1e-11')
 assert abs(fo/dec(ev['factor_old'])-1)<D('1e-11') and abs(fn/dec(ev['factor_new'])-1)<D('1e-11')
 data.events[(s,dt)]=dict(ev,factor_old=str(fo),factor_new=str(fn))
 data.admission.append(dict(sid=s,sector51=data.sid_sector[s],ex_date=day(dt),event_id=ev['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))

def manifest_records(manifest,checked):
 assert manifest['schema']=='EXACT_REVIEWED_PURE_CASH_BATCH_V1'
 assert manifest['earliest_ex_date']=='2024-10-11' and manifest['latest_ex_date']=='2024-10-31'
 allowed={(r['sid'],r['ex_date'],r['economic_event_id_candidate']) for r in manifest['events']}
 assert len(allowed)==len(manifest['events']) and allowed
 events=[]
 for adapter in manifest['adapters']:
  checked(adapter['path'],adapter['sha256']);events+=read(Path(adapter['path']))
 assert len(events)==len(allowed) and {(r['sid'],r['ex_date'],r['economic_event_id_candidate']) for r in events}==allowed
 assert len({(r['sid'],r['ex_date']) for r in events})==len(events)
 return events,allowed

class Data(v4.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  assert sha(MANIFEST_PATH)==MANIFEST_SHA
  self.hashes[str(MANIFEST_PATH)]=MANIFEST_SHA
  def checked(p,h):
   assert sha(Path(p))==h,('CASH_FACT_DRIFT',p);self.hashes[str(p)]=h
  events,allowed=manifest_records(read(MANIFEST_PATH),checked)
  for ev in events:admit_cash(self,ev,checked,allowed)
  for p in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_batch.py']:self.hashes[str(p)]=sha(p)

EXCLUDED_INVENTORY={'SOURCE_HASHES','OUTPUT_HASHES','EVENT_ADMISSION'}
FUTURE_BLOCKER_DIAGNOSTICS={'BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY'}
def check_prefix(path,date):
 baseline=v4.v3.BASE/'once_20241008' if date=='2024-10-08' else v4.BASE/'once_20241031' if date=='2024-10-09' else BASE/'once_20241031'
 excluded=EXCLUDED_INVENTORY|(FUTURE_BLOCKER_DIAGNOSTICS if date in ('2024-10-09','2024-10-10') else set())
 names=sorted(p.stem for p in baseline.glob('*.json') if p.stem not in excluded);checks={}
 for n in names:
  a=read(path/(n+'.json'));b=read(baseline/(n+'.json'));mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('PREFIX_MISMATCH',date,n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('PREFIX_MISMATCH',date,n)
  checks[n]=dict(comparison=mode,count=len(a) if hasattr(a,'__len__') else None)
 save(O/('PREFIX_QA_'+date.replace('-','')+'.json'),dict(result='PASS',through=date,baseline=str(baseline),families=checks,exclusions=sorted(excluded)))

class Engine(v4.Engine):
 def export(self,path):
  # Bypass prior wrappers' export routing only; keep all frozen economic exports.
  v4.v3.m7.Engine.export(self,path)
  for date in ['2024-10-08','2024-10-09','2024-10-10']:
   if Path(path).name=='checkpoint_'+date.replace('-',''):check_prefix(path,date)

old_source=v4.source
old_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09']"
new_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09','2024-10-10']"
assert old_source.count(old_dates)==1
source=old_source.replace(old_dates,new_dates)
exec(compile(source,'CASH_V5_SAME_ATOMIC_LOOP_ADDED_1010_CHECKPOINT','exec'),globals())
def self_check():
 methods={n:getattr(Engine,n) is getattr(v4.Engine,n) for n in dir(v4.Engine) if not n.startswith('__') and callable(getattr(v4.Engine,n)) and n!='export'}
 assert all(methods.values()) and source.replace(new_dates,old_dates)==old_source
 return dict(result='PASS',method_identity=methods,only_loop_change='add_20241010_checkpoint',history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args();save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  approval=read(O/'CONTRACT_APPROVAL.json');assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md')
  qa=read(O/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==sha(O/'engine.py') and qa['contract_sha256']==sha(O/'CONTRACT.md')
  facts_qa=read(O/'FACTS_LOADER_QA.json');assert facts_qa['result']=='PASS' and facts_qa['manifest_sha256']==MANIFEST_SHA
  assert not (O/'RUN_STARTED.json').exists()
  prior=read(BASE/'RUN_STATUS.json');assert prior['days']==22 and prior['last']['day']=='2024-10-10'
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,base_engine_sha256=BASE_SHA,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')))
  save(O/'RUN_STARTED.json',dict(end='2024-10-31',time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20241031')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_1008_pass=(O/'PREFIX_QA_20241008.json').exists(),prefix_1009_pass=(O/'PREFIX_QA_20241009.json').exists(),prefix_1010_pass=(O/'PREFIX_QA_20241010.json').exists(),planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))
