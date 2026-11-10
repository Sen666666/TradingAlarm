"""Read already completed smoke output only. No engine or indicator execution."""
from pathlib import Path
import ast,hashlib,json,math
from collections import Counter
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES={'000620.SZ':'2022-01-06','002583.SZ':'2024-09-19','300085.SZ':'2024-08-30',
       '603061.SH':'2025-11-06','300623.SZ':'2025-12-16'}
EPS=4*2**-53/(1-4*2**-53)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def finite(x):return x is not None and x is not pd.NA and pd.notna(x) and math.isfinite(float(x))
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if x is None or x is pd.NA:return None
    if isinstance(x,np.generic):x=x.item()
    return None if isinstance(x,float) and not math.isfinite(x) else x
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def frame(p):
    d=pd.read_parquet(p);d.index=pd.DatetimeIndex(d.index).as_unit('ns');return d.loc[:'2026-06-30']


def main():
    metas={r['symbol']:r for r in json.loads(SM.read_text())};sources={str(SM):sha(SM)}
    oldtree=ast.parse((HERE/'engine_pre_unknown_fixes.py').read_text());newtree=ast.parse((HERE/'engine.py').read_text())
    named=lambda tree,name:next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    assert ast.dump(named(oldtree,'features'))==ast.dump(named(newtree,'features'))
    startblock=lambda tree:next(n for n in ast.walk(named(tree,'market_fsm')) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='raw_positive')
    assert ast.dump(startblock(oldtree))==ast.dump(startblock(newtree))
    result=[]
    for sid,launch in CASES.items():
        directory=HERE/'smoke_v1'/sid.replace('.','_')
        daily_path=directory/'MARKET_DAILY.parquet';event_path=directory/'MARKET_EVENTS.json';gen_path=directory/'MARKET_GENERATIONS.json'
        for p in [daily_path,event_path,gen_path]:sources[str(p)]=sha(p)
        daily=frame(daily_path);events=json.loads(event_path.read_text());generations=json.loads(gen_path.read_text())
        gen=next(g for g in generations if g['start_day']==launch);gid=gen['generation_id']
        ev=[e for e in events if e['generation_id']==gid]
        seen=next((e for e in ev if e['kind']=='CHANNEL_SEEN'),None)
        advance=next((e for e in ev if e['kind']=='CHANNEL_ADVANCE'),None)
        exit_event=next((e for e in ev if e['kind'].startswith('EXIT_')),None)
        selected=[('START',{'day':launch})]+([('CHANNEL_SEEN',seen)] if seen else [])+([('FIRST_ADVANCE',advance)] if advance else [])+([('EXIT',exit_event)] if exit_event else [])
        pp=Path(next(p for p in metas[sid]['source_sha256'] if p.endswith('/signal.parquet')));sources[str(pp)]=sha(pp)
        assert sources[str(pp)]==metas[sid]['source_sha256'][str(pp)]
        price=frame(pp);rows=[]
        for stage,event in selected:
            day=event['day'];t=pd.Timestamp(day);origin_note='CURRENT_IMMUTABLE_SMOKE'
            if t in daily.index:r=daily.loc[t].to_dict()
            else:
                old=HERE/'smoke_main_v1'/(sid.replace('.','_')+'_FULL_DAILY.parquet');sources[str(old)]=sha(old)
                r=frame(old).loc[t].to_dict();origin_note='PRESERVED_REAL_START_SNAPSHOT: features/start initialization AST unchanged; current final generation origin confirms date/C; version IDs not reused.'
                assert stage=='START' and float(r['C'])==gen['start_C']
            prior=r.get('P_old');atr=r.get('ATR14_prior');Q=event.get('Q')
            if Q is None and stage!='START' and event.get('kind')!='EXIT_STORED_LINE' and all(finite(r.get(k)) for k in ['P_old','hard_old','shadow_peak_before','ATR14_prior']):
                if not ge(float(prior),float(r['C'])):
                    Q=max(float(prior),float(r['hard_old']),float(r['shadow_peak_before'])-3*float(atr))
            factor=float(price.loc[t,'adjustment_factor']);trigger=event.get('Q') if event.get('kind')=='EXIT_NEW_ATR_PROPOSAL' else prior if stage=='EXIT' else None
            nxt=None
            for nt,p in price.loc[price.index>t].iterrows():
                flags=[p.get(k) for k in ['price_eligible','observed_bar','synthetic_event_bar','source_invalid']]
                if not all(isinstance(v,(bool,np.bool_)) for v in flags) or [bool(v) for v in flags]!=[True,True,False,False]:continue
                if not finite(p.get('open')) or p['open']<=0:continue
                nxt=dict(day=str(nt.date()),raw_OPEN=float(p.raw_open),adjusted_OPEN=float(p.open),
                    OPEN_minus_trigger_line=None if not finite(trigger) else float(p.open)-float(trigger),
                    quote_scope='Historical next observed source OPEN only; no executable fill/queue/fees/PNL claim; full missing-session calendar NOT_VERIFIED')
                break
            rows.append(dict(stage=stage,day=day,raw_C=float(price.loc[t,'raw_close']),C=r['C'],
                P_old=prior,raw_P_old=None if not finite(prior) else float(prior)/factor,
                proposal_Q=Q,raw_proposal_Q=None if not finite(Q) else float(Q)/factor,
                Q_scope='Recorded event Q, otherwise frozen max formula from stored prior inputs; not evaluated after old-line exit or at START.',
                P_next=r.get('P_next'),hard_old=r.get('hard_old'),hard=r.get('hard'),
                ATR_prior=atr,raw_ATR_prior=None if not finite(atr) else float(atr)/factor,
                S_known_on_day=r.get('S'),j=event.get('j'),exit_kind=event.get('kind') if stage=='EXIT' else None,
                next_observed_OPEN_reference=nxt,numeric_snapshot_source=origin_note))
        full_events=ev
        if not any(x['kind']=='E0_START_ELIGIBILITY' for x in ev):
            old_ev=HERE/'smoke_main_v1'/(sid.replace('.','_')+'_EVENTS.json');sources[str(old_ev)]=sha(old_ev)
            old_daily=frame(HERE/'smoke_main_v1'/(sid.replace('.','_')+'_FULL_DAILY.parquet'))
            old_id=old_daily.loc[launch,'generation_id']
            full_events=[x for x in json.loads(old_ev.read_text()) if x['generation_id']==old_id]
            strip=lambda x:{k:v for k,v in x.items() if k not in ['event_id','generation_id','window']}
            assert [strip(x) for x in ev]==[strip(x) for x in full_events if x['day']>='2024-09-01']
        count_source=daily
        needed=price.loc[launch:seen['day']].index if seen else price.index[:0]
        if not needed.isin(daily.index).all():
            path=HERE/'smoke_main_v1'/(sid.replace('.','_')+'_FULL_DAILY.parquet');sources[str(path)]=sha(path)
            count_source=frame(path)
        def wait(a,b):
            if a is None or b is None:return None
            expected=price.index[(price.index>pd.Timestamp(a))&(price.index<=pd.Timestamp(b))]
            assert expected.isin(count_source.index).all()
            return int(count_source.reindex(expected).valid_bar.sum())
        result.append(dict(sid=sid,generation_id=gid,start_day=launch,selected_stages=rows,
                           generation_event_count=len(full_events),generation_event_counts=dict(Counter(x['kind'] for x in full_events)),
                           start_to_seen_effective_observations=None if not seen else wait(launch,seen['day']),
                           seen_to_first_advance_effective_observations=None if not seen or not advance else wait(seen['day'],advance['day']),
                           wait_clock='Saved valid_bar original observations; start observation excluded, destination included; missing-session calendar NOT_VERIFIED',
                           exit_ends_generation=True,shadow_not_actual_holding=True))
    yd=frame(HERE/'smoke_v1/000620_SZ/MARKET_DAILY.parquet')
    restart=[]
    for day in ['2022-01-18','2022-01-20','2022-01-21','2022-01-24','2022-01-25','2022-01-26']:
        r=yd.loc[day];restart.append({k:clean(r[k]) for k in ['day','C','raw_C','generation_id','mode','E0_start_event','CHANNEL_seen','CHANNEL_advance','A','S','j_consumed','P_old','P_next','exit_event_count']})
    assert yd.loc['2022-01-20','generation_id']!=yd.loc['2022-01-06','generation_id']
    assert yd.loc['2022-01-24','generation_id']==yd.loc['2022-01-20','generation_id']
    assert not bool(yd.loc['2022-01-24','CHANNEL_advance'])
    direct_pairs=[]
    for sid,anchor in [('000620.SZ','2022-01-07'),('002583.SZ','2024-09-20'),('300085.SZ','2024-10-09')]:
        path=HERE/'smoke_v1'/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json';sources[str(path)]=sha(path)
        match=next(x for x in json.loads(path.read_text()) if x['anchor_day']==anchor)
        direct_pairs.append(match)
    payload=dict(scope='Read completed output only; no engine/indicator rerun, account, sizing or return.',five_cases=result,
                 yingxin_exit_restart=restart,direct_same_CP_anchor_comparisons=direct_pairs,old_j_cannot_continue_after_exit=True,
                 preserved_origin_reuse_features_and_START_AST_identical=True,source_sha256=sources,
                 immutable_code_claim=json.loads((HERE/'CLAIM_SHA256.json').read_text())['code_sha256'])
    (HERE/'SMOKE_CASE_READOUT.json').write_text(json.dumps(clean(payload),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for case in result:
        print(case['sid'],json.dumps([{k:r[k] for k in ['stage','day','raw_C','P_old','proposal_Q','ATR_prior','S_known_on_day','j','exit_kind','next_observed_OPEN_reference']} for r in case['selected_stages']],ensure_ascii=False))
    print('YINGXIN_RESTART',json.dumps(clean(restart),ensure_ascii=False))


if __name__=='__main__':main()
