"""Saved-panel/matches/statistics audit only; never computes D, CP, or a match."""
from pathlib import Path
from collections import Counter
import hashlib,json,math
import numpy as np
import pandas as pd

P=Path(__file__).resolve().parents[1];D=P/'run_v1';O=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b):return a==b or a is not None and b is not None and math.isfinite(float(a)) and math.isfinite(float(b)) and abs(a-b)<=1e-11*max(1,abs(a),abs(b))
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def count_id(f):return {'reference_days':len(f),'unique_sid':f.sid.nunique(),'unique_anchor':len(f[['sid','anchor_id']].drop_duplicates()),'unique_I_cycle':len(f.dropna(subset=['cycle_id'])[['sid','cycle_id']].drop_duplicates()),'unique_decision_date':f.day.nunique()}
def q90(s):
    v=sorted(s);x=(len(v)-1)*.9;i=math.floor(x);j=math.ceil(x)
    return v[i] if i==j else v[i]*(j-x)+v[j]*(x-i)

rec=load(D/'RUN_RECEIPT.json');summary=load(D/'SAME_DAY_CALIPER_MATCH_SUMMARY.json');coarse=load(D/'COARSE_STRATA_DESCRIPTIVE.json')
assert rec['status']=='COMPLETE_LIMITED_SAVED_ANCHOR_PRICE_DIAGNOSTIC'
for path,h in rec['source_sha256'].items():assert sha(path)==h,path
assert sum(x['raw_anchors'] for x in rec['workers'])==rec['raw_anchor_mother']==51026
assert sum(x['errors'] for x in rec['workers'])==0
cols=['sid','day','analysis_window','anchor_id','anchor_day','entry_day','holding_age','known_close_peak','P_old','C','D','D_status','native_i_target','scale_status','s63','I_cycle_age','cycle_id','current_CP_I_exit','reference_status',
 'label_status','forward20_n_observations','MFE20','MAE20','first_hit20_label','first_hit20_step','first_hit20_day','first_hit_known_before_later_censor','rebound_after_down','rebound_after_down_status',
 'warning_inherited_at_entry','warning_inherited_at_entry_status','prior_entry_completed_close_day']
frames=[pd.read_parquet(f,columns=cols) for f in sorted(D.glob('PANEL_*.parquet'))]
panel=pd.concat(frames,ignore_index=True);matches=pd.read_parquet(D/'CALIPER_MATCHED_PAIRS.parquet')
assert len(panel)==rec['panel_rows_with_overlapping_scope_tags']==445912
assert len(matches)==rec['matched_pairs_with_overlapping_scope_tags']==7677
assert not panel[['analysis_window','sid','day']].duplicated().any()
assert panel.day.ge(panel.entry_day).all()
pre=panel.prior_entry_completed_close_day.notna();assert panel.loc[pre,'prior_entry_completed_close_day'].lt(panel.loc[pre,'entry_day']).all()
complete=panel.label_status.eq('COMPLETE_20')
assert panel.loc[complete,'forward20_n_observations'].eq(20).all()
assert panel.loc[complete,['MFE20','MAE20']].notna().all().all()
assert panel.loc[complete,['MFE20','MAE20']].ge(0).all().all()
assert panel.loc[~complete,['MFE20','MAE20']].isna().all().all()
hit=panel.first_hit20_label.isin(['UP_FIRST','DOWN_FIRST'])
assert panel.loc[hit,'first_hit20_step'].ge(1).all() and panel.loc[hit,'first_hit20_step'].le(panel.loc[hit,'forward20_n_observations']).all()
assert panel.loc[hit,'first_hit20_day'].gt(panel.loc[hit,'day']).all()
un=panel.first_hit20_label.eq('UNDECIDED_FULL20');assert complete.loc[un].all()
partial=panel.forward20_n_observations.lt(20)
assert not panel.loc[partial,'first_hit20_label'].eq('UNDECIDED_FULL20').any()
assert panel.loc[hit,'first_hit_known_before_later_censor'].eq(partial.loc[hit]).all()
down=panel.first_hit20_label.eq('DOWN_FIRST')
known_no_rebound=down&panel.rebound_after_down.eq(False)
assert complete.loc[known_no_rebound].all()
unresolved=down&partial&~panel.rebound_after_down.eq(True)
assert panel.loc[unresolved,'rebound_after_down'].isna().all()
assert panel.loc[unresolved,'rebound_after_down_status'].eq('REBOUND_UNRESOLVED_CENSORED').all()
for direction,col,bound in [('UP_FIRST','MFE20',np.expm1(panel.s63)),('DOWN_FIRST','MAE20',1-np.exp(-panel.s63))]:
    mask=complete&panel.first_hit20_label.eq(direction)
    assert (panel.loc[mask,col]+1e-11>=bound.loc[mask]).all()

# Independently form only the current-feature eligibility mask, not any pairs.
eligible=panel.reference_status.eq('ENTERED_ORIGINAL_CP_REFERENCE')&panel.current_CP_I_exit.eq(False)&panel.native_i_target.eq(1)&panel.D_status.eq('KNOWN')&panel.D.ge(0)&panel.scale_status.eq('READY')
for c in ['C','P_old','known_close_peak','s63','holding_age']:eligible &= panel[c].notna()&np.isfinite(panel[c])&panel[c].gt(0)
eligible &= panel.known_close_peak.ge(panel.C)&panel.holding_age.eq(np.floor(panel.holding_age))
primary=panel.loc[eligible].copy()
primary['oldP_logdist_s']=np.log(primary.C/primary.P_old)/primary.s63
primary['known_close_drawdown_s']=np.maximum(0,np.log(primary.known_close_peak/primary.C))/primary.s63
key=['analysis_window','day','sid','anchor_id'];indexed=primary.set_index(key,verify_integrity=True)
for role in ['warning','control']:
    idx=pd.MultiIndex.from_arrays([matches.analysis_window,matches.day,matches[f'{role}_sid'],matches[f'{role}_anchor_id']],names=key)
    chosen=indexed.loc[idx].reset_index(drop=True)
    assert chosen.D.ge(3).all() if role=='warning' else chosen.D.lt(3).all()
    for c in ['D','MFE20','MAE20','holding_age','s63','oldP_logdist_s','known_close_drawdown_s']:
        a=chosen[c].to_numpy(float);b=matches[f'{role}_{c}'].to_numpy(float)
        assert np.allclose(a,b,rtol=1e-11,atol=1e-11,equal_nan=True),(role,c)
    for c in ['first_hit20_label','rebound_after_down']:
        a=chosen[c].fillna('NULL').astype(str).reset_index(drop=True);b=matches[f'{role}_{c}'].fillna('NULL').astype(str)
        assert a.eq(b).all(),(role,c)
assert not matches[['analysis_window','day','control_sid']].duplicated().any()
assert not matches[['analysis_window','day','warning_sid']].duplicated().any()
assert matches.warning_sid.ne(matches.control_sid).all()
dd=(matches.warning_known_close_drawdown_s-matches.control_known_close_drawdown_s).abs()
dist=(matches.warning_oldP_logdist_s-matches.control_oldP_logdist_s).abs()
lv=np.log(matches.warning_s63/matches.control_s63).abs()
acap=np.maximum(2,.2*matches.warning_holding_age);age=(matches.warning_holding_age-matches.control_holding_age).abs()
assert dd.le(.25+1e-12).all() and dist.le(.25+1e-12).all() and lv.le(math.log(1.25)+1e-12).all() and age.le(acap+1e-12).all()
score=(dd/.25)**2+(dist/.25)**2+(lv/math.log(1.25))**2+(age/acap)**2
assert np.allclose(score,matches.score,rtol=1e-11,atol=1e-11)

checks={}
for w,p in primary.groupby('analysis_window'):
    s=summary[w];m=matches[matches.analysis_window.eq(w)];W=p[p.D.ge(3)];C=p[p.D.lt(3)]
    assert count_id(W)==s['primary_warning_known'] and count_id(C)==s['primary_control_known']
    assert len(m)==s['matched_pairs'] and eq(len(m)/len(W),s['warning_matched_coverage'])
    assert m.label_pair_status.value_counts().to_dict()==s['match_label_status_counts']
    both=m.label_pair_status.eq('BOTH_COMPLETE');good=m.loc[both];assert len(good)==s['complete_label_pair_n']
    wKnown=m.warning_MFE20.notna()&m.warning_MAE20.notna();cKnown=m.control_MFE20.notna()&m.control_MAE20.notna()
    expected=np.where(wKnown&cKnown,'BOTH_COMPLETE',np.where(~wKnown&cKnown,'WARNING_LABEL_MISSING',np.where(wKnown&~cKnown,'CONTROL_LABEL_MISSING','BOTH_LABELS_MISSING')))
    assert m.label_pair_status.eq(expected).all()
    for metric in ['MFE20','MAE20']:
        assert eq(good[f'warning_{metric}'].mean(),s['complete_pair_warning_means'][metric])
        assert eq(good[f'control_{metric}'].mean(),s['complete_pair_control_means'][metric])
        assert eq((good[f'warning_{metric}']-good[f'control_{metric}']).mean(),s['mean_warning_minus_control'][metric])
    lab=p[p.label_status.eq('COMPLETE_20')];q=q90(lab.MFE20)
    assert eq(q,s['future_MFE_q90']) and len(lab)==s['q90_population_n']
    assert lab.MFE20.ge(s['future_MFE_q90']).sum()==s['q90_ties_ge_threshold']
    for role,original in [('warning',W),('control',C)]:
        assert original.first_hit20_label.value_counts().to_dict()==s[f'primary_{role}_first_hit20_counts']
        assert m[f'{role}_first_hit20_label'].value_counts().to_dict()==s[f'matched_{role}_first_hit20_counts']
        rd=m.loc[m[f'{role}_first_hit20_label'].eq('DOWN_FIRST'),f'{role}_rebound_after_down'].map(lambda x:'None' if pd.isna(x) else str(bool(x)))
        assert rd.value_counts().to_dict()==s[f'matched_{role}_down_first_rebound_counts']
        assert m[f'{role}_MFE20'].ge(s['future_MFE_q90']).sum()==s[f'matched_{role}_future_q90_n']
    assert len(panel[panel.analysis_window.eq(w)])==coarse[w]['selected_reference_day_rows']
    checks[w]={'panel_rows':len(panel[panel.analysis_window.eq(w)]),'primary_warning_days':len(W),'primary_control_days':len(C),
       'matched':len(m),'complete20_pairs':len(good),'label_status':s['match_label_status_counts'],
       'coverage':s['warning_matched_coverage'],'warning_minus_control_fraction':s['mean_warning_minus_control'],
       'q90_fraction':q,'q90_population':len(lab)}

main_names=['2022_2023','2024_Sep_Dec','2025_2026Jun_FIXED_SEMICONDUCTOR']
out={'status':'PASS_BOUNDED_SAVED_PANEL_MATCHES_SUMMARY_WITH_LIMITS',
 'scope':'Read all saved panel rows and match rows; current eligibility, provided calipers/no-replacement/row joins, summary means/label-missing/q90/firsthit-rebound invariants. No D/CP recalculation or rematching; no optimality check over unchosen controls.',
 'raw_anchor_mother':51026,'panel_rows_with_overlap':len(panel),'matched_rows_with_overlap':len(matches),
 'main_window_matched_rows':sum(checks[x]['matched'] for x in main_names),'window_checks':checks,
 'firsthit_all_panel_counts':panel.first_hit20_label.value_counts().to_dict(),
 'known_firsthit_before_incomplete20':int((hit&partial).sum()),'down_rebound_unknown_in_incomplete20':int(unresolved.sum()),
 'policy_extra_field_not_final_rawleg_strict_rate':True,'metadata_sidecar_not_yet_audited':True,
 'code_sha256_verified':rec['source_sha256'],
 'output_sha256':{str(x):sha(x) for x in [D/'RUN_RECEIPT.json',D/'SAME_DAY_CALIPER_MATCH_SUMMARY.json',D/'CALIPER_MATCHED_PAIRS.parquet',D/'COARSE_STRATA_DESCRIPTIVE.json',*sorted(D.glob('PANEL_*.parquet'))]},
 'limits':['Future label values/path order not independently reconstructed from all original source prices',
 'Greedy nearest-match selection statically reviewed; provided pairs verified, not rematched',
 'Matched counts include repeated stock/I cycles; overlapping appendix scopes cannot be added as independent observations',
 'MFE/MAE are price fractions, multiply100 for percentage points; no actual trade or portfolio return',
 'Policy e0_target does not imply raw leg up; final strict extra rates require separate rawleg sidecar'],
 'remaining_blocks_for_reviewed_saved_statistical_scope':[],'new_D_CP_or_matching_runs':0,'new_accounts':0}
(O/'SAVED_PANEL_AUDIT.json').write_text(json.dumps(clean(out),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps(clean({'status':out['status'],'windows':checks,'prefix_hit':out['known_firsthit_before_incomplete20'],'rebound_unresolved':out['down_rebound_unknown_in_incomplete20']}),ensure_ascii=False))
