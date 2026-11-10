"""Saved feature audit only; never calls assembly/algorithms."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');P=O.parent/'risk_constraints/volume_feature_fixtures_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def exact(a,b):pd.testing.assert_frame_equal(a,b,check_exact=True,check_dtype=False,check_names=False,check_freq=False)
f=read(P/'EXECUTION_FREEZE.json');assert len(f['sources'])==52
for p,h in f['sources'].items():assert sha(p)==h
checks=[]
for sid,r in f['series'].items():
 real={key:pd.read_parquet(P/(sid+'_REAL')/(key+'.parquet'))for key in ['facts','q','CP1','PVR','evidence']}
 count={}
 for key,refkey in [('facts','facts'),('q','CP1_input'),('CP1','CP1')]:
  old=pd.read_parquet(r[refkey]).loc[:'2026-06-30'];exact(real[key].reindex(columns=old.columns),old);count[key]=len(old)
 if 'PVR8'in r:
  old=pd.read_parquet(r['PVR8']);exact(real['PVR'].reindex(old.index),old);count['PVR8_reference_dates']=len(old)
  old=pd.concat([pd.read_parquet(r['scores2024']),pd.read_parquet(r['scores_old']).loc['2025-07-01':'2026-06-30']]);assert len(old)==968 and old.index.is_unique;exact(real['PVR'][['score']].reindex(old.index),old);count['score_reference_dates']=len(old)
 checks.append(dict(sid=sid,exact_saved_reference_counts=count))
failed=read(P/'FAILED.json');assert failed['stage']=='neutral_000001.SZ'and 'Series is ambiguous'in failed['reason']
assert not list(P.glob('*_NEUTRAL'))
x=dict(status='PASS_TRUE_COLD_PARITY_SOURCE_WITH_NEUTRAL_STOPPED_AT_COMPARATOR_TYPE_ERROR',source_checks=52,series=checks,
 producer_wall_seconds=failed['wall_seconds'],neutral_outputs_saved=0,reviewer_account_events=0,
 source_review={'E0':'Replaces only EVENT_COLUMNS with existingnumeric jointFalse; no old numeric target/floor. Common C/V clock retained.', 'B4_G1_I':'Recomputes B4 jointFalse then original grade and original e0_policy with decline_candidate=False and original G1_I project. No truegrade/I consumed in neutral.', 'CP1':'Rebuiltneutral eligibility and negativeevents; original price_only True. Diagnosticobserved cp.m is not effective multiplier.', 'PVR':'Only functionlocal copy positive finite amount->1; invalid originalamount and allraw/masks/source remain unchanged. Originalscore function makes b0/eu, no truePVR consumed.', 'ACT':'No toy/fullACT computation, remains explicit unresolvedfullpool boundary.'},
 physical_prefix_scope='Frozen firstcontroller planned NEUTRAL only6x3; REAL physicalprefix was not executed by thisattempt. Existingrealcacheexact above is distinctproof.',
 disposition='Preserve frozen source/failure; comparison-only corrected continuation may reuse REAL only under root grant. No newparameter,fixture,fullpool,account or automatic retry.',
 inputs={str(p):sha(p)for p in [P/'EXECUTION_FREEZE.json',P/'FAILED.json',P/'TRUE_ALL_6_SERIES_GATE.json',Path(__file__)]})
(O/'VOLUME_FIXTURE_FIRST_PASS_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],series=len(checks),sources=52)))
