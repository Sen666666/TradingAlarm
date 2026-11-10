"""Final saved-state checks; no runner construction or market events."""
from pathlib import Path
import sys,pickle,json,hashlib,gzip
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'c1-drawdown-capacity-20261101'));import adapter_c1 as C
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 reports=[]
 for ref in ['Bdiag','C1']:
  root=O/'runs'/ref;assert read(root/'DONE.json')['completed'];prefix=read(root/'first-Jan3/checkpoint.provenance.json')['engine_identity'];freeze=read(root/'FREEZE.json')['sources'];assert all(sha(p)==h for p,h in freeze.items())
  assert read(root/'GATES.json')['passed'] and read(root/'VERIFIED_IMPORT.json')['passed']
  for d in ['2023-03-31','2023-06-30','2023-09-28','2023-12-29']:
   path=root/('checkpoint-'+d+'.pkl');meta=read(path.with_suffix('.json'));prov=read(path.with_suffix('.provenance.json'));assert sha(path)==meta['sha256']==prov['checkpoint_sha256'];assert prov['engine_identity']==prefix
   p=pickle.loads(path.read_bytes());a=p['accounts']['B'];b=a['budget'];assert str(p['last_completed_event'])==d+' 15:10:00+08:00'
   assert p['source_freeze']==meta['source_freeze']==freeze and p['quarter_or_budget_reset'] is False
   assert all(sum(x.qty for x in b.lots if x.stock==sid)==pos.shares for sid,pos in a['positions'].items())
   assert abs(b.nav-float(a['current_nav']))<1e-6 and abs(b.cash-b.resources()[2]-float(a['available']))<1e-6
   if ref=='C1':b.c1.validate();assert str(b.c1.decision_at)==d+'T15:10:00+08:00' and b.c1.high>=C.D(1000000) and b.c1.decision_nav==a['current_nav'];assert len([x for x in p['runner']['c1_rows'] if str(x['at'].date())<=d])==len(p['runner']['daily'])
   reports.append(dict(policy=ref,day=d,SHA256=sha(path),identity_exact=True,NAV=str(a['current_nav']),cumulative_trades=len(a['trades']),daily_rows=len(p['runner']['daily']),C1=C.J.W.canon(getattr(b,'c1',None)),share_and_spendable_bridge_zero=True,no_quarter_reset=True))
 save=O/'FINAL_CHECKPOINT_VERIFICATION.json';C.IO.write_json(save,dict(passed=True,quarter_checkpoints=reports,total=8,old2022_not_replayed=True,old_provenance_not_backfilled=True,all_frozen_sources_unchanged=True));print('ALL8_CHECKPOINTS_PASS',flush=True)
if __name__=='__main__':main()
