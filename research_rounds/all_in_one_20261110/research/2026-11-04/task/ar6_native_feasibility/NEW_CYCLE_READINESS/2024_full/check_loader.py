"""Complete input-only physical horizon check; zero account construction/events."""
from pathlib import Path
import json,time
import numpy as np
import pandas as pd
import loader_2024 as A

def save(p,x):A.IO.write_json(p,A.J.W.canon(x))

def main():
 begun=time.monotonic();A.assert_data()
 paths=[Path(__file__),Path(A.__file__),A.O/'DATA_GATE.json',A.O/'SOURCE_FREEZE.json',A.O/'inputs/MANIFEST.json',A.O/'SCORES_MANIFEST.json']
 freeze=dict(scope='2024_input_loader_only',sources={str(p):A.sha(p)for p in paths},
             unchanged_native_sources=A.S.freeze(),account_construction=0,account_events=0)
 target=A.O/'TECHNICAL_SOURCE_FREEZE.json'
 if target.exists():assert A.read(target)==freeze
 else:save(target,freeze)
 value=A.inputs();shared,receipts,cp,states,ir,identity=value;loaded=time.monotonic()
 cut='2024-06-28';small=A.physical(value,cut);sb,sm,sf=small[0];b,m,f=shared
 assert set(b.series)==set(sb.series)and set(f.f)==set(sf.f)
 for sid in b.series:pd.testing.assert_frame_equal(b.series[sid].states.loc[:cut],sb.series[sid].states,check_exact=True,check_freq=False)
 for sid in f.f:pd.testing.assert_frame_equal(f.f[sid].loc[:cut],sf.f[sid],check_exact=True,check_freq=False)
 for sid in m.raw:pd.testing.assert_frame_equal(m.raw[sid].loc[:cut],sm.raw[sid],check_exact=True,check_freq=False)
 d,col,score=b._h1_cache;sd,scol,sscore=sb._h1_cache;mask=d<=pd.Timestamp(cut)
 assert d[mask].equals(sd)and col==scol
 np.testing.assert_allclose(score[mask],sscore,rtol=0,atol=0,equal_nan=True)
 assert all(x['effective_date']<=cut for rows in sm.actions.values()for x in rows)
 assert small[1]=={s:{d:x for d,x in rs.items()if d<=cut}for s,rs in receipts.items()}
 for sid in cp:pd.testing.assert_frame_equal(cp[sid].loc[:cut],small[2][sid],check_exact=True,check_freq=False)
 assert small[3]=={s:[x for x in rows if x['day']<=cut]for s,rows in states.items()}
 assert small[4]=={k:x for k,x in ir.items()if x['confirmed_day']<=cut}
 scores=A.scores();assert len(scores.values)==1709
 events=A.next_events(shared)
 save(A.O/'LOADER_GATE.json',dict(passed=True,account_construction=0,account_events=0,
  same1709stocks90industries=True,identity=identity,source_freeze_sha256=A.sha(target),
  full_input_physical_June28_exact=True,channels=['facts','states','raw_prices','actions','H1','CP1','stock_canonical','industry_canonical','industry_stage'],
  original_immutable_session_calendar_retained=True,score_manifest_loaded_by_original_FrozenScores=True,
  next_event_inventory=events,first_new_account_event_not_executed=True,
  load_seconds=loaded-begun,total_seconds=time.monotonic()-begun))
 assert all(A.sha(p)==h for p,h in freeze['sources'].items())
 assert all(A.sha(p)==h for p,h in freeze['unchanged_native_sources'].items())
 print('LOADER2024_PASS',round(time.monotonic()-begun,2),flush=True)

if __name__=='__main__':main()
