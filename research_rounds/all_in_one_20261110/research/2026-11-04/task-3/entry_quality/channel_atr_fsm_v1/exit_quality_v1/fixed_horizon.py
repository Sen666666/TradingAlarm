"""Read stored exits plus original prices. No feature, FSM, account or order run."""
from pathlib import Path
from collections import Counter
import json, hashlib, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
RUNS=[ROOT/x/'run_v1' for x in ['shard_a','shard_b','semiconductor_full']]

def load(p): return json.loads(p.read_text())
def positive(x): return isinstance(x,(int,float,np.number)) and math.isfinite(x) and x>0
def flag(x): return bool(x) if isinstance(x,(bool,np.bool_)) else None
def group(x):
    d=x['anchor_day']
    if x['window']=='2022-01-01__2023-12-31': return '2022_2023'
    if x['window']=='2024-09-01__2024-12-31' and d>='2024-09-24': return '2024_924_DEC'
    if x['window']=='2025-01-01__2026-06-30' and d>='2026-01-01': return '2026_H1_SEMICONDUCTOR'
    return None
def dist(v):
    a=np.asarray([x for x in v if x is not None and math.isfinite(x)],float)
    return dict(n=len(a),**({f'q{int(q*100):02}':float(np.quantile(a,q)) for q in [0,.1,.5,.9,1]} if len(a) else {}),mean=float(np.mean(a)) if len(a) else None)
def perf(rows,key):
    a=[x[key] for x in rows]
    return dict(distribution=dist(a),negative_n=sum(x<0 for x in a),negative_sum_percentage_points=sum(x for x in a if x<0),positive_sum_percentage_points=sum(x for x in a if x>0),zero_n=sum(x==0 for x in a))

def main():
    rows=[];source_bindings={};raw_n=0
    for run in RUNS:
        for pf in sorted(run.glob('*/CP_ANCHOR_PAIRS.json')):
            pairs=load(pf);raw_n+=len(pairs)
            selected=[x for x in pairs if group(x) or x['window']=='2024-09-01__2024-12-31']
            if not selected: continue
            sf=load(pf.parent/'SOURCE_FREEZE.json')
            pp=Path(next(p for p in sf['source_sha256'] if p.endswith('/signal.parquet')))
            actual=hashlib.sha256(pp.read_bytes()).hexdigest();assert actual==sf['source_sha256'][str(pp)]
            source_bindings[str(pp)]=actual
            p=pd.read_parquet(pp,columns=['open','close','high','low','segment_id','price_eligible','observed_bar','synthetic_event_bar','source_invalid'])
            ix=pd.DatetimeIndex(pd.to_datetime(p.index))
            if ix.tz is not None: ix=ix.tz_localize(None)
            p.index=ix.as_unit('ns').normalize();p=p.loc[:'2026-06-30']
            assert p.index.is_unique and p.index.is_monotonic_increasing
            days=[str(t.date()) for t in p.index];lookup={d:i for i,d in enumerate(days)}
            O=p.open.to_numpy();C=p.close.to_numpy();H=p.high.to_numpy();L=p.low.to_numpy();seg=p.segment_id.to_numpy()
            flags=[p[k].to_numpy() for k in ['price_eligible','observed_bar','synthetic_event_bar','source_invalid']]
            eligible=np.array([[flag(v[i]) for v in flags]==[True,True,False,False] for i in range(len(p))])
            valid=np.array([eligible[i] and positive(C[i]) and positive(H[i]) and positive(L[i]) and H[i]>=C[i]>=L[i] for i in range(len(p))])
            def quote_status(j,q):
                if not q or not positive(q.get('OPEN')): return 'NO_KNOWN_SAVED_QUOTE'
                if j+1>=len(p): return 'NO_NEXT_SOURCE_ROW'
                if q.get('next_observation_day')!=days[j+1]: return 'SAVED_QUOTE_SKIPS_SOURCE_ROW'
                if not eligible[j+1] or not positive(O[j+1]) or seg[j+1]!=seg[j]: return 'NEXT_SOURCE_ROW_UNKNOWN_OR_INCOMPARABLE'
                assert math.isclose(O[j+1],q['OPEN'],rel_tol=1e-12,abs_tol=1e-12)
                return 'REFERENCE_ONLY_CLOCK_MATCH'
            for x in selected:
                r=dict(sid=x['sid'],anchor_day=x['anchor_day'],anchor_id=x['anchor_id'],primary_group=group(x),original_window=x['window'],pair_status=x['status'],common_end_day=x.get('common_end_day'),common_end_reason=x.get('common_end_reason'),h20_status='NOT_PAIRED',execution_status='UNKNOWN_FOR_ALL_REFERENCES')
                rows.append(r)
                if x['status']!='PAIRED_SHADOWS': continue
                a=lookup[x['anchor_day']];E=x['entry_reference']['OPEN'];assert positive(E)
                r['entry_OPEN']=E;r['entry_clock']=quote_status(a,x['entry_reference'])
                if r['entry_clock']!='REFERENCE_ONLY_CLOCK_MATCH': r['h20_status']='ENTRY_QUOTE_CLOCK_UNQUALIFIED';continue
                end=lookup.get(x['common_end_day'],len(p)-1)
                if x['common_end_reason'] in ['UNKNOWN_DATA_OR_I','SOURCE_INCOMPARABLE']:
                    end-=1  # These boundary rows are excluded by the original stored common lifecycle.
                future=[];bad=False
                for j in range(a+1,end+1):
                    if not valid[j] or seg[j]!=seg[a]: bad=True;break
                    future.append(j)
                # Local exit diagnostics are conditional on the original native-I common lifecycle.
                for arm in ['CP','ATR3']:
                    b=x[arm];r[f'{arm}_outcome']=b['outcome'];r[f'{arm}_exit_day']=b['exit_day'];r[f'{arm}_post5_status']='NO_EXIT_SIGNAL'
                    if b['outcome']!='EXIT_SIGNAL': continue
                    j=lookup[b['exit_day']];q=b['next_observation_quote'];clock=quote_status(j,q);r[f'{arm}_exit_quote_clock']=clock
                    if clock!='REFERENCE_ONLY_CLOCK_MATCH':r[f'{arm}_post5_status']='EXIT_QUOTE_CLOCK_UNQUALIFIED';continue
                    X=q['OPEN'];r[f'{arm}_exit_OPEN']=X;r[f'{arm}_native_proxy_pp']=100*(X/E-1)
                    before=[k for k in future if k<=j]
                    if before:r[f'{arm}_preexit_close_giveback_pp']=100*(max(C[k] for k in before)-X)/E
                    after=[k for k in future if k>j][:5]
                    if len(after)<5:
                        r[f'{arm}_post5_status']='SHORT_ORIGINAL_I_LIFECYCLE' if x['common_end_reason']=='ORIGINAL_I_INVALID' else 'UNKNOWN_OR_SOURCE_END_UNDER5'
                        continue
                    closes=[float(C[k]) for k in after];r[f'{arm}_post5_status']='COMPLETE_5_WITHIN_ORIGINAL_I'
                    r[f'{arm}_post5_endpoint_pp']=100*(closes[-1]/X-1)
                    r[f'{arm}_post5_max_pp']=100*(max(closes)/X-1);r[f'{arm}_post5_min_pp']=100*(min(closes)/X-1)
                    r[f'{arm}_post5_all_above_exit_OPEN']=all(c>X for c in closes)
                    r[f'{arm}_post5_strict_up']=all(v>u for u,v in zip(closes[:-1],closes[1:]))
                if len(future)<20:
                    r['h20_status']='UNKNOWN_BEFORE20' if bad or x['common_end_reason'].startswith('UNKNOWN') else 'SHORT_ORIGINAL_I_UNDER20' if x['common_end_reason']=='ORIGINAL_I_INVALID' else 'SOURCE_END_UNDER20'
                    continue
                j20=future[19];r['h20_close_day']=days[j20]
                if j20+1>=len(p) or not eligible[j20+1] or not positive(O[j20+1]) or seg[j20+1]!=seg[a]:
                    r['h20_status']='TERMINAL_OPEN_UNKNOWN_OR_INCOMPARABLE';continue
                T=float(O[j20+1]);r['terminal_day']=days[j20+1];r['terminal_OPEN']=T;r['common_H20_proxy_pp']=100*(T/E-1)
                good=True
                for arm in ['CP','ATR3']:
                    b=x[arm];exitindex=lookup.get(b['exit_day'])
                    if b['outcome']=='UNKNOWN' and b['effective_observations_held']<=20:
                        good=False;continue
                    if exitindex is not None and exitindex<=j20:
                        if r.get(f'{arm}_exit_quote_clock')!='REFERENCE_ONLY_CLOCK_MATCH':good=False;continue
                        X=r[f'{arm}_exit_OPEN'];kind='SAVED_EXIT_QUOTE_WITHIN20'
                        if exitindex==j20:assert X==T
                    else:X=T;kind='COMMON_H20_MARK_NOT_EXIT'
                    r[f'{arm}_H20_kind']=kind;r[f'{arm}_H20_proxy_pp']=100*(X/E-1)
                r['h20_status']='PAIRED_H20_QUOTED' if good else 'ONE_ARM_UNKNOWN_OR_EXIT_QUOTE_UNQUALIFIED'
                if good:r['H20_ATR_minus_CP_pp']=r['ATR3_H20_proxy_pp']-r['CP_H20_proxy_pp']
    assert raw_n==51026
    pd.DataFrame(rows).to_parquet(HERE/'PRICE_DIAGNOSTIC_ROWS.parquet',index=False)
    out=dict(status='READ_ONLY_SAVED_EXITS_NO_FSM_OR_ACCOUNT',raw_existing_mother=raw_n,diagnostic_rows=len(rows),H=20,post_exit_K=5,groups={},source_price_sha256=source_bindings,new_accounts=0,new_orders=0,new_FSM_runs=0,halt_count='UNKNOWN_NOT_INFERRED_FROM_MISSING_DATES')
    groups=['2022_2023','2024_924_DEC','2026_H1_SEMICONDUCTOR','BRIDGE_2024_SEP_DEC']
    for g in groups:
        rr=[r for r in rows if r['primary_group']==g] if not g.startswith('BRIDGE') else [r for r in rows if r['original_window']=='2024-09-01__2024-12-31']
        h=[r for r in rr if r['h20_status']=='PAIRED_H20_QUOTED']
        z=dict(raw_anchor_n=len(rr),distinct_stocks=len({r['sid'] for r in rr}),pair_status=dict(Counter(r['pair_status'] for r in rr)),h20_funnel=dict(Counter(r['h20_status'] for r in rr)),all_actual_execution_UNKNOWN_n=len(rr),branches={})
        for arm in ['CP','ATR3']:
            z['branches'][arm]=dict(H20=perf(h,f'{arm}_H20_proxy_pp'),H20_kind=dict(Counter(r[f'{arm}_H20_kind'] for r in h)),post5_status=dict(Counter(r.get(f'{arm}_post5_status','NOT_PAIRED_OR_ENTRY_UNKNOWN') for r in rr)),preexit_giveback_pp=dist([r.get(f'{arm}_preexit_close_giveback_pp') for r in rr]))
            post=[r for r in rr if r.get(f'{arm}_post5_status')=='COMPLETE_5_WITHIN_ORIGINAL_I']
            z['branches'][arm]['post5']=dict(n=len(post),endpoint_pp=dist([r[f'{arm}_post5_endpoint_pp'] for r in post]),max_close_pp=dist([r[f'{arm}_post5_max_pp'] for r in post]),min_close_pp=dist([r[f'{arm}_post5_min_pp'] for r in post]),all_above_exit_OPEN_n=sum(r[f'{arm}_post5_all_above_exit_OPEN'] for r in post),strict_up_n=sum(r[f'{arm}_post5_strict_up'] for r in post))
        z['H20_ATR_minus_CP_pp']=dist([r['H20_ATR_minus_CP_pp'] for r in h]);z['H20_ATR_better_n']=sum(r['H20_ATR_minus_CP_pp']>0 for r in h);z['H20_ATR_worse_n']=sum(r['H20_ATR_minus_CP_pp']<0 for r in h);z['H20_same_n']=sum(r['H20_ATR_minus_CP_pp']==0 for r in h)
        label_rows=[r for r in rr if 'common_H20_proxy_pp' in r]
        if label_rows:
            threshold=float(np.quantile([r['common_H20_proxy_pp'] for r in label_rows],.9));w_all=[r for r in label_rows if r['common_H20_proxy_pp']>=threshold];w=[r for r in h if r['common_H20_proxy_pp']>=threshold]
            z['common_H20_strong_q90']=dict(threshold_pp=threshold,label='FUTURE_DIAGNOSTIC_WINNERS' if threshold>0 else 'RELATIVE_STRONG_QUANTILE_NOT_WINNERS',common_label_n=len(label_rows),strong_label_n=len(w_all),n=len(w),strong_label_but_paired_comparison_unavailable_n=len(w_all)-len(w),stocks=len({r['sid'] for r in w}),CP=perf(w,'CP_H20_proxy_pp'),ATR3=perf(w,'ATR3_H20_proxy_pp'),ATR_minus_CP_pp=dist([r['H20_ATR_minus_CP_pp'] for r in w]))
            for arm in ['CP','ATR3']:
                total=z['branches'][arm]['H20']['positive_sum_percentage_points'];winner_positive=z['common_H20_strong_q90'][arm]['positive_sum_percentage_points']
                z['common_H20_strong_q90'][arm]['share_of_all_positive_unit_price_proxies']=winner_positive/total if total>0 else None
            z['diagnostic_examples_ATR_worse']=sorted(h,key=lambda r:r['H20_ATR_minus_CP_pp'])[:3]
            z['diagnostic_examples_ATR_better']=sorted(h,key=lambda r:r['H20_ATR_minus_CP_pp'],reverse=True)[:3]
        out['groups'][g]=z
    (HERE/'FIXED_H20_AND_POST5_STATS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
    for g,z in out['groups'].items():
        print(g,json.dumps({k:z[k] for k in ['raw_anchor_n','h20_funnel','H20_ATR_minus_CP_pp','H20_ATR_better_n','H20_ATR_worse_n','H20_same_n']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
