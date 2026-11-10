"""Read saved pair JSON only: native exit OPEN reference quality, never PnL."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,time
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
VALID='REFERENCE_ONLY_NOT_EXECUTABLE_FILL'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def positive(v):return isinstance(v,(int,float)) and math.isfinite(v) and v>0
def quote_ok(q):return isinstance(q,dict) and q.get('quote_status')==VALID and positive(q.get('OPEN'))
def save(n,x):(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def distribution(values):
    values=[float(v) for v in values];a=np.array(values,dtype=float);n=len(values)
    if not n:return dict(n=0,negative_n=0,zero_n=0,positive_n=0,negative_sum=None,positive_sum=None,total_sum=None,
                          mean=None,quantiles=None,unit='percentage_points_of_common_entry_OPEN')
    neg=[x for x in values if x<0];pos=[x for x in values if x>0]
    probs=[0,.01,.05,.1,.25,.5,.75,.9,.95,.99,1]
    return dict(n=n,negative_n=len(neg),zero_n=sum(v==0 for v in values),positive_n=len(pos),
                negative_sum=math.fsum(neg),positive_sum=math.fsum(pos),total_sum=math.fsum(values),
                mean=float(a.mean()),quantiles={str(p):float(q) for p,q in zip(probs,np.quantile(a,probs,method='linear'))},
                unit='percentage_points_of_common_entry_OPEN')
def relation(cp,at):
    return 'ATR_EARLIER' if at['exit_day']<cp['exit_day'] else 'SAME_SIGNAL_DAY' if at['exit_day']==cp['exit_day'] else 'ATR_LATER'
def raw_counts(rows):
    both=0;common=0;outcomes=Counter()
    for r in rows:
        cp,at=r.get('CP'),r.get('ATR3')
        if not cp or not at:continue
        outcomes[cp['outcome']+' / '+at['outcome']]+=1
        if cp['outcome']==at['outcome']=='EXIT_SIGNAL':
            both+=1
            common+=int(quote_ok(r.get('entry_reference')) and quote_ok(cp.get('next_observation_quote')) and quote_ok(at.get('next_observation_quote')))
    return dict(raw_anchors=len(rows),pair_status_counts=dict(Counter(r['status'] for r in rows)),
                both_native_exit_signals=both,both_exit_with_three_valid_reference_OPENs=common,
                paired_branch_outcome_counts=dict(outcomes))


def summarize(rows):
    status=Counter(r['status'] for r in rows);outcomes=Counter();timing_all=Counter();missing=Counter()
    entry_status=Counter();cp_quote_status=Counter();atr_quote_status=Counter()
    common=[];non_common_examples=[];both=0
    for r in rows:
        cp,at=r.get('CP'),r.get('ATR3');entry=r.get('entry_reference')
        entry_status[(entry or {}).get('quote_status','NO_ENTRY_REFERENCE')]+=1
        if not cp or not at:continue
        outcomes[cp['outcome']+' / '+at['outcome']]+=1
        if cp['outcome']=='EXIT_SIGNAL':cp_quote_status[(cp.get('next_observation_quote') or {}).get('quote_status','NO_QUOTE_OBJECT')]+=1
        if at['outcome']=='EXIT_SIGNAL':atr_quote_status[(at.get('next_observation_quote') or {}).get('quote_status','NO_QUOTE_OBJECT')]+=1
        if cp['outcome']!='EXIT_SIGNAL' or at['outcome']!='EXIT_SIGNAL':continue
        both+=1;rel=relation(cp,at);timing_all[rel]+=1
        reasons=[]
        if not quote_ok(entry):reasons.append('ENTRY_OPEN_MISSING_NONPOSITIVE_OR_STATUS_NOT_VALID')
        if not quote_ok(cp.get('next_observation_quote')):reasons.append('CP_EXIT_OPEN_MISSING_NONPOSITIVE_OR_STATUS_NOT_VALID')
        if not quote_ok(at.get('next_observation_quote')):reasons.append('ATR_EXIT_OPEN_MISSING_NONPOSITIVE_OR_STATUS_NOT_VALID')
        if reasons:
            missing[' + '.join(reasons)]+=1
            if len(non_common_examples)<12:non_common_examples.append(dict(sid=r['sid'],anchor_day=r['anchor_day'],reasons=reasons))
            continue
        oe=float(entry['OPEN']);oc=float(cp['next_observation_quote']['OPEN']);oa=float(at['next_observation_quote']['OPEN'])
        rc=100*(oc/oe-1);ra=100*(oa/oe-1);delta=100*(oa-oc)/oe
        common.append(dict(sid=r['sid'],anchor_day=r['anchor_day'],relation=rel,d_pp=delta,r_CP=rc,r_ATR=ra,
                           CP_holding_observations=cp['effective_observations_held'],ATR_holding_observations=at['effective_observations_held'],
                           identity_error=abs(delta-(ra-rc))))
    by_relation={}
    for rel in ['ATR_EARLIER','SAME_SIGNAL_DAY','ATR_LATER']:
        a=[x for x in common if x['relation']==rel]
        by_relation[rel]=dict(n=len(a),d_pp=distribution(x['d_pp'] for x in a),
                             r_CP=distribution(x['r_CP'] for x in a),r_ATR=distribution(x['r_ATR'] for x in a),
                             CP_mean_holding_observations=None if not a else float(np.mean([x['CP_holding_observations'] for x in a])),
                             ATR_mean_holding_observations=None if not a else float(np.mean([x['ATR_holding_observations'] for x in a])))
    return dict(raw_anchor_n=len(rows),all_samples_execution_unknown=True,
                execution_unknown_n=len(rows),pair_status_counts=dict(status),
                paired_shadows_n=sum(outcomes.values()),paired_branch_outcome_counts=dict(outcomes),
                both_EXIT_SIGNAL_n=both,timing_relation_among_both_exit_signals=dict(timing_all),
                non_both_exit_outcomes_not_assigned_early_late={k:v for k,v in outcomes.items() if k!='EXIT_SIGNAL / EXIT_SIGNAL'},
                entry_reference_status_counts=dict(entry_status),CP_exit_reference_status_counts=dict(cp_quote_status),
                ATR_exit_reference_status_counts=dict(atr_quote_status),
                both_exit_excluded_missing_reference_n=sum(missing.values()),both_exit_missing_reference_reason_counts=dict(missing),
                missing_reference_examples=non_common_examples,common_valid_reference_n=len(common),
                common_valid_reference_entry_denominator='Same saved entry_reference.OPEN for both branches of each anchor, finite >0 and status exactly '+VALID,
                common_valid_reference_d_pp=distribution(x['d_pp'] for x in common),
                common_valid_reference_r_CP=distribution(x['r_CP'] for x in common),
                common_valid_reference_r_ATR=distribution(x['r_ATR'] for x in common),
                common_valid_reference_by_timing_relation=by_relation,
                max_abs_dpp_minus_rATR_plus_rCP=None if not common else max(x['identity_error'] for x in common))


def main():
    started=time.monotonic();sources={};historical=[];semiconductor=[]
    batches=[('shard_a',24151),('shard_b',23974),('semiconductor_full',2901)]
    for folder,expected in batches:
        root=ROOT/folder/'run_v1';rp=root/'RUN_RECEIPT.json';sources[str(rp)]=sha(rp)
        receipt=json.loads(rp.read_text());assert receipt['status']=='COMPLETE' and receipt['raw_CP_anchors']==expected
        current=[]
        for path in sorted(root.glob('*/CP_ANCHOR_PAIRS.json')):
            sources[str(path)]=sha(path);current.extend(json.loads(path.read_text()))
        assert len(current)==expected
        (semiconductor if folder=='semiconductor_full' else historical).extend(current)
    assert len(historical)+len(semiconductor)==51026
    symbols=ROOT/'semiconductor_full/SYMBOLS126.json';sources[str(symbols)]=sha(symbols)
    fixed=set(json.loads(symbols.read_text()));assert all(r['sid'] in fixed for r in semiconductor)
    windows={
       '2022_2023':[r for r in historical if '2022-01-01'<=r['anchor_day']<='2023-12-31'],
       '2024_0924_1231':[r for r in historical if '2024-09-24'<=r['anchor_day']<='2024-12-31'],
       '2026_H1_fixed_semiconductor126':[r for r in semiconductor if '2026-01-01'<=r['anchor_day']<='2026-06-30']}
    full924=[r for r in historical if '2024-09-01'<=r['anchor_day']<='2024-12-31']
    pre924=[r for r in historical if '2024-09-01'<=r['anchor_day']<='2024-09-23']
    assert len(full924)==12412 and len(semiconductor)==2901 and len(windows['2026_H1_fixed_semiconductor126'])==1220
    groups={name:summarize(rows) for name,rows in windows.items()}
    bridge=dict(original_2024_0901_1231=raw_counts(full924),excluded_2024_0901_0923=raw_counts(pre924),
                frozen_2024_0924_1231=raw_counts(windows['2024_0924_1231']),
                semiconductor_original_2025_2026H1_raw=2901,semiconductor_excluded_2025_raw=1681,semiconductor_frozen_2026H1_raw=1220)
    output=dict(status='SAVED_PAIR_NATIVE_EXIT_OPEN_REFERENCE_STATS_COMPLETE',
        formulas=dict(d_pp='100*(OPEN_ATR_exit-OPEN_CP_exit)/common_entry_OPEN',
                      r_CP='100*(OPEN_CP_exit/common_entry_OPEN-1)',r_ATR='100*(OPEN_ATR_exit/common_entry_OPEN-1)'),
        source_pair_rows_read=51026,groups=groups,period_bridge=bridge,
        quote_policy='Both EXIT_SIGNAL; entry/CP exit/ATR exit each finite positive OPEN and exact reference-valid status. No fill is inferred.',
        units='Unweighted percentage points per raw CP anchor; overlapping anchors and securities are not independent account trades.',
        execution_unknown_for_every_source_anchor=True,
        interpretation='Common entry / each branch native exit quote. Horizons differ; not a fixed-horizon effect, executable trade profit or account return. No costs, position size, capacity, order ACK, halt/limit confirmation or reinvestment.',
        fixed_H20_or_postexit5_analysis_run=False,source_sha256=sources,script_sha256=sha(__file__),
        new_FSM_runs=0,new_accounts=0,new_parameters=0,elapsed_seconds=time.monotonic()-started)
    save('EXIT_OPEN_NATIVE_STATS.json',output)
    save('EXIT_OPEN_NATIVE_STATS_SHA256.json',dict(output_sha256=sha(HERE/'EXIT_OPEN_NATIVE_STATS.json'),script_sha256=sha(__file__)))
    for name,g in groups.items():
        print(json.dumps(dict(group=name,raw=g['raw_anchor_n'],paired=g['paired_shadows_n'],both_exit=g['both_EXIT_SIGNAL_n'],
              common=g['common_valid_reference_n'],missing=g['both_exit_excluded_missing_reference_n'],
              d=g['common_valid_reference_d_pp'],rCP=g['common_valid_reference_r_CP'],rATR=g['common_valid_reference_r_ATR'],
              by_timing={k:dict(n=v['n'],mean_d=v['d_pp']['mean'],negative_d_n=v['d_pp']['negative_n']) for k,v in g['common_valid_reference_by_timing_relation'].items()},
              censored=g['non_both_exit_outcomes_not_assigned_early_late']),ensure_ascii=False),flush=True)
    print('BRIDGE',json.dumps(bridge,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
