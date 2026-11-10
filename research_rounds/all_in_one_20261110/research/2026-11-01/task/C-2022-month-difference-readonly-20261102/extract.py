"""Read registered final state only. No financial/event method is called."""
from pathlib import Path
import argparse, json, sys, hashlib
from dataclasses import asdict
O=Path(__file__).resolve().parent
BASE=O.parent/'C-2022-month-native-baseline-20261102'
CORE=O.parent/'C-rights-month-resume-v2-20261102'
sys.path.insert(0,str(CORE))
import resume_runtime_v2 as C
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,default=C.E.encode,ensure_ascii=False,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--arm',required=True);arm=p.parse_args().arm
 index=BASE/'CONTINUATION_CHECKPOINTS.json';rec=next(v for v in C.read(index)['accounts'] if v['arm']==arm)
 r=C.ContinuationRunner.restore(rec['checkpoint'],registry_sha=rec['trusted_registry_sha256'])
 before=C.FP.snapshot(r);a=r.account
 fields=['layers','trades','capital_meta','supports','exit_duties','inventory_map','rejections','fees_cny','dividend_income','dividend_receivable','share_ratio']
 account={k:getattr(a,k) for k in fields if hasattr(a,k)}
 out=dict(arm=arm,at=str(r.last_completed_event),account=account,fills=[asdict(f) for f in a.fills],results=r.results,certificates=r.authority.certificates,events=r.events,stock_sectors=a.market.sectors,account_field_names=list(a.__dict__),runner_field_names=list(r.__dict__))
 save(O/(arm+'-EXTRACT.json'),out)
 assert before==C.FP.snapshot(r),'export changed complete state'
 save(O/(arm+'-EXTRACT-CHECKS.json'),dict(passed=True,financial_events=0,complete_state_unchanged=True,certificates=len(r.authority.certificates),inputs={str(p):sha(p) for p in [index,Path(rec['checkpoint']),Path(rec['checkpoint']).with_suffix('.provenance.json'),Path(rec['registry']),Path(__file__),CORE/'resume_runtime_v2.py']},extract_sha256=sha(O/(arm+'-EXTRACT.json'))))
 print(arm,'READ_ONLY_EXTRACT_PASS',len(a.trades),len(a.layers),flush=True)
if __name__=='__main__':main()
