"""Frozen first-versus-second S0 decision comparison, no portfolio matrix."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,collections,datetime,math
from decimal import Decimal as D
from types import SimpleNamespace as NS
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/s0-first-margin-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029';LS=ROOT/'research_rounds/loss-switch-reparticipation-20261029'
sp=importlib.util.spec_from_file_location('s0_margin_h',E1/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
B=H.B;Z=H.Z
def save(p,x):H.save(p,x)
def enc(x):return H.encoded(x)
def order(rows):
    groups=collections.defaultdict(list)
    for r in rows:groups[r['sector']].append(r)
    sectors=sorted(groups,key=lambda s:(-groups[s][0]['sector_rank'],s));qs={s:sorted(groups[s],key=lambda r:(-r['stock_rank'],r['symbol'])) for s in sectors}
    return [qs[s][j] for j in range(max([len(v) for v in qs.values()] or [0])) for s in sectors if j<len(qs[s])]
def pairs_from(cache,risk):
    keys={}
    for sid,g in cache.groupby('symbol',sort=True):
        prev=None;key=None
        for z in g.sort_values('date').itertuples():
            valid=pd.notna(z.e0_target) and bool(z.e0_target) and pd.notna(z.e0_ready) and bool(z.e0_ready) and pd.notna(z.segment_id);state=int(z.segment_id) if valid else None
            if state is None:key=None
            elif key is None or state!=prev:key=f'{sid}|source={state}|visible_E0_start={z.date.date()}'
            keys[(z.date,sid)]=key;prev=state
    used=set();pairs=[];skips=[]
    for day,g in risk.groupby('date',sort=True):
        oo=order(g.to_dict('records'))
        if len(oo)<2:skips.append(dict(date=day,reason='fewer_than_two'));continue
        a,b=oo[:2];ka,kb=keys[(day,a['symbol'])],keys[(day,b['symbol'])];assert ka and kb and ka!=kb
        if ka in used or kb in used:skips.append(dict(date=day,reason='top_two_event_already_used',first_used=ka in used,second_used=kb in used));continue
        used.update([ka,kb]);known=f'{day.date()}|{ka}|{kb}';pid=hashlib.sha256(known.encode()).hexdigest()
        p=dict(pair_id=pid,date=str(day.date()),known_id_fields=known,candidates=len(oo),same_sector=a['sector']==b['sector'])
        for role,r,key in [('first',a,ka),('second',b,kb)]:
            p.update({role+'_'+k:r[k] for k in ['symbol','sector','stock_rank','sector_rank']});p[role+'_epoch']=key
        pairs.append(p)
    return pd.DataFrame(pairs),pd.DataFrame(skips)
def prepare():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    protocol=dict(version='v1',frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),question='In the frozen event-disjoint same-day comparison, is allocating one cash unit to S0 first rather than second valuable? Mainly sector-first composite choice; not full ranking monotonicity, PVR, E0 correctness or portfolio performance.',scope='407 frozen technology pool, Dec29 2023 through Oct27 2026; full original legal I-Q pool each day, no funding/actual-fill selection.',selection='Chronological full S0 industry-round-robin priority. Compare actual positions1/2 only when both current causal E0 events never appeared in either role; otherwise skip whole date, never promote position3. Each E0 event at most once, include left-censored visible epochs.',size='193 equal pairs x 2 roles x costs1/2 =772 units; each alternative starts same 1m; no shared cash or compounding/reentry. Same single decision-close, next open original day lease and frozen support gap guard.',exit='Original I/E0 invalidity, original stored protection, observed source/E0 boundary. No F/CP/ACT. Cash after exit idle through common Oct27 terminal; no assumed reinvestment or mechanical annualization.',terminal='All no-fill, open and claims included. Raw causal marks and realized cash separate, estimated liquidation costs memo not actual fills.',tail='Pair-tail iff either arm net_pnl/(buy_gross+buy_fees)>=.30, post-outcome only; ordinary complement; realized versus terminal-valued labels separate. Continuous sorted contributions, no threshold search.',primary='Sum and mean(first P-second P), plus absolute net contributions of both arms versus idle cash0. Full negative trials, saved losses, extra positive contribution, all fees/slippage. Tail+ordinary=total.',occupancy='Actual initial invested cost, held market close sessions and cost-basis sessions. Higher return with longer use is a tradeoff; this E0 exit-and-idle convention does not identify optimal recycling.',verdict='Positive difference, first absolute contribution positive and tail preservation give limited support. Less-negative first is not proof worth funding. Mixed tail/ordinary signs or cost/occupancy reversal disclose tradeoff/inconclusive. Conclusions restricted to frozen193, mostly interindustry.',checks='Full native S0 order identity, causal IDs and physical matching prefixes, first6 chronological pairs sample, exact costs/cash/shares/actions/NAV, six economic prefix truncations and sample/full identity.',budget_seconds=300,no_new_arms=True)
    save(O/'PROTOCOL.json',protocol)
    cache=pd.read_parquet(E1/'market-cache.parquet');r=pd.read_parquet(LS/'candidates.parquet');r=r[r.I][['date','symbol','sector','stock_rank','sector_rank']].copy();assert len(r)==32899
    for day,g in r.groupby('date'):
        cl=H.at(day,datetime.time(15,10));clock=H.A.Clock(cl,cl+datetime.timedelta(days=1),day.date());rows=g.to_dict('records');ss={x['symbol']:NS(rank=H.A.Rank(x['stock_rank'],cl,cl)) for x in rows};secs={x['sector']:NS(rank=H.A.Rank(x['sector_rank'],cl,cl)) for x in rows};res={x['symbol']:NS(sector_id=x['sector']) for x in rows};assert H.A._priority(list(ss),ss,secs,res,clock,'S0',[],'frozen')==[x['symbol'] for x in order(rows)]
    p,skip=pairs_from(cache,r);assert len(p)==193 and int(p.same_sector.sum())==7
    prefix=[]
    for cut in ['2024-12-31','2025-12-31','2026-06-30']:
        small,_=pairs_from(cache[cache.date.le(pd.Timestamp(cut))],r[r.date.le(pd.Timestamp(cut))]);ref=p[p.date.le(cut)].reset_index(drop=True);pd.testing.assert_frame_equal(small.reset_index(drop=True),ref,check_exact=True);prefix.append(dict(cutoff=cut,pairs=len(small)))
    r.to_parquet(O/'risk-set.parquet',index=False);p.to_parquet(O/'pairs.parquet',index=False);skip.to_csv(O/'skipped-dates.csv',index=False)
    paths=[E1/'market-cache.parquet',E1/'opportunities.parquet',E1/'code/audit.py',E1/'freeze.json',LS/'candidates.parquet',LS/'candidate-freeze.json',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py',ROOT/'research_rounds/rs-h1-execution-20261025/code/rs_h1_model.py',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_account.py',H.SNAP/'h1.npz',O/'PROTOCOL.json',O/'risk-set.parquet',O/'pairs.parquet']
    save(O/'input-identity.json',dict(sha256={str(x):H.sha(x) for x in paths},snapshot=str(H.SNAP),before_any_new_economic_results=True))
    save(O/'coverage-freeze.json',dict(pairs=len(p),unique_events=386,first_stocks=p.first_symbol.nunique(),second_stocks=p.second_symbol.nunique(),all_stocks=len(set(p.first_symbol)|set(p.second_symbol)),same_sector=7,cross_sector=186,legal_candidate_rows=len(r),candidate_dates=r.date.nunique(),skipped=skip.reason.value_counts().to_dict(),native_order_exact_days=r.date.nunique(),prefix_exact=prefix,main_weight=1,sample='first6 chronological pairs',seconds=time.monotonic()-t))
    H.progress(stage='pairs_frozen',pairs=len(p),stocks=len(set(p.first_symbol)|set(p.second_symbol)),same_sector=7,prefixes=prefix,seconds=time.monotonic()-t)
def cashcheck(a):
    cash=B;reserved={}
    for x in a['audit']:
        k=x['kind']
        if k=='reserve':cash-=x['gross_budget_cny']+x['fee_reserved_cny'];reserved[x['order_id']]=x['fee_reserved_cny']
        elif k=='release_buy':cash+=x['gross_released']+x['fee_released'];reserved.pop(x['order_id'],None)
        elif k=='fill' and x['receipt'].side=='buy':fee=x['receipt'].fees_cny;cash-=max(Z,fee-reserved[x['order_id']]);reserved[x['order_id']]=max(Z,reserved[x['order_id']]-fee)
        elif k=='settle' and not x['settlement'].debit:cash+=x['settlement'].cny_amount
        elif k=='dividend_payment':cash+=x['entitlement'].net_local
        assert cash>=0
    return cash
def occupancy(a,g,day):
    q=0;basis=Z;pos=0;tot=Z;ix=0;arr=a['audit'];dates=g.index[g.index>=day]
    def tm(x):return x['receipt'].at if x['kind']=='fill' else x['receivable'].ex_at if x['kind']=='dividend_accrual' else x['at']
    for d in dates:
        cl=H.at(d,datetime.time(15,10))
        while ix<len(arr) and tm(arr[ix])<=cl:
            x=arr[ix];ix+=1
            if x['kind']=='fill':
                rr=x['receipt']
                if rr.side=='buy':q+=rr.shares;basis+=rr.gross_cny+rr.fees_cny
                else:basis-=basis*D(rr.shares)/D(q);q-=rr.shares
            elif x['kind'] in ['split','split_fraction_floor_proxy']:q=int(D(q)*D(x['ratio']))
        if q:pos+=1;tot+=basis
    return dict(held_close_sessions=pos,invested_cost_sessions=tot)
def compute(sample=False):
    t=time.monotonic();ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());p=pd.read_parquet(O/'pairs.parquet');p=p.head(6) if sample else p;ids=set(p.first_symbol)|set(p.second_symbol);_,m,_,_=H.context(ids,False);cache=pd.read_parquet(E1/'market-cache.parquet');grids={s:g.set_index('date').sort_index() for s,g in cache[cache.symbol.isin(ids)].groupby('symbol')};ep=pd.read_parquet(E1/'opportunities.parquet');dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False);units=[];prefix=[]
    save(dest/'execution-freeze.json',dict(code_sha256=H.sha(Path(__file__)),pairs=len(p),units=len(p)*4,before_run=True))
    with gzip.open(dest/'audit.jsonl.gz','wt') as af:
        for n,pair in enumerate(p.to_dict('records')):
            day=pd.Timestamp(pair['date'])
            for role in ['first','second']:
                s=pair[role+'_symbol'];g=grids[s].copy();assert bool(g.loc[day,'Q']);g['Q']=False;g.loc[day,'Q']=True
                ee=ep[ep.symbol.eq(s)&ep.start.le(pair['date'])&(ep.end_signal.isna()|ep.end_signal.gt(pair['date']))];assert len(ee)==1;e=ee.iloc[0].to_dict();original=e['event_id'];e.update(event_id=pair['pair_id']+'|'+role,start=pair['date'],carry_in=False)
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    u,a=H.run_event(e,g,m,'I',cost);res=abs(cashcheck(a)-u['available']);assert res<=u['precision_bound'];u.update(pair_id=pair['pair_id'],role=role,decision_day=pair['date'],original_event_id=original,same_sector=pair['same_sector'],cash_residual=res,**occupancy(a,g,day));units.append(u);a.update(pair_id=pair['pair_id'],role=role,decision_day=pair['date']);af.write(json.dumps(enc(a),ensure_ascii=False)+'\n')
                    assert u['first_signal'] is None or str(u['first_signal'].date())==pair['date']
                    if sample and cost==1:
                        cut=pd.Timestamp('2024-06-28');ex=dict(e)
                        # Future end metadata is not used as an early-exit signal.
                        if ex['end_signal'] and pd.Timestamp(ex['end_signal'])>cut:ex['end_signal']=None
                        _,pa=H.run_event(ex,g.loc[:cut],m,'I',cost,cutoff=cut)
                        def tm(x):return x['receipt'].at if x['kind']=='fill' else x['receivable'].ex_at if x['kind']=='dividend_accrual' else x['at']
                        for k in ['audit','attempts']:
                            expected=[x for x in a[k] if (tm(x) if k=='audit' else x['signal_at'])<=H.at(cut,datetime.time(15,10))];assert enc(expected)==enc(pa[k]),('physical economic prefix',pair['pair_id'],role,k)
                        prefix.append(dict(pair_id=pair['pair_id'],role=role,cutoff=str(cut.date())))
            if sample or (n+1)%50==0:H.progress(stage='capital_pairs',sample=sample,pairs=n+1,seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second frozen full compute budget exceeded')
    pd.DataFrame(enc(units)).to_parquet(dest/'units.parquet',index=False)
    if not sample:
        a=pd.read_parquet(O/'sample/units.parquet');b=pd.read_parquet(dest/'units.parquet');b=b[b.pair_id.isin(a.pair_id)];keys=['pair_id','role','cost'];a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
        for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','nav','available','dividend_receivable','held_close_sessions','invested_cost_sessions']:assert a[k].tolist()==b[k].tolist(),('sample/full',k)
    save(dest/'verification.json',dict(passed=True,pairs=len(p),units=len(units),independent_fees_shares_cash_raw_marks_rights=True,max_cash_residual=max(u['cash_residual'] for u in units),max_nav_residual=max(u['independent_nav_residual'] for u in units),single_decision_day=True,economic_prefixes=prefix,sample_full_exact=not sample,seconds=time.monotonic()-t))
    H.progress(stage='finished',sample=sample,pairs=len(p),seconds=time.monotonic()-t)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='sample':compute(True)
    elif sys.argv[1]=='full':compute(False)
