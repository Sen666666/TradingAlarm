"""Frozen first-participation mechanism audit. Never loads a trading account."""
from pathlib import Path
import sys, json, gzip, hashlib, time, csv, math, collections
from decimal import Decimal as D, getcontext
from datetime import datetime, time as dtime
from dataclasses import replace, asdict
import numpy as np
import pandas as pd

ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
OUT=ROOT/'research_rounds/s-entry-mechanism-audit-20261029'
PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
STRICT=ROOT/'research_rounds/strict-entry-capacity-20261027'
sys.path.insert(0,str(ROOT/'research_rounds/tech-finite-compound-20261026/code'))
import common as C
import current_fixed_pool as pool
FM=C.import_path('s_audit_frozen_market',ROOT/'research_rounds/temperature-sizing-20261026/code/fast_market.py').FastMarket
L=C.ledger; A=C.admission; TZ=C.native.TZ
START=pd.Timestamp('2023-12-29'); END=pd.Timestamp('2026-10-27')
B=D('1000000'); Z=D(0)
SNAP=Path(json.loads((PRIOR/'input.json').read_text())['snapshot']['path'])
SAMPLE=['000100.SZ','001339.SZ','002439.SZ','300308.SZ','300502.SZ','688041.SH','688048.SH','688498.SH']

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''): h.update(b)
    return h.hexdigest()
def read(p): return json.loads(Path(p).read_text())
def encoded(x): return C.native.encoded(x)
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f: json.dump(encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def at(day,tm): return datetime.combine(pd.Timestamp(day).date(),tm,TZ)
def progress(**x): print(json.dumps(encoded(x),ensure_ascii=False),flush=True)
def roster(): return list(csv.DictReader((C.DESIGN/'proposed-pool.csv').open()))

def context(ids,states=False):
    b=C.load_bundle(OLD/'inputs-v2/input-manifest.json')
    b.lines=tuple(x for x in b.lines if x.security_id in ids)
    sectors={x.sector_id for x in b.lines}; needed=set(ids)|sectors
    rec={x['series_id']:x for x in read(PRIOR/'input/manifest.json')['series']}
    b.series={s:x for s,x in b.series.items() if s in needed}
    b.sector_series={s:x for s,x in b.sector_series.items() if s in sectors}
    frames={}
    for s,x in b.series.items():
        x.record=rec[s]
        if states:
            f=pd.read_parquet(SNAP/'facts'/f'{s}.parquet');frames[s]=f
            x.states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
    if states:
        with np.load(SNAP/'h1.npz') as h:
            b._h1_cache=(pd.DatetimeIndex(h['dates']),{str(s):j for j,s in enumerate(h['symbols'])},h['score'].copy())
    rules=read(PRIOR/'execution-rules-v2.json')
    rules['calendars']['A']=sorted(set(rules['calendars']['A'])|{f'2026-10-{d}T09:30:00+08:00' for d in [27,28,29,30]})
    # Restore exactly the close sessions omitted from the old list, as its context does.
    rules['decision_cutoffs']=sorted(set(rules['decision_cutoffs'])|{f'{d}T15:10:00+08:00' for d in ['2023-12-29','2026-10-23','2026-10-26','2026-10-27']})
    m=FM(b,rules,[],read(OLD/'inputs-v2/economic-protocol.json'))
    dates=[pd.Timestamp(t.date()) for t in m.cutoffs if START.date()<=t.date()<=END.date()]
    assert len(dates)==len(set(dates))
    return b,m,frames,dates

def epochs(s,f):
    result=[];cur=None
    for day,r in f.iterrows():
        valid=bool(r.e0_target) and bool(r.e0_ready)
        key=int(r.segment_id) if valid else None
        if cur is not None and (not valid or key!=cur['source_segment']):
            cur['end_signal']=str(day.date());cur['end_kind']='source_boundary' if valid else 'E0_off';cur=None
        if valid and cur is None:
            cur=dict(event_id=f'{s}|{key}|{day.date()}',symbol=s,source_segment=key,start=str(day.date()),end_signal=None,end_kind='right_censored')
            result.append(cur)
    return [x for x in result if x['start']<=str(END.date()) and (x['end_signal'] is None or x['end_signal']>str(START.date()))]

def freeze():
    t=time.monotonic();ids={r['symbol'] for r in roster()};b,m,ff,dates=context(ids,True)
    progress(stage='input_loaded',seconds=time.monotonic()-t,stocks=len(ids),cutoffs=len(dates))
    records=[];events=[];grids={};source={};coverage=[]
    for s in sorted(ids):
        f=ff[s];g=f.reindex(pd.DatetimeIndex(dates),method='ffill').copy()
        g['i_buy']=[bool(f.loc[d,'i_buy']) if d in f.index else False for d in dates]
        st=pd.read_parquet(STRICT/'signals'/f'{s}.parquet')
        g['strict_target']=st.strict_target.reindex(g.index).fillna(False).astype(bool)
        g['symbol']=s;g['Q']=False;grids[s]=g
        events.extend(epochs(s,f))
        q=st.loc['2024':];coverage.append((int(q.original_buy.sum()),int(q.strict_buy.sum())))
        for p in [SNAP/'facts'/f'{s}.parquet',STRICT/'signals'/f'{s}.parquet']:
            source[str(p)]=sha(p)
        rec=b.series[s].record
        for ref in [rec['raw'],rec['adjustment']['actions']]:
            p=Path(ref['path']);assert sha(p)==ref['sha256'];source[str(p)]=ref['sha256']
    assert tuple(map(sum,zip(*coverage)))==(35242,33673)
    for n,d in enumerate(dates):
        dec=at(d,dtime(15,10));opens=m.sessions['A'];i=__import__('bisect').bisect_right(opens,dec)
        clock=A.Clock(dec,opens[i],dec.date());buyable=m.market_buyable(dec)
        inp=b.at_decision(clock,market_buyable=buyable);secs={s.sector_id:s for s in inp.sectors}
        for line,h in zip(inp.lines,inp.historical):
            s=line.security_id;row=grids[s].loc[d]
            if h.trend_up.read(clock) is not None:
                h=replace(h,trend_up=replace(h.trend_up,value=bool(row.i_target) if pd.notna(row.i_target) else False))
            sec=pool.build_security(line,h,inp.evidence);allowed=sec.buy_allowed.read(clock,for_execution=True)
            sec=replace(sec,buy_allowed=A.Fact(None if allowed is None else bool(allowed and row.i_buy),dec,dec,source_id='frozen_original_I_daily_event'))
            grids[s].loc[d,'Q']=A.eligibility(sec,secs,clock,'S0').q is True
        if (n+1)%100==0:progress(stage='common_eligibility',days=n+1,total=len(dates),seconds=time.monotonic()-t)
    for s,g in grids.items():records.append(g.reset_index(names='date'))
    cache=pd.concat(records,ignore_index=True)
    cache.to_parquet(OUT/'market-cache.parquet',index=False)
    ec=pd.DataFrame(events);ec['carry_in']=ec.start<str(START.date());ec.to_parquet(OUT/'opportunities.parquet',index=False)
    for s in b.series:
        p=SNAP/'facts'/f'{s}.parquet';source[str(p)]=sha(p)
    code=Path(__file__);source[str(code)]=sha(code)
    for p in [OUT/'PROTOCOL-v2.json',OUT/'input-identity.json',OUT/'market-cache.parquet',OUT/'opportunities.parquet',SNAP/'h1.npz']:
        source[str(p)]=sha(p)
    save(OUT/'freeze.json',dict(before_economic_results=True,events=len(ec),stocks=len(ids),common_rows=len(cache),main_event_weight=1,robustness_stock_denominator=407,stock_event_counts=ec.symbol.value_counts().to_dict(),sha256=source,seconds=time.monotonic()-t,raw_signal_check=[35242,33673],ledger_precision=getcontext().prec))
    progress(stage='frozen',events=len(ec),rows=len(cache),seconds=time.monotonic()-t)

def pay(a,m,tm):
    a.settle_due(tm)
    for k,e in list(a.dividends.items()):
        if e.paid_at is not None and e.paid_at<=tm:
            a.pay_dividend(k,at=tm,fx=m.rate('CNY',tm),payment_evidence_id=e.source_id+':declared-payment-field',payment_known_at=e.paid_at)

def action(a,m,s,e):
    tm=at(e['effective_date'],dtime.min);old=a.quantity(s)
    if old and D(e['cash_per_old_share']):
        a.accrue_dividend(event_id=f"dividend:{s}:{e['effective_date']}",sid=s,currency='CNY',net_local=D(old)*D(e['cash_per_old_share'])*D(m.protocol['dividend_net_factor']['A']),ex_at=tm,paid_at=C.native.iso(e['paid_at']) if e.get('paid_at') else None,source_id=e['source_id'],entitlement_basis='protocol_previous_close_inventory_and_explicit_net_factor')
    if D(e['split_ratio'])!=1 and (old or s in a.buys or s in a.exits):
        sellable=C.native.iso(e['new_shares_sellable_at']) if e.get('new_shares_sellable_at') else m.lag('A',tm,m.protocol['bonus_sellable_lag_sessions']['A'])
        a.split(event_id=f"split:{s}:{e['effective_date']}",sid=s,ratio=D(e['split_ratio']),at=tm,new_shares_sellable_at=sellable)

def independent(a,m,s,final):
    q=0;basis=Z;realized=Z;buys=sells=bf=sf=accrued=paid=Z;fee_state={};max_fee_error=Z
    for x in a.audit_log:
        k=x['kind']
        if k=='fill':
            r=x['receipt'];qty=r.shares;price=D(x['price']);gross=D(qty)*price
            assert gross==r.gross_cny and sum(x['fee_components'].values(),Z)==r.fees_cny
            tm=r.at;assert D(str(m.raw[s].loc[pd.Timestamp(tm.date()),'open']))==D(x['raw_open'])
            assert r.execution_basis.startswith('explicit_daily_bar_proxy')
            oldpaid,oldaccr=fee_state.get(x['order_id'],({},{}))
            sched=m.fees(s,tm);components=sched.incremental(r.side,gross,oldpaid,oldaccr,a.cost_multiplier,shares=qty,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'))
            assert components==x['fee_components']
            newpaid={c:oldpaid.get(c,Z)+v for c,v in components.items()}
            ra=sched.rate_accrual(r.side,gross,a.cost_multiplier,shares=qty,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'))
            fee_state[x['order_id']]=(newpaid,{c:oldaccr.get(c,Z)+v for c,v in ra.items()})
            if r.side=='buy':q+=qty;basis+=gross+r.fees_cny;buys+=gross;bf+=r.fees_cny
            else:
                assert q>=qty;released=basis*D(qty)/D(q);basis-=released;realized+=gross-r.fees_cny-released;q-=qty;sells+=gross;sf+=r.fees_cny
        elif k in ('split','split_fraction_floor_proxy'):
            q=int(D(q)*D(x['ratio']))
        elif k=='dividend_accrual':accrued+=x['receivable'].net_local
        elif k=='dividend_payment':paid+=x['entitlement'].net_local
    assert q==a.quantity(s),(s,'independent shares',q,a.quantity(s))
    mark=m.latest_mark(s,final) if q else None;mv=D(q)*mark.raw_price if q else Z
    # Reconstruct the terminal raw observation independently, including stale ex-action unit transforms.
    if q:
        f=m.raw[s];r=f.loc[:pd.Timestamp(final.date())];r=r[r.valid_price & r.observed_bar];last=r.iloc[-1];dd=r.index[-1]
        rp=D(str(last.close))
        for e in m.actions.get(s,[]):
            if str(dd.date())<e['effective_date']<=str(final.date()):rp=(rp-D(e.get('signal_cash_per_old_share',e['cash_per_old_share'])))/D(e.get('signal_split_ratio',e['split_ratio']))
        assert rp==mark.raw_price,(s,'terminal raw mark')
    bal=a.balance(final,{s:mark} if q else {})
    pnl=sells-sf+accrued-buys-bf+mv
    residual=abs(pnl-(bal['nav']-B))
    scale=max(B,abs(buys),abs(sells),abs(mv));ulp=D(1).scaleb(scale.adjusted()-getcontext().prec+1)
    bound=ulp*D(max(1,len(a.audit_log))*32)
    assert residual<=bound,(s,'precision explained residue',residual,bound)
    assert abs(realized+paid+(mv-basis)+(accrued-paid)-pnl)<=bound
    est=sum(m.fees(s,final).incremental('sell',mv,{}, {},a.cost_multiplier,shares=q,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),Z) if q else Z
    return dict(net_pnl=pnl,realized_trading_pnl=realized,paid_dividend_income=paid,unrealized_inventory_pnl=mv-basis,accrued_unpaid_dividend_income=accrued-paid,buy_gross=buys,buy_fees=bf,sell_gross=sells,sell_fees=sf,shares=q,market_value=mv,remaining_cost_basis=basis,net_return=float(pnl/(buys+bf)) if buys+bf else None,share_closed=not q,financial_closed=not q and not a.dividends and not a.settlements and not a.buys,estimated_liquidation_fee=est,estimated_exit_slippage=mv*D('.0005')*a.cost_multiplier,mark_known_at=mark.known_at if q else None,mark_source=mark.source_id if q else None,independent_nav_residual=residual,precision_bound=bound,**bal)

def run_event(e,g,m,variant,cost,allow_all=False,cutoff=END):
    s=e['symbol'];a=L.SectorAccount(initial_cash=B,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy'])
    start=max(pd.Timestamp(e['start']),START);end=pd.Timestamp(e['end_signal']) if e['end_signal'] is not None else None
    entered=False;floor=None;pending={};first_signal=first_fill=None;attempts=[];activity=[]
    dates=g.index[(g.index>=start)&(g.index<=cutoff)]
    events=collections.defaultdict(list)
    for x in m.actions.get(s,[]):events[x['effective_date']].append(x)
    for day in dates:
        r=g.loc[day];op=at(day,dtime(9,30));cl=at(day,dtime(15,10))
        for x in events.get(str(day.date()),[]):action(a,m,s,x)
        pay(a,m,op)
        if s in a.exits:
            w=m.window(s,op,'sell',cost)
            if w:a.fill_exit(s,w)
        if s in a.buys:
            o=a.buys[s];z=pending[o.order_id];w=m.window(s,op,'buy',cost)
            if w and w.raw_open<=z['floor']/D(str(r.factor)):
                a.audit_log.append(dict(kind='audit_open_support_reject',at=op,sid=s,order_id=o.order_id));a.cancel_buy(s)
            elif w:
                fill=a.fill_buy(s,w)
                if fill:
                    assert op>z['at'];entered=True;floor=z['floor'];first_signal=z['at'];first_fill=op
                    assert bool(g.loc[pd.Timestamp(first_signal.date()),'Q'])
                    if variant=='S' and not allow_all:assert bool(g.loc[pd.Timestamp(first_signal.date()),'strict_target'])
        pay(a,m,op);pay(a,m,cl);a.expire_day_buys(cl)
        clock=A.Clock(cl,m.sessions['A'][__import__('bisect').bisect_right(m.sessions['A'],cl)],cl.date())
        ended=end is not None and day>=end
        if a.quantity(s) and s not in a.exits:
            lost=ended or not bool(r.i_target) or (floor is not None and D(str(r.close))<=floor)
            if lost:
                quote=m.quote(s,cl)
                if quote:a.request_exit(quote,clock)
                else:activity.append(dict(at=cl,kind='exit_quote_unavailable'))
            elif pd.notna(r.i_floor):floor=max(floor,D(str(r.i_floor)))
        if not entered and not ended and bool(r.Q) and (variant=='I' or allow_all or bool(r.strict_target)):
            quote=m.quote(s,cl)
            if quote is not None and pd.notna(r.i_floor):
                ok,reason=a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=B,candidate_id=e['event_id'])
                attempts.append(dict(signal_at=cl,earliest_at=clock.earliest_execution_at,accepted=ok,reason=reason,strict=bool(r.strict_target)))
                if ok:pending[reason]=dict(at=cl,floor=D(str(r.i_floor)))
        # Fully settled completed units have no further cashflows, but terminal mark clock remains common.
        if ended and not a.quantity(s) and not a.buys and not a.exits and not a.dividends and not a.settlements:break
    final=at(cutoff,dtime(15,10));res=independent(a,m,s,final)
    res.update(event_id=e['event_id'],symbol=s,variant=variant,cost=cost,first_signal=first_signal,first_fill=first_fill,strict_at_entry=bool(g.loc[pd.Timestamp(first_signal.date()),'strict_target']) if first_signal else None,attempt_count=len(attempts),start=e['start'],end_signal=e['end_signal'],end_kind=e['end_kind'],carry_in=e['carry_in'],initial_cash=B,notes=activity)
    return res,dict(event_id=e['event_id'],symbol=s,variant=variant,cost=cost,attempts=attempts,audit=a.audit_log)

def economic(sample=False):
    freeze=read(OUT/'freeze.json');assert sha(OUT/'market-cache.parquet')==freeze['sha256'][str(OUT/'market-cache.parquet')]
    assert sha(OUT/'opportunities.parquet')==freeze['sha256'][str(OUT/'opportunities.parquet')]
    t=time.monotonic();ids=set(SAMPLE) if sample else {r['symbol'] for r in roster()}
    b,m,_,_=context(ids,False);progress(stage='execution_inputs_loaded',sample=sample,seconds=time.monotonic()-t)
    cache=pd.read_parquet(OUT/'market-cache.parquet');ev=pd.read_parquet(OUT/'opportunities.parquet');ev=ev[ev.symbol.isin(ids)]
    dest=OUT/('sample' if sample else 'results');dest.mkdir(exist_ok=False)
    units=[];checks=[];audits=gzip.open(dest/'audit.jsonl.gz','wt');tim=[]
    try:
        for n,s in enumerate(sorted(ids)):
            ts=time.monotonic();g=cache[cache.symbol.eq(s)].set_index('date').sort_index()
            for e in ev[ev.symbol.eq(s)].to_dict('records'):
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    results={}
                    for arm in ['I','S']:
                        u,a=run_event(e,g,m,arm,cost);units.append(u);results[arm]=u
                        audits.write(json.dumps(encoded(a),ensure_ascii=False)+'\n')
                    i,ss=results['I'],results['S']
                    if ss['first_fill']:assert i['first_fill'] and ss['first_fill']>=i['first_fill']
                    checks.append(dict(event_id=e['event_id'],cost=cost,same_entry=ss['first_fill']==i['first_fill'],I_filled=i['first_fill'] is not None,S_filled=ss['first_fill'] is not None))
            tim.append(dict(symbol=s,seconds=time.monotonic()-ts))
            if sample or (n+1)%25==0:progress(stage='paired_units',sample=sample,stocks=n+1,events=len(checks)//2,seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second economic compute budget; checkpoint retained')
        audits.close()
        pd.DataFrame(encoded(units)).to_parquet(dest/'units.parquet',index=False)
        pd.DataFrame(checks).to_csv(dest/'pair-checks.csv',index=False)
        if sample:
            # Actual history integration control: remove only the S gate, then it must equal I.
            controls=[];prefix=[]
            for s in SAMPLE:
                g=cache[cache.symbol.eq(s)].set_index('date').sort_index();es=ev[ev.symbol.eq(s)].to_dict('records')
                z=next((x for x in es if any(u['event_id']==x['event_id'] and u['variant']=='I' and u['first_fill'] for u in units)),es[0])
                if pd.isna(z['end_signal']):z['end_signal']=None
                u,_=run_event(z,g,m,'S',1,allow_all=True);ref=next(x for x in units if x['event_id']==z['event_id'] and x['variant']=='I' and x['cost']==1)
                for k in ['first_signal','first_fill','net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','dividend_receivable']:assert u[k]==ref[k],(s,'always-allow',k)
                controls.append(z['event_id'])
                cut=pd.Timestamp('2025-12-31')
                z=next((x for x in es if pd.Timestamp(x['start'])<=cut and (pd.isna(x['end_signal']) or pd.Timestamp(x['end_signal'])>cut)),z)
                if pd.isna(z['end_signal']):z['end_signal']=None
                if pd.Timestamp(z['start'])<=cut:
                    _,a1=run_event(z,g,m,'S',1)
                    raw,arr,actions=m.raw[s],m.arr[s],m.actions[s]
                    m.raw[s]=raw.loc[:cut].copy();length=len(m.raw[s])
                    m.arr[s]={k:(v[v<length] if k in ['good','positive'] else v[:length] if isinstance(v,np.ndarray) else v) for k,v in arr.items()}
                    m.actions[s]=[x for x in actions if x['effective_date']<=str(cut.date())]
                    _,a2=run_event(z,g.loc[:cut].copy(),m,'S',1,cutoff=cut)
                    m.raw[s],m.arr[s],m.actions[s]=raw,arr,actions
                    def when(x):
                        if 'at' in x:return x['at']
                        if 'receipt' in x:return x['receipt'].at
                        return x['receivable'].ex_at
                    previous=[x for x in a1['audit'] if when(x)<=at(cut,dtime(15,10))]
                    assert encoded(previous)==encoded(a2['audit']),(s,'physical future truncation')
                    prefix.append(z['event_id'])
            save(dest/'verification.json',dict(passed=True,units=len(units),paired_rows=len(checks),always_allow_exact=controls,physical_cache_prefix=prefix,independent_fees_shares_cash_and_terminal_values=True,precision=getcontext().prec,max_nav_residual=max(x['independent_nav_residual'] for x in units)))
        else:save(dest/'verification.json',dict(passed=True,units=len(units),paired_rows=len(checks),all_common_events=len(ev),independent_fees_shares_cash_and_terminal_values=True,max_nav_residual=max(x['independent_nav_residual'] for x in units),precision=getcontext().prec))
        save(dest/'timings.json',dict(total_seconds=time.monotonic()-t,stocks=tim,context_seconds=None,full_compute_budget_seconds=300))
        progress(stage='verified',sample=sample,units=len(units),events=len(ev),seconds=time.monotonic()-t)
    except BaseException as ex:
        audits.close();pd.DataFrame(encoded(units)).to_parquet(dest/'partial-units.parquet',index=False)
        save(dest/'FAILURE.json',dict(error=repr(ex),seconds=time.monotonic()-t,completed_units=len(units)))
        raise

if __name__=='__main__':
    command=sys.argv[1]
    if command=='freeze':freeze()
    elif command=='sample':economic(True)
    elif command=='full':economic(False)
    else:raise ValueError(command)
