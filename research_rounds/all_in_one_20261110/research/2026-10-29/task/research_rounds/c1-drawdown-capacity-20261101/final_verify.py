"""Read-only full H path and quarterly checkpoint identity/account-state checks."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,pickle,hashlib
import adapter_c1 as C
O=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def main():
 out=[]
 for win in ['2022','2025_26']:
  p=O/'runs'/win;assert read(p/'DONE.json')['completed'];frozen=read(p/'FREEZE.json')['sources'];changed=[f for f,h in frozen.items() if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=h];assert not changed,changed
  cs=read(p/'pair/C1.json')['decisions'];ds=rows(p/'pair/daily.jsonl.gz');assert len(cs)==len(ds)==242;cap={x['at'][:10]:x for x in cs};daily={x['at'][:10]:x for x in ds};h=D(1000000)
  for c,d in zip(cs,ds):
   assert c['at'][:10]==d['at'][:10];nav=D(d['nav']);h=max(h,nav);dd=max(D(0),1-nav/h);frac=D('.1')+D('.5')*max(D(0),1-dd/D('.2'))
   assert D(c['high'])==h and D(c['decision_nav'])==nav and D(c['drawdown'])==dd and D(c['fraction'])==frac
  provenances=[]
  for file in sorted(p.glob('checkpoint-*.pkl')):
   prov=read(file.with_suffix('.provenance.json'));assert hashlib.sha256(file.read_bytes()).hexdigest()==prov['checkpoint_sha256']
   identity=prov['engine_identity'];assert identity['trading_class']['module_sha256']==hashlib.sha256(Path(C.__file__).read_bytes()).hexdigest();assert identity['trading_class']['class_name']=='Runner'
   blob=pickle.loads(file.read_bytes());day=str(blob['last_completed_event'].date());a=blob['accounts']['B'];s=a['budget'].c1;s.validate();assert s.mode=='C1' and str(s.high)==cap[day]['high'] and a['current_nav']==D(daily[day]['nav']);assert len(blob['runner']['c1_rows'])==list(daily).index(day)+1
   assert {sid:v.shares for sid,v in a['positions'].items()}==daily[day]['positions'];assert blob['source_freeze']==frozen
   provenances.append(dict(file=str(file),day=day,H=str(s.high),decision_NAV=str(s.decision_nav),fraction=str(s.fraction),cumulative_close_count=len(blob['runner']['c1_rows']),identity_bound=True))
  assert len(provenances)==4
  out.append(dict(window=win,rows=242,independent_closing_highwater_and_fraction_exact=True,all_frozen_sources_unchanged=True,quarter_checkpoints=provenances,original_native_balance_verification=read(O/'analysis'/win/'COMPLETION.json')))
 C.IO.write_json(O/'FINAL_VERIFICATION.json',dict(passed=True,new_history_runs=2,baseline_history_runs=0,windows=out));print('FINAL_VERIFIED2windows484closes8quarter_checkpoints')
if __name__=='__main__':main()
