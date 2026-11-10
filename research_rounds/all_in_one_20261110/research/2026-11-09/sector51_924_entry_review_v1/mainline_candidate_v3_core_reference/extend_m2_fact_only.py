"""Authorized M2 fact-only extension; all economic methods are frozen M2."""
import engine as e
import copy,json
P=e.O/'m2_fact_extension_20241008';P.mkdir(exist_ok=True)
assert not (P/'RUN_STARTED.json').exists()
e.save(P/'RUN_STARTED.json',dict(parent_authorized_fact_extension=True,only_new_fact='300870 record09-30/ex-pay10-08',M2_engine_sha256=e.sha(e.V2/'engine.py'),M3_economic_methods_used=False))
d=e.Data();all_days=d.days.copy();d.days=all_days[all_days<=e.pd.Timestamp('2024-09-30')];a=e.m2.Engine(d);e.run_loop(a,False);a.export(P/'prefix_20240930');checks={}
for name in e.m2.BASE_FAMILIES+['AVAILABILITY_EVENTS','QUOTE_GAPS']:
 x=e.read(P/'prefix_20240930'/(name+'.json'));y=e.read(e.V2/'checkpoint_20240930'/(name+'.json'));assert x==y,('PREFIX_MISMATCH',name);checks[name]=len(x)
e.save(P/'EXACT_PREFIX_QA.json',dict(result='PASS',days=19,records=checks,supplement=e.sha(e.ROOT/'joint_equity_evidence_v1/EXTRA_REVIEWED_EQUITY_EVENTS_300870_V1.json')));print('EXACT_19_DAY_PREFIX_PASS',flush=True)
pending=a.pending;keys=['cash','receivable','active','archive','seq','claims','snapshots','tickets','transfer_plan','quote_gaps'];logs=['orders','candidates','cp_log','profit','ledger','holdings','equity','sector_daily','ticket_log','confirmations','transfers','request_details','floor_risk','open_exposure','availability']
for day in all_days[all_days>e.pd.Timestamp('2024-09-30')]:
 snap=copy.deepcopy({k:getattr(a,k) for k in keys});p0=copy.deepcopy(pending);lengths={k:len(getattr(a,k)) for k in logs}
 try:
  a.economic_preflight(day,pending);a.accrue(day);a.exit_open(day);a.alloc_open(day,pending);pending=a.close(day,d.cal[d.cal.get_loc(day)-1])
 except e.Blocked as ex:
  a.uncertified_day=dict(day=e.day(day),reason=str(ex),partial_orders=a.orders[lengths['orders']:])
  for k,v in snap.items():setattr(a,k,v)
  for k,n in lengths.items():del getattr(a,k)[n:]
  pending=p0;a._preflight_excluded=set();a.all_blockers=a.scan_restored_targets(day,pending);a.blockers.append(str(ex));break
 print('EXTEND_DAY '+json.dumps(a.ledger[-1]),flush=True)
a.pending=pending;a.export(P/'account_20241008');e.save(P/'RUN_STATUS.json',dict(days=len(a.ledger),orders=len(a.orders),last=a.ledger[-1],blockers=a.blockers));print(json.dumps(e.read(P/'RUN_STATUS.json')))
