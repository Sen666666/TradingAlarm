"""Frozen E0 event replay and structure-conditional PVR, no accounts/orders.

Stage generation never loads outcome files. Diagnose is a separate invocation
which consumes an already-written and hashed stage/rank table.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse, datetime, hashlib, json, math, os, sys, time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parent
CORE = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code')
sys.path.insert(0, str(CORE))
from numeric import event_frame_numeric, compare, higher
from data_utils import eligible_prices

DATES = ['2022-01-24', '2024-09-24', '2026-01-15']
CASES = json.loads((HERE / 'FREEZE.json').read_text())['cases']
SOURCE = Path(json.loads((HERE / 'FREEZE.json').read_text())['source'])
PRIOR = {d: ENTRY / 'full_local_signal_two_dates_v1' / d / 'FROZEN_IBUY_PRIOR_RANKS.parquet' for d in DATES}
PRIOR[DATES[1]] = ENTRY / 'pvr_924_discrimination_v1/FROZEN2313_PRIOR_RANKS.parquet'
RAW = {d: ENTRY / 'full_local_signal_two_dates_v1' / d / 'signals/ALL_SIGNALS.parquet' for d in DATES}
RAW[DATES[1]] = ENTRY / 'full_local_signal_20240924_v1/signals/ALL_SIGNALS.parquet'
COLS = ['symbol', 'trade_date', 'open', 'high', 'low', 'close', 'volume', 'source']
PRIORITY = {'BREAKOUT': 0, 'START': 1, 'RETRACED': 2}


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for q in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(q)
    return h.hexdigest()


def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if isinstance(x, np.generic): x = x.item()
    if x is pd.NA or x is pd.NaT: return None
    if isinstance(x, (pd.Timestamp, np.datetime64)): return str(pd.Timestamp(x).date())
    if isinstance(x, float) and not math.isfinite(x): return None
    return x


def save(p, x):
    Path(p).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def same(a, b):
    if pd.isna(a) and pd.isna(b): return True
    if isinstance(a, (float, np.floating)) and isinstance(b, (float, np.floating)):
        return np.float64(a).view(np.uint64) == np.float64(b).view(np.uint64)
    return a == b


def binding():
    files = [Path(__file__), HERE / 'FREEZE.json', CORE / 'numeric.py', CORE / 'data_utils.py']
    files += list(PRIOR.values()) + list(RAW.values())
    return {str(p): sha(p) for p in files}


def replay(f, e, trail=False):
    """Original E0 state loop with parallel research-only phase annotation."""
    active, floor, ready = False, math.nan, False
    phase, epoch, subcycle = 'UNKNOWN', 0, 0
    peak = trough = reference = None
    start_date = breakout_date = downgrade_date = None
    last_events, changes = [], []
    for n, row in enumerate(f.itertuples()):
        date, c, ev = row.Index, float(row.close), e.loc[row.Index]
        event = int(ev.event)
        ready = ready or pd.notna(ev.leg_direction)
        exited = entered = 0
        previous_phase = phase
        if active and compare(c, floor) <= 0:
            active, exited, phase = False, 1, 'BROKEN'
            reference = None
            breakout_date = None
        if event:
            fact = dict(price=float(ev.confirmed_pivot_price), occurred=str(ev.confirmed_pivot_date),
                        confirmed=str(date.date()), confirmation=float(ev.confirmation),
                        pivot_age=int(ev.pivot_age), observation=n, kind='TROUGH' if event == 1 else 'PEAK')
            assert fact['occurred'] < fact['confirmed']
            last_events.append(fact)
            if event == 1:
                trough = fact
                if active: floor = higher(floor, fact['price'])
                elif not exited:
                    active, entered, floor = True, 1, fact['price']
                    epoch += 1
            else: peak = fact
        if not ready: phase = 'UNKNOWN'
        elif not active:
            if not exited: phase = 'INACTIVE'
        elif event == -1:
            phase, reference = 'RETRACED', None
            downgrade_date, breakout_date = str(date.date()), None
        elif event == 1:
            phase, reference = 'START', peak.copy() if peak else None
            start_date, breakout_date = str(date.date()), None
            subcycle += 1
        if active and phase == 'START' and reference and compare(c, reference['price']) > 0:
            assert reference['confirmed'] <= str(date.date())
            phase, breakout_date = 'BREAKOUT', str(date.date())
        snapshot = dict(sid=None, day=str(date.date()), phase=phase,
            no_confirmed_peak_reference=phase == 'START' and reference is None,
            research_e0_ready=int(ready), research_e0_target=int(active),
            research_e0_floor=floor if active or exited else math.nan,
            research_e0_entered=entered, research_e0_exited=exited,
            numeric_event=float(event), numeric_leg_direction=ev.leg_direction,
            close=c, epoch=epoch, up_subcycle=subcycle, start_date=start_date,
            breakout_date=breakout_date, downgrade_date=downgrade_date,
            reference_peak=reference['price'] if reference else math.nan,
            reference_peak_occurred=reference['occurred'] if reference else None,
            reference_peak_confirmed=reference['confirmed'] if reference else None,
            reference_age_observations=n-reference['observation'] if reference else None,
            reference_age_calendar_days=(date-pd.Timestamp(reference['confirmed'])).days if reference else None,
            last_confirmed_peak=peak['price'] if peak else math.nan,
            last_peak_occurred=peak['occurred'] if peak else None,
            last_peak_confirmed=peak['confirmed'] if peak else None,
            last_confirmed_trough=trough['price'] if trough else math.nan,
            last_trough_occurred=trough['occurred'] if trough else None,
            last_trough_confirmed=trough['confirmed'] if trough else None,
            close_vs_reference=c/reference['price']-1 if reference else math.nan)
        if trail and (event or previous_phase != phase or entered or exited): changes.append(snapshot.copy())
    return snapshot, changes, last_events[-6:]


def stock(sid, day, g):
    begin = time.monotonic()
    r = dict(sid=sid, day=day, status='MISSING_TARGET', phase='UNKNOWN')
    if g is None or not g.trade_date.eq(pd.Timestamp(day)).any(): return r
    assert g.trade_date.is_unique and g.trade_date.le(pd.Timestamp(day)).all()
    assert g.source.nunique(dropna=False) == 1 and g.source.notna().all()
    f = g.set_index('trade_date')[['open', 'high', 'low', 'close', 'volume']].copy()
    f['segment_id'] = 0
    f = eligible_prices(f)
    if pd.Timestamp(day) not in f.index: return dict(r, status='TARGET_INVALID_PRICE')
    e = event_frame_numeric(f.close, f.volume, joint=True, event_exit=False)
    q, changes, last = replay(f, e, sid in CASES)
    r.update(q)
    r.update(sid=sid, status='COMPLETE', source_prefix_first=str(f.index[0].date()),
        source_prefix_last=str(f.index[-1].date()), eligible_rows=len(f),
        pre2014_history_available=bool(f.index[0] < pd.Timestamp('2014-01-01')),
        full_listing_history_certified=False, last_six_confirmed_events=last,
        case_event_trail=changes, seconds=time.monotonic()-begin)
    return clean(r)


def worker(day, symbols, destination):
    start = time.monotonic()
    data = ds.dataset(SOURCE).to_table(columns=COLS,
        filter=ds.field('symbol').isin(symbols) & (ds.field('trade_date') <= pd.Timestamp(day))).to_pandas()
    groups = {s:g.sort_values('trade_date') for s,g in data.groupby('symbol', sort=False)}
    with Path(destination).open('x') as f:
        for sid in symbols:
            r = stock(sid, day, groups.get(sid))
            f.write(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n')
            f.flush(); os.fsync(f.fileno())
    return dict(day=day, N=len(symbols), seconds=time.monotonic()-start, file=destination, sha256=sha(destination))


def records():
    rows = []
    for p in sorted((HERE/'parts').glob('*.jsonl')):
        for line in p.read_text().splitlines(): rows.append(json.loads(line))
    keys = [(r['day'],r['sid']) for r in rows]
    assert len(keys) == len(set(keys))
    return rows


def check_raw(rows):
    source = {d:pd.read_parquet(RAW[d]).set_index('sid') for d in DATES}
    checked = 0
    for r in rows:
        old = source[r['day']].loc[r['sid']]
        if r['status'] != 'COMPLETE':
            assert old.signal_status != 'EXACT_TARGET_STOCK_SIGNAL', (r['sid'],r['day'])
            continue
        for new, orig in [('research_e0_ready','e0_ready'), ('research_e0_target','e0_target'),
            ('research_e0_floor','e0_floor'), ('research_e0_entered','e0_entered'),
            ('research_e0_exited','e0_exited'), ('numeric_event','numeric_event'),
            ('numeric_leg_direction','numeric_leg_direction'), ('close','close')]:
            assert same(r[new],old[orig]), (r['day'],r['sid'],orig,r[new],old[orig])
        checked += 1
    return checked


def generate(pilot):
    (HERE/'parts').mkdir(exist_ok=True)
    b = binding()
    receipt = HERE/'SOURCE_BINDING.json'
    if receipt.exists(): assert json.loads(receipt.read_text())['files'] == b
    else:
        assert sha(SOURCE) == json.loads((HERE/'FREEZE.json').read_text())['source_sha256']
        save(receipt,dict(files=b,source_sha256=sha(SOURCE),source_size=SOURCE.stat().st_size,
                          source_mtime_ns=SOURCE.stat().st_mtime_ns))
    old = records(); done={(r['day'],r['sid']) for r in old}
    jobs=[]
    for day in DATES:
        cohort=pd.read_parquet(PRIOR[day])
        symbols=['000620.SZ','300666.SZ','300085.SZ','002583.SZ'] if pilot else sorted(set(cohort.sid)|set(CASES))
        pending=[s for s in symbols if(day,s)not in done]
        for n in range(0,len(pending),64):
            dest=HERE/'parts'/f'{day}_{"pilot" if pilot else "full"}_{n//64:03d}_{len(old):04d}.jsonl'
            jobs.append((day,pending[n:n+64],str(dest)))
    start=time.monotonic(); results=[]
    with ProcessPoolExecutor(max_workers=min(10,len(jobs) or 1)) as pool:
        futures=[pool.submit(worker,*j) for j in jobs]
        for f in as_completed(futures):
            result=f.result();results.append(result)
            save(HERE/'LIVE_PROGRESS.json',dict(mode='pilot' if pilot else 'full',completed_new=sum(r['N'] for r in results),jobs_done=len(results),jobs_total=len(jobs),elapsed_seconds=time.monotonic()-start))
            print('BLOCK',result['day'],result['N'],'DONE',len(results),'OF',len(jobs),flush=True)
    allrows=records();checked=check_raw(allrows)
    save(HERE/('PILOT_RECEIPT.json' if pilot else 'GENERATION_RECEIPT.json'),
         dict(status='COMPLETE_EVENT_ONLY_PREFIX_REPLAY_RAW_MATCH',rows=len(allrows),exact_checked=checked,
              wall_seconds=time.monotonic()-start,jobs=results,original_full_signal_models=0,accounts=0))
    print('COMPLETE',len(allrows),'raw matched',checked,'seconds',time.monotonic()-start,flush=True)


def rank():
    assert not (HERE/'STAGED_PRIOR_RANKS.parquet').exists()
    rows=records();check_raw(rows)
    flat=pd.DataFrame([{k:v for k,v in r.items() if k not in ['case_event_trail','last_six_confirmed_events']}for r in rows])
    flat.to_parquet(HERE/'ALL_REQUEST_STAGE_SNAPSHOTS.parquet',index=False)
    flat.to_csv(HERE/'ALL_REQUEST_STAGE_SNAPSHOTS.csv',index=False)
    outputs=[]
    for day in DATES:
        prior=pd.read_parquet(PRIOR[day]);f=flat.loc[flat.day.eq(day)].drop(columns=['day'])
        q=prior.merge(f,on='sid',validate='one_to_one',how='left')
        assert len(q)==len(prior) and q.status.eq('COMPLETE').all()
        assert q.phase.isin(PRIORITY).all(),q.loc[~q.phase.isin(PRIORITY),['sid','phase']]
        q['phase_priority']=q.phase.map(PRIORITY);q['rank_STAGE_PVR']=pd.Series(pd.NA,index=q.index,dtype='Int64')
        known=q.score.notna();sort=q.loc[known].sort_values(['phase_priority','score','sid'],ascending=[True,False,True])
        q.loc[sort.index,'rank_STAGE_PVR']=range(1,len(sort)+1)
        q['rank_WITHIN_PHASE']=pd.Series(pd.NA,index=q.index,dtype='Int64')
        for phase,g in q.loc[known].groupby('phase'):
            ix=g.sort_values(['score','sid'],ascending=[False,True]).index
            q.loc[ix,'rank_WITHIN_PHASE']=range(1,len(ix)+1)
        outputs.append(q)
    ranks=pd.concat(outputs,ignore_index=True)
    ranks.to_parquet(HERE/'STAGED_PRIOR_RANKS.parquet',index=False)
    ranks.to_csv(HERE/'STAGED_PRIOR_RANKS.csv',index=False)
    trails=[]
    for r in rows:
        if r['sid'] in CASES:
            for t in r.get('case_event_trail',[]):trails.append(dict(t,sid=r['sid'],target_day=r['day']))
    pd.DataFrame(trails).to_csv(HERE/'PREDECLARED_CASE_EVENT_TRAILS.csv',index=False)
    save(HERE/'RANK_FREEZE_RECEIPT.json',dict(status='NEW_STAGE_RANKS_SAVED_BEFORE_OUTCOME_JOIN',rows=len(ranks),
        stage_rank_sha256=sha(HERE/'STAGED_PRIOR_RANKS.parquet'),freeze_sha256=sha(HERE/'FREEZE.json'),
        code_sha256=sha(__file__),by_date={d:dict(N=len(g),known_PVR=int(g.score.notna().sum()),phases=g.phase.value_counts().to_dict())for d,g in ranks.groupby('day')},future_labels_loaded=False))
    print(json.dumps(json.loads((HERE/'RANK_FREEZE_RECEIPT.json').read_text()),ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pilot','full','rank']);a=p.parse_args()
    if a.mode=='rank':rank()
    else:generate(a.mode=='pilot')
