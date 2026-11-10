"""Read original facts for preselected cases only; no numeric model recalculation."""
from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
cases=json.loads((O/'SYSTEMATIC_CASES.json').read_text())
refs={r['symbol']:r['refs']['facts'] for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
frames={};sources={};out=[]
for item in cases:
 r=item['row'];sid=r['sid'];day=pd.Timestamp(r['decision_at'][:10])
 if sid not in frames:
  p=Path(refs[sid]);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();frames[sid]=pd.read_parquet(p)
 f=frames[sid].loc[:day];q=f.loc[day];assert abs(float(q.close)-float(r['H2_entry_context']['close']))<1e-10*max(1,float(q.close))
 v=dict(key=r['key'],sid=sid,selection=item['selection'],actual_action=r['actual_entry_action'],actual_role=r['role'],decision_at=r['decision_at'],
        original_I_on=bool(q.i_target),same_close_i_buy=bool(q.i_buy),original_E0_on=bool(q.e0_target),source_segment=int(q.segment_id),g_grade=float(q.g_grade),
        CP_formation_start=r['original_receipt']['formation_start_exclusive'] if r['original_receipt'] else None,candidate_blocked=r['candidate_blocked_on_JOINT_history'])
 for field,label in [('i_target','I'),('e0_target','E0')]:
  if bool(q[field]):
   z=f.loc[f.segment_id.eq(q.segment_id)]
   ix=z.index.get_loc(day);i=ix
   while i>0 and bool(z.iloc[i-1][field]):i-=1
   start=z.index[i]
   v[label+'_continuous_start']=str(start.date());v[label+'_known_observations_through_decision']=ix-i+1
   v[label+'_source_left_censored']=i==0
  else:v[label+'_continuous_start']=None
 out.append(v)
(O/'SELECTED_CASE_I_E0_CONTEXT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
(O/'CASE_FACT_SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
for r in out:
 if any(s.startswith('2022_2024:Dec_new135') and ':negative:' in s for s in r['selection']):print(r['sid'],r['actual_action'],r['decision_at'],'I start',r['I_continuous_start'],'I age',r['I_known_observations_through_decision'],'i_buy',r['same_close_i_buy'],'CP start',r['CP_formation_start'],'blocked',r['candidate_blocked'])
