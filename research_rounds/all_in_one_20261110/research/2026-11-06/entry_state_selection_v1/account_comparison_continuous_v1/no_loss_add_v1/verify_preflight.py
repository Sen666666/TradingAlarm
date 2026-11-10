"""Verify completed bounded outputs and independently replay cost journal only."""
from pathlib import Path
import json,pickle,hashlib,sys,gzip
from decimal import Decimal as D
from profit_gate import RemainingCostBook
O=Path(__file__).resolve().parent
p=Path(sys.argv[1]).resolve();assert json.loads((p/'DONE.json').read_text())['completed'];gate=json.loads((p/'RESTART_OPEN_PERTURB_GATE.json').read_text());assert gate['passed'] and gate['normal_sha256']==gate['restored_poison_sha256']
cp=p/'latest_checkpoint/checkpoint.pkl';b=cp.read_bytes();h=hashlib.sha256(b).hexdigest();m=json.loads(cp.with_suffix('.json').read_text());prov=json.loads(cp.with_suffix('.provenance.json').read_text());assert h==m['sha256']==prov['checkpoint_sha256'];x=pickle.loads(b)
a=x['accounts']['PVR'];book=x['runner']['cost_books']['PVR'];assert book.journal_cursor==len(a['journal']);fresh=RemainingCostBook()
for r in a['journal']:fresh.apply(r)
assert fresh.states==book.states and fresh.processed==book.processed
for sid,s in fresh.states.items():assert s['qty']==sum(r['qty']for r in a['layers']if r['sid']==sid)
events=x['runner']['profit_gate_events'];assert any(not e['allowed']for e in events)
report=dict(checkpoint_sha256=h,cursor=book.journal_cursor,journal_rows=len(a['journal']),processed=book.processed,cost_states=len(book.states),independent_full_journal_cost_replay_equal=True,remaining_quantity_equals_layers=True,restart_poison_equal=True,gate_decisions=len(events),gate_negative_verdicts=sum(not e['allowed']for e in events),first_negative_verdict=next(e for e in events if not e['allowed']),new_accounts=0)
(p/'INDEPENDENT_COST_RESTART_CHECK.json').write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report,indent=2,default=str))
