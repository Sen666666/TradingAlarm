"""One reviewed fact-only extension. No economic-rule changes or parameter search."""
from pathlib import Path
import argparse,json,shutil,hashlib,sys
sys.dont_write_bytecode=True
import ablation_engine as impl
O=impl.O;BASE=impl.BASE;base=impl.base
PACK=O/'facts_revision_2';EVENT=O.parent/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_603083_V1.json'
EVENT_SHA='30bee171a5055cfabd8785cad3d62615ea2680aceab5eb0893124e54751cccb8'
EXTRA_FAMILIES=['RETRY_TICKETS','RETAINED_AT_END','ADDITIONAL_EXIT','ADD_QUANTITY_LIMITS','FULL_CAP_VIOLATIONS']

def prepare():
 assert base.sha(EVENT)==EVENT_SHA;PACK.mkdir(exist_ok=False)
 for name in ['CLASSIFICATION_ALL1709.csv','MAPPING_SOURCE_HASHES.json','FROZEN_CONTRACT.md','engine.py','SYNTHETIC_QA.json','synthetic_joint.py']:
  shutil.copyfile(BASE/name,PACK/name)
 old=base.read(BASE/'ADDITIONAL_REVIEWED_EVENTS.json');new=base.read(EVENT);assert len(new)==1 and new[0]['sid']=='603083.SH' and new[0]['ex_date']=='2024-09-27'
 assert (new[0]['sid'],new[0]['ex_date']) not in {(e['sid'],e['ex_date']) for e in old}
 base.save(PACK/'ADDITIONAL_REVIEWED_EVENTS.json',old+new)
 base.save(PACK/'FACT_REVISION.json',dict(parent_baseline=str(BASE),parent_additional_events_sha=base.sha(BASE/'ADDITIONAL_REVIEWED_EVENTS.json'),added_adapter=str(EVENT),added_adapter_sha=EVENT_SHA,economic_rule_changes=0,existing_completed_prefixes_must_replay_exactly=True,scope='ACTUAL_HELD_PENDING_603083_ONLY'))
 base.save(PACK/'FACT_FREEZE.json',dict(files={str(p):base.sha(p) for p in PACK.iterdir() if p.is_file()},runner_sha=base.sha(__file__),unchanged_implementation_hashes=base.read(O/'EXECUTION_FREEZE.json')['implementation_hashes'],event_sha=EVENT_SHA))
 print('FACT_PACK_PREPARED',PACK,flush=True)

class ReplayEngine(impl.AblationEngine):
 def __init__(self,data,arm,out,prior):
  super().__init__(data,arm);self.out=out;self.prior=prior;self.replay_date=base.read(prior/'RUN_STATUS.json')['certified_through'];self.replay_passed=False
 def close(self,d,prev):
  pending=super().close(d,prev)
  if impl.day(d)==self.replay_date:
   self.pending=pending;path=self.out/'prior_prefix_replay';self.export_ablation(path);checks={}
   for name in impl.FAMILIES+EXTRA_FAMILIES:
    before=base.read(self.prior/'full_prefix'/(name+'.json'));after=base.read(path/(name+'.json'));assert before==after,('FACT_ONLY_PRIOR_PREFIX_CHANGED',self.arm.name,name);checks[name]=len(after)
   base.save(self.out/'FACT_PREFIX_REPLAY_QA.json',dict(result='PASS',certified_through=self.replay_date,exact_records=checks,economic_rule_changes=0));self.replay_passed=True
   print('FACT_PREFIX_REPLAY_PASS '+self.arm.name+' '+self.replay_date,flush=True)
  return pending

def run(arms):
 freeze=base.read(PACK/'FACT_FREEZE.json');assert base.sha(__file__)==freeze['runner_sha'];assert base.sha(EVENT)==freeze['event_sha']
 for p,h in {**freeze['files'],**freeze['unchanged_implementation_hashes']}.items():assert base.sha(p)==h,('FROZEN_INPUT_DRIFT',p)
 base.O=PACK # Data files only. base.P remains the original common research root.
 data=base.Data('2024-10-31');original=base.read(O/'EXECUTION_FREEZE.json')['data_hashes'];shared={p:h for p,h in original.items() if not Path(p).is_relative_to(BASE)}
 assert all(data.hashes.get(p)==h for p,h in shared.items()),'SHARED_PRICE_SIGNAL_OR_ECONOMIC_INPUT_CHANGED'
 base.save(PACK/'DATA_FREEZE.json',dict(data_hashes=data.hashes,unchanged_shared_input_count=len(shared),new_event_count=1))
 for arm in arms:
  impl.arm_config(arm);out=O/f'run_{arm}_fact2';out.mkdir(exist_ok=False);prior=O/f'run_{arm}_v1';e=ReplayEngine(data,arm,out,prior).run_ablation(out);assert e.replay_passed
  base.save(out/'RUN_STATUS.json',dict(arm=arm,fact_revision=2,days=len(e.ledger),orders=len(e.orders),certified_through=e.ledger[-1]['day'] if e.ledger else None,blockers=e.blockers,last=e.ledger[-1] if e.ledger else None,economic_rule_changes=0))
  print('FACT_RESULT '+arm+' '+json.dumps(dict(days=len(e.ledger),orders=len(e.orders),blockers=e.blockers,last=e.ledger[-1]),ensure_ascii=False),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--run',action='store_true');ap.add_argument('--arms',default='A,B,D,E,F');args=ap.parse_args()
 assert args.prepare != args.run
 if args.prepare:prepare()
 else:run(args.arms.split(','))
