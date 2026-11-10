from pathlib import Path
import json,hashlib
O=Path(__file__).parent
src=(O/'GATE_diagnose.py').read_text()
exec(compile(src[:src.index('results=[];life=[];states={}')],'FIXED_GATE_LOCAL_READERS','exec'))
rr=rd(O/'GATE_ACTUAL_ENTRY_ROWS.json');tt=rd(O/'GATE_WAIT_TIMING_FOCUS.json');visits=set()
for r in rr:
 for ds in [d for d in days if r['signal_day']<=d<=r['plan_day']]:
  visits.add((r['sid'],ds,'CLOSE'))
  if ds>r['signal_day']:visits.add((r['sid'],ds,'OPEN'))
 if r['gate_status']=='PASS':visits.add((r['sid'],r['seed_day'],'OPEN'))
for r in tt:
 for p in r['path']:visits.add((r['sid'],p['day'],p['phase']))
sentinels={'unknown','none','null','nan','na','n/a','<na>'};bad=[];counts=Counter()
for sid,ds,phase in sorted(visits):
 z=row(frames[sid],pd.Timestamp(ds));counts[phase]+=1
 for k in ['source_kind','source_path','segment_id']:
  v=z.get(k)
  if pd.isna(v) or str(v).strip().lower() in sentinels or str(v).strip()=='':bad.append(dict(sid=sid,day=ds,phase=phase,field=k,value=str(v)))
 fld='raw_open' if phase=='OPEN' else 'raw_close';f=z.get('adjustment_factor');p=z.get(fld)
 if not valid(z) or not finite(f) or f<=0 or not finite(p) or p<=0:bad.append(dict(sid=sid,day=ds,phase=phase,field='PRICE_OR_FACTOR',value=str(p)))
out=dict(unique_sid_day_phase_visits=len(visits),by_phase=dict(counts),source_unknown_text_sentinels_checked=sorted(sentinels),source_or_quote_factor_unknown_rows=bad,scope='All 833 signal-to-plan CLOSE/intervening OPEN visits, 401 PASS original nextOPENs, and 26 focused waiting path visits. Unique rows, not per-ticket counts.',limitation='Diagnostic does not implement complete original Q0 action_inventory interval recovery or comprehensive original known_origin logic. Current visited rows contain no such gap/sentinel. A candidate implementation must inherit original Q0, not reuse this helper as a replacement.')
save('SOURCE_SENTINEL_COVERAGE',out)
print(json.dumps(out,ensure_ascii=False))
