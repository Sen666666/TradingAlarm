"""Prepare original OHLC source facts only; no channel/ATR/trading algorithm run."""
from pathlib import Path
import json, hashlib, math, csv
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
RULES = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if x is pd.NA or x is None: return None
    if isinstance(x, np.generic): x=x.item()
    if isinstance(x, pd.Timestamp): return str(x.date())
    return None if isinstance(x,float) and not math.isfinite(x) else x
def save(n,x): (HERE/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    metas={r['symbol']:r for r in json.loads(SM.read_text())};sources={str(SM):sha(SM),str(RULES):sha(RULES)}
    schema=[];bars=[]
    keys=['2024-09-19','2024-09-20','2024-09-24','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11','2024-10-31','2024-11-01','2024-11-04','2024-11-05']
    for sid in ['002583.SZ','300085.SZ']:
        meta=metas[sid];path=Path(next(p for p in meta['source_sha256'] if p.endswith('/signal.parquet')))
        sources[str(path)]=sha(path);assert sources[str(path)]==meta['source_sha256'][str(path)]
        f=pd.read_parquet(path).loc[:'2024-11-29'];window=f.loc['2024-09-01':'2024-11-29']
        hlc=np.isfinite(f[['high','low','close']]).all(axis=1)&f[['high','low','close']].gt(0).all(axis=1)
        source=f.observed_bar.fillna(False).astype(bool)&f.price_eligible.fillna(False).astype(bool)&~f.synthetic_event_bar.fillna(True).astype(bool)&~f.source_invalid.fillna(True).astype(bool)
        geometry=f.high.ge(f[['low','close']].max(axis=1))&f.low.le(f[['high','close']].min(axis=1))
        ready=hlc&source&geometry
        export=f.copy();export['prepared_observed_HLC_source_eligible']=ready
        export.to_parquet(HERE/(sid.replace('.','_')+'_ORIGINAL_PREFIX_OHLC.parquet'))
        maxdiff={c:float((window[c]-window['raw_'+c]*window.adjustment_factor).abs().max()) for c in ['open','high','low','close']}
        for day in keys:
            if pd.Timestamp(day) not in f.index:continue
            row=f.loc[day]
            bars.append(dict(sid=sid,day=day,**{c:row[c] for c in ['raw_open','raw_high','raw_low','raw_close','open','high','low','close','adjustment_factor','raw_volume','amount','source_kind','source_path','price_adjustment','observed_bar','source_invalid','synthetic_event_bar','segment_id']},
                source_HLC_ready=bool(ready.loc[day]),flat_bar_H_equals_L_expost=bool(row.raw_high==row.raw_low),
                halt_status='NOT_RECORDED_UNKNOWN',price_limit_status='NOT_RECORDED_UNKNOWN',
                previous_20_55_highs='NOT_CALCULATED_AWAIT_FROZEN_OBSERVATION_RULE',
                ATR14_tminus1='NOT_CALCULATED_AWAIT_FROZEN_RMA_SEED_AND_GAP_RULE'))
        schema.append(dict(sid=sid,source_path=str(path),source_columns=list(f),first_day=str(f.index[0].date()),last_day=str(f.index[-1].date()),
            full_prefix_rows=len(f),source_HLC_ready_rows=int(ready.sum()),window_rows=len(window),
            window_source_HLC_all_ready=bool(ready.loc[window.index].all()),
            source_unready_dates=[str(t.date()) for t in f.index[~ready]],
            segment_values=clean(f.segment_id.unique().tolist()),window_factors=clean(window.adjustment_factor.unique().tolist()),
            window_OHLC_raw_times_factor_max_abs_difference=maxdiff,
            direct_halt_limit_ST_receive_columns=[c for c in f if any(v in c.lower() for v in ['halt','suspend','limit','is_st','risk_warning','receive'])]))
    rule=json.loads(RULES.read_text());fieldpaths=[]
    def walk(x,p=''):
        if isinstance(x,dict):
            for k,v in x.items():fieldpaths.append(p+'.'+k);walk(v,p+'.'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,p+f'[{i}]')
    walk(rule)
    needles={'limit_up','limit_down','limit_ratio','upper_limit','lower_limit','halt','suspend','is_st','risk_warning','tick'}
    found=[p for p in fieldpaths if p.split('.')[-1] in needles]
    save('SOURCE_SCHEMA_AND_READINESS.json',schema);save('KEY_ORIGINAL_OHLC_BARS.json',bars)
    with (HERE/'KEY_ORIGINAL_OHLC_BARS.csv').open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(bars[0]));w.writeheader();w.writerows(bars)
    save('EXECUTION_FLAG_AVAILABILITY.json',dict(actual_rules_path=str(RULES),rules_top_level=list(rule),explicit_limit_halt_ST_tick_fields_found=found,
        signal_direct_flag_status='No direct halt/ST/daily legal limit/real receive field in either frozen source schema.',
        availability_original=rule.get('availability'),
        limitations=['H=L is a completed daily-bar fact, not a verified locked-limit flag or trade guarantee.',
        'Missing/nonobserved/synthetic bars are not suspension proofs.',
        'Current source_path raw store may have been updated; frozen prepared source SHA is the data binding.',
        'Daily OHLC cannot establish next OPEN quote, queue, order arrival/fill/cancel ACK.']))
    save('PREPARATION_RECEIPT.json',dict(status='ORIGINAL_OHLC_READY_INDICATORS_NOT_RUN',source_sha256=sources,script_sha256=sha(__file__),
        channel_or_ATR_calculations=0,new_strategies=0,new_accounts=0,new_quantities=0,new_returns=0))
    print(json.dumps(clean(schema),ensure_ascii=False))


if __name__=='__main__':main()
