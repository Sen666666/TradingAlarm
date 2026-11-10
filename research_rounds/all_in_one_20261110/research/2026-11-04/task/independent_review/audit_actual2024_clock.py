"""Independent actual ACT-clock and PVR-score audit, no strategy imports."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import gzip,hashlib,json,math
import pandas as pd
getcontext().prec=60
HERE=Path(__file__).parent;R=HERE.parent/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full'
REC=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
recovery=pd.read_csv(REC,index_col=0,parse_dates=True);manifest=read(R/'SCORES_MANIFEST.json');score={}
available=Counter()
for x in manifest['entries']:
    p=R/'scores'/(x['symbol']+'.parquet');assert sha(p)==x['output_sha256']
    v=pd.read_parquet(p).loc['2024-01-01':'2024-12-31'].score
    score[x['symbol']]={str(d.date()):(float(n)if pd.notna(n)and math.isfinite(float(n))else None)for d,n in v.items()}
    available.update(str(d.date())[:7]for d,n in v.items()if pd.notna(n)and math.isfinite(float(n)))
out={}
for policy in ['original','no60']:
    root=R/'cycle2024'/policy/'run-2024';book=json.loads(gzip.decompress((root/'pair/B.json.gz').read_bytes()))
    audits=[x for x in book['audit']if x['kind']=='risk_checkpoint'];parent=next(x for x in audits if x['at']=='2023-12-29 15:10:00+08:00')
    state={k:parent[k]for k in ['on','peak','saw_off','previous_fast','episode']};state['peak']=D(state['peak'])
    ds={x['at'][:10]:x for x in [json.loads(s)for s in gzip.decompress((root/'pair/daily.jsonl.gz').read_bytes()).decode().splitlines()]}
    monthly=defaultdict(Counter);events=[];focus=[];count=0
    for x in audits:
        day=x['at'][:10]
        if not day.startswith('2024'):continue
        loc=recovery.index.searchsorted(pd.Timestamp(day),side='right')-1;assert loc>=0
        rr=recovery.iloc[loc];fast=bool(rr.fast_on);br=bool(rr.breakout)if recovery.index[loc]==pd.Timestamp(day)else False
        assert fast==x['fast']and br==x['breakout'];r=ds[day]
        assert D(r['order_reserved'])==0 and x['flat']==(not any(r['positions'].values()))
        nav=D(r['nav']);event=None
        if state['on']:state['peak']=max(state['peak'],nav)
        dd=1-nav/state['peak']
        if state['on']:
            if dd>=D('.2'):state.update(on=False,saw_off=not fast);event='pause'
        else:
            state['saw_off']=state['saw_off']or not fast
            if x['flat']and br:state.update(on=True,peak=nav,episode=state['episode']+1,saw_off=False);event='resume'
        state['previous_fast']=fast
        assert all(state[k]==x[k]for k in ['on','saw_off','previous_fast','episode'])
        assert abs(state['peak']-D(x['peak']))<D('1e-12')and abs(dd-D(x['episode_drawdown']))<D('1e-12')
        assert event==x['event']and x['on']==r['on'];count+=1
        monthly[day[:7]].update(closes=1,on_closes=int(x['on']),fast_closes=int(fast),breakout_closes=int(br))
        if event:events.append(dict(day=day,event=event,nav=r['nav']))
        if '2024-09-24'<=day<='2024-10-10':focus.append(dict(day=day,on=x['on'],fast=fast,breakout=br,NAV=r['nav'],inventory=r['inventory'],exposure=D(r['inventory'])/nav,available=r['available'],held_stocks=len(r['positions'])))
    assert count==242
    rank_byday=defaultdict(list)
    with gzip.open(root/'pair/rank-policy.jsonl.gz','rt')as f:
        for s in f:
            x=json.loads(s)
            if x['day'].startswith('2024'):rank_byday[x['day']].append(x)
    rank_count=0
    for day,rs in rank_byday.items():
        rs=sorted(rs,key=lambda z:z['original_H1_rank']);assert len({r['sid']for r in rs})==len(rs)
        values={r['sid']:score[r['sid']][day]for r in rs};positions={r['sid']:k for k,r in enumerate(rs)}
        ready=sorted((r['sid']for r in rs if values[r['sid']]is not None),key=lambda s:(-round(values[s],12),positions[s]))
        order=iter(ready);final=[r['sid']if values[r['sid']]is None else next(order)for r in rs]
        targets={s:rs[k]['original_H1_rank']for k,s in enumerate(final)}
        for k,r in enumerate(rs):
            v=values[r['sid']];assert r['PVR_ready']==(v is not None)
            assert (r['PVR']is None and v is None)or abs(r['PVR']-v)<1e-12
            assert r['priority_rank']==targets[r['sid']]and r['original_slot']==k and r['final_slot']==final.index(r['sid'])
        rank_count+=len(rs);monthly[day[:7]].update(actual_ranked_stock_days=len(rs),actual_ready_ranked_stock_days=sum(r['PVR_ready']for r in rs))
    out[policy]=dict(passed=True,independent_ACT_clock_and_state_transitions=242,actual_priority_log_scores_and_slots_verified=rank_count,
        actual_ACT_events=events,monthly={k:dict(v)for k,v in monthly.items()},Sep24_Oct10=focus,
        actual_book_SHA256=sha(root/'pair/B.json.gz'),rank_log_SHA256=sha(root/'pair/rank-policy.jsonl.gz'))
out.update(recovery_SHA256=sha(REC),score_manifest_SHA256=sha(R/'SCORES_MANIFEST.json'),frozen_ready_stock_days_by_month=dict(available),
    reviewer_account_events=0,reviewer_source_SHA256=sha(__file__),
    scope='Actual2024 exported ACT inputs/state/fee-inclusive NAV and all actual PVR rank lookups match frozen recovery/score data, not only Jan2 proof. Market input maps remain new by reviewed exclusion/copy paths. Industry/stockCP1/eligibility channels reviewed separately by native owner; financial validity alone does not establish those. Matrix/matrix_days are not consumed by actual J.planning, b0 contains state rather than signal frames, fresh facts/market/structure_lookup are not copied from2023.')
(HERE/'PVR_2024_ACT_SCORE_FIDELITY_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n')
print(json.dumps({k:{kk:vv for kk,vv in v.items()if kk not in ['monthly','Sep24_Oct10']}if isinstance(v,dict)else v for k,v in out.items()if k!='frozen_ready_stock_days_by_month'},indent=2,default=str))
