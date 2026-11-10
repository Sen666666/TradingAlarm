"""One-time participation-policy switch after first rule-confirmed net loss."""
from pathlib import Path
import sys,json,gzip,time,hashlib,importlib.util,collections,bisect,math,copy
from decimal import Decimal as D,getcontext
from datetime import time as dt,datetime,timezone
from types import SimpleNamespace as NS
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/loss-switch-reparticipation-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029';E2=ROOT/'research_rounds/cp1-incremental-mechanism-20261029'
sp=importlib.util.spec_from_file_location('loss_h',E1/'code/audit.py');H=importlib.util.module_from_spec(sp);sys.modules[sp.name]=H;sp.loader.exec_module(H)
B=H.B;Z=H.Z;SAMPLE_END=pd.Timestamp('2024-06-28')
def clean(x):
    x=H.encoded(x)
    def c(y):
        if y is pd.NA or y is pd.NaT:return None
        if isinstance(y,dict):return {k:c(v) for k,v in y.items()}
        if isinstance(y,(list,tuple)):return [c(v) for v in y]
        return y
    return c(x)
def save(p,x):
    p=Path(p)
    with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def dec(x):return D(str(x))
def rt(x):
    if x['kind']=='fill':return x['receipt'].at if not isinstance(x['receipt'],dict) else pd.Timestamp(x['receipt']['at']).to_pydatetime()
    return x.get('at',x.get('receivable',{}).get('ex_at') if isinstance(x.get('receivable'),dict) else getattr(x.get('receivable'), 'ex_at',None))
def ordered(rows):
    groups=collections.defaultdict(list)
    for r in rows:
        if math.isfinite(r['stock_rank']) and math.isfinite(r['sector_rank']):groups[r['sector']].append(r)
    sectors=sorted(groups,key=lambda s:(-groups[s][0]['sector_rank'],s))
    q={s:sorted(groups[s],key=lambda r:(-r['stock_rank'],r['symbol'])) for s in sectors}
    return [q[s][n] for n in range(max([len(x) for x in q.values()] or [0])) for s in sectors if n<len(q[s])]

def prepare():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    protocol=dict(name='首次规则亏损后扩大再参与通道',version='v1',frozen_at=datetime.now(timezone.utc).isoformat(),scope='407 tech, 2023-12-29 through 2026-10-27; one finite cash sleeve, initial 1m, max one held stock, no injection/reset/leverage/ACT.',policies=['I_ONLY','I_PLUS_CP_AFTER_LOSS'],trigger='First actually completed original I/E0 exit cycle with net proceeds + then-known accrued entitlements - actual buy/sell costs < 0. Timestamp actual final sale. No later payment information can change trigger. One permanent policy switch, not continuous adaptive error diagnosis.',common='Both arms identical original I admission/rank/exit and initial actual capital until trigger. New channel does not force sell or change holding protection. Failure trigger necessity is NOT identified.',CP='Reuse experiment-two first qualifying receipt, continuous Q, warm G1, PVR>50, anchor age 0-20. Full pool all matching statuses. Only new receipt today, no replay of signal seen while funded.',priority='Original S0 sector round-robin and stock H1 ranks; CP gets no priority bonus; lot cost only feasibility, not score.',sizing='Native reserve own actual available cash incl actual settled proceeds, one holding/order; no buffer/10% limit; original minimum lot/day lease/support gap guard/T+1/costs/rights.',exit='Original I/E0 state/source loss or close<=old original protection; else max old/original i_floor, next-observation effect. No F/CP exits.',initial_perturbation='First nonempty I batch only: original versus exchange first two original-priority candidates. No future fill/PnL selection. Less than two means no perturbation; no replacement date.',paths='2 initial scenarios x 2 policies x costs1/2 =8 only; prefix sample is validation, not another variant.',main='Terminal NAV adaptive-I per initial/cost. Worst and range of two initial paths are case-level sensitivity only. Tail/ordinary plus displacement and all costs; win rate descriptive.',verdict='No trigger or no distinct allowed/selected/filled CP opportunity means unidentified, not CP ineffective. Positive total/worst improvement/nonwider range/tail preservation sufficient, not mandatory; mixed signs tradeoff; cost/scenario reversal inconclusive. No retune/start replacement.',identification='Preflight actual initial fills, common failure dates, CP-only not-I candidates while flat, selected and filled. New cash allocation is only a link in correction, not early-sale/trigger correctness or antifragility proof.',budget_seconds=300,not_identified=['necessity of loss-trigger switch','E0 algorithm reliability','PVR threshold/ranking increment','general path robustness','full ACT portfolio performance'])
    save(O/'PROTOCOL.json',protocol)
    files=[E1/'market-cache.parquet',E1/'opportunities.parquet',E1/'code/audit.py',E1/'freeze.json',E1/'results/units.parquet',E2/'all-confirmations.parquet',E2/'continuous-eligibility.parquet',E2/'match-freeze.json',H.SNAP/'h1.npz',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py',ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_account.py']
    ids={x['symbol'] for x in H.roster()};meta={x['symbol']:x for x in H.roster()};cache=pd.read_parquet(E1/'market-cache.parquet');cp=pd.read_parquet(E2/'all-confirmations.parquet');cp=cp[cp.age_bin.eq('0-20')].copy();cp['date']=pd.to_datetime(cp.date)
    cpmap={(x['date'],x['symbol']):x for x in cp.to_dict('records')};cq=pd.read_parquet(E2/'continuous-eligibility.parquet');cmap={(r.date,r.symbol):r.Q_cont for r in cq.itertuples()}
    for k in cpmap:assert cmap[k]
    with np.load(H.SNAP/'h1.npz') as h:
        hd=pd.DatetimeIndex(h['dates']);col={str(s):j for j,s in enumerate(h['symbols'])};score=h['score'].copy()
    out=[];first=None;prefixchecks=0
    for day,df in cache.groupby('date',sort=True):
        di=hd.get_loc(day);rows=[]
        for r in df.itertuples():
            cr=cpmap.get((day,r.symbol));isI=bool(r.Q)
            if not isI and cr is None:continue
            sector=meta[r.symbol]['sector_id'];sr=float(np.round(score[di,col[r.symbol]],12));gr=float(np.round(score[di,col[sector]],12))
            rows.append(dict(date=day,symbol=r.symbol,sector=sector,stock_rank=sr,sector_rank=gr,I=isI,CP=cr is not None,CP_only=cr is not None and not isI,cp_matched=cr['match_status']=='matched' if cr else None,cp_id=cr['decision_id'] if cr else None,cp_age=cr['age'] if cr else None))
        sortedrows=ordered(rows);ip=ordered([r for r in rows if r['I']])
        if first is None and ip:first=dict(date=str(day.date()),batch=ip,swap_available=len(ip)>=2)
        # Independently compare the compact order with the original pure selector.
        clock=H.A.Clock(H.at(day,dt(15,10)),H.at(day+pd.Timedelta(days=1),dt(9,30)),day.date())
        ss={r['symbol']:NS(rank=H.A.Rank(r['stock_rank'],clock.decision_at,clock.decision_at)) for r in rows};sec={r['sector']:NS(rank=H.A.Rank(r['sector_rank'],clock.decision_at,clock.decision_at)) for r in rows};res={r['symbol']:NS(sector_id=r['sector']) for r in rows}
        ref=H.A._priority(list(ss),ss,sec,res,clock,'S0',[],'frozen');assert ref==[r['symbol'] for r in sortedrows];prefixchecks+=1
        out.extend(sortedrows)
    pd.DataFrame(out).to_parquet(O/'candidates.parquet',index=False)
    save(O/'input-identity.json',dict(sha256={str(p):H.sha(p) for p in files},snapshot=str(H.SNAP),frozen_before_path_results=True))
    save(O/'candidate-freeze.json',dict(rows=len(out),CP_early=len(cp),CP_only=sum(x['CP_only'] for x in out),first_batch=first,original_priority_identity_days=prefixchecks,main_start=str(H.START.date()),end=str(H.END.date()),seconds=time.monotonic()-t,sha256=H.sha(O/'candidates.parquet')))
    H.progress(stage='candidate_identity_frozen',CP_early=len(cp),CP_only=sum(x['CP_only'] for x in out),first_batch=[x['symbol'] for x in first['batch'][:2]],first_date=first['date'],seconds=time.monotonic()-t)

class Watch:
    def __init__(self):self.q={};self.cash=B;self.fees=Z;self.slip=Z;self.current=None;self.closed=[];self.n=0;self.index=0
    def drain(self,a,orders):
        done=[]
        for x in a.audit_log[self.index:]:
            k=x['kind']
            if k=='fill':
                r=x['receipt'];s=r.security_id;q=r.shares;gr=r.gross_cny;fee=r.fees_cny;old=self.q.get(s,0);self.fees+=fee;self.slip+=abs(D(x['price'])-D(x['raw_open']))*q
                if r.side=='buy':
                    if not old:
                        self.n+=1;self.current=dict(cycle=self.n,symbol=s,buy_at=r.at,sell_at=None,buy_gross=Z,sell_gross=Z,buy_fees=Z,sell_fees=Z,fees=Z,dividend=Z,**orders[x['order_id']])
                    self.q[s]=old+q;self.cash-=gr+fee;self.current['buy_gross']+=gr;self.current['buy_fees']+=fee
                else:self.q[s]=old-q;self.cash+=gr-fee;self.current['sell_gross']+=gr;self.current['sell_fees']+=fee;self.current['sell_at']=r.at
                self.current['fees']+=fee
                if not self.q[s]:
                    c=self.current;c['net_pnl']=c['sell_gross']+c['dividend']-c['buy_gross']-c['fees'];c['closed']=True;c['market_value']=Z;self.closed.append(c);done.append(c);self.current=None
            elif k in ['split','split_fraction_floor_proxy']:self.q[x['sid']]=int(D(self.q.get(x['sid'],0))*D(x['ratio']))
            elif k=='dividend_accrual':self.cash+=x['receivable'].net_local;self.current['dividend']+=x['receivable'].net_local
        self.index=len(a.audit_log);return done
    def nav(self,m,at):return self.cash+sum((D(q)*m.latest_mark(s,at).raw_price for s,q in self.q.items() if q),Z)

def audit(a,m,watch,orders,final):
    w=Watch();w.drain(a,orders);assert w.q==watch.q;assert w.closed==watch.closed
    av=B;reservedfees={};fee_state={};maxfee=Z
    for x in a.audit_log:
        k=x['kind']
        if k=='reserve':av-=x['gross_budget_cny']+x['fee_reserved_cny'];reservedfees[x['order_id']]=x['fee_reserved_cny']
        elif k=='release_buy':av+=x['gross_released']+x['fee_released'];reservedfees.pop(x['order_id'],None)
        elif k=='settle' and not x['settlement'].debit:av+=x['settlement'].cny_amount
        elif k=='dividend_payment':av+=x['entitlement'].net_local
        elif k=='fill':
            r=x['receipt'];s=r.security_id;assert r.gross_cny==D(r.shares)*D(x['price']);assert sum(x['fee_components'].values(),Z)==r.fees_cny
            paid,accr=fee_state.get(x['order_id'],({},{}));fs=m.fees(s,r.at);comp=fs.incremental(r.side,r.gross_cny,paid,accr,a.cost_multiplier,shares=r.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));assert comp==x['fee_components']
            ra=fs.rate_accrual(r.side,r.gross_cny,a.cost_multiplier,shares=r.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));fee_state[x['order_id']]=({n:paid.get(n,Z)+v for n,v in comp.items()},{n:accr.get(n,Z)+v for n,v in ra.items()})
            assert D(str(m.raw[s].loc[pd.Timestamp(r.at.date()),'open']))==D(x['raw_open'])
            if r.side=='buy':old=reservedfees.get(x['order_id'],Z);av-=max(Z,r.fees_cny-old);reservedfees[x['order_id']]=max(Z,old-r.fees_cny)
        assert av>=0
    marks={s:m.latest_mark(s,final) for s,q in w.q.items() if q};bal=a.balance(final,marks);scale=max(B,abs(bal['nav']));bound=D(1).scaleb(scale.adjusted()-getcontext().prec+1)*max(1,len(a.audit_log))*32
    assert abs(av-a.available)<=bound
    assert all(q==a.quantity(s) for s,q in w.q.items())
    assert abs(w.nav(m,final)-bal['nav'])<=bound
    return dict(passed=True,cash_residual=abs(av-a.available),nav_residual=abs(w.nav(m,final)-bal['nav']),precision_bound=bound,**bal)

def path(scenario,policy,cost,m,grids,candidates,first,cutoff):
    a=H.L.SectorAccount(initial_cash=B,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);w=Watch();orders={};decisions=[];daily=[];trigger=None;initial=None;floor=None;held_segment=None;events=[];candidate_rows=[];attempts=[]
    actionmap=collections.defaultdict(list)
    for s,acts in m.actions.items():
        for act in acts:actionmap[act['effective_date']].append((s,act))
    def feasible(row,clock):
        s=row['symbol'];quote=m.quote(s,clock.decision_at);r=grids[s].loc[pd.Timestamp(clock.decision_at.date())]
        if quote is None or pd.isna(r.i_floor):return False
        temp=H.L.SectorAccount(initial_cash=a.available,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);ok,_=temp.reserve_budget(quote=quote,clock=clock,gross_budget_cny=a.available);return ok
    dates=next(iter(grids.values())).index
    for day in dates[dates<=cutoff]:
        op=H.at(day,dt(9,30));cl=H.at(day,dt(15,10))
        for s,act in actionmap.get(str(day.date()),[]):
            if a.quantity(s) or s in a.buys or s in a.exits:H.action(a,m,s,act)
        H.pay(a,m,op)
        for s in list(a.exits):
            win=m.window(s,op,'sell',cost)
            if win:a.fill_exit(s,win)
        H.pay(a,m,op)
        for s in list(a.buys):
            z=orders[a.buys[s].order_id];r=grids[s].loc[day];win=m.window(s,op,'buy',cost)
            if win and win.raw_open<=z['floor']/dec(r.factor):a.cancel_buy(s);events.append(dict(at=op,kind='open_support_reject',symbol=s))
            elif win:
                rec=a.fill_buy(s,win)
                if rec:
                    floor=z['floor'];held_segment=z['segment'];assert rec.at>z['decision_at']
                    if initial is None:initial=dict(symbol=s,at=rec.at,shares=rec.shares,gross=rec.gross_cny,fees=rec.fees_cny)
        closed=w.drain(a,orders)
        if trigger is None:
            neg=next((c for c in closed if c['net_pnl']<0),None)
            if neg:trigger=dict(at=neg['sell_at'],cycle=neg['cycle'],symbol=neg['symbol'],net_pnl_known_now=neg['net_pnl'],dividend_accrued_known_now=neg['dividend'],gross_price_only_pnl=neg['sell_gross']-neg['buy_gross'],policy_switch_permanent=True)
        H.pay(a,m,cl);a.expire_day_buys(cl)
        clock=H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date())
        held=[s for s in a.positions if a.quantity(s)];assert len(held)<=1 and len(a.buys)<=1
        for s in held:
            if s in a.exits:continue
            r=grids[s].loc[day];off=not bool(r.i_target) or not bool(r.e0_target) or not bool(r.e0_ready) or int(r.segment_id)!=held_segment;broken=floor is not None and dec(r.close)<=floor
            if off or broken:
                q=m.quote(s,cl)
                if q:a.request_exit(q,clock)
                events.append(dict(at=cl,kind='original_exit_signal',symbol=s,off=off,old_floor=floor,close=dec(r.close)))
            elif pd.notna(r.i_floor):floor=max(floor,dec(r.i_floor))
        if not held and not a.buys and not a.exits:
            rows=candidates.get(day,[]);ip=ordered([r for r in rows if r['I']]);cpp=[r for r in rows if r['CP_only']];expanded=policy=='I_PLUS_CP_AFTER_LOSS' and trigger is not None
            pool=ordered(rows) if expanded else ip
            if str(day.date())==first['date'] and scenario=='swap' and len(pool)>=2:pool=[pool[1],pool[0],*pool[2:]]
            alt=next((r['symbol'] for r in ip if feasible(r,clock)),None) if trigger is not None and cpp else None
            chosen=None;orderid=None
            for row in pool:
                s=row['symbol'];r=grids[s].loc[day];q=m.quote(s,cl)
                if q is None or pd.isna(r.i_floor):continue
                av=a.available;ok,reason=a.reserve_budget(quote=q,clock=clock,gross_budget_cny=av,candidate_id=f'{s}:{day.date()}')
                attempts.append(dict(date=day,symbol=s,accepted=ok,reason=reason,available=av,I=row['I'],CP=row['CP'],expanded=expanded))
                if ok:
                    chosen=s;orderid=reason;orders[reason]=dict(decision_at=cl,floor=dec(r.i_floor),segment=int(r.segment_id),I=row['I'],CP=row['CP'],CP_only=row['CP_only'],cp_matched=row['cp_matched'],cp_id=row['cp_id'],displaced_I_candidate=alt if row['CP_only'] else None,available_at_decision=av);break
            if trigger is not None:
                for row in cpp:candidate_rows.append(dict(date=day,symbol=row['symbol'],cp_id=row['cp_id'],cp_matched=row['cp_matched'],policy_allows=expanded,selected=chosen==row['symbol'],order_id=orderid if chosen==row['symbol'] else None,available_before=attempts[-1]['available'] if chosen else a.available,old_I_feasible_candidate=alt,chosen_symbol=chosen))
            decisions.append(dict(at=cl,expanded=expanded,CP_only_candidates=len(cpp),I_candidates=len(ip),chosen=chosen,order_id=orderid))
        w.drain(a,orders);marks={s:m.latest_mark(s,cl) for s in held};bal=a.balance(cl,marks);assert abs(w.nav(m,cl)-bal['nav'])<=D('1e-15')
        daily.append(dict(date=day,nav=bal['nav'],available=bal['available'],inventory=bal['inventory'],dividend_receivable=bal['dividend_receivable'],order_reserved=bal['order_reserved'],fees=bal['fees_cny'],held=held[0] if held else None,triggered=trigger is not None))
    final=H.at(cutoff,dt(15,10));check=audit(a,m,w,orders,final);cycles=copy.deepcopy(w.closed)
    if w.current:
        c=copy.deepcopy(w.current);q=w.q[c['symbol']];mv=D(q)*m.latest_mark(c['symbol'],final).raw_price;c.update(closed=False,market_value=mv,net_pnl=c['sell_gross']+c['dividend']+mv-c['buy_gross']-c['fees']);cycles.append(c)
    assert abs(sum((c['net_pnl'] for c in cycles),Z)-(check['nav']-B))<=check['precision_bound']
    res=dict(scenario=scenario,policy=policy,cost=cost,initial=initial,trigger=trigger,nav=check['nav'],net_pnl=check['nav']-B,fees=w.fees,slippage=w.slip,cycles=len(cycles),closed_cycles=len(w.closed),CP_only_flat_candidates=len(candidate_rows),CP_only_selected=sum(r['selected'] for r in candidate_rows),CP_only_entries=sum(c['CP_only'] for c in cycles),CP_only_actual_cost=sum((c['buy_gross']+c['buy_fees'] for c in cycles if c['CP_only']),Z),**{k:check[k] for k in ['available','order_reserved','dividend_receivable','inventory','precision_bound','cash_residual','nav_residual']})
    return dict(result=res,daily=daily,cycles=cycles,CP_candidates=candidate_rows,attempts=attempts,audit=a.audit_log,events=events,decisions=decisions,orders=orders)

def compute(sample=False):
    t=time.monotonic();ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());fr=H.read(O/'candidate-freeze.json');assert H.sha(O/'candidates.parquet')==fr['sha256'];ids={r['symbol'] for r in H.roster()};_,m,_,_=H.context(ids,False)
    cache=pd.read_parquet(E1/'market-cache.parquet');grids={s:g.set_index('date').sort_index() for s,g in cache.groupby('symbol')};cand={d:g.to_dict('records') for d,g in pd.read_parquet(O/'candidates.parquet').groupby('date')};cut=SAMPLE_END if sample else H.END;dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False);runs=[]
    save(dest/'execution-freeze.json',dict(code_sha256=H.sha(Path(__file__)),paths=8,cutoff=str(cut.date()),before_run=True))
    for scenario in ['original','swap']:
        for cost in [1,2]:
            pair=[]
            for policy in ['I_ONLY','I_PLUS_CP_AFTER_LOSS']:
                x=path(scenario,policy,cost,m,grids,cand,fr['first_batch'],cut);pair.append(x);runs.append(x)
                H.progress(stage='path',sample=sample,scenario=scenario,policy=policy,cost=cost,initial=x['result']['initial'],trigger=x['result']['trigger'],CP_only_candidates=x['result']['CP_only_flat_candidates'],CP_only_entries=x['result']['CP_only_entries'],seconds=time.monotonic()-t)
            assert clean(pair[0]['result']['initial'])==clean(pair[1]['result']['initial']);assert clean(pair[0]['result']['trigger'])==clean(pair[1]['result']['trigger'])
            trigger=pair[0]['result']['trigger'];tm=trigger['at'] if trigger else H.at(cut,dt(15,10));a=[r for r in pair[0]['audit'] if rt(r)<=tm];b=[r for r in pair[1]['audit'] if rt(r)<=tm];assert clean(a)==clean(b)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second eight-path compute budget exceeded')
    for group in ['daily','cycles','CP_candidates','attempts','events','decisions']:
        rows=[]
        for x in runs:
            tag={k:x['result'][k] for k in ['scenario','policy','cost']};rows.extend(dict(**tag,**r) for r in x[group])
        pd.DataFrame(clean(rows)).to_parquet(dest/f'{group}.parquet',index=False)
    save(dest/'results.json',[x['result'] for x in runs]);
    with gzip.open(dest/'audit.jsonl.gz','wt') as f:
        for x in runs:f.write(json.dumps(clean({k:x[k] for k in ['result','audit','orders']}),ensure_ascii=False)+'\n')
    if not sample:
        sd=pd.read_parquet(O/'sample/daily.parquet');fd=pd.read_parquet(dest/'daily.parquet');fd=fd[fd.date.le(str(SAMPLE_END))]
        keys=['scenario','policy','cost','date'];pd.testing.assert_frame_equal(sd.sort_values(keys).reset_index(drop=True),fd.sort_values(keys).reset_index(drop=True),check_exact=True)
    save(dest/'verification.json',dict(passed=True,paths=8,initial_and_trigger_and_pretrigger_audit_exact=True,all_daily_nav_and_native_fees_cash_shares_cycles=True,sample_full_prefix_exact=not sample,seconds=time.monotonic()-t))
    H.progress(stage='finished',sample=sample,seconds=time.monotonic()-t)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='sample':compute(True)
    elif sys.argv[1]=='full':compute(False)
