"""Read-only metadata counts/source samples; no models, labels or match selection."""
from pathlib import Path
import hashlib,json,math
import pandas as pd

P=Path(__file__).resolve().parents[1];D=P/'run_v1';M=P/'metadata_v1';O=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(x):
    if x is None or pd.isna(x):return None
    return x if isinstance(x,str) else str(int(x)) if float(x).is_integer() else str(x)
def eq(a,b):return a==b or pd.isna(a) and pd.isna(b) or not pd.isna(a) and not pd.isna(b) and abs(float(a)-float(b))<1e-11*max(1,abs(float(a)),abs(float(b)))
cols=['analysis_window','sid','day','anchor_id','source_key','label_status','MFE20','MAE20','active_cross_warning','first_threshold_cross_in_cycle','I_cycle_age','extra_incremental_active_cross_candidate','first_hit20_label','rebound_after_down']
panel=pd.concat([pd.read_parquet(D/f'PANEL_{i}.parquet',columns=cols) for i in range(3)],ignore_index=True)
meta=pd.read_parquet(M/'REFERENCE_DAY_METADATA.parquet');mp=pd.read_parquet(M/'MATCHED_ENDPOINT_AND_RAWLEG_METADATA.parquet');orig=pd.read_parquet(D/'CALIPER_MATCHED_PAIRS.parquet')
s=load(M/'METADATA_SUMMARY.json');final=load(M/'FINAL_EXTRA_MATCHED_AND_FIRST_CYCLE.json');rec=load(M/'RECEIPT.json')
assert sha(P/'metadata_sidecar.py')==rec['script_sha256'] and sha(D/'RUN_RECEIPT.json')==rec['original_run_receipt_sha256']
for name,h in rec['outputs'].items():assert sha(M/name)==h,name
old=load(O/'SAVED_PANEL_AUDIT.json')
for path,h in old['output_sha256'].items():assert sha(path)==h,path
assert len(panel)==len(meta)==445912 and len(mp)==len(orig)==7677
keys=['analysis_window','sid','day','anchor_id']
assert panel[keys].equals(meta[keys])
assert panel.extra_incremental_active_cross_candidate.eq(meta.extra_incremental_active_cross_candidate).all()
p=panel.join(meta[['raw_E0_leg_current','raw_E0_leg_status','forward20_end_day','forward20_calendar_span','extra_rawleg_strict_candidate']])
assert p.extra_rawleg_strict_candidate.eq(p.extra_incremental_active_cross_candidate.eq(True)&p.raw_E0_leg_current.eq(1)).all()
complete=p.label_status.eq('COMPLETE_20');assert p.forward20_end_day.notna().eq(complete).all()
assert p.loc[complete,'forward20_end_day'].gt(p.loc[complete,'day']).all()
spans=(pd.to_datetime(p.loc[complete,'forward20_end_day'])-pd.to_datetime(p.loc[complete,'day'])).dt.days
assert spans.eq(p.loc[complete,'forward20_calendar_span']).all()
matchkeys=['analysis_window','day','warning_sid','control_sid'];assert mp[matchkeys].equals(orig[matchkeys])
lookup=p.set_index(['analysis_window','sid','day'])
for role in ['warning','control']:
    rows=lookup.loc[pd.MultiIndex.from_arrays([mp.analysis_window,mp[f'{role}_sid'],mp.day])].reset_index(drop=True)
    assert rows.forward20_end_day.fillna('NULL').eq(mp[f'{role}_end'].fillna('NULL')).all()
    for c in ['MFE20','MAE20']:assert rows[c].fillna(-999).eq(mp[f'{role}_{c}'].fillna(-999)).all()
    assert rows.raw_E0_leg_current.fillna(-999).eq(mp[f'{role}_rawleg'].fillna(-999)).all()
    if role=='warning':assert rows.extra_rawleg_strict_candidate.eq(mp.warning_strict_extra).all()
both=mp.warning_end.notna()&mp.control_end.notna();same=both&mp.warning_end.eq(mp.control_end)
expected=pd.Series('ONE_OR_BOTH_FORWARD20_MISSING',index=mp.index)
expected.loc[both]='BOTH_COMPLETE_DIFFERENT_ENDPOINT';expected.loc[same]='BOTH_COMPLETE_SAME_ENDPOINT'
assert expected.eq(mp.endpoint_status).all()
checks={}
for w,q in p.groupby('analysis_window'):
    active=q[q.active_cross_warning.eq(True)];bridge=q[q.extra_incremental_active_cross_candidate.eq(True)];strict=q[q.extra_rawleg_strict_candidate.eq(True)]
    f=final[w];z=s['windows'][w];mm=mp[mp.analysis_window.eq(w)];sel=mm[mm.warning_strict_extra];se=sel[sel.endpoint_status.eq('BOTH_COMPLETE_SAME_ENDPOINT')]
    first=q[q.active_cross_warning.eq(True)&q.first_threshold_cross_in_cycle.eq(True)]
    assert not first[['sid','day']].duplicated().any()
    assert len(active)==z['active_cross_n'] and len(bridge)==z['policy_target_candidate_n'] and len(strict)==z['strict_extra_n']
    assert eq(len(strict)/len(active),z['strict_extra_fraction_all_active_cross'])
    assert bridge.raw_E0_leg_status.value_counts().to_dict()==z['policy_candidates_raw_leg_counts']
    assert mm.endpoint_status.value_counts().to_dict()==z['all_match_endpoint_status']
    assert len(first)==f['first_in_I_active_cross_n_in_saved_reference_days']
    assert int(first.extra_rawleg_strict_candidate.sum())==f['first_in_I_strict_extra_n']
    assert eq(first.extra_rawleg_strict_candidate.mean(),f['first_in_I_strict_extra_fraction'])
    assert len(strict)==f['strict_extra_total_n'] and len(se)==f['strict_extra_same_endpoint_matched_n']
    assert eq(len(se)/len(strict),f['strict_extra_same_endpoint_coverage']) if len(strict) else True
    for sub,field in [(se,'strict_extra_same_endpoint'),(se[se.control_rawleg.eq(1)],'diagnostic_existing_pairs_control_also_raw_up')]:
        assert len(sub)==f[field]['n']
        for k,v in f[field]['means'].items():assert v is None if not len(sub) else eq(sub[k].mean(),v)
        for role in ['warning','control']:assert sub[f'{role}_first_hit'].value_counts().to_dict()==f[field][role+'_first_hit']
    age=[]
    for role in ['warning','control']:
        a=lookup.loc[pd.MultiIndex.from_arrays([se.analysis_window,se[role+'_sid'],se.day]),'I_cycle_age']
        v=None if not len(a) else a.mean();target=f['same_endpoint_I_cycle_age_'+role]
        assert v is None and target is None or eq(v,target);age.append(v)
    checks[w]={'active_cross':len(active),'policy_bridge':len(bridge),'bridge_rawleg_counts':bridge.raw_E0_leg_status.value_counts().to_dict(),
      'strict':len(strict),'strict_fraction':len(strict)/len(active),'first_active_cross':len(first),'first_strict':int(first.extra_rawleg_strict_candidate.sum()),
      'endpoint_status':mm.endpoint_status.value_counts().to_dict(),'strict_same_endpoint_matched':len(se),
      'strict_same_endpoint_I_age_warning_control':age,'existing_pairs_control_raw_up':int(se.control_rawleg.eq(1).sum())}

# Deterministic source samples: one bridge DOWN and one strict UP per main window,
# and one differing-endpoint match plus a known-missing case. All counts above are full.
main=['2022_2023','2024_Sep_Dec','2025_2026Jun_FIXED_SEMICONDUCTOR'];sample_keys=set()
for w in main:
    q=p[p.analysis_window.eq(w)]
    for mask in [q.extra_incremental_active_cross_candidate.eq(True)&q.raw_E0_leg_current.eq(-1),q.extra_rawleg_strict_candidate.eq(True)]:
        x=q.loc[mask].sort_values(['day','sid']).iloc[0];sample_keys.add((x.sid,x.day))
    mm=mp[mp.analysis_window.eq(w)&mp.endpoint_status.eq('BOTH_COMPLETE_DIFFERENT_ENDPOINT')]
    if len(mm):
        x=mm.iloc[0]
        for role in ['warning','control']:sample_keys.add((x[role+'_sid'],x.day))
sm=load('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');source={x['symbol']:x for x in sm};samples=[];hashes={}
for sid,day in sorted(sample_keys):
    r=source[sid];pp=Path(next(x for x in r['source_sha256'] if x.endswith('/signal.parquet')));ep=Path(next(x for x in r['source_sha256'] if x.endswith('/events.parquet')))
    for path in [pp,ep]:assert sha(path)==s['source_sha256'][str(path)];hashes[str(path)]=sha(path)
    e=pd.read_parquet(ep,columns=['leg_direction','segment_id']);ix=pd.read_parquet(pp,columns=[]).index
    ix=pd.DatetimeIndex(pd.to_datetime(ix)).as_unit('ns').normalize();ix=ix[ix<=pd.Timestamp('2026-06-30')]
    x=p[p.sid.eq(sid)&p.day.eq(day)].iloc[0];er=e.loc[pd.Timestamp(day)]
    assert norm(er.segment_id)==norm(x.source_key) and float(er.leg_direction)==x.raw_E0_leg_current
    end=None
    if x.label_status=='COMPLETE_20':end=str(ix[ix.get_loc(pd.Timestamp(day))+20].date());assert end==x.forward20_end_day
    samples.append({'sid':sid,'day':day,'raw_leg_original':float(er.leg_direction),'source_segment':norm(er.segment_id),'COMPLETE20':x.label_status=='COMPLETE_20','j_plus20_original_source_endpoint':end})
files=[M/'REFERENCE_DAY_METADATA.parquet',M/'MATCHED_ENDPOINT_AND_RAWLEG_METADATA.parquet',M/'METADATA_SUMMARY.json',M/'FINAL_EXTRA_MATCHED_AND_FIRST_CYCLE.json',M/'RECEIPT.json',P/'metadata_sidecar.py',P/'finalize_metadata.py']
out={'status':'PASS_BOUNDED_RAWLEG_ENDPOINT_AND_FIRST_CYCLE_METADATA_WITH_LIMITS','full_row_and_match_counts':{'reference_rows':len(p),'existing_matches':len(mp)},'window_checks':checks,
 'original_source_samples':samples,'source_sha256_verified':hashes,'source_outputs':{str(x):sha(x) for x in files},
 'original_panel_and_matching_bytes_unchanged_verified':True,
 'scope':'Full metadata/key/count/subgroup-mean/first-cycle flag consistency; deterministic exact-event/source-index samples for leg and j+20. No new D/CP/labels, no rematching.',
 'limits':['Original source leg and j+20 checked for sampled rows, not all445912 annotations',
 'First-in-I refers global first_threshold_cross flag observed inside saved CP riskset, not all I episodes or first visible re-cross',
 'I cycle age was not matched; current rawleg-equal control filter is descriptive and not a new preregistered match',
 'Same endpoint is a future-completeness subset, not proof all middle observation dates/calendar/session/execution are equal',
 'All price labels and repeated days/cycles are dependent; no causal alpha/portfolio return or actual fill evidence'],
 'remaining_blocks_for_reviewed_metadata_scope':[],'new_model_runs':0,'new_matching_runs':0,'new_accounts':0}
(O/'METADATA_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':out['status'],'main':{w:checks[w] for w in main},'source_sample_rows':len(samples)},ensure_ascii=False))
