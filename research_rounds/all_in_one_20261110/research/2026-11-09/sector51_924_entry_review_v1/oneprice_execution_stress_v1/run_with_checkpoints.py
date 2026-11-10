"""Output-only driver for the frozen simulator; additional dated exports, no rule changes."""
from stress_engine import *
ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--prior');ap.add_argument('--checkpoint',action='append',default=[]);ap.add_argument('--gate-off',action='store_true');args=ap.parse_args()
out=ROOT/args.output;f=read(out/'FREEZE.json');assert f['gate_enabled']==(not args.gate_off);assert f['source_facts']==str(FACTS)
assert all(sha(p)==h for p,h in {**f['source_hashes'],**f['scenario_hashes']}.items())
seal=out/'CHECKPOINT_DRIVER_SEAL.json';assert not seal.exists()
save(seal,dict(driver=str(Path(__file__).resolve()),driver_sha256=sha(__file__),additional_checkpoints=args.checkpoint,created_before_run=True,economic_rule_changes=0))
d=b.Data();assert d.hashes==f['source_hashes'];e=StressEngine(d,not args.gate_off);e.output_root=out
e.run(checkpoints=sorted(set(['2024-09-23','2024-09-25']+args.checkpoint)),prior=Path(args.prior) if args.prior else None);e.export(out/'full_20241031_once')
status=dict(scope='CONDITIONAL_EXPOST_SCENARIO_NOT_LIVE_EXECUTION_OR_RETURN_BOUND',certified_through=e.ledger[-1]['day'] if e.ledger else None,days=len(e.ledger),orders=len(e.orders),no_fills=len(e.nofills),blockers=e.blockers,last=e.ledger[-1] if e.ledger else None)
save(out/'RUN_STATUS.json',status);print(json.dumps(status,ensure_ascii=False))
