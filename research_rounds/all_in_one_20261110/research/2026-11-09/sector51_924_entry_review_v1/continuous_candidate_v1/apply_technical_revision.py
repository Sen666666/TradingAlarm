from pathlib import Path
import json,hashlib
O=Path(__file__).resolve().parent;p=O/'engine.py';old=p.read_text();(O/'engine_initial_frozen.py').write_text(old)
a=O.parent/'independent_audit_v1/REVIEWED_CASH_EVENTS_14.json';rows=json.loads(a.read_text());assert len(rows)==14;ah=hashlib.sha256(a.read_bytes()).hexdigest();extra=[]
base=json.loads(Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1/cash_dividend_2024_coverage_v1/EVENT_ADAPTER_CANDIDATES.json').read_text());known={(r['sid'],r['ex_date']) for r in base}
for r in rows:
 if (r['sid'],r['ex_date']) in known:continue
 r['evidence_hashes']={str(a):ah}
 if r.get('source_fact_path'):r['evidence_hashes'][r['source_fact_path']]=r['source_fact_sha256']
 extra.append(r)
(O/'EXTRA_REVIEWED_EQUITY_EVENTS_V2.json').write_text(json.dumps(extra,ensure_ascii=False,indent=2)+'\n')
s=old.replace("xp=O/'EXTRA_REVIEWED_EQUITY_EVENTS.json'","xp=O/'EXTRA_REVIEWED_EQUITY_EVENTS_V2.json'")
s=s.replace("self.snapshots.get((s,ev['record_date']),0)","self.snapshots.get((s,ev['record_date']),{'q':0})['q']")
s=s.replace("   try:\n    self.economic_preflight(d,pending)","   keys=['cash','receivable','active','archive','seq','claims','snapshots'];snap=copy.deepcopy({k:getattr(self,k) for k in keys});logs=['orders','candidates','cp_log','profit','ledger','holdings','equity'];lengths={k:len(getattr(self,k)) for k in logs}\n   try:\n    self.economic_preflight(d,pending)")
s=s.replace("   except Blocked as ex:self.blockers.append(str(ex));break","   except Blocked as ex:\n    self.uncertified_day=dict(day=day(d),reason=str(ex),partial_orders=self.orders[lengths['orders']:]);\n    for k,v in snap.items():setattr(self,k,v)\n    for k,n in lengths.items():del getattr(self,k)[n:]\n    self.blockers.append(str(ex));break")
s=s.replace("save(path/'BLOCKERS.json',self.blockers)","save(path/'UNCERTIFIED_DAY.json',getattr(self,'uncertified_day',None));save(path/'BLOCKERS.json',self.blockers)")
s=s.replace("ap.add_argument('--output',default='run_once')","ap.add_argument('--output',default='run_once');ap.add_argument('--seal',default='FREEZE_V2.json')")
s=s.replace("O/'FREEZE.json'","O/args.seal")
assert s!=old and 'snap=copy.deepcopy' in s;p.write_text(s)
(O/'TECHNICAL_AMENDMENT.json').write_text(json.dumps(dict(no_economic_rule_change=True,prior_freeze_sha256=hashlib.sha256((O/'FREEZE.json').read_bytes()).hexdigest(),prior_engine_sha256=hashlib.sha256(old.encode()).hexdigest(),changes=['Add independently reviewed missing corporate cash facts; accounting only','Rollback uncertified day mutations before exporting certified prefix; preserve partial orders separately','Normalize bridge record_qty diagnostic field to integer'],first_prefix_results_preserved=True),indent=2)+'\n')
