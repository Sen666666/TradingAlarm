"""Ten explicit points only: reuse saved EMA and bound prior10-close inputs."""
from pathlib import Path
import csv
import hashlib
import json
import math
import pickle
import time
import pandas as pd

O=Path(__file__).resolve().parent
ROOT=O.parents[1]
PLAN={
    '002583.SZ':['2024-10-15','2024-10-16','2024-10-21'],
    '300085.SZ':['2024-10-10'],
    '300339.SZ':['2024-10-10'],
    '301236.SZ':['2024-10-10'],
    '688593.SH':['2024-10-10','2024-10-11','2024-10-21','2024-10-23'],
}
LAYER_IDS=[1963,1967,1971,1972,2031]
SOURCES={}
def bind(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def main():
    start=time.monotonic();bind(__file__)
    prior=read(O/'FINITE_KEYPOINT_SNAPSHOTS.json')
    lookup={(x['sid'],x['day']):x for x in prior}
    chains=read(O/'ACTUAL_NINE_LAYER_CHAINS.json')
    fp=bind(ROOT/'new_price_trend_v1/PRICE_FEATURES.pkl')
    fm=read(ROOT/'new_price_trend_v1/PRICE_FEATURE_MANIFEST.json')
    assert SOURCES[str(fp.resolve())]==fm['output_sha256']
    features=pickle.loads(fp.read_bytes())
    card=bind(ROOT/'upside_state_v1/PAPER_CARD.txt')
    rows=[]
    for sid,days in PLAN.items():
        f=features[sid]
        for day in days:
            d=pd.Timestamp(day);j=f.index.get_loc(d);z=f.iloc[j]
            old=lookup[sid,day];factor=float(old['original_fields']['factor'])
            ten=f.iloc[j-10:j];six=f.iloc[j-5:j+1];lag=f.iloc[j-5];prev=f.iloc[j-1]
            l10_known=(len(ten)==10 and ten.source_segment.notna().all()
                and ten.source_segment.eq(z.source_segment).all()
                and ten.close.notna().all() and ten.close.gt(0).all())
            slope_known=(len(six)==6 and six.source_segment.notna().all()
                and six.source_segment.eq(z.source_segment).all()
                and six.close.notna().all() and six.close.gt(0).all()
                and six.ema20.notna().all())
            assert l10_known and slope_known, (sid,day,'Unexpected unknown input')
            l10=float(ten.close.min());c=float(z.close);ema=float(z.ema20)
            lag5=float(lag.ema20)
            t5=bool(c>ema and ema>lag5)
            oldv=old['finite_descriptors']
            b5=bool(t5 and oldv['current_close_above_prior20_close_high'])
            x=bool(c<=float(z.ema60) or
                (c<ema and float(prev.close)<float(prev.ema20) and c<l10))
            rows.append(dict(sid=sid,name=old['name'],day=day,source_segment=int(z.source_segment),
                fixed_clock='Known at this stock CLOSE; no new order/quantity or portfolio simulation',
                close=c,EMA20=ema,EMA20_lag5=lag5,EMA20_lag5_day=str(f.index[j-5].date()),
                prev10_close_min=l10,prev10_input_dates=[str(x.date())for x in ten.index],
                prev10_input_close=[float(x)for x in ten.close],
                prev5_EMA20_comparison_input_dates=[str(x.date())for x in six.index],
                raw_equivalents=dict(close=c/factor,EMA20=ema/factor,EMA20_lag5=lag5/factor,prev10_close_min=l10/factor),
                T5=t5,B5=b5,old_D_one_day_slope=oldv['exploratory_price_progress_C_HC20_EMA20_rising'],
                old_one_day_EMA20_rising=oldv['EMA20_rising_one_observation'],
                candidate_X_from_known_inputs_only=x,
                original_CP_receipt=old['original_CP1_fields']['receipt'],
                original_I_target=bool(old['original_fields']['i_target']),
                original_I_buy=bool(old['original_fields']['i_buy']),
                actual_held_qty=old['original_account']['held_quantity'],
                original_live_layer_floors=old['original_account']['live_layers']))
    save('T5_L10_FINITE_ADDENDUM.json',dict(scope='Only10 explicit points: HaiNengDa3 and5 selected losing layers first-buy/first-exit points deduplicated7. The sixth losing layer2042 remains in original9-layer evidence but is not recomputed here.',
        selected_losing_layer_ids=LAYER_IDS,plan=PLAN,
        formula=dict(T5='C_t > EMA20_t AND EMA20_t > EMA20_(t-5)',B5='T5 AND C_t > max(C_(t-20)..C_(t-1))',
            L10='min(C_(t-10)..C_(t-1)), same source, excluding today',
            old_D='C_t > prior20_close_max AND C_t > EMA20_t AND EMA20_t > EMA20_(t-1); the last two comparisons are algebraically equivalent under standard EMA, not independent evidence'),
        rows=rows,source_sha256=SOURCES,
        cost=dict(seconds=time.monotonic()-start,new_accounts=0,new_backtests=0,new_parameter_tests=0,
            recomputed_EMA_series=0,new_universe_feature_experiments=0,native_price_evaluations=0,
            finite_lag_lookups=10,finite_prev10_minima=10)))
    headers=['name','sid','day','close_raw_equiv','EMA20_raw_equiv','EMA20_lag5_day','EMA20_lag5_raw_equiv',
        'prev10_close_min_raw_equiv','T5','B5','old_D','candidate_X_only','original_CP_receipt','original_I_target','actual_held_qty']
    with (O/'T5_L10_KEYPOINT_TABLE.csv').open('w',newline='')as out:
        w=csv.DictWriter(out,fieldnames=headers);w.writeheader()
        for x in rows:
            r=x['raw_equivalents'];w.writerow(dict(name=x['name'],sid=x['sid'],day=x['day'],
                close_raw_equiv=r['close'],EMA20_raw_equiv=r['EMA20'],EMA20_lag5_day=x['EMA20_lag5_day'],
                EMA20_lag5_raw_equiv=r['EMA20_lag5'],prev10_close_min_raw_equiv=r['prev10_close_min'],
                T5=x['T5'],B5=x['B5'],old_D=x['old_D_one_day_slope'],candidate_X_only=x['candidate_X_from_known_inputs_only'],
                original_CP_receipt=x['original_CP_receipt'],original_I_target=x['original_I_target'],actual_held_qty=x['actual_held_qty']))
    print(json.dumps(dict(points=len(rows),new_accounts=0,seconds=time.monotonic()-start)))

if __name__=='__main__':main()
