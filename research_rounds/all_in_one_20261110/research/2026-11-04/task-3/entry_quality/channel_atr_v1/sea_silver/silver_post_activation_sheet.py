"""Silver selected activation arithmetic only; no position or holding peak defined."""
from pathlib import Path
import importlib.util, hashlib, json, math
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=HERE/'frozen_features/300085_SZ_PAPER_CONDITIONAL'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    OUT.mkdir(exist_ok=False)
    pp=HERE/'300085_SZ_ORIGINAL_PREFIX_OHLC.parquet'
    fp=HERE/'frozen_features/300085_SZ_FULL_PREFIX_FEATURES.parquet'
    hp=ROOT/'indicators.py';sp=ROOT/'PAPER_SPEC.md';ep=HERE/'frozen_features/ORIGINAL_E0_EVENT_DATES.json'
    sources={str(p):sha(p) for p in [pp,fp,hp,sp,ep,Path(__file__)]}
    spec=importlib.util.spec_from_file_location('silver_frozen_gt',hp);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    price=pd.read_parquet(pp);f=pd.read_parquet(fp);activation='2024-08-30'
    source=json.loads(ep.read_text());original=next(r for r in source['original_event_rows'] if r['sid']=='300085.SZ')
    assert original['last_positive_before_September'][0]['confirmed_at']==activation
    assert f.loc[activation:].valid_bar.all()
    arms={};events=[]
    for L in [20,55]:
        hit=f.loc[activation:];hit=hit[hit[f'break{L}'].eq(True)]
        assert not hit.empty
        t0=hit.index[0];A=float(price.loc[t0,'close']);S=float(f.loc[t0,'ATR14_prior']);F=A;consumed=0;path=[]
        for t,p in price.loc[t0:].iterrows():
            C=float(p.close)
            if t==t0:
                path.append(dict(L=L,day=str(t.date()),kind='CHANNEL_CONFIRM',C=C,raw_C=float(p.raw_close),
                    A=A,S=S,j=0,U=float(f.loc[t0,f'U{L}']),z=float(f.loc[t0,f'z{L}']),rolloff=bool(f.loc[t0,f'rolloff{L}'])))
                continue
            before=F;F=max(F,C);j=math.floor((F-A)/S)
            if helper.gt(C,before) and j>consumed:
                path.append(dict(L=L,day=str(t.date()),kind='ATR_NET_ADVANCE',C=C,raw_C=float(p.raw_close),
                    A=A,S=S,j=j,previous_consumed_j=consumed,prior_close_frontier=before,
                    same_day_channel_break=bool(f.loc[t,f'break{L}']),same_day_z=float(f.loc[t,f'z{L}'])))
                consumed=j
        arms[str(L)]={'first_confirm':str(t0.date()),'A':A,'S':S,'raw_A':float(price.loc[t0,'raw_close']),
                     'raw_S_same_coordinate':S/float(price.loc[t0,'adjustment_factor']),
                     'first_z':float(f.loc[t0,f'z{L}']),'first_rolloff':bool(f.loc[t0,f'rolloff{L}']), 'events':path}
        events.extend(path)
    save('POST_ACTIVATION_PAPER.json',dict(sid='300085.SZ',activation=activation,
         activation_instruction='Parent explicitly selected original August30 positive confirmation; no September activation invented.',
         activation_is_not_holding_start=True,no_exit_premise=True,ordinary_down_does_not_reset_milestones_under_this_premise=True,
         hard_I_P_failure_not_replayed=True,actual_position_or_order_claim=False,arms=arms,
         holding_peak_and_N_lines='NOT_DEFINED: no actual layer/protection activation; E0 activation high is not a holding peak.'))
    save('NET_ADVANCE_EVENTS.json',events)
    save('PAPER_RECEIPT.json',dict(source_sha256=sources,feature_calculations=0,new_accounts=0,new_quantities=0,new_returns=0,
                                 activation_is_E0_eligibility_only=True,holding_peak_computed=False))
    print(json.dumps({'arms':{k:{z:v[z] for z in ['first_confirm','A','S','raw_A','raw_S_same_coordinate','first_z','first_rolloff']} for k,v in arms.items()},
        'fixed_events':[e for e in events if e['day'] in ['2024-09-24','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11','2024-10-14','2024-10-16','2024-10-28','2024-10-30']]},ensure_ascii=False))


if __name__=='__main__':main()
