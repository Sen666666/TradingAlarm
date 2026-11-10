"""Frozen M7/v3 extension: append reviewed ordinary cash events only."""
from pathlib import Path
import sys,importlib.util,copy,json,collections,argparse
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;BASE=ROOT/'mainline_m7_downturn_q0_split_v3'
sp=importlib.util.spec_from_file_location('v4_frozen_v3',BASE/'engine.py');v3=importlib.util.module_from_spec(sp);sys.modules[sp.name]=v3;sp.loader.exec_module(v3)
read=v3.read;save=v3.save;sha=v3.sha;day=v3.day;pd=v3.pd;Blocked=v3.Blocked;D=v3.m7.D;dec=v3.m7.dec
BASE_SHA='35f8edfd8af9719b7878d2c0dcbbaebacd555a2f2c7201543456bc6747efd0d1'
assert sha(BASE/'engine.py')==BASE_SHA
FACT_PATH=ROOT/'retained_20241010_cash_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_20241010_TWO_V1.json'
FACT_SHA='627a13e0975d7afdc1890a77cf3da051ee01e32b5a4b8fb53b042ccbd3a06130'

def admit_cash(data,ev,checked):
 s=ev['sid'];dt=pd.Timestamp(ev['ex_date'])
 assert s in ('600535.SH','600750.SH') and ev['ex_date']=='2024-10-10' and ev['record_date']=='2024-10-09'
 assert pd.Timestamp(ev['record_date'])<dt<=pd.Timestamp(ev['pay_date'])
 assert dec(ev['d_source'])==D('.26' if s=='600535.SH' else '.50') and D(0)<=dec(ev['d_cash'])<=dec(ev['d_source'])
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
 assert day(prev.name)==ev['record_date'] and v3.m7.m3.valid(prev) and v3.m7.m3.valid(cur)
 assert v3.m7.m3.lineage(prev)==v3.m7.m3.lineage(cur)
 fo=dec(prev.adjustment_factor);fn=dec(cur.adjustment_factor);pc=dec(prev.raw_close)
 assert fo.is_finite() and fn.is_finite() and fo>0 and fn>0 and pc>dec(ev['d_source'])
 assert abs(fo*pc/(pc-dec(ev['d_source']))/fn-1)<D('1e-11')
 assert abs(fo/dec(ev['factor_old'])-1)<D('1e-11') and abs(fn/dec(ev['factor_new'])-1)<D('1e-11')
 data.events[(s,dt)]=dict(ev,factor_old=str(fo),factor_new=str(fn))
 data.admission.append(dict(sid=s,sector51=data.sid_sector[s],ex_date=day(dt),event_id=ev['economic_event_id_candidate'],status='BOUNDED_RESEARCH_NET80_ONLY',factor_bridge_verified=True,not_PIT=True,not_production_admission=True))

class Data(v3.Data):
 def __init__(self,end='2024-10-31'):
  super().__init__(end)
  assert sha(FACT_PATH)==FACT_SHA
  self.hashes[str(FACT_PATH)]=FACT_SHA;events=read(FACT_PATH)
  assert len(events)==2 and {e['sid'] for e in events}=={'600535.SH','600750.SH'}
  def checked(p,h):
   assert sha(Path(p))==h,('CASH_FACT_DRIFT',p);self.hashes[str(p)]=h
  for ev in events:admit_cash(self,ev,checked)
  for p in [O/'engine.py',O/'CONTRACT.md',O/'synthetic_cash.py']:self.hashes[str(p)]=sha(p)

EXCLUDED_INVENTORY={'SOURCE_HASHES','OUTPUT_HASHES','EVENT_ADMISSION'}
FUTURE_BLOCKER_DIAGNOSTICS={'BLOCKERS','ALL_TARGETS_BLOCKER_SCAN','UNCERTIFIED_DAY'}
def check_prefix(path,date):
 baseline=v3.BASE/'once_20241008' if date=='2024-10-08' else BASE/'once_20241031'
 excluded=EXCLUDED_INVENTORY|(FUTURE_BLOCKER_DIAGNOSTICS if date=='2024-10-09' else set())
 names=sorted(p.stem for p in baseline.glob('*.json') if p.stem not in excluded);checks={}
 for n in names:
  a=read(path/(n+'.json'));b=read(baseline/(n+'.json'));mode='exact_ordered'
  if a!=b and n=='AVAILABILITY_EVENTS':
   assert collections.Counter(json.dumps(r,sort_keys=True) for r in a)==collections.Counter(json.dumps(r,sort_keys=True) for r in b),('PREFIX_MISMATCH',date,n)
   mode='full_record_multiset_unordered_diagnostic'
  else:assert a==b,('PREFIX_MISMATCH',date,n)
  checks[n]=dict(comparison=mode,count=len(a) if hasattr(a,'__len__') else None)
 save(O/('PREFIX_QA_'+date.replace('-','')+'.json'),dict(result='PASS',through=date,baseline=str(baseline),families=checks,exclusions=sorted(excluded)))

class Engine(v3.Engine):
 def export(self,path):
  # Bypass prior wrappers' export routing only; keep all frozen economic exports.
  v3.m7.Engine.export(self,path)
  for date in ['2024-10-08','2024-10-09']:
   if Path(path).name=='checkpoint_'+date.replace('-',''):check_prefix(path,date)

old_source=v3.source
old_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08']"
new_dates="['2024-09-23','2024-09-27','2024-09-30','2024-10-08','2024-10-09']"
assert old_source.count(old_dates)==1
source=old_source.replace(old_dates,new_dates)
exec(compile(source,'CASH_V4_SAME_ATOMIC_LOOP_ADDED_1009_CHECKPOINT','exec'),globals())
def self_check():
 methods={n:getattr(Engine,n) is getattr(v3.Engine,n) for n in dir(v3.Engine) if not n.startswith('__') and callable(getattr(v3.Engine,n)) and n!='export'}
 assert all(methods.values()) and source.replace(new_dates,old_dates)==old_source
 return dict(result='PASS',method_identity=methods,only_loop_change='add_20241009_checkpoint',history_run=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check','run'],required=True);args=ap.parse_args();save(O/'STATIC_QA.json',self_check())
 if args.mode=='run':
  approval=read(O/'CONTRACT_APPROVAL.json');assert approval['approved'] and approval['engine_sha256']==sha(O/'engine.py') and approval['contract_sha256']==sha(O/'CONTRACT.md')
  qa=read(O/'SYNTHETIC_QA.json');assert qa['result']=='PASS' and qa['engine_sha256']==sha(O/'engine.py') and qa['contract_sha256']==sha(O/'CONTRACT.md')
  assert not (O/'RUN_STARTED.json').exists()
  prior=read(BASE/'RUN_STATUS.json');assert prior['days']==21 and prior['last']['day']=='2024-10-09'
  data=Data();save(O/'FROZEN_INPUTS.json',dict(hashes=data.hashes,base_engine_sha256=BASE_SHA,engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md')))
  save(O/'RUN_STARTED.json',dict(end='2024-10-31',time=str(pd.Timestamp.now(tz='UTC'))))
  e=run_loop(Engine(data));e.export(O/'once_20241031')
  save(O/'RUN_STATUS.json',dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,prefix_1008_pass=(O/'PREFIX_QA_20241008.json').exists(),prefix_1009_pass=(O/'PREFIX_QA_20241009.json').exists(),planned_end='2024-10-31',completed_horizon=bool(e.ledger and e.ledger[-1]['day']=='2024-10-31' and not e.blockers)))
  print(json.dumps(read(O/'RUN_STATUS.json')))
