"""Read completed M8 records and source facts; no Engine, no strategy replay."""
from pathlib import Path
import importlib.util,sys,json
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('m9_examples',P/'engine.py');e=importlib.util.module_from_spec(sp);sys.modules[sp.name]=e;sp.loader.exec_module(e)
freeze=e.read(P/'CONTRACT_FREEZE.json')
assert freeze['engine_sha256']==e.sha(P/'engine.py') and freeze['contract_sha256']==e.sha(P/'CONTRACT.md')
source=e.ROOT/'mainline_candidate_v8_false_mainline_retirement_run_v1/once_20241031'
rows=e.read(source/'CANDIDATES.json')
gates={(r['round_id'],r['day']):r for r in rows if r.get('event')=='ADD_GATE'}
retirements=[r for r in rows if r.get('event')=='EXPANSION_RETIREMENT']
cap=e.read(source/'CAPITAL_LOTS.json')
cap_by={(r['round_id'],r['day']):r for r in cap}
calendar=e.pd.DatetimeIndex([r['day'] for r in e.read(source/'DAY_LEDGER.json')])
sectors={r['sid']:r['sector51'] for r in cap}
assert not e.read(source/'BLOCKERS.json')
def evidence(s,r,d):
    g=gates.get((r,e.day(d)));c=cap_by.get((r,e.day(d)))
    ss=c.get('sector_state') if c else None;m=c.get('M') if c else None;st=c.get('stock_state') if c else None
    n=g.get('close_net') if g else None
    if c and g:assert e.dec(c['round_net'])==e.dec(n)
    known=bool(g and c and n is not None and ss in (0,1) and m in (0,1) and st in (0,1))
    return dict(day=e.day(d),round_id=r,sector_state=ss,M=m,stock_state=st,close_net=n,
                close_certification='completed M8 saved CLOSE, inherited validity checks; no raw reload',
                known=known,qualifies=bool(known and ss==m==st==0 and e.dec(n)<=0))

examples=[]
for r in retirements:
    s=r['sid'];dt=e.pd.Timestamp(r['day']);prev=calendar[calendar.get_loc(dt)-1]
    cur=evidence(s,r['round_id'],dt);prior=evidence(s,r['round_id'],prev)
    examples.append(dict(sid=s,sector51=sectors[s],round_id=r['round_id'],
      m8_signal_day=r['day'],lot_id=r['lot_id'],M8_retirement_record=r,current=cur,prior=prior,
      passes_M9_predicates_on_M8_path=cur['qualifies'] and prior['qualifies']))
targets=('000158','002261','002049','002865')
chosen=[r for r in examples if r['sid'][:6] in targets or '光伏' in r['sector51']]
# Include all daily observations for specifically requested names, plus each M8 PV retirement round.
rounds={r['round_id'] for r in chosen}
rounds.update(r['round_id'] for r in rows if r.get('event')=='ADD_GATE' and r['sid'][:6] in targets)
daily=[dict(sid=r['sid'],sector51=sectors[r['sid']],**evidence(r['sid'],r['round_id'],e.pd.Timestamp(r['day'])))
       for r in rows if r.get('event')=='ADD_GATE' and r['round_id'] in rounds]
result=dict(history_run=False,kind='POST_FREEZE_M8_PATH_DIAGNOSTIC_NOT_M9_REPLAY',
  warning='Uses saved M8 per-round close net and factual daily signals, not M9 holdings. M9 replay can change cashflows, positions and later round identities; predicate pass does not establish actual M9 order or performance.',
  contract_freeze=freeze,source_candidates_sha256=e.sha(source/'CANDIDATES.json'),source_candidates=str(source/'CANDIDATES.json'),
  counts=dict(m8_marked_lots=len(examples),m8_marks_passing_m9_predicates=sum(r['passes_M9_predicates_on_M8_path'] for r in examples)),
  requested_examples=chosen,all_m8_mark_examples=examples,daily_requested_examples=daily,
  source_hashes={str(source/n):e.sha(source/n) for n in ['CANDIDATES.json','CAPITAL_LOTS.json','DAY_LEDGER.json','BLOCKERS.json']})
e.save(P/'ACTUAL_EXAMPLES.json',result)
print(json.dumps(result['counts']))
for r in chosen:print(r['sid'],r['sector51'],r['m8_signal_day'],r['current']['close_net'],r['current']['stock_state'],r['prior']['close_net'],r['prior']['stock_state'],r['passes_M9_predicates_on_M8_path'])
