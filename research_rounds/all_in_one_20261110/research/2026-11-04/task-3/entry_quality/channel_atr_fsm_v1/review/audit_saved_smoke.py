"""Independent read-only saved-smoke check. Never imports the candidate engine."""
from pathlib import Path
import hashlib,json,math
from collections import Counter
import pandas as pd

P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;D=P/'smoke_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def finite(v):return v is not None and math.isfinite(float(v))
rec=load(D/'RUN_RECEIPT.json')
assert rec['status']=='COMPLETE' and rec['symbols_completed']==5 and rec['errors']==0
for path,h in rec['code_sha256'].items():assert sha(path)==h,path
cases=[('000620.SZ','2022-01-07','2022-01-10',2,'2022-01-18'),
       ('002583.SZ','2024-09-20','2024-09-23',3,'2024-11-04'),
       ('300085.SZ','2024-09-19','2024-09-20',6,'2024-10-10'),
       ('603061.SH','2025-12-22','2026-01-05',1,'2026-02-24'),
       ('300623.SZ','2026-01-05','2026-01-09',1,'2026-02-02')]
points=[];status=Counter();rowcount=0;paircount=0;pairbranches=0;early=0;no_post20=0
source_hashes={};bindings={str(D/'RUN_RECEIPT.json'):sha(D/'RUN_RECEIPT.json')}
runtime_boundaries=Counter()
for sid,seen_day,advance_day,j,exit_day in cases:
    d=D/sid.replace('.','_');cov=load(d/'COVERAGE.json');sf=load(d/'SOURCE_FREEZE.json')
    assert sf['code_sha256']==rec['code_sha256']
    for path,h in sf['source_sha256'].items():
        if path not in source_hashes:assert sha(path)==h,path;source_hashes[path]=h
    price_path=next(x for x in sf['source_sha256'] if x.endswith('/signal.parquet'))
    event_path=next(x for x in sf['source_sha256'] if x.endswith('/events.parquet'))
    price=pd.read_parquet(price_path);ev=pd.read_parquet(event_path)
    daily=pd.read_parquet(d/'MARKET_DAILY.parquet');events=load(d/'MARKET_EVENTS.json')
    rowcount+=len(daily)
    runtime_boundaries['same_CLOSE_exit_restart']+=int(daily.exit_and_restart_same_CLOSE.sum())
    runtime_boundaries['START_while_ATR_or_channel_unready']+=int((daily.E0_start_event & (daily.ATR14_prior.isna() | daily.U20.isna())).sum())
    runtime_boundaries['SKIPPED_DATA_UNREADY']+=sum(x['kind']=='SKIPPED_DATA_UNREADY' for x in events)
    assert not (daily.E0_start_event & daily.CHANNEL_advance).any()
    assert not ((~daily.valid_bar) & daily.CHANNEL_advance).any()
    assert not (daily.CHANNEL_seen & daily.current_mature.fillna(False).astype(bool)).any()
    sr=daily.loc[seen_day];ar=daily.loc[advance_day];xr=daily.loc[exit_day]
    assert sr.CHANNEL_seen and not sr.current_mature and sr.j_consumed==0
    assert ar.CHANNEL_advance and ar.current_mature and ar.j_consumed==j
    assert sr.generation_id==ar.generation_id
    assert ar.A==sr.A and ar.S==sr.S and ar.S==sr.ATR14_prior and ar.A==sr.C
    assert xr.exit_event_count==1
    # Actual original source OHLC and completed prior20 H; no engine recalculation.
    for day in [seen_day,advance_day,exit_day]:assert daily.loc[day,'C']==price.loc[day,'close']
    t=pd.Timestamp(seen_day);i=price.index.get_loc(t);prior=price.iloc[i-20:i]
    assert len(prior)==20 and prior.segment_id.eq(price.loc[t,'segment_id']).all()
    assert sr.U20==float(prior.high.max()) and sr.C>sr.U20
    # Independent interval check of the first frozen-ATR integer milestone.
    diff=float(ar.C-ar.A);scale=float(ar.S)
    assert diff>=j*scale and diff<(j+1)*scale
    gevents=[x for x in events if x['generation_id']==sr.generation_id]
    exits=[x for x in gevents if x['kind'].startswith('EXIT_')]
    assert exits[0]['day']==exit_day
    ex=exits[0]
    if ex['kind']=='EXIT_STORED_LINE':assert ex['C']<=ex['P_old']
    else:assert ex['C']>ex['P_old'] and ex['C']<=ex['Q'] and ex['Q']==max(ex['P_old'],ex['hard_old'],ex['peak_before']-3*ex['ATR_prior'])
    # Display can start after an already-existing full-prefix generation.
    starts=[x for x in gevents if x['kind']=='E0_START_ELIGIBILITY']
    if starts:
        st=starts[0];assert ev.loc[st['day'],'event']==1
        assert st['C']==price.loc[st['day'],'close'] and st['shadow_peak']==st['C']
    pairs=load(d/'CP_ANCHOR_PAIRS.json');paircount+=len(pairs)
    assert len(pairs)==cov['raw_CP_anchors']
    for x in pairs:
        status[x['status']]+=1
        if x['status']!='PAIRED_SHADOWS':continue
        assert x['P0']==max(x['original_candidate'],x['original_I_floor'])
        assert x['common_risk_denominator_ATR']==x['anchor_ATR_prior']>0
        assert x['position_or_fill_claim'] is False
        for b in ['CP','ATR3']:
            q=x[b];pairbranches+=1
            assert q['no_price_return_or_PnL'] is True
            if q['effective_observations_held']<20:
                assert q['twentieth_observation'] is None
                assert q['post20_observations']==0 and q['post20_max_close_drawdown_ATR'] is None
                early+=1
            if q['post20_observations']==0:
                assert q['post20_max_close_drawdown_ATR'] is None;no_post20+=1
    points.append(dict(sid=sid,seen=seen_day,A=float(sr.A),S=float(sr.S),U20=float(sr.U20),
        first_advance=advance_day,j=j,advance_C=float(ar.C),exit=exit_day,exit_kind=ex['kind'],
        exit_C=ex['C'],P_old=ex['P_old'],Q=ex.get('Q'),
        launch_inside_display=None if not starts else starts[0]['day']))
    for name in ['COVERAGE.json','SOURCE_FREEZE.json','MARKET_DAILY.parquet','MARKET_EVENTS.json','CP_ANCHOR_PAIRS.json']:
        bindings[str(d/name)]=sha(d/name)
assert rowcount==4333 and paircount==291 and status==Counter({'PAIRED_SHADOWS':290,'ENTRY_QUOTE_UNKNOWN':1})
result=dict(status='PASS_STATIC_MAIN_AND_FIVE_REAL_SMOKE_WITH_LIMITS',code_sha256=rec['code_sha256'],
    scope='Full engine and runner static read; saved five-symbol 4333-row invariants, five real selected generations/source values/milestone intervals, all291 pair coverage and NA/denominator checks. No independent FSM/indicator/account run.',
    actual_cases=[x[0] for x in cases],five_key_generations=points,saved_rows_checked=rowcount,
    paired_anchors=paircount,pair_status_counts=dict(status),paired_branch_rows=pairbranches,
    branches_less_than20_NA_checked=early,branches_with_no_post20_NA_checked=no_post20,
    runtime_branch_coverage=dict(runtime_boundaries),
    repaired_static_invariants=['Known valid same-source close frontier retained independent of ATR/channel readiness',
        'Unready crossed grids consumed as SKIPPED without permission or maturity','Pair known close checks oldI/oldP before HLC-unknown censor'],
    source_sha256_verified=source_hashes,output_bindings=bindings,
    limits=['Not economic approval, account, quantity, fill, ACK or return evidence',
        'Zero observed same-close exit+restart/unready-START/SKIPPED rows in these displays: those branches are static-reviewed, not runtime exercised here',
        'Complete absent-market-session calendar check remains NOT_VERIFIED',
        'Original raw CP/I context and main E0 generations are separate',
        'Pair strong-decile aggregate not yet reviewed; no selection by realized profits'],
    allowed_next_scope='Frozen pure-signal batch using exactly these code/freeze hashes, retaining missing-data/clock limits; no account or parameter changes.',
    remaining_blocks_for_that_scope=[],new_candidate_runs=0,new_accounts=0,parameter_searches=0)
(O/'MAIN_AND_SMOKE_GATE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'key_generations':points,'pairs':dict(status),'runtime_branch_coverage':dict(runtime_boundaries)},ensure_ascii=False))
