"""Decimal reservation feasibility only. No fills, PnL or account replay."""
from dataclasses import dataclass
from decimal import Decimal as D
from collections import defaultdict
ZERO=D(0)
def dec(value):
    if not isinstance(value,D) or not value.is_finite():raise ValueError('finite Decimal required')
    return value
@dataclass(frozen=True)
class Exposure:
    sid:str
    round_id:str
    sector:str
    pool:str
    qty:int
    mark:D
    floor:D
    fee:D=ZERO
    status:str='held'
    def __post_init__(self):
        for name in ('sid','round_id','sector'):
            if not isinstance(getattr(self,name),str) or not getattr(self,name).strip():raise ValueError('nonempty identity required')
        for name in ('mark','floor','fee'):dec(getattr(self,name))
        if type(self.qty) is not int or self.qty<=0 or self.mark<=0 or self.floor<=0 or self.fee<0:raise ValueError('invalid exposure')
        if self.pool not in ('probe','confirmed'):raise ValueError('pool required')
        if self.status not in ('held','live','cancel_pending'):raise ValueError('unresolved order status must not be dropped')
    @property
    def capital(self):return D(self.qty)*self.mark
    @property
    def nominal_risk(self):return D(self.qty)*max(ZERO,self.mark-self.floor)
    @property
    def reserved_cash(self):return self.capital+self.fee if self.status in ('live','cancel_pending') else ZERO
@dataclass(frozen=True)
class Snapshot:
    cash:D
    receivable:D
    nav:D|None
    daily_planning_nav:D
    holdings:tuple
    pending:tuple
    unknown:tuple
    source_ref:str
    def __post_init__(self):
        for name in ('cash','receivable','daily_planning_nav'):dec(getattr(self,name))
        if self.nav is not None:dec(self.nav)
        if self.cash<0 or self.receivable<0 or self.daily_planning_nav<=0:raise ValueError('invalid cash/receivable/NAV')
        object.__setattr__(self,'holdings',tuple(self.holdings));object.__setattr__(self,'pending',tuple(self.pending));object.__setattr__(self,'unknown',tuple(self.unknown))
        if any(not isinstance(x,Exposure) or x.status!='held' for x in self.holdings):raise ValueError('holdings must contain only held exposures')
        if any(not isinstance(x,Exposure) or x.status not in ('live','cancel_pending') for x in self.pending):raise ValueError('pending must contain live/cancel_pending exposures')
        if self.unknown and self.nav is not None:raise ValueError('UNKNOWN cannot have certified NAV')
        if self.nav is not None and self.nav!=self.cash+self.receivable+sum((x.capital for x in self.holdings),ZERO):raise ValueError('certified NAV must equal cash plus receivable plus gross held MTM')

    @property
    def certified(self):return self.nav is not None and not self.unknown
class ReserveBook:
    def __init__(self,snapshot):
        self.snapshot=snapshot;self.orders=list(snapshot.pending);self.audit=[]
    def resources(self,pool=None,sector=None,sid=None):
        rows=[x for x in self.snapshot.holdings+self.snapshot.pending if x.status=='held']+[x for x in self.orders if x.status in ('live','cancel_pending')]
        rows=[x for x in rows if (pool is None or x.pool==pool) and (sector is None or x.sector==sector) and (sid is None or x.sid==sid)]
        return sum((x.capital for x in rows),ZERO),sum((x.nominal_risk for x in rows),ZERO)
    @property
    def reserved_cash(self):return sum((x.reserved_cash for x in self.orders),ZERO)
    @property
    def unbooked_buy_fees(self):return sum((x.fee for x in self.orders if x.status in ('live','cancel_pending')),ZERO)
    def reasons(self,proposal):
        s=self.snapshot
        if not s.certified:return ['NAV_OR_ASSET_UNKNOWN']
        effective=s.nav-self.unbooked_buy_fees-proposal.fee
        if effective<=0:return ['EFFECTIVE_NAV_NONPOSITIVE']
        pc,pr=self.resources(pool='probe');sc,sr=self.resources(sector=proposal.sector);stock,_=self.resources(sid=proposal.sid)
        cashlimit=min(s.cash-self.reserved_cash-s.daily_planning_nav*D('.10'),s.cash-self.reserved_cash)
        out=[]
        if proposal.capital+proposal.fee>cashlimit:out.append('cash_or_original_reserve')
        if proposal.pool=='probe' and pc+proposal.capital>effective*D('.10'):out.append('pool_capital')
        if proposal.pool=='probe' and pr+proposal.nominal_risk>effective*D('.005'):out.append('probe_risk')
        frac=D('.02') if proposal.pool=='probe' else D('.10')
        if sc+proposal.capital>effective*frac:out.append('sector_capital')
        if sr+proposal.nominal_risk>effective*D('.01'):out.append('sector_risk')
        if stock+proposal.capital>s.daily_planning_nav*D('.10'):out.append('stock_capital')
        return out
    def reserve(self,proposal):
        if proposal.status!='live':raise ValueError('new reservation must be live')
        if any(x.sid==proposal.sid and x.status in ('live','cancel_pending') for x in self.orders):return ['stock_order_pending']
        reasons=self.reasons(proposal)
        if reasons:return reasons
        self.orders.append(proposal)
        self.audit.append({'sid':proposal.sid,'round_id':proposal.round_id,'qty':proposal.qty,'pool':proposal.pool,
                           'effective_nav':self.snapshot.nav-self.unbooked_buy_fees,'reserved_cash':self.reserved_cash,
                           'probe_resources':self.resources(pool='probe')})
        return []
def snapshot_from_ab(module,states,at,*,seed_cash,daily_planning_nav,pool_by_round,pending=()):
    """Caller must first complete original all-known exits/accrual/settlements.
    All archives, including closed-round claims and UNKNOWN, remain accounted.
    This function does not perform those phases or certify corporate actions.
    """
    cash=dec(seed_cash);recv=ZERO;holdings=[];unknown=[]
    prev=module.cal[module.cal<at]
    prev=prev[-1] if len(prev) else None
    for rid,st in module.archives.items():
        cash+=D(str(st.get('cash',0)));recv+=D(str(st.get('receivable',0)))
        sid=st['sid'];current=states.get(sid,{})
        if current.get('state')=='UNKNOWN' and current.get('round_id')==rid:
            unknown.append({'sid':sid,'round_id':rid,'reason':current.get('unknown_reason','ARCHIVE_UNKNOWN'),'core':st.get('core'),'add':st.get('add'),'receivable':st.get('receivable',0)})
            continue
        q=int(st.get('core',0))+int(st.get('add',0))
        if not q:continue
        z=module.raw[sid].get(at,{})
        if not module.finite(z.get('raw_open')) or z['raw_open']<=0 or module.lineage(z)!=st.get('origin') or not module.finite(z.get('adjustment_factor')) or st.get('fac') is None or not module.np.isclose(z['adjustment_factor'],float(st['fac']),rtol=1e-11):
            unknown.append({'sid':sid,'round_id':rid,'reason':'OPEN_SOURCE_FACTOR_NOT_CERTIFIED','qty':q});continue
        if rid not in pool_by_round:
            unknown.append({'sid':sid,'round_id':rid,'reason':'POOL_IDENTITY_MISSING','qty':q});continue
        corefloor=module.facts[sid].get(prev,{}).get('i_floor')
        if not module.finite(corefloor) or corefloor<=0:
            unknown.append({'sid':sid,'round_id':rid,'reason':'PREVIOUS_I_FLOOR_UNKNOWN','qty':q});continue
        for key,floor in [('core',D(str(corefloor))/st['fac']),('add',st.get('addfloor'))]:
            qty=int(st.get(key,0))
            if not qty:continue
            if floor is None or D(str(floor))<=0:
                unknown.append({'sid':sid,'round_id':rid,'reason':'LAYER_FLOOR_UNKNOWN','layer':key,'qty':qty});continue
            holdings.append(Exposure(sid,rid,st['sector'],pool_by_round[rid],qty,D(str(z['raw_open'])),D(str(floor))))
    nav=None if unknown else cash+recv+sum((x.capital for x in holdings),ZERO)
    return Snapshot(cash,recv,nav,daily_planning_nav,tuple(holdings),tuple(pending),tuple(unknown),'ORIGINAL_AB_ARCHIVES_POST_SELL_PRE_BUY')
def reserve_initial(module,book,st,at,nd):
    """Original source metadata/fee/size, then independent shared shrink only."""
    dec(nd)
    if nd<=0:raise ValueError('positive frozen Nd required')
    sid=st['sid'];row={'event_id':st['event_id'],'round_id':st['round_id'],'sid':sid,'sector':st['sector'],'PVR_score':st['PVR_score'],'signal_day':st['signal_day'],'open_day':at,
                     'reservation_only':True,'original_single_q':None,'shared_q':0}
    if st['state']!='BUY_PENDING':return row|{'reason':['NOT_ORIGINAL_PENDING_INITIAL']}
    if at!=module.cal[module.cal>st['signal_day']][0]:return row|{'reason':['NOT_IMMEDIATE_COMMON_OPEN']}
    z=module.raw[sid].get(at,{});prev=module.raw[sid].get(st['signal_day'],{})
    if not module.finite(z.get('raw_open')) or z['raw_open']<=0:return row|{'reason':['MISSING_NEXT_OPEN_UNKNOWN']}
    if module.lineage(z)!=module.lineage(prev):return row|{'reason':['SOURCE_CHANGED_AT_ENTRY_UNKNOWN']}
    if not module.finite(z.get('adjustment_factor')) or not module.np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):return row|{'reason':['FACTOR_AT_ENTRY_UNKNOWN']}
    op=D(str(z['raw_open']));floor=D(str(st['i_floor']))/D(str(prev['adjustment_factor']))
    if op<=floor:return row|{'reason':['NEXT_OPEN_BELOW_PROTECTION_NOFILL']}
    px=op*(1+module.SLIP);budget=D('.02')*nd;riskmax=D('.0025')*nd
    formula_q,bf,risk,fs,par=module.size(sid,at,px,floor,budget,riskmax,st['prior20_capacity'])
    legacy_q,_,_,_,_=module.size(sid,at,px,floor,module.INIT,module.RISK,st['prior20_capacity'])
    qr,_,_=module.getmeta(sid,at)
    row.update(minimum_buy_quantity=qr.buy_minimum,original_single_q=legacy_q,source_formula_q_at_round_nd=formula_q,close_q=int(st['close_q']),known_open=op,buy_price=px,floor=floor,round_nd=nd,initial_fee_budget=budget,round_fee_risk_cap=riskmax)
    q=qr.buy_floor(min(formula_q,int(st['close_q'])))
    row['before_shared_caps_q']=q;initial_reasons=[];row['quantity_checks']=[]
    while q>0:
        fee=module.fee(q,px,fs,'buy',par)
        proposal=Exposure(sid,st['round_id'],st['sector'],'probe',q,px,floor,fee,'live')
        reasons=book.reasons(proposal)
        row['quantity_checks'].append({'qty':q,'buy_fee':fee,'effective_nav':None if book.snapshot.nav is None else book.snapshot.nav-book.unbooked_buy_fees-fee,'reasons':reasons})
        if not initial_reasons:initial_reasons=reasons
        if not reasons:
            errors=book.reserve(proposal)
            if errors:return row|{'reason':errors}
            planned_risk=max(ZERO,D(q)*(px-floor*(1-module.SLIP))+fee+module.fee(q,floor*(1-module.SLIP),fs,'sell',par))
            assert proposal.capital+fee<=budget and planned_risk<=riskmax and q<=int(st['close_q'])
            return row|{'shared_q':q,'gross':proposal.capital,'buy_fee':fee,'fee_inclusive_risk':planned_risk,'nominal_line_risk':proposal.nominal_risk,
                        'reason':[],'shrink_reasons':initial_reasons,'effective_nav_after_reservation':book.snapshot.nav-book.unbooked_buy_fees}
        q=qr.buy_floor(q-1)
    return row|{'reason':initial_reasons or ['ORIGINAL_SIZE_OR_CLOSE_CEILING_ZERO']}
