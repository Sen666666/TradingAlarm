"""Five frozen real-source main-FSM smoke cases; no accounts or CP pairing."""
from pathlib import Path
import json,hashlib,time
import pandas as pd
import engine

HERE=Path(__file__).resolve().parent
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=HERE/'smoke_main_v1';out.mkdir(exist_ok=False)
    meta={r['symbol']:r for r in json.loads(SM.read_text())}
    sources={str(p):sha(p) for p in [HERE/'FREEZE.md',HERE/'engine.py',Path(__file__),SM]}
    version=engine.key('FIXED_N3_V1',sources[str(HERE/'FREEZE.md')],sources[str(HERE/'engine.py')])
    cases={'000620.SZ':'2022-01-06','002583.SZ':'2024-09-19','300085.SZ':'2024-08-30',
           '603061.SH':'2025-11-06','605111.SH':'2026-01-05'}
    reports=[];started=time.monotonic()
    for sid,launch in cases.items():
        m=meta[sid];pp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));ep=Path(next(p for p in m['source_sha256'] if p.endswith('/events.parquet')))
        for p in [pp,ep]:assert sha(p)==m['source_sha256'][str(p)];sources[str(p)]=sha(p)
        price=pd.read_parquet(pp).loc[:'2026-06-30'];events=pd.read_parquet(ep).loc[:'2026-06-30']
        f=engine.features(price);result=engine.market_fsm(sid,price,events,version,f)
        daily=result['daily'];daily.to_parquet(out/(sid.replace('.','_')+'_FULL_DAILY.parquet'))
        (out/(sid.replace('.','_')+'_EVENTS.json')).write_text(json.dumps(result['events'],ensure_ascii=False,indent=2)+'\n')
        assert not daily.query('E0_start_event and CHANNEL_advance').shape[0]
        assert not daily.query('not valid_bar and CHANNEL_advance').shape[0]
        assert daily[daily.CHANNEL_advance].groupby('day').size().max()<=1 if daily.CHANNEL_advance.any() else True
        row=daily.loc[launch];gid=row.generation_id
        path=daily[daily.generation_id.eq(gid)] if gid else daily.iloc[:0]
        exits=[e for e in result['events'] if e['generation_id']==gid and e['kind'].startswith('EXIT_')]
        record=dict(sid=sid,legacy_launch_day=launch,source_rows=len(price),new_market_generations=len(result['generations']),
                    same_CLOSE_exit_restart_days=daily[daily.exit_and_restart_same_CLOSE].day.tolist(),
                    launch_row=engine.clean(row.to_dict()),generation_events=[e for e in result['events'] if e['generation_id']==gid],
                    first_exit=exits[0] if exits else None,case_is_not_forced_new_generation=not bool(row.E0_start_event))
        reports.append(record)
        print(json.dumps(engine.clean(dict(sid=sid,launch=launch,E0_start=bool(row.E0_start_event),mode=row['mode'],
              gen=gid,first_exit=record['first_exit'],case_events=[{k:e.get(k) for k in ['kind','day','j','C','P_old','Q']} for e in record['generation_events']][:15])),ensure_ascii=False),flush=True)
    m=meta['600345.SH'];p=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));sources[str(p)]=sha(p)
    guard_source=pd.read_parquet(p).loc['2022-08-04':'2022-08-08'];guard=engine.features(guard_source)
    assert not bool(guard.loc['2022-08-05','valid_bar']) and not bool(guard.loc['2022-08-05','close_valid'])
    guard.to_parquet(out/'ACTUAL_UNKNOWN_GUARD_600345.parquet')
    receipt=dict(status='FIVE_REAL_MAIN_SMOKE_PASS',source_sha256=sources,version=version,cases=reports,
                 actual_unknown_guard_pass=True,new_accounts=0,new_quantities=0,new_returns=0,
                 elapsed_seconds=time.monotonic()-started,full_calendar_missing_session_check='NOT_VERIFIED')
    (out/'SMOKE_RECEIPT.json').write_text(json.dumps(engine.clean(receipt),ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
