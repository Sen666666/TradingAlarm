"""Selected-paper activation arithmetic under explicit NO EXIT premise. No account."""
from pathlib import Path
import argparse, hashlib, importlib.util, math, json, csv
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None or x is pd.NA:return None
    if isinstance(x,np.generic):x=x.item()
    return None if isinstance(x,float) and not math.isfinite(x) else x
def save(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main(sid,activation):
    out=HERE/'frozen_features'/(sid.replace('.','_')+'_PAPER_CONDITIONAL')
    out.mkdir(exist_ok=False)
    pp=HERE/(sid.replace('.','_')+'_ORIGINAL_PREFIX_OHLC.parquet')
    fp=HERE/'frozen_features'/(sid.replace('.','_')+'_FULL_PREFIX_FEATURES.parquet')
    feature_receipt=HERE/'frozen_features/FEATURE_RECEIPT.json'
    receipt=json.loads(feature_receipt.read_text())
    helper=ROOT/'indicators.py';paper=ROOT/'PAPER_SPEC.md'
    assert sha(helper)==receipt['source_sha256'][str(helper)]
    assert sha(paper)==receipt['source_sha256'][str(paper)]
    spec=importlib.util.spec_from_file_location('frozen_channel_gt_only',helper);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    price=pd.read_parquet(pp);f=pd.read_parquet(fp);p=price.loc[activation:];ff=f.loc[p.index]
    assert ff.valid_bar.all(), 'Fixed paper interval contains unknown source; no silent carry permitted.'
    launch_C=float(p.iloc[0].close);launch_ATR=float(ff.iloc[0].ATR14_prior)
    results={};all_events=[]
    for L in [20,55]:
        eligible=ff[ff[f'break{L}'].eq(True)]
        if eligible.empty:
            results[str(L)]={'first_confirm':None};continue
        t0=eligible.index[0];A=float(price.loc[t0,'close']);S=float(f.loc[t0,'ATR14_prior'])
        frontier=A;consumed=0;events=[]
        for t,row in price.loc[t0:].iterrows():
            C=float(row.close)
            if t==t0:
                events.append(dict(sid=sid,L=L,day=str(t.date()),kind='CHANNEL_CONFIRM',C=C,A=A,S=S,j=0,
                                   U=float(f.loc[t,f'U{L}']),z=float(f.loc[t,f'z{L}']),rolloff=bool(f.loc[t,f'rolloff{L}'])))
                continue
            before=frontier;frontier=max(frontier,C);j=math.floor((frontier-A)/S)
            if m.gt(C,before) and j>consumed:
                events.append(dict(sid=sid,L=L,day=str(t.date()),kind='ATR_NET_ADVANCE',C=C,A=A,S=S,j=j,
                                   previous_consumed_j=consumed,prior_close_frontier=before,
                                   same_day_channel_break=bool(f.loc[t,f'break{L}']),
                                   same_day_U=float(f.loc[t,f'U{L}']),same_day_z=float(f.loc[t,f'z{L}'])))
                consumed=j
        results[str(L)]={'first_confirm':str(t0.date()),'A':A,'S':S,'raw_A_at_that_day':float(price.loc[t0,'raw_close']),
                         'raw_S_same_day_coordinate':S/float(price.loc[t0,'adjustment_factor']),
                         'first_confirm_z':float(f.loc[t0,f'z{L}']),
                         'first_confirm_rolloff':bool(f.loc[t0,f'rolloff{L}']),
                         'events':events,'scope':'NO EXIT premise only; not actual held, not V5 execution/mature/grant.'}
        all_events.extend(events)
    sensitivity=[]
    key=json.loads((HERE/'frozen_features/FIXED_KEY_DAYS.json').read_text())
    for row in key:
        if row['sid']!=sid or row['day']<activation:continue
        t=pd.Timestamp(row['day']);prior=p.loc[p.index<t]
        M=None if prior.empty else float(prior.high.max());atr=float(f.loc[t,'ATR14_prior'])
        for N in [2,3,4]:
            line=None if M is None else M-N*atr
            sensitivity.append(dict(sid=sid,day=row['day'],activation=activation,N=N,
                M_prior_from_activation=M,ATR_prior=atr,C=float(price.loc[t,'close']),
                unratcheted_M_minus_N_ATR=line,
                raw_coordinate_line=None if line is None else line/float(price.loc[t,'adjustment_factor']),
                line_ge_C=None if line is None else not m.gt(float(price.loc[t,'close']),line),
                scope='Static paper sensitivity, assumes no prior exit; not actual P_old/max(I,P_old) or executable sell price.'))
    early=[str(t.date()) for t,row in p.iterrows() if float(row.close)-launch_C>=2*launch_ATR]
    save(out/'POST_ACTIVATION_PAPER.json',dict(sid=sid,activation=activation,
        no_exit_premise=True,actual_position_or_order_claim=False,arms=results,
        early_progress_diagnostic_only=dict(launch_C=launch_C,launch_ATR_prior=launch_ATR,
                                           first_C_minus_launch_ge_2_frozen_ATR=None if not early else early[0],not_permission_OR=True)))
    save(out/'PRIOR_PEAK_N2_N3_N4_SENSITIVITY.json',sensitivity)
    save(out/'NET_ADVANCE_EVENTS.json',all_events)
    save(out/'PAPER_RECEIPT.json',dict(source_sha256={str(x):sha(x) for x in [pp,fp,feature_receipt,helper,paper,Path(__file__)]},
         new_accounts=0,new_quantities=0,new_returns=0,no_exit_assumption=True,N_selected=False))
    print(json.dumps(clean({'sid':sid,'activation':activation,'arms':{k:{q:v.get(q) for q in ['first_confirm','A','S','first_confirm_z','first_confirm_rolloff']} for k,v in results.items()},
        'key_events':[e for e in all_events if e['day'] in ['2024-09-23','2024-09-24','2024-09-30','2024-10-10','2024-10-11','2024-10-14','2024-10-16','2024-11-01','2024-11-04']],
        'key_N_lines':[r for r in sensitivity if r['day'] in ['2024-10-10','2024-10-11','2024-11-01','2024-11-04']]}),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sid',required=True);p.add_argument('--activation',required=True)
    a=p.parse_args();main(a.sid,a.activation)
