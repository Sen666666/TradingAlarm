"""Isolated daily-data unified first-probe contract. No implicit execution.

Original role, evidence, protection and ledger callbacks are preserved. Pool
promotion is an explicit stock-specific confirmation event, separate from buys.
"""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace as NS
import sys, inspect, textwrap, copy, hashlib, pickle
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'account_comparison_continuous_v1'
sys.path.insert(0,str(BASE/'no_loss_add_v1'))
import profit_gate as P
A,N,J,LR=P.A,P.N,P.J,P.J.LR
SUFFIX=':UNIFIED_EMPTY_POSITION_PROBE_V1'
Z=D(0)

# Native request retains every original identity, consumption and budget guard.
# Its implicit sector migration is replaced by explicit candidate authorization.
REQUEST_SOURCE=textwrap.dedent('    def request('+A.P.NEW_MODEL.split('    def request(',1)[1].split('    def fill(',1)[0])
REQUEST_SOURCE=REQUEST_SOURCE.replace('if not self.migrate(sector):','if not self.confirmed_stock_ready(stock, sector, stock_token, bar):')
assert REQUEST_SOURCE.count('self.confirmed_stock_ready')==1
_req_env=dict(A.P.MOD.__dict__)
exec(compile(REQUEST_SOURCE,str(HERE/'derived_request.py'),'exec'),_req_env)

class UnifiedBudget(A.NoConfirmed60Budget):
    request=_req_env['request']
    def migrate(self,sector):
        # Industry and cancel callbacks may update stage but never free probe
        # capacity by sweeping stocks that lack their own confirmation.
        state=self.sectors[sector]
        if state.active and state.level>0:state.status='confirmed' if state.level==1 else 'expanded'
        return False
    def confirmed_stock_ready(self,stock,sector,token,bar):
        return bool(token and self._admission== (stock,sector,token.event_id,bar)
                    and self.expand and self.sectors[sector].active
                    and self.sectors[sector].level>0
                    and self.confirmed_stock_lot(stock,sector))
    def confirmed_stock_lot(self,stock,sector):
        state=self.sectors[sector]
        return any(x.stock==stock and x.sector==sector and x.qty>0 and x.pool=='confirmed' and x.episode==state.episode and x.attempt==state.attempt for x in self.lots)
    def promote_stock(self,stock,sector,token,bar,net_profit):
        s=self.sectors.get(sector)
        if not (s and s.active and s.level>0 and self.expand and net_profit>0):return [],'promotion_not_eligible'
        if (token is None or token.stock!=stock or token.sector!=sector
            or token.confirmed_time!=bar or not self.valid(token,'stock_cp1',bar)
            or token.event_id in self.consumed):return [],'no_fresh_stock_CP1'
        key=(stock,token.event_id,s.attempt)
        if key in self.promotion_seen:return [],'promotion_evidence_already_used'
        if any(o.stock==stock and o.qty>0 and o.status in ('open','cancel_pending') for o in self.orders.values()):return [],'stock_order_pending'
        move=[x for x in self.lots if x.stock==stock and x.sector==sector and x.episode==s.episode and x.attempt==s.attempt and x.pool=='probe' and x.qty>0]
        if not move:return [],'no_eligible_probe_layers'
        before=(self.cash,self.nav,self.resources(),self.shared_loss)
        identities=[(x.batch,x.qty,x.cost,x.floor,x.role,x.episode,x.attempt) for x in self.lots]
        for x in move:x.pool='confirmed'
        self.promotion_seen.add(key)
        assert before==(self.cash,self.nav,self.resources(),self.shared_loss)
        assert identities==[(x.batch,x.qty,x.cost,x.floor,x.role,x.episode,x.attempt) for x in self.lots]
        self.audit.append(('stock_confirmation_promotion',stock,token.event_id,tuple(x.batch for x in move)))
        return [x.batch for x in move],'promoted'

def token_for(b,i):
    if i['role']!='mobile':return None
    sector=i.get('_sector');s=b.sectors[sector];bar=J.ordinal(i['clock'].decision_at.date());cp=i['CP1_trace']
    return J.V.Evidence(i['CP1_id'],sector,'stock_cp1','21',J.ordinal(cp['formation_start_exclusive']),bar,bar,s.episode,i['sid'],s.attempt)

# Exact native opening with one promotion phase after sells/settlement/sync,
# before original PVR allocation. Promotion-only evidence is not a buy intent.
OPEN_SOURCE=textwrap.dedent(inspect.getsource(J.Runner.opening))
_OPEN_ANCHOR=" a.settle_due(at);a.sync(at);funded=[];done=set()"
assert OPEN_SOURCE.count(_OPEN_ANCHOR)==1
OPEN_SOURCE=OPEN_SOURCE.replace(_OPEN_ANCHOR," a.settle_due(at);a.sync(at);self.promote_open_candidates(a,at);funded=[];done=set()")
_env=dict(J.__dict__);exec(compile(OPEN_SOURCE,str(HERE/'derived_opening.py'),'exec'),_env)
OPENING=_env['opening']

def prune_restore_keys(r,snapshot):
    """Legacy restore updates keys but cannot remove caches born after snapshot.
    Validate before any mutation. Preserve only the native immutable handles.
    """
    assert snapshot['source_freeze']==r.source_freeze,'resume input/code freeze differs'
    keep={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}
    removed={'runner':sorted(set(vars(r))-keep-set(snapshot['runner'])),'accounts':{}}
    assert not removed['runner'],('unrecognized post-checkpoint runner keys',removed['runner'])
    for label,a in r.accounts.items():
        assert label in snapshot['accounts']
        keys=sorted(set(vars(a))-{'market','facts'}-set(snapshot['accounts'][label]))
        allowed={'_ix','_ixn','_buy_filling','_deferred_buy_cancels'}
        assert set(keys)<=allowed,('unrecognized post-checkpoint account keys',label,keys)
        removed['accounts'][label]=keys
        for key in keys:del a.__dict__[key]
    return removed

class UnifiedRunner(P.ProfitRunner):
    opening=OPENING
    def planning(self,at):
        old=len(self.opportunities)
        N.Runner.planning(self,at)
        for a in self.accounts.values():
            decision=a.decisions[-1]
            for i in a.pending:
                i['_decision_nav']=a.current_nav
                i['_sector']=self.sector_by_sid[i['sid']]
                if not a.quantity(i['sid']):
                    i['budget']=min(i['budget'],a.current_nav*D('.02'))
                    i['_flat_risk_budget']=a.current_nav*D('.0025')
                    # Freeze a joint cash/risk cap at decision CLOSE; OPEN may
                    # reduce it, but a favorable gap cannot create new shares.
                    quote=i['quote'];ref=quote.raw_price*(1+LR.SLIP);rawfloor=i['floor']/self.facts.factor(i['sid'],at)
                    maxq=min(i['cap'],int(i['budget']/ref))
                    i['cap']=LR.maximum_quantity(quote.quantity,maxq,lambda q:LR.protection_risk(q,ref,rawfloor,quote.fees,quote.par_value)<=i['_flat_risk_budget'])
            a.promotion_candidates=[]
            clock=None
            for row in self.opportunities[old:]:
                if row['account']!=a.label or not row['held'] or row['barriers'] or 'mobile' not in row['roles'] or row['mobile_Q'] is not True:continue
                sid=row['sid'];cp=self.receipts[sid].get(J.gidday(at));q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
                if cp is None or q is None or floor is None:continue
                if clock is None:clock=self.facts.packet(at,'I')[0]
                floor=max(floor,D(str(self.cp[sid].loc[J.pd.Timestamp(at.date()),'candidate'])))
                a.promotion_candidates.append(dict(sid=sid,clock=clock,quote=q,role='mobile',floor=floor,CP1_id=cp['receipt_id'],CP1_trace=cp,_sector=row['sector']))
            decision['unified_intents']=[{k:v for k,v in i.items() if k not in ('quote','clock','CP1_trace')} for i in a.pending]
            decision['promotion_candidates']=[{k:v for k,v in i.items() if k not in ('quote','clock','CP1_trace')} for i in a.promotion_candidates]
    def promote_open_candidates(self,a,at):
        prepared=[]
        for i in sorted(getattr(a,'promotion_candidates',[]),key=lambda x:x['sid']):
            if i['clock'].earliest_execution_at!=at:continue
            raw=self.market.raw[i['sid']];day=J.pd.Timestamp(at.date())
            if day not in raw.index:
                self.promotion_reject(a,i,at,'missing_open',historical_tradability='UNKNOWN');continue
            if not J.np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:
                self.promotion_reject(a,i,at,'invalid_open',historical_tradability='UNKNOWN');continue
            proof=self.promote_candidate(a,i,D(str(raw.loc[day].open)),at,prepare_only=True)
            if proof is not None:prepared.append(proof)
        # Every proof was computed before any pool mutation, on the same
        # post-sell/pre-buy snapshot. Commits cannot affect other eligibility.
        for proof in prepared:self.commit_promotion(a,proof)
    def net_verdict(self,a,i,op,at):
        assert self.market.phase=='OPEN' and self.market.phase_at==at
        assert i['clock'].decision_at<at and i['clock'].earliest_execution_at==at
        state=self.cost_books[a.label].sync(a).states.get(i['sid'],{'qty':0,'cost':Z,'round':0})
        px=op*(1-LR.SLIP);sched=self.market.fees(i['sid'],at)
        fee=LR.fees(state['qty'],px,sched,'sell',i['quote'].par_value) if state['qty'] else Z
        return dict(round=state['round'],**P.judge(state['qty'],state['cost'],op,fee))
    def promotion_reject(self,a,i,at,reason,**detail):
        self.promotion_events.append(dict(account=a.label,sid=i['sid'],at=at,signal_at=i['clock'].decision_at,CP1_id=i.get('CP1_id'),reason=reason,moved=[],allowed=False,independent_of_buy=True,**detail))
    def promote_candidate(self,a,i,op,at,prepare_only=False):
        sid=i['sid'];b=a.budget;sector=self.sector_by_sid[sid];s=b.sectors.get(sector)
        def reject(reason,**detail):self.promotion_reject(a,i,at,reason,**detail)
        if i['role']!='mobile':return reject('not_original_mobile_confirmation')
        if not a.quantity(sid):return reject('post_sell_qty_zero')
        if sid in a.buys or sid in a.exits:return reject('real_buy_or_exit_pending')
        if not(s and s.active and s.level>0 and b.expand):return reject('industry_not_expansion_authorized')
        i['_sector']=sector;token=token_for(b,i);bar=J.ordinal(i['clock'].decision_at.date())
        if not b.valid(token,'stock_cp1',bar) or token.event_id in b.consumed:return reject('no_fresh_stock_CP1')
        if i['CP1_trace']['receipt_id']!=i['CP1_id'] or i['CP1_trace']['confirmed_day']!=J.gidday(i['clock'].decision_at):return reject('CP_identity_or_date_mismatch')
        eligible=[x for x in a.live(sid) if a.jmeta[x['id']]['pool']=='probe' and a.jmeta[x['id']]['attempt']==s.attempt and a.jmeta[x['id']]['episode']==s.episode]
        if not eligible:return reject('no_eligible_probe_layers')
        if any(i['clock'].decision_at<=x['opened'] for x in eligible):return reject('CP_not_after_probe_fill')
        try:factor=D(str(self.facts.factor(sid,at)))
        except (ValueError,TypeError,KeyError,ArithmeticError):return reject('invalid_factor',price_domain='UNKNOWN')
        if not factor.is_finite() or factor<=0:return reject('invalid_factor',price_domain='UNKNOWN')
        if not op.is_finite() or op<=0:return reject('invalid_open',historical_tradability='UNKNOWN')
        floor=i['floor']/factor
        if not floor.is_finite() or floor<=0:return reject('invalid_effective_floor',price_domain='UNKNOWN')
        verdict=self.net_verdict(a,i,op,at)
        reason='open_at_or_below_protection' if op<=floor else 'nonprofitable_remaining_holding' if not verdict['allowed'] else 'eligible'
        proof=dict(i=i,op=op,at=at,token=token,bar=bar,verdict=verdict,floor=floor,reason=reason)
        if prepare_only:return proof
        return self.commit_promotion(a,proof)
    def commit_promotion(self,a,proof):
        i,op,at,token,bar,verdict,floor,reason=(proof[k] for k in ('i','op','at','token','bar','verdict','floor','reason'))
        b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors[sector]
        if reason=='eligible':moved,reason=b.promote_stock(sid,sector,token,bar,verdict['net_profit'])
        else:moved=[]
        if moved:
            a.pools_from_model()
            for layer in moved:assert a.jmeta[int(layer)]['pool']=='confirmed'
            a.assert_budget_view(at)
        event=dict(verdict);event.update(account=a.label,sid=sid,at=at,CP1_id=i['CP1_id'],signal_at=i['clock'].decision_at,attempt=s.attempt,moved=moved,reason=reason,profit_reason=verdict['reason'],known_open=op,effective_floor=floor,independent_of_buy=True,CP_consumed=token.event_id in b.consumed)
        self.promotion_events.append(event)
        return event
    def route(self,a,i,x,at):
        b=a.budget;sid=i['sid'];sector=self.sector_by_sid[sid];s=b.sectors.get(sector);role=i['role'];bar=J.ordinal(i['clock'].decision_at.date())
        if not s or not s.active:return None,'industry_invalidated'
        i['_sector']=sector;token=token_for(b,i)
        if role=='mobile' and (not b.valid(token,'stock_cp1',bar) or token.event_id in b.consumed):return None,'no_fresh_stock_CP1'
        assert not getattr(a,'_budget_sync_pending',False)
        held=a.quantity(sid);verdict=self.net_verdict(a,i,x['known_open'],at)
        self.profit_gate_events.append(dict(account=a.label,sid=sid,role=role,at=at,signal_at=i['clock'].decision_at,**verdict))
        if held and not verdict['allowed']:return None,'nonprofitable_remaining_holding'
        if held and role!='mobile':return None,'held_requires_fresh_stock_CP1'
        routes=['probe']
        if held and role=='mobile' and b.expand and s.level>0 and b.confirmed_stock_lot(sid,sector):routes.append('confirmed')
        results=[];reasons={};p=float(x['price']);floor=float(x['floor']);rule=x['rule']
        for pool in routes:
            pc,pr,_=b.resources(pool);sc,sr,_=b.resources(sector=sector);_,_,reserve=b.resources();pending_fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ('open','cancel_pending'));frac=.02 if pool=='probe' else (.02,.1,.2)[s.level]
            def allowed(q,detail=False):
                fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value);nav=b.nav-pending_fees-float(fee);cap=q*p;risk=q*max(0.,p-floor);fails=[]
                if cap+float(fee)>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:fails.append('cash_or_original_reserve')
                if pool=='probe' and pc+cap>.10*nav+1e-9:fails.append('pool_capital')
                if pool=='probe' and pr+risk>.005*nav+1e-9:fails.append('probe_risk')
                if sc+cap>frac*nav+1e-9:fails.append('sector_capital')
                if sr+risk>.01*nav+1e-9:fails.append('sector_risk')
                if float(held)*float(x['known_open'])+cap>.10*float(a.current_nav)+1e-9:fails.append('stock_capital')
                if not held:
                    if D(q)*x['price']>D(i['_decision_nav'])*D('.02'):fails.append('flat_capital_2pct')
                    if LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value)>D(i['_decision_nav'])*D('.0025'):fails.append('flat_fee_inclusive_risk_025pct')
                return fails if detail else not fails
            q=LR.maximum_quantity(rule,x['maxq'],allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)
        q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))
        if not q:return None,','.join(sorted(set(sum(reasons.values(),[])))) or 'minimum_unit_not_funded'
        bid=f"{a.label}|{i['clock'].decision_at.isoformat()}|{sid}|{role}";fee=LR.fees(q,x['price'],x['schedule'],'buy',i['quote'].par_value)
        b._admission=(sid,sector,token.event_id,bar) if held and token and verdict['allowed'] else None
        try:result=b.request(bid,sid,sector,q,p,floor,token,bar,float(fee/D(q)),probe_request=pool=='probe',role=role,order_expiry_bar=J.ordinal(at.date()),core_epoch_locked=role=='core' and a.core_epoch.get(sid)==i['epoch'])
        finally:b._admission=None
        assert result=='reserved',(bid,result,reasons)
        self.admission_events.append(dict(account=a.label,at=at,sid=sid,role=role,flat=held==0,qty=q,pool=pool,decision_nav=i['_decision_nav'],price=x['price'],floor=x['floor'],gross=D(q)*x['price'],fee=fee,fee_inclusive_risk=LR.protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value),probe_after=b.resources('probe'),budget_nav=b.nav-pending_fees-float(fee),CP1_id=i.get('CP1_id')))
        i.update(budget_order=bid,pool=pool);return (q,pool),None
    def restore(self,path):
        snapshot=pickle.loads(Path(path).read_bytes())
        # No legacy checkpoint is re-certified: outer atomic provenance and
        # parent policy/source-freeze guards remain in force.
        assert snapshot['runner']['integration_policy']==self.integration_policy
        assert snapshot['runner']['rank_scores_manifest_sha256']==self.rank_scores_manifest_sha256
        prune_restore_keys(self,snapshot)
        return A.Runner.restore(self,path)
    def assert_native_wiring(self):
        assert self.integration_policy==A.POLICY+':'+self.rank_mode+P.SUFFIX+SUFFIX
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is OPENING and self.planning.__func__ is UnifiedRunner.planning and self.route.__func__ is UnifiedRunner.route
        for a in self.accounts.values():
            assert type(a) is J.Account and type(a.budget) is UnifiedBudget
            assert a.budget.request.__func__ is _req_env['request']
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)

def install(r):
    P.install(r)
    r.__class__=UnifiedRunner;r.integration_policy+=SUFFIX
    r.promotion_events=[];r.admission_events=[]
    for a in r.accounts.values():
        a.budget.__class__=UnifiedBudget;a.budget.promotion_seen=set();a.budget._admission=None
    r.assert_native_wiring()

def source_hashes():
    paths=[Path(__file__),Path(P.__file__),Path(J.__file__),Path(LR.__file__),Path(N.__file__),Path(A.__file__),Path(A.P.__file__),A.P.W/'account-risk-ablation-20261031/model_without_account_check.py',A.P.W/'account-risk-ablation-20261031/route_without_account_check.py']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
