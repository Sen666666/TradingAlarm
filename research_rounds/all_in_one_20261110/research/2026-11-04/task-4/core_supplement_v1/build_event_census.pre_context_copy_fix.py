"""One frozen EMA pullback event census. No account or order construction."""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib, json, time
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
M = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
WINDOWS = [('long', '2022-01-01', '2024-12-31'), ('strong', '2025-07-01', '2026-06-30')]
SOURCES = {}

def bind(path):
    path = Path(path)
    SOURCES[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path

def save(name, value):
    (O/name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def compute(f):
    c = f.close.astype(float)
    valid = np.isfinite(c) & c.gt(0) & f.segment_id.notna()
    block = (f.segment_id.ne(f.segment_id.shift()) | ~valid | ~valid.shift(fill_value=False)).cumsum()
    ema = c.where(valid).groupby(block, sort=False).transform(lambda s:s.ewm(span=20, adjust=False, min_periods=20).mean())
    prev_c = c.groupby(block, sort=False).shift()
    prev_e = ema.groupby(block, sort=False).shift()
    prior_high = c.where(valid).groupby(block, sort=False).transform(lambda s:s.rolling(20, min_periods=20).max().shift())
    on = valid & f.e0_target.eq(1)
    run = (block.ne(block.shift(fill_value=-1)) | on.ne(on.shift(fill_value=False))).cumsum()
    seq = pd.Series(np.arange(len(f)), index=f.index)
    floor = pd.to_numeric(f.e0_floor, errors='coerce').astype(float)
    floor_ok = np.isfinite(floor) & c.gt(floor)
    B = on & floor_ok & prior_high.notna() & prev_e.notna() & c.gt(prior_high) & c.gt(ema) & ema.gt(prev_e)
    prior_b = seq.where(B).groupby(run, sort=False).ffill().groupby(run, sort=False).shift()
    P = on & floor_ok & prev_e.notna() & c.gt(ema) & ema.gt(prev_e) & prev_c.le(prev_e) & (seq-prior_b).between(1, 20)
    known_i = f.i_target.isin([0,1])
    known_buy = f.i_buy.isin([False,True])
    i_on = valid & known_i & f.i_target.eq(1)
    prior_i = i_on.groupby(run, sort=False).cummax().groupby(run, sort=False).shift(fill_value=False)
    state = pd.Series('OUTSIDE_E0', index=f.index, dtype=object)
    state.loc[on & ~known_i] = 'UNKNOWN_I'
    state.loc[valid & ~f.e0_target.isin([0,1])] = 'UNKNOWN_E0'
    state.loc[on & known_i & ~i_on & ~prior_i] = 'A_I_never_started_in_E0'
    state.loc[on & known_i & ~i_on & prior_i] = 'A2_I_previously_started_now_off'
    state.loc[on & i_on & ~known_buy] = 'UNKNOWN_I_BUY'
    state.loc[on & i_on & known_buy & ~f.i_buy.eq(True)] = 'B_I_on_no_i_buy'
    state.loc[on & i_on & known_buy & f.i_buy.eq(True)] = 'C_original_i_buy'
    return pd.DataFrame(dict(close=c, source=f.segment_id, price_block=block, e0_run=run,
                             ema20=ema, ema20_previous=prev_e, previous_close=prev_c,
                             prior20_high=prior_high, B=B, P=P, prior_b_index=prior_b,
                             state=state, valid=valid, E0=on, I=i_on), index=f.index)

def future_labels(z, idx, stop):
    """Close-to-close evaluation only, same source/block, and no horizon past window."""
    cv,bv,dates=z.attrs['_forward_ctx']
    c = float(cv[idx]); result = {}
    for h in (5, 20, 60):
        j = idx+h
        if j >= len(z) or z.index[j] > stop or bv[j] != bv[idx]:
            result[str(h)] = None
        else:
            path = cv[idx+1:j+1]
            result[str(h)] = dict(end_day=dates[j],
                                  close_return_pct=(float(cv[j])/c-1)*100,
                                  min_close_return_pct=(float(path.min())/c-1)*100,
                                  max_close_return_pct=(float(path.max())/c-1)*100)
    return result

def main():
    started = time.monotonic(); bind(__file__); bind(O/'PRICE_EVENT_PRECARD.txt')
    records = json.loads(bind(M).read_text()); assert len(records)==1709
    pullbacks=[]; breakouts=[]; episodes=[]; prefixes=[]; totals=defaultdict(Counter)
    samples={r['symbol'] for r in records[::150]} | {'300666.SZ','301611.SZ','603061.SH'}
    for r in records:
        assert time.monotonic()-started < 120, 'Frozen read-only event construction budget exceeded'
        sid=r['symbol']; path=bind(r['refs']['facts'])
        assert SOURCES[str(path)] == r['output_sha256'][str(path)]
        f=pd.read_parquet(path, columns=['close','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','factor','raw_close'])
        assert f.index.is_unique and f.index.is_monotonic_increasing
        z=compute(f)
        if sid in samples:
            for cut in ('2023-12-29','2024-09-30','2026-03-31'):
                small=compute(f.loc[:cut]); pd.testing.assert_frame_equal(small,z.loc[small.index],check_exact=True)
                prefixes.append(dict(sid=sid,cut=cut,rows=len(small),passed=True))
        z.attrs['_forward_ctx']=(z.close.to_numpy(),z.price_block.to_numpy(),[str(d.date()) for d in z.index])
        run_starts={int(z.e0_run.iloc[i]):str(z.index[i].date()) for i in np.flatnonzero(z.e0_run.ne(z.e0_run.shift(fill_value=-1)).to_numpy(dtype=bool))}
        for w,lo,hi in WINDOWS:
            stop=pd.Timestamp(hi); mask=(z.index>=pd.Timestamp(lo)) & (z.index<=stop)
            for state,n in z.loc[mask,'state'].value_counts().items():totals[w]['stock_CLOSEs_'+state]+=int(n)
            for kind, store in [('B',breakouts),('P',pullbacks)]:
                for d in z.index[mask & z[kind]]:
                    i=z.index.get_loc(d); row=z.loc[d]; fact=f.loc[d]
                    event=dict(window=w,sid=sid,day=str(d.date()),event=kind,state=row.state,
                               source_segment=int(row.source),e0_run_start=run_starts[int(row.e0_run)],
                               close=float(row.close),ema20=float(row.ema20),previous_ema20=float(row.ema20_previous),
                               original_i_target=bool(fact.i_target) if pd.notna(fact.i_target) else None,
                               original_i_buy=bool(fact.i_buy) if pd.notna(fact.i_buy) else None,
                               original_e0_floor=float(fact.e0_floor) if pd.notna(fact.e0_floor) else None,
                               original_i_floor=float(fact.i_floor) if pd.notna(fact.i_floor) else None,
                               price_evaluation_only=True,future=future_labels(z,i,stop))
                    if kind=='P':
                        b=int(row.prior_b_index); touch=z.iloc[b+1:i+1]; touch=touch.index[touch.close.le(touch.ema20)]
                        assert len(touch) and z.B.iloc[b] and z.e0_run.iloc[b]==row.e0_run
                        event.update(breakout_day=str(z.index[b].date()),breakout_age_observations=i-b,
                                     breakout_close=float(z.close.iloc[b]),first_EMA20_close_touch=str(touch[0].date()),
                                     price_progress_since_breakout_pct=(float(row.close)/float(z.close.iloc[b])-1)*100)
                    store.append(event);totals[w][kind+'_'+row.state]+=1
            # Every E0 run with at least one true not-yet-activated I observation is retained,
            # including zero breakout/zero pullback. Known history before each window is not reset.
            raw=z.loc[mask & z.state.eq('A_I_never_started_in_E0')]
            for run,a in raw.groupby('e0_run',sort=False):
                inds=z.index.get_indexer(a.index); first=int(inds[0]); last=int(inds[-1])
                bs=a.index[a.B]; ps=a.index[a.P]
                later=z.loc[(z.index>=a.index[0]) & (z.index<=stop) & z.e0_run.eq(run)]
                i_dates=later.index[later.I]; bpos=z.index.get_loc(bs[0]) if len(bs) else None
                next_p=z.index[(z.index>bs[0]) & (z.index<=stop) & z.e0_run.eq(run) & z.P] if len(bs) else pd.DatetimeIndex([])
                next_i=z.index[(z.index>=bs[0]) & (z.index<=stop) & z.e0_run.eq(run) & z.I] if len(bs) else pd.DatetimeIndex([])
                rec=dict(window=w,sid=sid,e0_run_start=run_starts[int(run)],gap_first_day=str(a.index[0].date()),
                         gap_last_day=str(a.index[-1].date()),gap_observations=len(a),breakout_count=int(a.B.sum()),
                         pullback_count=int(a.P.sum()),first_breakout=str(bs[0].date()) if len(bs) else None,
                         first_gap_pullback=str(ps[0].date()) if len(ps) else None,
                         first_original_I_active=str(i_dates[0].date()) if len(i_dates) else None,
                         first_P_after_B=str(next_p[0].date()) if len(next_p) else None,
                         first_P_wait_observations=z.index.get_loc(next_p[0])-bpos if len(next_p) else None,
                         first_P_wait_natural_days=(next_p[0]-bs[0]).days if len(next_p) else None,
                         original_I_active_on_or_after_B=str(next_i[0].date()) if len(next_i) else None,
                         from_first_B_future=future_labels(z,bpos,stop) if bpos is not None else None)
                episodes.append(rec)
    # All aggregation is descriptive; future outcomes never feed compute().
    groups=[]
    for w,_,_ in WINDOWS:
        for kind,rows in [('B',breakouts),('P',pullbacks)]:
            for state in ('A_I_never_started_in_E0','A2_I_previously_started_now_off','B_I_on_no_i_buy','C_original_i_buy'):
                a=[x for x in rows if x['window']==w and x['state']==state]
                g=dict(window=w,event=kind,state=state,events=len(a),stocks=len({x['sid'] for x in a}),
                       stock_source_E0_epochs=len({(x['sid'],x['source_segment'],x['e0_run_start']) for x in a}),future={})
                for h in ('5','20','60'):
                    vals=[x['future'][h]['close_return_pct'] for x in a if x['future'][h] is not None]
                    lows=[x['future'][h]['min_close_return_pct'] for x in a if x['future'][h] is not None]
                    g['future'][h]=dict(known=len(vals),unknown=len(a)-len(vals),mean_close_return_pct=float(np.mean(vals)) if vals else None,
                                          median_close_return_pct=float(np.median(vals)) if vals else None,
                                          negative_close_returns=sum(v<0 for v in vals),
                                          min_close_below_minus10pct=sum(v<=-10 for v in lows))
                groups.append(g)
    save('P_EVENTS.json',pullbacks);save('B_EVENTS.json',breakouts);save('ALL_A_GAP_EPISODES.json',episodes)
    save('EVENT_CENSUS_SUMMARY.json',dict(price_rule='PRICE_EVENT_PRECARD.txt',stocks=1709,windows=WINDOWS,
         totals={w:dict(c) for w,c in totals.items()},groups=groups,A_gap_episodes=len(episodes),
         physical_prefix_checks=prefixes,seconds=time.monotonic()-started,limit_seconds=120,
         new_accounts=0,new_authorizations=0,scope='Raw price evidence and original frozen E0/I states only; forward close labels are not execution or account profit.'))
    save('EVENT_SOURCE_SHA256.json',SOURCES)
    print(json.dumps(dict(P_events=len(pullbacks),B_events=len(breakouts),A_gap_episodes=len(episodes),
                         totals={w:dict(c)for w,c in totals.items()},physical_prefix_checks=len(prefixes),seconds=time.monotonic()-started),ensure_ascii=False,indent=2))

if __name__=='__main__':
    attempt_started=time.monotonic()
    try:main()
    finally:print(json.dumps(dict(attempt_elapsed_seconds=time.monotonic()-attempt_started)),flush=True)
