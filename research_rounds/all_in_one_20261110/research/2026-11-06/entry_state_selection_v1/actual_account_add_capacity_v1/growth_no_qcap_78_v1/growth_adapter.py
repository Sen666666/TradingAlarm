"""Growth admission only, installed AFTER strictly guarded original restoration."""
from pathlib import Path
from decimal import Decimal as D
import sys
from growth_book import GrowthBook,Round,principal,layer_profit,growth_allowed,close,Z
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'growth_continuous_78_v1'
sys.path.insert(0,str(OLD/'baseline'))
import resume_baseline as B
S=B.S;J=S.J
import profit_gate as PG
SUFFIX=':LAYER_COST_GROWTH_025_NO_QCAP_V1'
ANCHOR="  profit_ok=self.profit_permission(a,i,x,at)"
CHECK="    if not profit_ok:fails.append('nonprofitable_remaining_holding')"
assert PG.DERIVED.count(ANCHOR)==PG.DERIVED.count(CHECK)==1
SOURCE=PG.DERIVED.replace(ANCHOR,ANCHOR+"\n  growth=self.growth_context(a,i,x,at)").replace(CHECK,CHECK+"\n    if not self.growth_quantity_allowed(growth,q):fails.append('growth_budget_or_size')")
assert SOURCE.replace("\n  growth=self.growth_context(a,i,x,at)",'').replace("\n    if not self.growth_quantity_allowed(growth,q):fails.append('growth_budget_or_size')",'')==PG.DERIVED
_env=dict(J.__dict__)
exec(compile(SOURCE,str(HERE/'derived_growth_route.py'),'exec'),_env)
DERIVED_ROUTE=_env['route']

class GrowthRunner(PG.ProfitRunner):
    def route(self,a,i,x,at):
        before=len(self.growth_candidates)
        result,why=DERIVED_ROUTE(self,a,i,x,at)
        if len(self.growth_candidates)>before:
            g=self.growth_candidates[-1]
            q,pool=result if result else (0,None)
            g.update(selected_qty=q,selected_pool=pool,native_result=why or 'reserved')
            if not g['flat']:
                v=self.growth_values(g,q)
                g.update(selected_values=v,minlot_values=self.growth_values(g,x['rule'].buy_minimum))
            # Context contains original schedule solely for current evaluation.
            g.pop('_schedule',None);g.pop('_par',None)
        return result,why
    def seed_risk(self,a,row):
        idx=self.growth_trade_index[a.label]
        for t in a.trades[self.growth_trade_cursor[a.label]:]:
            if t['side']=='buy':idx[t['layer']]=t
        self.growth_trade_cursor[a.label]=len(a.trades)
        t=idx[row['layer']];sid=row['sid'];at=t['at'];q=int(t['shares'])
        assert q==int(row['shares'])
        factor=self.market._growth_factors.factor_at(sid,at.date().isoformat())
        floor=t['floor']/factor;price=D(t['gross_cny'])/q
        schedule=self.market.fees(sid,at);par=self.market.rules['security_metadata'][sid]['par_value']
        stop= floor*(1-J.LR.SLIP)
        sellfee=J.LR.fees(q,stop,schedule,'sell',D(str(par)))
        return max(Z,D(t['gross_cny'])+D(t['fees_cny'])-q*stop+sellfee)
    def sync_growth(self,a):
        book=self.growth_books[a.label].sync(a,lambda row:self.seed_risk(a,row))
        avg=self.cost_books[a.label].sync(a)
        for sid,state in book.states.items():
            old=avg.states.get(sid,dict(qty=0,cost=Z))
            assert state.qty==old['qty'] and close(state.avg_cost,old['cost']),('average_book_bridge',sid,state.avg_cost,old['cost'])
        return book
    def growth_context(self,a,i,x,at):
        assert self.market.phase=='OPEN' and self.market.phase_at==at
        assert i['clock'].decision_at<at
        book=self.sync_growth(a);sid=i['sid'];s=book.states.get(sid,Round());q=s.qty
        g=dict(account=a.label,sid=sid,role=i['role'],at=at,signal_at=i['clock'].decision_at,
               round=s.number,flat=q==0,qty=q,C_layer=s.layer_cost,C_avg=s.avg_cost,delta=s.delta,
               H=s.H,H_all=s.H_all,realized=s.realized,avg_realized=s.avg_realized,R0=s.R0,
               candidate_floor=x['floor'],buy_price=x['price'],known_open=x['known_open'],
               seed_layer=s.seed_layer,unknown=list(s.unknown),
               available=a.available,decision_nav=a.current_nav,
               native_pending_cash=a.balance(at,self.market.marks(at,a.positions))['order_reserved'],
               maxq=x['maxq'],_schedule=x['schedule'],_par=i['quote'].par_value)
        g['L']=Z;g['P']=Z;g['live_added_layers']=[];g['own_pending']=[]
        if q:
            schedule=x['schedule'];par=i['quote'].par_value
            mark=x['known_open']*(1-J.LR.SLIP)
            sellfee=J.LR.fees(q,mark,schedule,'sell',par)
            g['U_avg']=D(q)*mark-sellfee-s.avg_cost
            g['U_layer']=D(q)*mark-sellfee-s.layer_cost
            assert close(g['U_layer'],g['U_avg']-s.delta)
            for native in a.live(sid):
                lot=s.lots[native['id']]
                if not lot.added:continue
                floor=(D(str(a.jmeta[native['id']]['last_core_line'])) if native['kind']=='core' else native['floor'])/self.facts.factor(sid,at)
                stop=floor*(1-J.LR.SLIP)
                loss=principal(lot.cost,lot.qty,floor,J.LR.fees(lot.qty,stop,schedule,'sell',par))
                g['L']+=loss
                g['live_added_layers'].append(dict(layer=native['id'],qty=lot.qty,cost=lot.cost,floor=floor,L=loss))
            for bid,bo in a.budget.orders.items():
                if bo.stock!=sid or bo.status not in ('open','cancel_pending') or bo.qty<=0:continue
                native=a.buys.get(sid)
                if native is None or a.order_bridge[native.order_id]!=bid:
                    g['unknown'].append('PENDING_BUDGET_WITHOUT_NATIVE_ORDER')
                    continue
                assert native.remaining_shares==bo.qty
                if bid==s.seed_order:continue
                floor=a.order_meta[native.order_id]['floor']/self.facts.factor(sid,at)
                stop=floor*(1-J.LR.SLIP)
                risk=principal(native.remaining_budget_cny+native.fee_reserved_cny,bo.qty,floor,J.LR.fees(bo.qty,stop,schedule,'sell',par))
                g['P']+=risk;g['own_pending'].append(dict(order=bid,qty=bo.qty,status=bo.status,risk=risk))
        else:g['U_avg']=g['U_layer']=Z
        self.growth_candidates.append(g)
        return g
    def growth_values(self,g,q):
        if not q:return dict(qty=0,U_post=g['U_layer'],Dnew=Z,buy_cash=Z,headroom=D('.25')*g['R0']+g['U_layer']-g['H']-g['L']-g['P'])
        mark=g['known_open']*(1-J.LR.SLIP);stop=g['candidate_floor']*(1-J.LR.SLIP)
        schedule=g['_schedule'];par=g['_par']
        cash=D(q)*g['buy_price']+J.LR.fees(q,g['buy_price'],schedule,'buy',par)
        up=D(g['qty']+q)*mark-J.LR.fees(g['qty']+q,mark,schedule,'sell',par)-g['C_layer']-cash
        dn=max(Z,cash-D(q)*stop+J.LR.fees(q,stop,schedule,'sell',par))
        return dict(qty=q,U_post=up,Dnew=dn,buy_cash=cash,headroom=D('.25')*g['R0']+up-g['H']-g['L']-g['P']-dn)
    def growth_quantity_allowed(self,g,q):
        if g['flat']:return True
        v=self.growth_values(g,q)
        return growth_allowed(q,g['qty'],g['U_avg'],g['U_layer'],v['U_post'],g['H'],g['L'],g['P'],v['Dnew'],g['R0'],not g['unknown'])
    def assert_growth_wiring(self):
        assert self.integration_policy==S.A.POLICY+':'+self.rank_mode+PG.SUFFIX+SUFFIX
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is S.N.Runner.planning
        assert self.profit_permission.__func__ is PG.ProfitRunner.profit_permission
        assert self.route.__func__ is GrowthRunner.route
        for a in self.accounts.values():
            assert type(a)is J.Account and type(a.budget)is S.A.NoConfirmed60Budget
            assert a.budget.request.__func__ is S.A.P.MOD.Contract.request
            assert a.budget.migrate.__func__ is S.A.NoConfirmed60Budget.migrate
            for name in ('reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys'):
                assert getattr(a,name).__func__ is getattr(J.Account,name)
    def restore(self,path):
        # Own new identity and source-freeze required by atomic wrapper.
        last=S.L.PreparedRunner.restore(self,path)
        self.assert_growth_wiring()
        return last

def install_growth(boot):
    r=boot['runner'];assert type(r)is PG.ProfitRunner
    r.assert_native_wiring()
    r.__class__=GrowthRunner;r.integration_policy+=SUFFIX
    r.growth_books={k:GrowthBook() for k in r.accounts}
    r.growth_candidates=[];r.growth_observations=[]
    r.growth_trade_index={k:{} for k in r.accounts}
    r.growth_trade_cursor={k:0 for k in r.accounts}
    r.market._growth_factors=boot['factors']
    for a in r.accounts.values():r.sync_growth(a)
    r.source_freeze=dict(r.source_freeze)
    for p in (HERE/'CONTRACT.md',HERE/'growth_book.py',Path(__file__),HERE/'test_growth_book.py',Path(B.__file__)):
        r.source_freeze[str(p)]=B.sha(p)
    r.assert_growth_wiring()
    return r

def observe(boot,at,phase):
    r=boot['runner']
    for a in r.accounts.values():
        book=r.sync_growth(a)
        if phase!='CLOSE':continue
        for sid in a.positions:
            s=book.states[sid]
            r.growth_observations.append(dict(account=a.label,at=at,sid=sid,qty=s.qty,
                C_layer=s.layer_cost,C_avg=s.avg_cost,delta=s.delta,H=s.H,H_all=s.H_all,
                realized=s.realized,avg_realized=s.avg_realized,R0=s.R0,seed_layer=s.seed_layer,
                round=s.number,unknown=list(s.unknown)))
