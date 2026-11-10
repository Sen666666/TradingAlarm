"""Existing saved contribution reader, explicit same-delay baseline only."""
from pathlib import Path
import sys,inspect,json
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P.parent));import analyze_pvr_no60 as L
baseline=L.ROOT/'pvr-slot1-d1-v2-composition-preflight-20261101/run-PVR-D1'
new=P.parent.parent/'pvr_pressure_readiness/run-D1-strong'
out=P/'D1_strong'
src=inspect.getsource(L.main)
old="roots={'PVR_BASELINE':OLD/'runs'/args.window,'PVR_NO60':Path(args.new_root)}"
assert src.count(old)==1
src=src.replace(old,"roots={'PVR_BASELINE':Path("+repr(str(baseline))+"),'PVR_NO60':Path(args.new_root)}")
env=dict(L.__dict__);exec(compile(src,__file__+'::same-delay-saved-reader','exec'),env)
sys.argv=[__file__,'--window','2025_26','--new-root',str(new),'--out',str(out)]
env['main']()
L.save(out/'PRESSURE_SCOPE.json',dict(policy_labels={'PVR_BASELINE':'original PVR D1-v2 delay1 cost1','PVR_NO60':'NO_CONFIRMED60 D1-v2 delay1 cost1'},same_delay_baseline=str(baseline),candidate=str(new),financial_events=0,normal_control_used=False,source_wrapper_sha256=L.sha(__file__),source_reader_sha256=L.sha(L.__file__),only_reader_change='explicit same-pressure baseline path; all aggregation identical',raw_signals_recomputed=0))
