"""Five named 924 cases: saved actual chains and bounded causal snapshots only.

No execution/strategy objects, signal experiment over the universe, or backtest.
Existing EMA/BB columns are reused. Only prior20-close-high and volume descriptors are
computed at an explicit finite list of actual decision/execution dates.
"""
from pathlib import Path
from decimal import Decimal
import csv
import gzip
import hashlib
import json
import math
import pickle
import time
import pandas as pd

O = Path(__file__).resolve().parent
ROOT = O.parents[1]
BASE = ROOT / 'new_price_trend_v1/funding/runs/long_OFF/pair'
SOURCES = {}
NAMES = {'002583.SZ': '海能达', '300085.SZ': '银之杰',
         '300339.SZ': '润和软件', '301236.SZ': '软通动力', '688593.SH': '新相微'}
ANCHORS = ['2024-09-23', '2024-09-24', '2024-09-30', '2024-10-08', '2024-10-09']
HAI_OBSERVATIONS = ['2024-10-14', '2024-10-15', '2024-10-16', '2024-10-17',
    '2024-10-18', '2024-10-21', '2024-10-22', '2024-10-23', '2024-10-24',
    '2024-10-25', '2024-10-28', '2024-10-29', '2024-10-30', '2024-10-31',
    '2024-11-01', '2024-11-04', '2024-11-05', '2024-11-26', '2024-11-27']

def bind(path):
    path = Path(path)
    SOURCES[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path

def read(path):
    return json.loads(bind(path).read_text())

def gz(path, lines=False):
    with gzip.open(bind(path), 'rt') as f:
        return list(map(json.loads, f)) if lines else json.load(f)

def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if hasattr(x, 'item'): return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x): return None
    if isinstance(x, (Decimal, pd.Timestamp)): return str(x)
    return x

def save(name, x):
    (O / name).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2) + '\n')

def main():
    start = time.monotonic()
    bind(__file__)
    b = gz(BASE / 'B.json.gz')
    actual_layers = [x for x in b['layers'] if x['sid'] in NAMES
                     and '2024-09-23' <= x['opened'][:10] <= '2024-12-31']
    buys = {x['layer']: x for x in b['trades'] if x['side'] == 'buy'}
    days = {sid: set(ANCHORS) for sid in NAMES}
    days['002583.SZ'].update(HAI_OBSERVATIONS)
    chains = []
    for layer in actual_layers:
        lid = layer['id']; sid = layer['sid']; buy = buys[lid]
        sells = [{**t, 'selected_part': p} for t in b['trades']
                 if t['side'] == 'sell' for p in t['parts'] if p['layer'] == lid]
        # B.exits is the final pending-exit map (empty after flattening), not the
        # historical proposal stream. Historical CLOSE proposals are in audit.
        proposals = [x for x in b['audit'] if x.get('kind') == 'pilot_layer_exit'
                     and lid in x.get('layers', [])]
        assert proposals, ('Saved actual layer has no historical exit proposal', lid)
        points = {buy['signal_at'][:10], buy['at'][:10], layer['closed'][:10]}
        points.update(x['at'][:10] for x in proposals)
        days[sid].update(points)
        chains.append(dict(name=NAMES[sid], sid=sid, layer=lid, original_role=buy['kind'],
            original_buy=buy, exit_proposals=proposals, actual_sells=sells,
            final_layer=layer, terminal_net_contribution=str(Decimal(layer['cash'])+Decimal(layer['dividend'])),
            mandatory_keypoint_dates=sorted(points)))
    save('ACTUAL_NINE_LAYER_CHAINS.json', chains)
    save('FINITE_SNAPSHOT_DATE_PLAN.json', {sid: sorted(ds) for sid, ds in days.items()})
    daily = {x['at'][:10]: x for x in gz(BASE / 'daily.jsonl.gz', True)
             if x['at'][:10] in set().union(*days.values())}
    saved_classes = read(ROOT / 'review_924_v1/review/INDEPENDENT_ACTUAL_BUY_CLASSIFICATIONS.json')
    for x in chains:
        x['actual_entry_classification'] = saved_classes.get(str(x['layer']))
    save('ACTUAL_NINE_LAYER_CHAINS.json', chains)
    feat_path = bind(ROOT / 'new_price_trend_v1/PRICE_FEATURES.pkl')
    fm = read(ROOT / 'new_price_trend_v1/PRICE_FEATURE_MANIFEST.json')
    assert SOURCES[str(feat_path.resolve())] == fm['output_sha256']
    features = pickle.loads(feat_path.read_bytes())
    bind(ROOT / 'new_price_trend_v1/build_price_features.py')
    bind(ROOT / 'new_price_trend_v1/review/BB20_FEATURE_FORMULA_AUDIT.json')
    manifest_path = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    records = {r['symbol']: r for r in read(manifest_path)}
    raw_manifest = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json')
    raw_records = {r['series_id']: r for r in read(raw_manifest)['series']}
    snapshots = []
    for sid in NAMES:
        rec = records[sid]
        fp = bind(rec['refs']['facts'])
        assert SOURCES[str(fp.resolve())] == rec['output_sha256'][str(fp)]
        facts = pd.read_parquet(fp)
        cp = pd.read_parquet(bind(rec['refs']['CP1']))
        rawref = raw_records[sid]['raw']; rp = bind(rawref['path'])
        assert SOURCES[str(rp.resolve())] == rawref['sha256']
        raw = pd.read_parquet(rp)
        raw = raw.set_index(pd.to_datetime(raw.trade_date)).sort_index()
        assert facts.index.is_unique and raw.index.is_unique
        pf = features[sid]
        for day in sorted(days[sid]):
            d = pd.Timestamp(day)
            assert d in facts.index and d in pf.index and d in raw.index
            f = facts.loc[d]; z = pf.loc[d]; r = raw.loc[d]
            assert math.isclose(float(z.close), float(f.close), rel_tol=1e-12)
            assert math.isclose(float(f.raw_close), float(r.close), rel_tol=1e-12)
            idx = raw.index.get_loc(d)
            window = raw.iloc[idx-20:idx]
            wf = facts.reindex(window.index)
            valid_window = (len(window) == 20 and wf.segment_id.notna().all()
                and wf.segment_id.eq(f.segment_id).all() and wf.factor.notna().all()
                and window[['open', 'high', 'low', 'close']].notna().all().all()
                and window['high'].gt(0).all()
                and window['low'].gt(0).all()
                and all(math.isclose(float(a), float(c), rel_tol=1e-12)
                        for a, c in zip(wf.raw_close, window.close)))
            hh = float(wf.close.astype(float).max()) if valid_window else None
            ll = float((window.low.astype(float) * wf.factor.astype(float)).min()) if valid_window else None
            prev = pf.loc[:d].iloc[-2]
            known = bool(z.ema_trend_known) and valid_window
            high_breakout = bool(float(f.close) > hh) if valid_window else None
            ema_up = bool(float(z.ema20) > float(z.ema60)) if bool(z.ema_trend_known) else None
            above_ema20 = bool(float(f.close) > float(z.ema20)) if pd.notna(z.ema20) else None
            ema20_rising = bool(float(z.ema20) > float(prev.ema20)) if pd.notna(z.ema20) and pd.notna(prev.ema20) else None
            hold = bool(float(f.close) >= float(z.ema20) and float(z.ema20) > float(z.ema60)) if bool(z.ema_trend_known) else None
            progress = bool(high_breakout and above_ema20 and ema20_rising) if valid_window and above_ema20 is not None and ema20_rising is not None else None
            original = daily[day]
            live = [l for l in original['layers'] if l['sid'] == sid]
            cr = cp.loc[d] if d in cp.index else None
            snapshots.append(dict(sid=sid, name=NAMES[sid], day=day,
                clock='CLOSE 15:10 +08; earliest new execution next tradable OPEN, not an order',
                original_fields=f.to_dict(), original_CP1_fields=cr.to_dict() if cr is not None else None,
                saved_price_features=z.to_dict(),
                raw_ohlcv={k:r.get(k) for k in ['open','high','low','close','volume','observed_bar']},
                source_crosscheck_raw_close_exact=True,
                prev_raw_close=float(raw.iloc[idx-1].close),
                open_gap_vs_prev_CLOSE_pct=(float(r.open)/float(raw.iloc[idx-1].close)-1)*100,
                flat_day_proxy=bool(r.high <= r.low),
                raw_limit_queue_not_available=True,
                original_account=dict(NAV=original['nav'], held_quantity=original['positions'].get(sid,0),
                    live_layers=live, ACT_on=original['on']),
                finite_descriptors=dict(prior20_window_known=valid_window,
                    prior20_dates=[str(x.date()) for x in window.index],
                    prior20_adjusted_close_high=hh, prior20_adjusted_intraday_low_context_only=ll,
                    prior20_close_high_raw_equivalent=hh/float(f.factor) if hh is not None else None,
                    current_close_above_prior20_close_high=high_breakout,
                    current_close_above_prior_BB_upper=bool(float(f.close)>float(z.bb20_prior_upper)) if pd.notna(z.bb20_prior_upper) else None,
                    EMA20_above_EMA60=ema_up,
                    current_close_above_EMA20=above_ema20,
                    EMA20_rising_one_observation=ema20_rising,
                    EMA20_slope_one_observation=float(z.ema20)-float(prev.ema20),
                    current_volume_over_prior20_mean=float(r.volume)/float(window.volume.mean()) if window.volume.mean()>0 else None,
                    exploratory_price_progress_C_HC20_EMA20_rising=progress,
                    exploratory_hold_above_EMA20_and_EMA20_above_EMA60=hold)))
    save('FINITE_KEYPOINT_SNAPSHOTS.json', snapshots)
    selected = set().union(*days.values())
    funding = [r for r in gz(BASE/'funding.jsonl.gz', True)
               if r.get('sid') in NAMES and r.get('at','')[:10] in days[r['sid']]]
    opportunities = [r for r in gz(BASE/'opportunities.jsonl.gz', True)
               if r.get('sid') in NAMES and r.get('day') in days[r['sid']]]
    save('SAVED_KEYPOINT_FUNDING.json', funding)
    save('SAVED_KEYPOINT_OPPORTUNITIES.json', opportunities)
    headers=['name','sid','day','raw_close','raw_open','raw_high','raw_low','EMA20_raw_equiv','EMA60_raw_equiv',
             'prior20_close_high_raw_equiv','above_prior20_close_high','above_prior_BB_upper','BB_cross',
             'EMA20_gt_EMA60_context','C_gt_EMA20','EMA20_rising','price_progress_descriptor','E0','I_target','I_buy',
             'I_floor_raw_equiv','CP_receipt','CP_candidate_raw_equiv','actual_live_layer_floors_raw_equiv','held_qty','flat_day_proxy']
    with (O/'KEYPOINT_TABLE.csv').open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=headers);w.writeheader()
        for x in snapshots:
            f=x['original_fields'];z=x['saved_price_features'];v=x['finite_descriptors'];c=x['original_CP1_fields']
            w.writerow(dict(name=x['name'],sid=x['sid'],day=x['day'],raw_close=f['raw_close'],
                raw_open=x['raw_ohlcv']['open'],raw_high=x['raw_ohlcv']['high'],raw_low=x['raw_ohlcv']['low'],
                EMA20_raw_equiv=float(z['ema20'])/float(f['factor']),EMA60_raw_equiv=float(z['ema60'])/float(f['factor']),
                prior20_close_high_raw_equiv=v['prior20_close_high_raw_equivalent'],above_prior20_close_high=v['current_close_above_prior20_close_high'],
                above_prior_BB_upper=v['current_close_above_prior_BB_upper'],BB_cross=z['bb20_cross'],
                EMA20_gt_EMA60_context=v['EMA20_above_EMA60'],C_gt_EMA20=v['current_close_above_EMA20'],EMA20_rising=v['EMA20_rising_one_observation'],
                price_progress_descriptor=v['exploratory_price_progress_C_HC20_EMA20_rising'],E0=f['e0_target'],I_target=f['i_target'],I_buy=f['i_buy'],
                I_floor_raw_equiv=float(f['i_floor'])/float(f['factor']) if pd.notna(f['i_floor']) else None,
                CP_receipt=c['receipt'] if c else None,CP_candidate_raw_equiv=float(c['candidate'])/float(f['factor']) if c is not None and pd.notna(c['candidate']) else None,
                actual_live_layer_floors_raw_equiv=';'.join(str(l['id'])+':'+str(float(l['floor'])/float(f['factor'])) for l in x['original_account']['live_layers']),
                held_qty=x['original_account']['held_quantity'],flat_day_proxy=x['flat_day_proxy']))
    save('SOURCE_SHA256.json',SOURCES)
    save('SCOPE_AND_COST.json',dict(named_stocks=5, actual_layers=len(chains), finite_snapshots=len(snapshots),
        snapshot_counts={sid:len(ds) for sid,ds in days.items()},
        new_universe_signal_experiments=0,new_accounts=0,new_backtests=0,new_parameter_tests=0,new_Market_Runner_RiskBook=0,
        existing_feature_table_reused=True,new_E0_I_CP_PVR_calculation=False,
        new_finite_descriptors='Prior20 same-source close maximum (NOT intraday high), low context, volume ratio, existing EMA/BB comparisons at explicit listed keypoints only; EMA60 is context, not an initial-entry gate',
        selection='Parent named successful HaiNengDa and failed YinZhiJie/RuanTong/XinXiangWei; include RunHe. Selected by known actual outcomes, illustrative case study only, no performance claims.',
        missing_fields=['True historical limit order queue and executable depth','Original strategy did not log EMA/BB as decision inputs; these are existing causal numeric features, not evidence original rules consulted them',
            'No frozen trend-holding structure/persistence duration/stress budget definition','V-shaped and slow bull counterexamples not yet sampled across universe'],
        runtime_seconds=time.monotonic()-start))
    print(json.dumps(dict(layers=len(chains),snapshots=len(snapshots),seconds=time.monotonic()-start,new_accounts=0)))

if __name__=='__main__':main()
