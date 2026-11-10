"""Pure incremental cost ledger. No market reads, account mutation or orders."""
from decimal import Decimal as D
from dataclasses import dataclass, field
Z=D(0)
EPS=D('1e-16')
def dec(x): return x if isinstance(x,D) else D(str(x))
def close(a,b): return abs(dec(a)-dec(b)) <= EPS

@dataclass
class Lot:
    qty:int
    cost:D
    added:bool
    order:str
    initial_qty:int

@dataclass
class Round:
    number:int=0
    qty:int=0
    avg_cost:D=Z
    H:D=Z
    H_all:D=Z
    avg_retired_cost:D=Z
    avg_realized:D=Z
    R0:D=Z
    buy_cash:D=Z
    sell_cash:D=Z
    retired_cost:D=Z
    realized:D=Z
    seed_layer:object=None
    seed_order:str=''
    lots:dict=field(default_factory=dict)
    unknown:list=field(default_factory=list)
    @property
    def layer_cost(self): return sum((x.cost for x in self.lots.values() if x.qty),Z)
    @property
    def delta(self): return self.layer_cost-self.avg_cost
    def assert_cost(self):
        if not self.unknown:
            assert close(self.buy_cash,self.retired_cost+self.layer_cost),(self.buy_cash,self.retired_cost,self.layer_cost)
            assert close(self.realized,self.sell_cash-self.retired_cost)
            assert close(self.buy_cash,self.avg_retired_cost+self.avg_cost)
            assert close(self.avg_realized,self.sell_cash-self.avg_retired_cost)
            assert close(self.realized-self.avg_realized,self.delta)

class GrowthBook:
    def __init__(self):
        self.states={}
        self.cursor=0
        self.history=[]
        self.archived=[]
        self.fill_orders=set()
    def apply(self,row,seed_risk=None):
        kind=row['kind']
        if kind not in ('real_buy_fill','real_sell_fill','actual_split'): return
        sid=row['sid'];s=self.states.setdefault(sid,Round())
        if kind=='real_buy_fill':
            q=int(row['shares']);assert q>0
            cost=dec(row['price'])*q+dec(row['fees'])
            bid=row['budget_order']
            if s.qty==0:
                self.archived.append((sid,s))
                s=Round(number=s.number+1);self.states[sid]=s
                s.seed_layer=row['layer'];s.seed_order=bid
                if seed_risk is None:s.unknown.append('SEED_RISK_UNKNOWN')
                else:s.R0=dec(seed_risk(row))
            added=s.qty>0
            if bid in self.fill_orders:
                s.unknown.append('MULTIFILL_ORDER_REQUIRES_SEED_CONTRACT_AUDIT')
            self.fill_orders.add(bid)
            assert row['layer'] not in s.lots
            s.lots[row['layer']]=Lot(q,cost,added,bid,q)
            s.qty+=q;s.avg_cost+=cost;s.buy_cash+=cost
        elif kind=='real_sell_fill':
            q=int(row['shares']);assert 0<q<=s.qty
            assert sum(int(p['shares']) for p in row['parts'])==q
            net=sum((dec(p['net_cash']) for p in row['parts']),Z)
            assert close(net,dec(row['price'])*q-dec(row['fees']))
            before=s.delta;new_avg=s.avg_cost*D(s.qty-q)/D(s.qty);avg_ret=s.avg_cost-new_avg;layer_ret=Z
            for p in row['parts']:
                lot=s.lots[p['layer']];take=int(p['shares']);assert 0<take<=lot.qty
                retired=lot.cost*D(take)/D(lot.qty);cash=dec(p['net_cash'])
                realized=cash-retired;hincr=max(Z,-realized) if lot.added else Z
                lot.qty-=take;lot.cost-=retired
                if not lot.qty:assert close(lot.cost,Z);lot.cost=Z
                s.H+=hincr;s.H_all+=max(Z,-realized);s.sell_cash+=cash;s.retired_cost+=retired;s.realized+=realized;layer_ret+=retired
                self.history.append(dict(sid=sid,round=s.number,at=row.get('at'),layer=p['layer'],qty=take,added=lot.added,retired_cost=retired,net_cash=cash,realized=realized,H_increment=hincr,H_after=s.H))
            s.avg_retired_cost+=avg_ret;s.avg_realized+=net-avg_ret
            s.qty-=q;s.avg_cost=new_avg
            if not s.qty:s.avg_cost=Z
            assert close(s.delta,before-(layer_ret-avg_ret)),('delta_bridge',s.delta,before,layer_ret,avg_ret)
        else:
            ratio=dec(row['ratio']);assert ratio>0
            live=[x for x in s.lots.values() if x.qty]
            target=int(D(s.qty)*ratio);parts=[int(D(x.qty)*ratio) for x in live]
            remain=target-sum(parts)
            for k in range(remain):parts[k%len(parts)]+=1
            for lot,q in zip(live,parts):
                lot.qty=q
                if not q and lot.cost:s.unknown.append('SPLIT_ZERO_LAYER_COST_REQUIRES_AUDIT')
            s.qty=target
            if not target:s.avg_cost=Z
        assert s.qty>=0 and s.avg_cost>=0 and s.H>=0
        assert sum(x.qty for x in s.lots.values())==s.qty
        s.assert_cost()
    def sync(self,account,seed_risk):
        for row in account.journal[self.cursor:]:self.apply(row,seed_risk)
        self.cursor=len(account.journal)
        for sid in set(self.states)|set(account.positions):
            s=self.states.get(sid,Round())
            assert s.qty==account.quantity(sid),('growth_quantity',sid,s.qty,account.quantity(sid))
            native={x['id']:x['qty'] for x in account.live(sid)}
            derived={k:x.qty for k,x in s.lots.items() if x.qty}
            assert native==derived,('growth_layers',sid,native,derived)
        return self

def principal(cost,qty,raw_floor,sell_fee,slip=D('.0005')):
    return max(Z,dec(cost)-D(qty)*dec(raw_floor)*(1-slip)+dec(sell_fee))

def layer_profit(qty,raw_open,sell_fee,cost,slip=D('.0005')):
    return D(qty)*dec(raw_open)*(1-slip)-dec(sell_fee)-dec(cost)

def growth_allowed(q,current_qty,U_avg,U_layer,U_post,H,L,P,Dnew,R0,known=True):
    if current_qty==0:return True
    return bool(known and 0<q and U_avg>0 and U_layer>0 and U_post>0 and H+L+P+Dnew<=D('.25')*R0+U_post)

class PendingLedger:
    """Unit-test model for native remaining cash/risk and ACK semantics."""
    def __init__(self):self.orders={}
    def reserve(self,key,qty,gross,fee,added=True):
        assert key not in self.orders
        self.orders[key]=dict(qty=qty,gross=dec(gross),fee=dec(fee),added=added,status='open')
    def fill(self,key,qty,gross,fee):
        o=self.orders[key];assert 0<qty<=o['qty']
        o['qty']-=qty;o['gross']-=dec(gross);o['fee']-=dec(fee)
        assert o['gross']>=0 and o['fee']>=0
    def split(self,key,ratio):
        o=self.orders[key];o['qty']=int(D(o['qty'])*dec(ratio))
    def request_cancel(self,key):self.orders[key]['status']='cancel_pending'
    def ack(self,key):del self.orders[key]
    def risk(self,key,floor,sell_fee):
        o=self.orders[key]
        return principal(o['gross']+o['fee'],o['qty'],floor,sell_fee) if o['qty'] and o['added'] else Z
