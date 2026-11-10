"""Frozen F same-stock capital mechanism; read-only experiment-one I controls."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,bisect,collections,math
from decimal import Decimal as D
from datetime import time as dt
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
O=ROOT/'research_rounds/f-reentry-capital-mechanism-20261029'
E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029'
SRC=ROOT/'research_rounds/intent-support-20261027'
sp=importlib.util.spec_from_file_location('f_reused_e1',E1/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
B=H.B;Z=H.Z
def save(p,x):H.save(p,x)
def dec(x):return D(str(x))
def stamp(x):return pd.Timestamp(x).to_pydatetime()
def rowtime(x):
    if x['kind']=='fill':return stamp(x['receipt']['at'])
    if x['kind']=='dividend_accrual':return stamp(x['receivable']['ex_at'])
    return stamp(x['at'])
def slim(x):
    def clean(y):
        if y is pd.NA or y is pd.NaT:return None
        if isinstance(y,dict):return {k:clean(v) for k,v in y.items()}
        if isinstance(y,(list,tuple)):return [clean(v) for v in y]
        return y
    return clean(H.encoded(x))
def freeze():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    protocol=dict(version='v1',frozen_before_F_economic=True,question='Same original I opportunity and one independent initial cash balance: E0/I hold versus F sell, wait and legally repurchase the SAME stock. No cross-stock reinvestment.',common='All experiment-one 5349 E0 epochs and 407 stocks; Dec29 2023 decisions through Oct27 2026 terminal. Equal events, stock-equal sensitivity, all no-fill/open/rights retained.',initial='Read-only I units/audits. Exact same actual first decision/fill/quantity/gross/fees per cost. Earlier zero-fill I attempts have no economic charges. After that no external funding.',F='Original INTENT-SUPPORT F: half sqrt5 reversal threshold, unchanged 63/21 share-volume participation clipped .5..2. At each close check old protection first. If not broken, max old protection/original i_floor/new F up-pivot, whose pivot_date >= actual buy date. New protection effective next observation.',reentry='After fully sold, next original full-Q I event observed after actual sale may reserve only own available cash. Same-day close after open sale allowed. Next eligible open/day-expiry, original gap support rejection. F alone never buys. Unlimited natural retries until frozen E0/source boundary.',reset='Each actual repurchase resets protection to i_floor frozen on its decision; old holding F line discarded, market F observer never reset. No carry to another E0 epoch. Pending exit persists until executable.',cash='Native A-sale settlement lag0 cash and buy-lot sellability lag1 are distinct. No invented day idle; no proceeds borrowing or principal resets. Whole-share quantities, minimum order/fees and capacity inherited.',terminal='All actual incurred fees and terminal raw marks/claims included. Estimated liquidation separately, not a fill. Frozen E0/source end forbids new buys; legal exit may settle later.',costs=[1,2],primary='Delta=sum(P_F-P_I), P=terminal NAV-1m; tail partition fixed to each cost original I net_return>=.30, realized/terminal separately. Tail retention plus ordinary Delta, continuous/top-I contributions. Win rate descriptive.',accounting='Daily close Delta increments in initial_hold, idle, repurchased_hold, pending_exit or mixed_trade_action. Sum equals terminal Delta. Fees and raw-open slippage are memo only, never deducted twice. Idle/reentry attribution is accounting not causal.',verdict='Positive total with nonnegative ordinary and tail is sufficient, not necessary. Mixed signs report tradeoff; negative total cannot pass on lower drawdown. Cost/weight reversal or limited cases inconclusive. No after-outcome rule change.',correctness='Exact initial control receipt; independent Decimal shares/fees/cash/NAV; daily I reconstruction equals existing terminal; daily Delta decomposition; no external cash; causal protection/entry/exit; prefix samples; sample/full consistency.',budget='Sample first, then full F computation <=300 seconds; input identity/development separate. No whole portfolio or scans.',boundaries=['Removed original ACT, ranking, six-slot/industry competition and 15% account budget only as authorized mechanism diagnostic.','Common independent E0 epoch ends and first I actual participation inherited from experiment one; not original whole-account strategy reproduction.','Original F code initializes its private fast_floor on first held close; this diagnostic explicitly starts original frozen entry support and applies original I guard, then F max; separately audited.','Original F entry-date inference scans fills after last sale date; diagnostic tracks actual fully-flat cycles to support partial fills without mislabelling a partial sale as a new holding.','Original I full Q retained including stock/sector readiness, sector E0/current availability, G1 and frozen snapshot identities; no ACT/cash/rank competition.'])
    save(O/'PROTOCOL.json',protocol)
    files=[E1/x for x in ['freeze.json','economic-freeze.json','market-cache.parquet','opportunities.parquet','results/units.parquet','results/audit.jsonl.gz','results/verification.json','code/audit.py']]
    files += [SRC/'RULES.txt',SRC/'code/study.py',SRC/'code/fast_kernel.py']
    files += sorted((SRC/'signals').glob('*.parquet'))
    prior=H.read(E1/'freeze.json')['sha256']
    for p in [E1/'market-cache.parquet',E1/'opportunities.parquet']:
        assert H.sha(p)==prior[str(p)]
    identity={str(p):H.sha(p) for p in files};save(O/'input-identity.json',dict(sha256=identity,source_snapshot=str(H.SNAP),seconds=time.monotonic()-t,read_only_I=True))
    H.progress(stage='protocol_and_identity_frozen',files=len(files),seconds=time.monotonic()-t)

class Econ:
    """Economic cash incl. claims; reserve/settlement/payment are NAV-neutral."""
    def __init__(self):self.q=0;self.cash=B;self.fee=Z;self.slip=Z;self.components=collections.defaultdict(lambda:Z)
    def add(self,x):
        k=x['kind']
        if k=='fill':
            r=x['receipt'];q=int(r['shares']);gr=dec(r['gross_cny']);fee=dec(r['fees_cny']);side=r['side'];self.fee+=fee;self.slip+=abs(dec(x['price'])-dec(x['raw_open']))*q
            for c,v in x['fee_components'].items():self.components[c]+=dec(v)
            if side=='buy':self.q+=q;self.cash-=gr+fee
            else:self.q-=q;self.cash+=gr-fee
        elif k in ['split','split_fraction_floor_proxy']:self.q=int(dec(self.q)*dec(x['ratio']))
        elif k=='dividend_accrual':self.cash+=dec(x['receivable']['net_local'])
        assert self.q>=0
    def nav(self,mark):return self.cash+self.q*mark

def cash_check(a):
    av=B;fees={}
    for x in a.audit_log:
        k=x['kind']
        if k=='reserve':av-=x['gross_budget_cny']+x['fee_reserved_cny'];fees[x['order_id']]=x['fee_reserved_cny']
        elif k=='release_buy':av+=x['gross_released']+x['fee_released'];fees.pop(x['order_id'],None)
        elif k=='fill' and x['receipt'].side=='buy':
            fee=x['receipt'].fees_cny;old=fees.get(x['order_id'],Z);av-=max(Z,fee-old);fees[x['order_id']]=max(Z,old-fee)
        elif k=='settle' and not x['settlement'].debit:av+=x['settlement'].cny_amount
        elif k=='dividend_payment':av+=x['entitlement'].net_local
        assert av>=0
    return abs(av-a.available)

def control_load(ids):
    u=pd.read_parquet(E1/'results/units.parquet');u=u[(u.variant=='I')&u.symbol.isin(ids)]
    units={(x['event_id'],x['cost']):x for x in u.to_dict('records')};aud={}
    with gzip.open(E1/'results/audit.jsonl.gz','rt') as f:
        for line in f:
            x=json.loads(line)
            if x['variant']=='I' and x['symbol'] in ids:aud[(x['event_id'],x['cost'])]=x
    assert set(units)==set(aud)
    return units,aud

def run(e,g,f,m,cost,ref,ca,marks,cutoff=H.END):
    s=e['symbol'];a=H.L.SectorAccount(initial_cash=B,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy'])
    ce=Econ();fe=Econ();ci=0;ai=0;rows=[];decisions=[];attempts=[];cycles=0;entry=None;floor=None;pending={};first=None;last_flat=None;end=pd.Timestamp(e['end_signal']) if e['end_signal'] else None
    hasfirst=pd.notna(ref['first_fill']);firstsignal=stamp(ref['first_signal']) if hasfirst else None
    crows=ca['audit'];economic=[rowtime(x) for x in crows if x['kind'] in ['fill','split','split_fraction_floor_proxy','dividend_accrual']];clast=max(economic) if economic else H.at(H.START,dt.min)
    olddelta=Z;idle_days=held_days=0;cash_days=Z;stats=collections.Counter();first_checked=False
    actions=collections.defaultdict(list)
    for x in m.actions.get(s,[]):actions[x['effective_date']].append(x)
    dates=g.index[(g.index>=max(pd.Timestamp(e['start']),H.START))&(g.index<=cutoff)]
    for day in dates:
        r=g.loc[day];op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10));logstart=len(a.audit_log);beforeq=a.quantity(s)
        for x in actions.get(str(day.date()),[]):H.action(a,m,s,x)
        H.pay(a,m,op)
        if s in a.exits:
            w=m.window(s,op,'sell',cost)
            if w:
                rec=a.fill_exit(s,w)
                if rec and not a.quantity(s):last_flat=op;floor=None;entry=None;stats['fully_sold']+=1
            else:stats['exit_unavailable_open']+=1
        # Proceeds lag0 are available now; this is different from bought shares' T+1.
        H.pay(a,m,op)
        if s in a.buys:
            o=a.buys[s];z=pending[o.order_id];w=m.window(s,op,'buy',cost)
            if w and w.raw_open<=z['floor']/dec(r.factor):
                a.audit_log.append(dict(kind='audit_open_support_reject',at=op,sid=s,order_id=o.order_id));a.cancel_buy(s);stats['gap_support_reject']+=1
            elif w:
                rec=a.fill_buy(s,w)
                if rec:
                    assert op>z['at'];cycles+=1;entry=op;floor=z['floor'];stats['actual_entries']+=1
                    if first is None:
                        first=op;cr=next(x for x in crows if x['kind']=='fill' and x['receipt']['side']=='buy')
                        for k,v in [('at',str(rec.at)),('shares',rec.shares),('gross_cny',str(rec.gross_cny)),('fees_cny',str(rec.fees_cny))]:
                            assert (stamp(cr['receipt'][k])==rec.at if k=='at' else dec(cr['receipt'][k])==dec(v)),(e['event_id'],'initial receipt',k)
                        assert z['at']==firstsignal;first_checked=True
                    else:assert last_flat is not None and z['at']>last_flat
                    stats['buy_to_sell_T1_contract']+=int(m.lag('A',op,1)>op)
            else:stats['buy_unavailable_open']+=1
        H.pay(a,m,op);H.pay(a,m,cl);a.expire_day_buys(cl)
        clock=H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date());ended=end is not None and day>=end
        if a.quantity(s) and s not in a.exits:
            z=f.loc[day] if day in f.index else None
            price=dec(z.close) if z is not None else dec(r.close)
            old=floor;broken=old is not None and price<=old
            if ended or not bool(r.i_target) or broken:
                q=m.quote(s,cl)
                if q:a.request_exit(q,clock)
                decisions.append(dict(at=cl,kind='exit',reason='epoch_end' if ended else 'I_off' if not bool(r.i_target) else 'old_protection',old=old,close=price,cycle=cycles))
            else:
                vals=[x for x in [floor,dec(r.i_floor) if pd.notna(r.i_floor) else None] if x is not None]
                newpivot=False
                if z is not None and z.event==1 and pd.notna(z.pivot_date) and str(z.pivot_date)>=entry.date().isoformat():
                    vals.append(dec(z.pivot));newpivot=True
                floor=max(vals) if vals else None
                assert old is None or floor>=old
                if floor!=old:decisions.append(dict(at=cl,kind='raise',previous=old,new=floor,pivot_eligible=newpivot,pivot_date=z.pivot_date if z is not None else None,entry=entry,cycle=cycles))
        # Only the exact existing I first participation is seeded; never a new cash allocation.
        eligible=hasfirst and not ended and not a.quantity(s) and s not in a.buys and s not in a.exits
        allowed=(first is None and cl==firstsignal) or (first is not None and last_flat is not None and cl>last_flat and bool(r.Q))
        if eligible and allowed:
            assert bool(r.Q);quote=m.quote(s,cl)
            if quote is not None and pd.notna(r.i_floor):
                owncash=a.available;ok,reason=a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=owncash,candidate_id=e['event_id'])
                attempts.append(dict(signal_at=cl,earliest_at=clock.earliest_execution_at,accepted=ok,reason=reason,available_before=owncash,cycle=cycles+1))
                if ok:pending[reason]=dict(at=cl,floor=dec(r.i_floor))
        while ci<len(crows) and rowtime(crows[ci])<=cl:ce.add(crows[ci]);ci+=1
        newlogs=slim(a.audit_log[ai:]);ai=len(a.audit_log)
        for x in newlogs:fe.add(x)
        if (ce.q or fe.q) and day not in marks:marks[day]=m.latest_mark(s,cl).raw_price
        mark=marks[day] if ce.q or fe.q else Z
        cn=ce.nav(mark);fn=fe.nav(mark);delta=fn-cn;increment=delta-olddelta;olddelta=delta
        kinds={x['kind'] for x in newlogs}
        boundary=bool(kinds&{'fill','split','split_fraction_floor_proxy','dividend_accrual'})
        # Control economic actions in this interval also belong to mixed boundaries.
        boundary=boundary or any(op<=x<=cl for x in economic if x.date()==day.date())
        bucket='mixed_trade_action' if boundary else 'idle' if not fe.q else 'pending_exit' if s in a.exits else 'repurchased_hold' if cycles>1 else 'initial_hold'
        if first is not None and not fe.q:idle_days+=1;cash_days+=a.available
        if fe.q:held_days+=1
        rows.append(dict(event_id=e['event_id'],symbol=s,cost=cost,date=day,bucket=bucket,delta_increment=increment,I_nav=cn,F_nav=fn,F_shares=fe.q,I_shares=ce.q,F_available=a.available,F_cycle=cycles))
        if ended and cl>=clast and not a.quantity(s) and not a.buys and not a.exits and not a.dividends and not a.settlements:break
    final=H.at(cutoff,dt(15,10));u=H.independent(a,m,s,final);bound=u['precision_bound']+dec(ref['precision_bound'])
    if cutoff==H.END:
        for x in crows[ci:]:ce.add(x)
        finalmark=m.latest_mark(s,final).raw_price if ce.q or fe.q else Z
        assert abs(ce.nav(finalmark)-dec(ref['nav']))<=bound,(e['event_id'],'read-only I terminal')
        assert ce.q==int(ref['shares'])
        assert abs(olddelta-(u['net_pnl']-dec(ref['net_pnl'])))<=bound,(e['event_id'],'daily delta')
        assert bool(first_checked)==hasfirst
    assert cash_check(a)<=bound
    assert abs(fe.nav(m.latest_mark(s,final).raw_price if fe.q else Z)-u['nav'])<=bound
    u.update(event_id=e['event_id'],symbol=s,cost=cost,variant='F_RE',first_fill=first,first_signal=firstsignal,cycles=cycles,reentries=max(0,cycles-1),attempt_count=len(attempts),idle_close_sessions=idle_days,idle_available_cash_sessions=cash_days,held_close_sessions=held_days,capital_return=float(u['net_pnl']/B),turnover_net_return_process_only=u.pop('net_return'),fees_by_component=dict(fe.components),slippage=fe.slip,control_slippage=ce.slip,control_fees=ce.fee,control_nav=ref['nav'],control_net_pnl=ref['net_pnl'],initial_receipt_exact=first_checked if hasfirst else True,cash_residual=cash_check(a),stats=dict(stats))
    return u,dict(event_id=e['event_id'],symbol=s,cost=cost,audit=a.audit_log,attempts=attempts,decisions=decisions),rows

def compute(sample=False):
    t=time.monotonic();identity=H.read(O/'input-identity.json')['sha256']
    for p in [E1/'market-cache.parquet',E1/'opportunities.parquet',E1/'results/units.parquet',E1/'results/audit.jsonl.gz']:
        assert H.sha(p)==identity[str(p)]
    ids=set(H.SAMPLE) if sample else {x['symbol'] for x in H.roster()}
    _,m,_,_=H.context(ids,False);cache=pd.read_parquet(E1/'market-cache.parquet');events=pd.read_parquet(E1/'opportunities.parquet');events=events[events.symbol.isin(ids)]
    refs,aud=control_load(ids);dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False)
    save(dest/'execution-freeze.json',dict(before_this_run=True,code_sha256=H.sha(Path(__file__)),event_count=len(events),event_ids=events.event_id.tolist(),weights='all events equally, stock-equal within-stock equally',controls_readonly=True))
    units=[];tim=[];allrows=[];coverage=collections.Counter();prefix=[]
    with gzip.open(dest/'audit.jsonl.gz','wt') as af:
        for n,s in enumerate(sorted(ids)):
            st=time.monotonic();g=cache[cache.symbol.eq(s)].set_index('date').sort_index();f=pd.read_parquet(SRC/'signals'/f'{s}.parquet');assert H.sha(SRC/'signals'/f'{s}.parquet')==identity[str(SRC/'signals'/f'{s}.parquet')]
            marks={}
            es=events[events.symbol.eq(s)].to_dict('records')
            for e in es:
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    key=(e['event_id'],cost);u,a,rs=run(e,g,f,m,cost,refs[key],aud[key],marks);units.append(u);allrows.extend(rs);af.write(json.dumps(slim(a),ensure_ascii=False)+'\n');coverage.update(u['stats'])
                    if sample and cost==1 and u['cycles']>1 and not any(x['symbol']==s for x in prefix):
                        cut=pd.Timestamp(rs[len(rs)//2]['date'])
                        _,pa,_=run(e,g.loc[:cut],f.loc[:cut],m,cost,refs[key],aud[key],marks,cutoff=cut)
                        for k in ['audit','attempts','decisions']:
                            expected=[x for x in slim(a[k]) if (rowtime(x) if k=='audit' else stamp(x.get('at',x.get('signal_at'))))<=H.at(cut,dt(15,10))]
                            assert slim(pa[k])==expected,(s,'physical prefix',k)
                        prefix.append(dict(symbol=s,event_id=e['event_id'],cut=str(cut.date())))
            tim.append(dict(symbol=s,seconds=time.monotonic()-st))
            if sample or (n+1)%25==0:H.progress(stage='F_same_capital',sample=sample,stocks=n+1,events=len(units)//2,seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('Frozen five-minute F economic budget exceeded; partial audit retained')
    pd.DataFrame(slim(units)).to_parquet(dest/'units.parquet',index=False);pd.DataFrame(slim(allrows)).to_parquet(dest/'daily-paired.parquet',index=False)
    pd.DataFrame(tim).to_csv(dest/'timings-by-stock.csv',index=False)
    if not sample:
        su=pd.read_parquet(O/'sample/units.parquet');fu=pd.read_parquet(dest/'units.parquet');a=su.sort_values(['event_id','cost']).reset_index(drop=True);b=fu[fu.symbol.isin(H.SAMPLE)].sort_values(['event_id','cost']).reset_index(drop=True)
        for k in ['net_pnl','nav','buy_gross','sell_gross','buy_fees','sell_fees','shares','cycles','first_fill','cash_residual']:assert a[k].fillna('NA').tolist()==b[k].fillna('NA').tolist(),('sample/full',k)
    save(dest/'verification.json',dict(passed=True,events=len(events),units=len(units),all_initial_receipts_exact=True,all_cash_shares_fees_nav_and_readonly_controls=True,daily_decomposition=True,physical_prefixes=prefix,sample_full_exact=not sample,coverage=dict(coverage),max_cash_residual=max(dec(x['cash_residual']) for x in units),max_native_nav_residual=max(dec(x['independent_nav_residual']) for x in units),seconds=time.monotonic()-t))
    H.progress(stage='completed',sample=sample,events=len(events),seconds=time.monotonic()-t)

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='freeze':freeze()
    elif mode=='sample':compute(True)
    elif mode=='full':compute(False)
