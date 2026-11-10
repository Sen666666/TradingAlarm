"""Read-only exact raw E0 leg and forward endpoint audit of fixed saved matches."""
from pathlib import Path
from collections import Counter
import json, hashlib, math, sys
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SHARED=BASE.parent/'channel_atr_fsm_v1'
sys.path.insert(0,str(SHARED))
import engine,runner

def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def idx(frame):
    x=pd.DatetimeIndex(pd.to_datetime(frame.index))
    if x.tz is not None:x=x.tz_localize(None)
    return x.as_unit('ns').normalize()
def ccounts(series):return dict(Counter(series.fillna('UNKNOWN')))
def dist(series):
    a=pd.to_numeric(series,errors='coerce').dropna().to_numpy(float)
    return dict(n=len(a),mean=None if not len(a) else float(np.mean(a)),**({f'q{int(q*100):02}':float(np.quantile(a,q)) for q in [0,.1,.5,.9,1]} if len(a) else {}))
def pathstats(q):
    d=q.loc[q.first_hit20_label.eq('DOWN_FIRST')]
    complete=q.loc[q.label_status.eq('COMPLETE_20')]
    return dict(n=len(q),stocks=q.sid.nunique(),I_cycles=q.cycle_id.nunique(),first_hit20_counts=ccounts(q.first_hit20_label),
        full20_n=len(complete),mean_MFE20=None if not len(complete) else float(complete.MFE20.mean()),mean_MAE20=None if not len(complete) else float(complete.MAE20.mean()),
        down_first_rebound_true=int(d.rebound_after_down.eq(True).sum()),down_first_rebound_false=int(d.rebound_after_down.eq(False).sum()),down_first_rebound_unknown=int(d.rebound_after_down.isna().sum()))

def main():
    run=HERE/'run_v1';out=HERE/'metadata_v1';out.mkdir(exist_ok=False)
    receipt=load(run/'RUN_RECEIPT.json');assert receipt['status']=='COMPLETE_LIMITED_SAVED_ANCHOR_PRICE_DIAGNOSTIC'
    panel=pd.concat([pd.read_parquet(run/f'PANEL_{i}.parquet') for i in range(3)],ignore_index=True)
    assert not panel.duplicated(['analysis_window','sid','day']).any()
    original_rows=len(panel);metas={x['symbol']:x for x in load(runner.MANIFEST)};bindings={}
    panel['raw_E0_leg_current']=np.nan;panel['raw_E0_leg_status']='UNKNOWN_OR_INCOMPARABLE'
    panel['forward20_end_day']=None;panel['forward20_calendar_span']=np.nan
    for sid, q in panel.groupby('sid',sort=True):
        meta=metas[sid]
        pp=Path(next(x for x in meta['source_sha256'] if x.endswith('/signal.parquet')))
        ep=Path(next(x for x in meta['source_sha256'] if x.endswith('/events.parquet')))
        for p in [pp,ep]:
            v=sha(p);assert v==meta['source_sha256'][str(p)];bindings[str(p)]=v
        price=pd.read_parquet(pp,columns=[]);pi=idx(price);pi=pi[pi<=pd.Timestamp('2026-06-30')]
        assert pi.is_unique and pi.is_monotonic_increasing
        events=pd.read_parquet(ep,columns=['leg_direction','segment_id']);events.index=idx(events)
        days=pd.DatetimeIndex(pd.to_datetime(q.day));e=events.reindex(days)
        leg=[];status=[]
        for raw,seg,pseg in zip(e.leg_direction,e.segment_id,q.source_key):
            if engine.finite(raw) and float(raw) in [-1.,0.,1.] and engine.source(seg)==engine.source(pseg) and engine.source(pseg) is not None:
                leg.append(float(raw));status.append('UP' if raw==1 else 'DOWN' if raw==-1 else 'NEUTRAL_OR_UNINITIALIZED')
            else:leg.append(np.nan);status.append('UNKNOWN_OR_INCOMPARABLE')
        panel.loc[q.index,'raw_E0_leg_current']=leg;panel.loc[q.index,'raw_E0_leg_status']=status
        complete=q.label_status.eq('COMPLETE_20').to_numpy();positions=pi.get_indexer(days)
        assert np.all(positions>=0)
        ends=positions[complete]+20;assert np.all(ends<len(pi))
        rows=q.index[complete];edays=pi[ends]
        panel.loc[rows,'forward20_end_day']=[str(t.date()) for t in edays]
        panel.loc[rows,'forward20_calendar_span']=(edays-days[complete]).days
    panel['extra_rawleg_strict_candidate']=panel.extra_incremental_active_cross_candidate.eq(True)&panel.raw_E0_leg_current.eq(1)
    # This is a metadata correction, not a new match or a different warning.
    selected_columns=['analysis_window','sid','day','anchor_id','raw_E0_leg_current','raw_E0_leg_status','forward20_end_day','forward20_calendar_span','extra_incremental_active_cross_candidate','extra_rawleg_strict_candidate']
    panel[selected_columns].to_parquet(out/'REFERENCE_DAY_METADATA.parquet',index=False)
    lookup=panel.set_index(['analysis_window','sid','day'],verify_integrity=True)
    matches=pd.read_parquet(run/'CALIPER_MATCHED_PAIRS.parquet');mp=[]
    for x in matches.to_dict('records'):
        w=lookup.loc[(x['analysis_window'],x['warning_sid'],x['day'])];c=lookup.loc[(x['analysis_window'],x['control_sid'],x['day'])]
        both=w.label_status=='COMPLETE_20' and c.label_status=='COMPLETE_20'
        same=bool(both and w.forward20_end_day==c.forward20_end_day)
        mp.append(dict(analysis_window=x['analysis_window'],day=x['day'],warning_sid=x['warning_sid'],control_sid=x['control_sid'],
            endpoint_status='BOTH_COMPLETE_SAME_ENDPOINT' if same else 'BOTH_COMPLETE_DIFFERENT_ENDPOINT' if both else 'ONE_OR_BOTH_FORWARD20_MISSING',
            warning_end=w.forward20_end_day,control_end=c.forward20_end_day,
            warning_calendar_span=w.forward20_calendar_span,control_calendar_span=c.forward20_calendar_span,
            warning_MFE20=w.MFE20,warning_MAE20=w.MAE20,control_MFE20=c.MFE20,control_MAE20=c.MAE20,
            warning_active_cross=bool(w.active_cross_warning),warning_strict_extra=bool(w.extra_rawleg_strict_candidate),
            warning_first_hit=w.first_hit20_label,control_first_hit=c.first_hit20_label,
            warning_rebound=w.rebound_after_down,control_rebound=c.rebound_after_down,
            warning_rawleg=w.raw_E0_leg_current,control_rawleg=c.raw_E0_leg_current))
    matched=pd.DataFrame(mp);matched.to_parquet(out/'MATCHED_ENDPOINT_AND_RAWLEG_METADATA.parquet',index=False)
    result=dict(status='READ_ONLY_METADATA_CORRECTION_NO_MODEL_OR_REMATCH',new_CUSUM_runs=0,new_CP_runs=0,new_matches=0,new_accounts=0,source_sha256=bindings,
        original_panel_rows_with_overlap=original_rows,scope_warning='Appendix periods overlap; do not sum windows',windows={})
    for window,q in panel.groupby('analysis_window',sort=True):
        active=q.loc[q.active_cross_warning.eq(True)]
        old=q.loc[q.extra_incremental_active_cross_candidate.eq(True)]
        extra=q.loc[q.extra_rawleg_strict_candidate.eq(True)]
        m=matched.loc[matched.analysis_window.eq(window)];same=m.loc[m.endpoint_status.eq('BOTH_COMPLETE_SAME_ENDPOINT')]
        def pair_stats(z):
            both=z.loc[z.endpoint_status.ne('ONE_OR_BOTH_FORWARD20_MISSING')]
            return dict(n=len(z),both_full20_n=len(both),
                warning_MFE20=None if not len(both) else float(both.warning_MFE20.mean()),control_MFE20=None if not len(both) else float(both.control_MFE20.mean()),
                warning_MAE20=None if not len(both) else float(both.warning_MAE20.mean()),control_MAE20=None if not len(both) else float(both.control_MAE20.mean()),
                warning_first_hit=ccounts(z.warning_first_hit),control_first_hit=ccounts(z.control_first_hit))
        final=dict(selected_reference_days=len(q),selected_stocks=q.sid.nunique(),active_cross_n=len(active),active_cross_stocks=active.sid.nunique(),active_cross_I_cycles=active.cycle_id.nunique(),
            policy_target_candidate_n=len(old),policy_candidates_raw_leg_counts=ccounts(old.raw_E0_leg_status),
            strict_extra_n=len(extra),strict_extra_fraction_all_active_cross=None if not len(active) else len(extra)/len(active),
            strict_extra_path=pathstats(extra),strict_extra_CP_lead=dist(extra.lead_to_CP_exit_observations_LABEL_ONLY),
            strict_extra_CP_status=ccounts(extra.saved_CP_exit_status_LABEL_ONLY),strict_extra_E0_lead=dist(extra.next_E0_down_same_I_cycle_lead_LABEL_ONLY),strict_extra_E0_status=ccounts(extra.next_E0_down_status_LABEL_ONLY),
            strict_extra_CP_exit_within20_n=int(extra.lead_to_CP_exit_observations_LABEL_ONLY.between(1,20).sum()),strict_extra_E0_down_within20_n=int(extra.next_E0_down_same_I_cycle_lead_LABEL_ONLY.between(1,20).sum()),
            all_match_endpoint_status=ccounts(m.endpoint_status),same_endpoint_fraction_all_match=None if not len(m) else len(same)/len(m),
            all_complete_future_calendar_spans=dist(q.forward20_calendar_span),same_endpoint_matched=pair_stats(same),
            matched_cross_subset=pair_stats(m.loc[m.warning_active_cross]),matched_strict_extra_subset=pair_stats(m.loc[m.warning_strict_extra]))
        result['windows'][window]=final
    (out/'METADATA_SUMMARY.json').write_text(json.dumps(engine.clean(result),ensure_ascii=False,indent=2,allow_nan=False))
    (out/'RECEIPT.json').write_text(json.dumps(dict(status=result['status'],script_sha256=sha(__file__),original_run_receipt_sha256=sha(run/'RUN_RECEIPT.json'),outputs={p.name:sha(p) for p in out.iterdir() if p.is_file()},new_model_runs=0,new_matches=0,new_accounts=0),indent=2))
    for k,v in result['windows'].items():print(k,json.dumps({x:v[x] for x in ['active_cross_n','policy_target_candidate_n','strict_extra_n','strict_extra_fraction_all_active_cross','all_match_endpoint_status','matched_strict_extra_subset']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
