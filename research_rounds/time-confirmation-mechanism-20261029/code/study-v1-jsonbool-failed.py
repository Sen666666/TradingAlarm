"""Frozen v2: original I versus targeted fixed-clock wait/time evidence."""
from pathlib import Path
import sys,json,gzip,time,datetime,collections,bisect,importlib.util,math,copy
from decimal import Decimal as D
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/time-confirmation-mechanism-20261029';E1=ROOT/'research_rounds/s-entry-mechanism-audit-20261029';TA=ROOT/'research_rounds/time-evidence-audit-20261029';E2=ROOT/'research_rounds/cp1-incremental-mechanism-20261029'
sp=importlib.util.spec_from_file_location('tc_time_original',TA/'code/audit.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;B=H.B;Z=H.Z
sp=importlib.util.spec_from_file_location('tc_old_cash',ROOT/'research_rounds/s0-first-margin-20261029/code/study.py');R=importlib.util.module_from_spec(sp);sys.modules[sp.name]=R;sp.loader.exec_module(R)
def save(p,x):H.save(p,x)
def enc(x):return H.encoded(x)
def ok(x):return pd.notna(x) and bool(x)
def at(d,t):return H.at(d,t)
def near2(v):return v is not None and math.isfinite(v) and S.EV.compare(v,2.)>=0
def stamp(x):return pd.Timestamp(x).to_pydatetime()
def logtime(x):return stamp(x['receipt']['at']) if x['kind']=='fill' else stamp(x['receivable']['ex_at']) if x['kind']=='dividend_accrual' else stamp(x['at'])
def prepare():
    t=time.monotonic();O.mkdir(exist_ok=False);(O/'code').mkdir()
    protocol=dict(version='v2',frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),development_target_minutes=15,full_compute_budget_seconds=300,base_contract=str(TA/'TIME_CONTRACT_DRAFT.txt'),scope='All fixed5349 E0 epochs, independent1m each alternative, costs1/2, original I/E0 exit and terminalOct27. A read-only experiment-one I; only W/T new computation.',feature='Causal adjusted valid C/V closes; origin last already-confirmed E0 up pivot frozen per intent. f_j=positive log increment above prior record high since pivot under original numerical tie rule. Neff=(sum f)^2/sum f^2; >=2 is only this research dispersion boundary, not sustained-trend guarantee.',clock='Origin is observation1; target=origin valid-stock-C/V observation number+4. Count as valid observations arrive, never put future calendar deadline into origin record. Halt/invalid CV does not advance. Source/I/E0 invalidity cancels.',policies=dict(A='Original I, existing ledger.',W='If origin Neff>=2 or unknown, original immediate I. If known<2, wait fixed fifth valid observation, no extra dispersion filter.',T='Same targeted wait as W, same origin clock; at fifth observation require frozen-anchor Neff>=2. Then original dayorder, not wait for fresh I at deadline.'),continuation='Deadline original non-event eligibility Q_cont AND known G1 ready/warm, original I/E0/source alive; exact current original i_floor for order. Temporary G1 cold while structure alive does not by itself cancel; warmth required at deadline.',unknown='Count absent/NaN origin Neff or pivot and use original I immediately, no added time restriction. Unknown-event outcomes separate and not confirmation support. Known-intent critical anchor/clock cannot become indeterminate; report blocker rather than fabricate cache.',rebuild='An intent ends on rejection/cancel or order submission; after submission original execution-day expiry applies. Only a future new original Q event may start next intent. A rejected deadline cannot reuse its same-close Q. A zero-fill execution day may use that day new close Q because it is later than submitted decision/consumed signal. No rolling extension, old-signal reuse or permanent deletion.',divergence='W/T first common intent has identical clock. After divergence each consumes only own future Q while unheld/no order. Rich-origin exact A identity only before first actual low-intent divergence, not unconditional after state differences.',entry='At most one actual entry per E0 unit, including partial fill as entry. All origin/rebuild/dayexpiry/no-fill and losing units included. F/ACT forced-exit reentries outside this test.',accounting='Compare T-A,W-A,T-W. Derived D copies W entire outcome iff T temporal rule would pass W first actual-entry intent, else cash0 PnL. T-W=(D-W)+(T-D). Later term includes restored/changed path, not pure causal information. No fourth economic arm.',report='Fixed5349 denominator plus first-origin-low subset, ever-low-eligible subset and actual-low-intent subset; unknown separate from no-Q cash. Realized/open/claims, tail either comparison arm>=30% and continuous curve, failures, delayed participation, no-fill, holding duration, raw/repeated signals, standardized first-order/waiting/holding concurrency. Waiting intents reserve no cash.',stop='No parameter change after results, no3/7/extra grade/volume gates, no product/accounts. Fewer fills alone not success. Mixed signs tradeoff; insufficient net/tail value stop this temporal gate.')
    save(O/'PROTOCOL-v2.json',protocol)
    paths=[TA/'TIME_CONTRACT_DRAFT.txt',TA/'code/audit.py',TA/'diagnostic/event-timing.parquet',TA/'diagnostic/verification.json',E1/'market-cache.parquet',E1/'opportunities.parquet',E1/'code/audit.py',E1/'results/units.parquet',E1/'results/audit.jsonl.gz',E2/'continuous-eligibility.parquet',R.__file__]
    for r in H.roster():paths += [H.SNAP/'signals'/f"{r['symbol']}.parquet",H.SNAP/'facts'/f"{r['symbol']}.parquet"]
    save(O/'input-identity.json',dict(sha256={str(p):H.sha(p) for p in paths},snapshot=str(H.SNAP),before_new_economics=True))
    cache=pd.read_parquet(E1/'market-cache.parquet');f=pd.read_parquet(TA/'diagnostic/event-timing.parquet');f=f[f.Q];unknown=f.frontier_neff.isna()|f.pivot_date.isna();first=f[f.first_Q_in_study_epoch];low=first.frontier_neff.map(lambda x:pd.notna(x) and not near2(float(x)));alllow=f.frontier_neff.map(lambda x:pd.notna(x) and not near2(float(x)))
    save(O/'preflight.json',dict(common_epochs=5349,full_Q_rows=len(f),unknown_feature_rows=int(unknown.sum()),unknown_feature_epochs=int(f.loc[unknown,'e0_epoch'].nunique()),first_Q_epochs=len(first),first_Q_low=int(low.sum()),ever_low_epochs=int(f.loc[alllow,'e0_epoch'].nunique()),no_Q_epochs=5349-len(first),seconds=time.monotonic()-t))
    H.progress(stage='v2_frozen',unknown=int(unknown.sum()),first_low=int(low.sum()),ever_low_epochs=int(f.loc[alllow,'e0_epoch'].nunique()),seconds=time.monotonic()-t)
class Evidence:
    def __init__(self,s,features,cut=None):
        facts=pd.read_parquet(H.SNAP/'facts'/f'{s}.parquet');sig=pd.read_parquet(H.SNAP/'signals'/f'{s}.parquet').reindex(facts.index)
        if cut is not None:sig=sig.loc[:cut]
        good=sig.close.gt(0)&sig.volume.gt(0)&np.isfinite(sig.close)&np.isfinite(sig.volume);d=sig[good];self.days=d.index;self.p=d.close.to_numpy(float);self.v=d.volume.to_numpy(float);self.pos={day:j for j,day in enumerate(self.days)};self.feature=features.set_index('date').to_dict('index');self.memo={}
    def neff(self,anchor,day):
        key=(pd.Timestamp(anchor),pd.Timestamp(day))
        if key not in self.memo:
            a=self.pos.get(key[0]);b=self.pos.get(key[1]);self.memo[key]=None if a is None or b is None or b<=a else float(S.metrics(self.p,self.v,a,b)['frontier_neff'])
        return self.memo[key]
    def origin(self,day):
        r=self.feature.get(day)
        if r is None or pd.isna(r['pivot_date']) or pd.isna(r['frontier_neff']):return None,None
        anchor=pd.Timestamp(r['pivot_date']);v=self.neff(anchor,day)
        if v is None or not math.isfinite(v):return None,None
        assert v==float(r['frontier_neff']),('origin cached identity',day,v,r['frontier_neff'])
        return anchor,v

class Exposure:
    def __init__(self):self.q=0;self.basis=Z;self.res={}
    def add(self,x,native=False):
        k=x['kind']
        if k=='reserve':self.res[x['order_id']]=[D(x['gross_budget_cny']),D(x['fee_reserved_cny'])]
        elif k=='release_buy':self.res.pop(x['order_id'],None)
        elif k=='fill':
            r=x['receipt'];side=r.side if native else r['side'];q=r.shares if native else r['shares'];gr=r.gross_cny if native else D(r['gross_cny']);fee=r.fees_cny if native else D(r['fees_cny'])
            if side=='buy':
                self.q+=q;self.basis+=gr+fee
                if x['order_id'] in self.res:self.res[x['order_id']][0]-=gr;self.res[x['order_id']][1]=max(Z,self.res[x['order_id']][1]-fee)
            else:self.basis-=self.basis*D(q)/D(self.q);self.q-=q
        elif k in ['split','split_fraction_floor_proxy']:self.q=int(D(self.q)*D(x['ratio']))
    def reserved(self):return sum((sum(v,Z) for v in self.res.values()),Z)
def addcurve(curve,arm,cost,day,q,basis,res,wait,mv,origin=0,submitted=0,fill=0,ready=0):
    k=(arm,cost,day);r=curve.setdefault(k,dict(arm=arm,cost=cost,date=day,held_units=0,cost_basis=Z,reserved=Z,waiting_units=0,market_value=Z,origins=0,submitted=0,fills=0,ready=0));r['held_units']+=int(q>0);r['cost_basis']+=basis;r['reserved']+=res;r['waiting_units']+=int(wait);r['market_value']+=mv;r['origins']+=origin;r['submitted']+=submitted;r['fills']+=fill;r['ready']+=ready
def run(e,g,m,ev,arm,cost,curve=None,cutoff=H.END):
    s=e['symbol'];a=H.L.SectorAccount(initial_cash=B,cost_multiplier=cost,fractional_split_policy=m.protocol['fractional_split_policy']);entered=False;floor=None;pending={};intent=None;first_signal=first_fill=None;firstmeta=None;logs=[];attempts=[];last_consumed=None;low_count=unknown_count=0;first_low=None;exp=Exposure();xi=0;heldsessions=0;costsessions=Z;waiting=0;ready_count=0
    dates=g.index[(g.index>=max(pd.Timestamp(e['start']),H.START))&(g.index<=cutoff)];end=pd.Timestamp(e['end_signal']) if e['end_signal'] is not None else None;actions=collections.defaultdict(list)
    for x in m.actions.get(s,[]):actions[x['effective_date']].append(x)
    def submit(day,clock,meta):
        quote=m.quote(s,clock.decision_at)
        if quote is None or pd.isna(g.loc[day,'i_floor']):return 0
        yes,why=a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=B,candidate_id=e['event_id']);attempts.append(dict(signal_at=clock.decision_at,accepted=yes,reason=why,**meta))
        if yes:pending[why]=dict(at=clock.decision_at,floor=D(str(g.loc[day,'i_floor'])),**meta)
        return int(yes)
    for day in dates:
        r=g.loc[day];op=at(day,datetime.time(9,30));cl=at(day,datetime.time(15,10));sub=filled=neworigin=readytoday=0
        for x in actions.get(str(day.date()),[]):H.action(a,m,s,x)
        H.pay(a,m,op)
        if s in a.exits:
            win=m.window(s,op,'sell',cost)
            if win:a.fill_exit(s,win)
        if s in a.buys:
            z=pending[a.buys[s].order_id];win=m.window(s,op,'buy',cost)
            if win and win.raw_open<=z['floor']/D(str(r.factor)):a.audit_log.append(dict(kind='audit_open_support_reject',at=op,sid=s,order_id=a.buys[s].order_id));a.cancel_buy(s)
            elif win:
                rec=a.fill_buy(s,win)
                if rec:entered=True;floor=z['floor'];first_signal=z['at'];first_fill=op;firstmeta=z;filled=1;assert op>z['at']
        H.pay(a,m,op);H.pay(a,m,cl);a.expire_day_buys(cl);clock=H.A.Clock(cl,m.sessions['A'][bisect.bisect_right(m.sessions['A'],cl)],cl.date());ended=end is not None and day>=end
        if a.quantity(s) and s not in a.exits:
            lost=ended or not ok(r.i_target) or (floor is not None and D(str(r.close))<=floor)
            if lost:
                quote=m.quote(s,cl)
                if quote:a.request_exit(quote,clock)
            elif pd.notna(r.i_floor):floor=max(floor,D(str(r.i_floor)))
        alive=not ended and ok(r.e0_target) and ok(r.e0_ready) and ok(r.i_target) and int(r.segment_id)==int(e['source_segment'])
        if not entered and intent is not None:
            if not alive:logs.append(dict(at=cl,kind='intent_cancel_structure',**intent));intent=None;last_consumed=day
            elif day in ev.pos and ev.pos[day]>=intent['target_pos']:
                assert ev.pos[day]==intent['target_pos'];v=ev.neff(intent['anchor'],day)
                if v is None or not math.isfinite(v):raise ValueError(f'Critical frozen-anchor/clock input unknown at deadline: {s} {day}')
                legal=ok(r.Q_cont) and ok(r.g_ready) and pd.notna(r.g_grade) and r.g_grade>=2;timepass=near2(v);accept=bool(legal and (arm=='W' or timepass));logs.append(dict(at=cl,kind='deadline',neff=v,timepass=timepass,legal=legal,accept=accept,**intent));readytoday=int(accept);ready_count+=int(accept)
                if accept:sub=submit(day,clock,dict(origin=intent['origin'],anchor=intent['anchor'],origin_neff=intent['origin_neff'],decision_neff=v,timepass=timepass,kind='wait5'))
                intent=None;last_consumed=day
        if not entered and intent is None and s not in a.buys and not ended and ok(r.Q) and (last_consumed is None or day>last_consumed):
            anchor,v=ev.origin(day);neworigin=1
            if v is None:
                unknown_count+=1;logs.append(dict(at=cl,kind='unknown_origin_fallback_I'));sub=submit(day,clock,dict(origin=day,anchor=None,origin_neff=None,decision_neff=None,timepass=True,kind='unknown_I'));last_consumed=day;readytoday=1;ready_count+=1
            elif near2(v):
                logs.append(dict(at=cl,kind='rich_immediate',neff=v,anchor=anchor));sub=submit(day,clock,dict(origin=day,anchor=anchor,origin_neff=v,decision_neff=v,timepass=True,kind='rich_I'));last_consumed=day;readytoday=1;ready_count+=1
            else:
                assert day in ev.pos;low_count+=1;first_low=cl if first_low is None else first_low;intent=dict(origin=day,origin_pos=ev.pos[day],target_pos=ev.pos[day]+4,anchor=anchor,origin_neff=v);logs.append(dict(at=cl,kind='intent_start',**intent));last_consumed=day
        for x in a.audit_log[xi:]:exp.add(x,True)
        xi=len(a.audit_log);assert exp.q==a.quantity(s)
        if exp.q:heldsessions+=1;costsessions+=exp.basis
        if intent is not None:waiting+=1
        if curve is not None and (exp.q or exp.reserved() or intent is not None or neworigin or sub or filled or readytoday):
            mv=D(exp.q)*m.latest_mark(s,cl).raw_price if exp.q else Z;addcurve(curve,arm,cost,day,exp.q,exp.basis,exp.reserved(),intent is not None,mv,neworigin,sub,filled,readytoday)
        if ended and not a.quantity(s) and not a.buys and not a.exits and not a.dividends and not a.settlements:break
    final=at(cutoff,datetime.time(15,10));u=H.independent(a,m,s,final);cash=R.cashcheck(dict(audit=a.audit_log));assert abs(cash-u['available'])<=u['precision_bound']
    u.update(event_id=e['event_id'],symbol=s,variant=arm,cost=cost,first_signal=first_signal,first_fill=first_fill,first_origin=firstmeta['origin'] if firstmeta else None,first_entry_kind=firstmeta['kind'] if firstmeta else None,entry_timepass=firstmeta['timepass'] if firstmeta else None,low_intents=low_count,unknown_origins=unknown_count,first_low_at=first_low,attempt_count=len(attempts),held_close_sessions=heldsessions,invested_cost_sessions=costsessions,waiting_close_sessions=waiting,ready_count=ready_count,pending_time_at_end=intent is not None,pending_time=intent,cash_residual=abs(cash-u['available']),initial_cash=B)
    return u,dict(event_id=e['event_id'],symbol=s,variant=arm,cost=cost,audit=a.audit_log,attempts=attempts,time=logs)
def controls(ids):
    u=pd.read_parquet(E1/'results/units.parquet');u=u[u.variant.eq('I')&u.symbol.isin(ids)];refs={(x['event_id'],x['cost']):x for x in u.to_dict('records')};aud={}
    with gzip.open(E1/'results/audit.jsonl.gz','rt') as f:
        for line in f:
            x=json.loads(line)
            if x['variant']=='I' and x['symbol'] in ids:aud[(x['event_id'],x['cost'])]=x
    assert refs.keys()==aud.keys();return refs,aud
def control_curve(e,g,m,cost,u,aa,curve):
    ex=Exposure();ix=0;rows=aa['audit'];held=0;cs=Z;last=max([stamp(x['at']) if 'at' in x else stamp(x['receipt']['at']) if x['kind']=='fill' else stamp(x['receivable']['ex_at']) for x in rows],default=at(H.START,datetime.time.min))
    for day in g.index[g.index>=max(pd.Timestamp(e['start']),H.START)]:
        cl=at(day,datetime.time(15,10));origin=sub=filled=0
        while ix<len(rows) and logtime(rows[ix])<=cl:
            x=rows[ix];ix+=1;ex.add(x);sub+=int(x['kind']=='reserve');filled+=int(x['kind']=='fill' and x['receipt']['side']=='buy')
        if ex.q:held+=1;cs+=ex.basis
        if ex.q or ex.reserved() or sub or filled:
            mv=D(ex.q)*m.latest_mark(e['symbol'],cl).raw_price if ex.q else Z;addcurve(curve,'A',cost,day,ex.q,ex.basis,ex.reserved(),False,mv,sub,sub,filled,sub)
        if ix==len(rows) and not ex.q and not ex.reserved():break
    return dict(held_close_sessions=held,invested_cost_sessions=cs)
def compute(sample=False):
    t=time.monotonic();ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());ids=set(H.SAMPLE) if sample else {r['symbol'] for r in H.roster()};_,m,_,_=H.context(ids,False);cache=pd.read_parquet(E1/'market-cache.parquet');ep=pd.read_parquet(E1/'opportunities.parquet');ep=ep[ep.symbol.isin(ids)];f=pd.read_parquet(TA/'diagnostic/event-timing.parquet');cont=pd.read_parquet(E2/'continuous-eligibility.parquet');cc={(r.date,r.symbol):r.Q_cont for r in cont.itertuples()};refs,aud=controls(ids);dest=O/('sample' if sample else 'results');dest.mkdir(exist_ok=False);units=[];A=[];curve={};prefix=[];identitychecks=[];featureschecks=0
    save(dest/'execution-freeze.json',dict(code_sha256=H.sha(Path(__file__)),sample=sample,events=len(ep),arms=['A_readonly','W','T'],before_new_economics=True))
    with gzip.open(dest/'audit.jsonl.gz','wt') as af:
        for n,s in enumerate(sorted(ids)):
            g=cache[cache.symbol.eq(s)].set_index('date').sort_index();g['Q_cont']=[cc.get((d,s),False) for d in g.index];ev=Evidence(s,f[f.symbol.eq(s)]);prefix_done=False
            for e in ep[ep.symbol.eq(s)].to_dict('records'):
                if pd.isna(e['end_signal']):e['end_signal']=None
                for cost in [1,2]:
                    key=(e['event_id'],cost);base=refs[key];ba=aud[key];au={k:base[k] for k in ['net_pnl','net_return','nav','first_signal','first_fill','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','realized_trading_pnl','paid_dividend_income','unrealized_inventory_pnl','accrued_unpaid_dividend_income','dividend_receivable','estimated_liquidation_fee','estimated_exit_slippage','precision_bound']};au.update(event_id=e['event_id'],symbol=s,cost=cost,variant='A',**control_curve(e,g,m,cost,base,ba,curve));A.append(au)
                    for arm in ['W','T']:
                        u,a=run(e,g,m,ev,arm,cost,curve);units.append(u);af.write(json.dumps(enc(a),ensure_ascii=False)+'\n')
                        cut=u['first_low_at'];native=enc(a['audit']);old=ba['audit'];assert [x for x in native if cut is None or logtime(x)<cut]==[x for x in old if cut is None or logtime(x)<cut],(s,e['event_id'],arm,'common rich/unknown native prefix')
                        if cut is None:
                            for k in ['net_pnl','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','dividend_receivable']:assert D(str(u[k]))==D(str(base[k])),(s,arm,'no-low exact',k)
                        identitychecks.append(dict(event_id=e['event_id'],cost=cost,arm=arm,first_low=cut,unknown=u['unknown_origins']))
                        if sample and not prefix_done and arm=='T' and cost==1 and cut is not None:
                            origin=pd.Timestamp(cut.date());p=ev.pos[origin];pcut=ev.days[min(p+2,len(ev.days)-1)];small=Evidence(s,f[f.symbol.eq(s)&f.date.le(pcut)],cut=pcut);gg=g.loc[:pcut];ee=dict(e)
                            if ee['end_signal'] and pd.Timestamp(ee['end_signal'])>pcut:ee['end_signal']=None
                            _,pa=run(ee,gg,m,small,arm,cost,cutoff=pcut)
                            for field in ['audit','attempts','time']:
                                def tm(x):return logtime(x) if field=='audit' else x['signal_at'] if field=='attempts' else x['at']
                                expect=[x for x in a[field] if tm(x)<=at(pcut,datetime.time(15,10))];assert enc(expect)==enc(pa[field]),(s,'physical feature/frozen anchor/clock prefix',field)
                            prefix.append(dict(symbol=s,event_id=e['event_id'],cutoff=str(pcut.date())));prefix_done=True
            if sample or (n+1)%25==0:H.progress(stage='time_capital',sample=sample,stocks=n+1,events=len(A)//2,new_units=len(units),seconds=time.monotonic()-t)
            if not sample and time.monotonic()-t>300:raise TimeoutError('300-second full computation budget')
    pd.DataFrame(enc(units)).to_parquet(dest/'units.parquet',index=False);pd.DataFrame(enc(A)).to_parquet(dest/'A-readonly.parquet',index=False);pd.DataFrame(enc(list(curve.values()))).to_parquet(dest/'daily-concurrency.parquet',index=False);pd.DataFrame(enc(identitychecks)).to_csv(dest/'common-prefix-checks.csv',index=False)
    if not sample:
        su=pd.read_parquet(O/'sample/units.parquet');fu=pd.read_parquet(dest/'units.parquet');fu=fu[fu.symbol.isin(H.SAMPLE)];keys=['event_id','variant','cost'];su=su.sort_values(keys).reset_index(drop=True);fu=fu.sort_values(keys).reset_index(drop=True)
        for k in ['net_pnl','first_signal','first_fill','buy_gross','buy_fees','sell_gross','sell_fees','shares','market_value','low_intents','unknown_origins','held_close_sessions','waiting_close_sessions']:assert su[k].fillna('NONE').tolist()==fu[k].fillna('NONE').tolist(),('sample/full',k)
    save(dest/'verification.json',dict(passed=True,events=len(ep),A_readonly_units=len(A),new_W_T_units=len(units),all_common_predivergence_native_prefixes_exact=True,no_low_actual_financial_identity=True,independent_fees_cash_shares_raw_terminal=True,max_cash_residual=max(x['cash_residual'] for x in units),max_nav_residual=max(x['independent_nav_residual'] for x in units),physical_clock_prefixes=prefix,sample_full_exact=not sample,unknown_origin_count=sum(x['unknown_origins'] for x in units),seconds=time.monotonic()-t))
    H.progress(stage='finished',sample=sample,events=len(ep),seconds=time.monotonic()-t)
if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='sample':compute(True)
    elif sys.argv[1]=='full':compute(False)
