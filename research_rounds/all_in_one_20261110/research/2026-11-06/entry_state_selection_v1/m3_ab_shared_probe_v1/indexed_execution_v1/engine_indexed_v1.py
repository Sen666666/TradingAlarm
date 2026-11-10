"""Bounded daily A+B conditional-execution bridge. No full-period entrypoint."""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import dataclass, asdict
import ast, copy, hashlib, json, sys, types
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'source_bridge_v1'))
import bridge
sys.path.insert(0,str(HERE.parent/'shared_feasibility_v1'))
from limits_v3 import Exposure,Snapshot,ReserveBook
import source_split_v2
ZERO=D(0)
ARM='A_UNION_B_SHARED_ENGINEERING_V1'
REAL_OPENS=('2022-01-06','2022-01-07','2022-01-10')
PHASE={'OPEN':0,'OPEN_FILLED':1,'CLOSE':2}

class StateInvariantError(AssertionError):pass

@dataclass
class Layer:
    layer_id:str
    round_id:str
    sid:str
    kind:str
    qty:int
    opened:object
    cost:D
    first_fill_id:str

class ExecutionBridge:
    def __init__(self,module,seed_cash=D('1200000'),*,evidence_domain='REAL_FROZEN_SOURCE',cp_provider=None):
        self.s=module;self.s.reset(True,'FULL')
        self.seed_cash=D(seed_cash);self.daily_nav=D(seed_cash)
        self.states={};self.seq={};self.layers=[];self.orders={};self.action_ids=set()
        self.caps={};self.pools={};self.pending_cp={};self.cp_attempts=set();self.promotion_seen=set()
        self.closecache={};self.cp_cache={};self.groups={d:g for d,g in module.ev.groupby('day',sort=True)}
        self.evidence_domain=evidence_domain;self.cp_provider=cp_provider
        self.split=source_split_v2.build(module.SOURCE)
        self.audit=[];self.phase='UNSET';self.day=None;self.last_close=None;self.last_open=None
        self.close_nd=None;self.completed_opens=[];self.source_hashes={}
    def _callback(self,name,**overrides):
        return source_split_v2.bind(self.split['codes'][name],self.s,**overrides)
    def _stage(self,day,phase):
        self.day=self.s.pd.Timestamp(day);self.phase=phase;self.s.CURRENT_PHASE=phase
    def _point(self,day,phase):
        return (self.s.pd.Timestamp(day),PHASE[phase])
    def _active_layers(self,rid):
        return [x for x in self.layers if x.round_id==rid and x.qty>0]
    def _live_orders(self,sid=None,rid=None):
        return [o for o in self.orders.values() if o['status'] in ('live','cancel_pending') and (sid is None or o['sid']==sid) and (rid is None or o['round_id']==rid)]
    def _claims_for(self,rid):
        return [c for c in self.s.claims.values() if c.get('owner_round_id')==rid]
    def _zero_liability_initial_unknown(self,rid,st):
        return (not any(a['round_id']==rid and a['side'].startswith('buy') for a in self.s.actions)
                and not any(x.round_id==rid for x in self.layers)
                and not int(st.get('core',0)) and not int(st.get('add',0))
                and D(str(st.get('receivable',0)))==0 and not self._claims_for(rid)
                and not self._live_orders(rid=rid)
                and not any(o['round_id']==rid and o['status'] not in ('rejected','cancelled') for o in self.orders.values()))
    def cash(self):
        return self.seed_cash+sum((D(str(st.get('cash',0))) for st in self.s.archives.values()),ZERO)
    def receivable(self):
        return sum((D(str(st.get('receivable',0))) for st in self.s.archives.values()),ZERO)
    def snapshot(self,day,phase):
        day=self.s.pd.Timestamp(day);holdings=[];unknown=[]
        prior=self.s.cal[self.s.cal<day];floor_day=(prior[-1] if len(prior) else None) if phase=='OPEN' else day
        for rid,st in self.s.archives.items():
            sid=st['sid'];state=self.states.get(sid,{})
            if state.get('state')=='UNKNOWN' and state.get('round_id')==rid:
                if self._zero_liability_initial_unknown(rid,st):continue
                unknown.append(dict(sid=sid,round_id=rid,reason=state.get('unknown_reason'),core=st.get('core'),add=st.get('add'),receivable=st.get('receivable',0)))
                continue
            qty=int(st.get('core',0))+int(st.get('add',0))
            if not qty:continue
            z=self.s.raw[sid].get(day,{});field='raw_open' if phase=='OPEN' else 'raw_close'
            if not self.s.finite(z.get(field)) or z[field]<=0 or self.s.lineage(z)!=st.get('origin') or not self.s.finite(z.get('adjustment_factor')) or not self.s.np.isclose(z['adjustment_factor'],st.get('factor'),rtol=1e-11):
                unknown.append(dict(sid=sid,round_id=rid,reason='MARK_SOURCE_OR_FACTOR_UNKNOWN',qty=qty));continue
            fact=self.s.facts[sid].get(floor_day,{})
            floor=fact.get('i_floor')
            if not self.s.finite(floor) or floor<=0 or rid not in self.pools:
                unknown.append(dict(sid=sid,round_id=rid,reason='FLOOR_OR_POOL_UNKNOWN',qty=qty));continue
            for kind,fl in [('core',D(str(floor))/st['fac']),('add',st.get('addfloor'))]:
                q=int(st.get(kind,0))
                if not q:continue
                if fl is None or not D(str(fl)).is_finite() or D(str(fl))<=0:
                    unknown.append(dict(sid=sid,round_id=rid,reason='ADD_FLOOR_UNKNOWN',qty=q));continue
                holdings.append(Exposure(sid,rid,st['sector'],self.pools[rid],q,D(str(z[field])),D(str(fl)),ZERO,'held'))
        pending=tuple(o['exposure'] for o in self._live_orders())
        nav=None if unknown else self.cash()+self.receivable()+sum((x.capital for x in holdings),ZERO)
        daily=self.daily_nav
        return Snapshot(self.cash(),self.receivable(),nav,daily,tuple(holdings),pending,tuple(unknown),self.evidence_domain+':'+phase)
    def _unknown(self,st,reason,day):
        self.s.freeze_unknown(self.states,st['sid'],st,reason,day)
        self.audit.append(dict(type='UNKNOWN',day=day,round_id=st['round_id'],reason=reason,liability_free_initial=self._zero_liability_initial_unknown(st['round_id'],st)))
    def _record_new_actions(self,start,day):
        for row in self.s.actions[start:]:
            uid=row['round_id']+'|'+str(self.s.pd.Timestamp(day).date())+'|'+row['side']
            if uid in self.action_ids:raise StateInvariantError('duplicate source cash/qty action '+uid)
            self.action_ids.add(uid);row['execution_action_id']=uid;row['execution_domain']='HISTORICAL_CONDITIONAL_OPEN_PROXY'
            if row['side'].startswith('sell'):
                kind='add' if row['side']=='sell_add' else None
                layers=[x for x in self._active_layers(row['round_id']) if kind is None or x.kind==kind]
                if any(x.opened>=day for x in layers):raise StateInvariantError('T+1 invalid source sell')
                if sum(x.qty for x in layers)!=int(row['q']):raise StateInvariantError('source sell/layer mismatch')
                for x in layers:x.qty=0
        return self.s.actions[start:]
    def _check_exit_t1(self,st,day):
        layers=self._active_layers(st['round_id'])
        requested=layers if st.get('exitpending') else [x for x in layers if x.kind=='add'] if st.get('addexitpending') and st.get('add') else []
        if any(x.opened>=day for x in requested):
            raise StateInvariantError('Illegal whole requested exit includes a same-session layer; no partial sell_all invented')
    def open_exits(self,day):
        self._stage(day,'OPEN');self.s.accrue_day(ARM,day)
        held_order=[]
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']!='HELD':continue
            rid=st['round_id'];held_order.append(rid)
            self._check_exit_t1(st,day)
            if not self.s.before_held(self.states,sid,st,day):continue
            before=len(self.s.actions)
            self._callback('source_exit_only')(self.states,sid,st,day,self.last_close)
            self._record_new_actions(before,day)
        return held_order
    def _cp_identity(self,st,day):
        if self.cp_provider is not None:
            if self.evidence_domain=='REAL_FROZEN_SOURCE':raise StateInvariantError('synthetic CP provider cannot be used as real source')
            return self.cp_provider(st,day)
        sid=st['sid'];path=Path(self.s.manifest[sid]['refs']['CP1'])
        expected=self.s.manifest[sid]['output_sha256'][str(path)]
        if sid not in self.cp_cache:
            if bridge.sha(path)!=expected:raise StateInvariantError('CP source hash changed')
            self.cp_cache[sid]=self.s.pd.read_parquet(path)
            self.source_hashes[str(path)]=expected
        row=self.cp_cache[sid].loc[day]
        if not self.s.true(row['receipt']):raise StateInvariantError('not a fresh source CP row')
        if not self.s.np.isclose(float(row['candidate']),float(self.s.cp[sid].get(day,{})['candidate']),rtol=1e-12):
            raise StateInvariantError('CP row/source candidate mismatch')
        def clean(v):
            try:
                if self.s.pd.isna(v):return None
            except (TypeError,ValueError):pass
            return v.item() if hasattr(v,'item') else v
        fields={k:clean(row[k]) for k in ('receipt','candidate','anchor','frontier','scale','credit','reset_reason') if k in row}
        z=self.s.raw[sid].get(day,{})
        payload=dict(cp_file_sha256=expected,sid=sid,signal_close=str(day.date()),row=fields,source_coordinate=self.s.lineage(z),factor=str(z.get('adjustment_factor')))
        identity=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
        return dict(consumption_id=identity,identity_kind='ORIGINAL_CP_SOURCE_ROW_CONSUMPTION_NOT_NEW_INDICATOR',known_at=(day,'CLOSE'),source=payload)
    def _capture_cp(self,st,day):
        if st.get('addpending') is None:return
        cr=self.s.cp[st['sid']].get(day,{})
        if not self.s.true(cr.get('receipt')):raise StateInvariantError('addpending without fresh CLOSE CP')
        rid=st['round_id'];layers=self._active_layers(rid)
        if not layers:raise StateInvariantError('CP proof without current held layers')
        first=min(layers,key=lambda x:x.opened)
        z=self.s.raw[st['sid']].get(day,{})
        net=self.s.mark(st,D(str(z['raw_close']))*(1-self.s.SLIP),day)
        cp=self._cp_identity(st,day)
        self.pending_cp[rid]=dict(cp=cp,signal_day=day,close_net=net,first_fill_id=first.first_fill_id,
            first_fill_day=first.opened,round_id=rid,sid=st['sid'],m3_true=self.s.sector[st['sector']].get(day,-1)==1)
    def _proof(self,st,day):
        rid=st['round_id'];p=self.pending_cp.get(rid)
        if p is None:return None,'no_current_CLOSE_proof'
        if p['round_id']!=rid or p['sid']!=st['sid']:return None,'round_identity_mismatch'
        if p['signal_day']!=self.last_close:return None,'stale_CP_signal'
        if self._point(p['signal_day'],'CLOSE')<=self._point(p['first_fill_day'],'OPEN_FILLED'):return None,'CP_not_after_first_fill'
        if (rid,p['cp']['consumption_id']) in self.cp_attempts:return None,'CP_already_attempted'
        if not self._active_layers(rid) or self._live_orders(sid=st['sid']):return None,'no_clean_live_round'
        if not p['m3_true'] or p['close_net']<=0:return None,'CLOSE_profit_or_M3_false'
        z=self.s.raw[st['sid']].get(day,{})
        if not self.s.finite(z.get('raw_open')) or z['raw_open']<=0:return None,'OPEN_price_unknown'
        op=D(str(z['raw_open']));net=self.s.mark(st,op*(1-self.s.SLIP),day)
        floor=st.get('addpending')
        if net<=0:return None,'OPEN_round_not_profitable'
        if floor is None or op<=floor:return None,'OPEN_at_or_below_ADD_floor'
        return dict(p,open_net=net,known_open=op,effective_floor=floor,proof_snapshot=(day,'POST_SELL_PRE_BUY')),'eligible'
    def prepare_promotions(self,held_order,day,snapshot):
        prepared=[];verdicts={}
        for rid in held_order:
            st=self.s.archives[rid]
            if self.states.get(st['sid'],{}).get('state')!='HELD' or st.get('addpending') is None:continue
            proof,reason=self._proof(st,day);verdicts[rid]=(proof,reason)
            self.audit.append(dict(type='PROMOTION_PROOF',day=day,round_id=rid,reason=reason,proof=proof,nav_certified=snapshot.certified))
            if proof is not None and snapshot.certified and self.pools.get(rid)=='probe':
                prepared.append((rid,proof))
        return verdicts,prepared
    def commit_promotions(self,prepared,day,snapshot):
        before=(self.cash(),self.receivable(),[(x.layer_id,x.qty,x.cost,x.opened) for x in self.layers])
        if not snapshot.certified:
            self.audit.append(dict(type='PROMOTION_COMMIT_BLOCKED_UNKNOWN',day=day,round_ids=[rid for rid,_ in prepared]))
            return
        for rid,proof in prepared:
            st=self.s.archives[rid]
            if self.states.get(st['sid'],{}).get('state')!='HELD':
                raise StateInvariantError('prepared promotion lost live ownership')
            key=(rid,proof['cp']['consumption_id'])
            if key in self.promotion_seen:raise StateInvariantError('duplicate promotion proof')
            self.pools[rid]='confirmed';self.promotion_seen.add(key)
            self.audit.append(dict(type='PROMOTED',day=day,round_id=rid,first_fill_id=proof['first_fill_id'],CP_id=key[1]))
        assert before==(self.cash(),self.receivable(),[(x.layer_id,x.qty,x.cost,x.opened) for x in self.layers])
    def _entry_proposal(self,st,day):
        sid=st['sid'];z=self.s.raw[sid].get(day,{});prev=self.s.raw[sid].get(st['signal_day'],{})
        if not self.s.finite(z.get('raw_open')) or z['raw_open']<=0:self._unknown(st,'MISSING_NEXT_OPEN_UNKNOWN',day);return None
        if self.s.lineage(z)!=self.s.lineage(prev):self._unknown(st,'SOURCE_CHANGED_AT_ENTRY_UNKNOWN',day);return None
        if hasattr(self.s,'unadmitted_action_at') and self.s.unadmitted_action_at(sid,day):
            self._unknown(st,'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN',day);return None
        if self.s.pending_bridge(st,day,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])
        if not self.s.finite(z.get('adjustment_factor')) or not self.s.np.isclose(z['adjustment_factor'],prev['adjustment_factor'],rtol=1e-11):
            self._unknown(st,'FACTOR_AT_ENTRY_UNKNOWN',day);return None
        op=D(str(z['raw_open']));floor=D(str(st['i_floor']))/D(str(prev['adjustment_factor']))
        if op<=floor:
            self.s.record(st,'NEXT_OPEN_BELOW_PROTECTION_NOFILL',day);self.states.pop(sid);return None
        nd=self.caps[st['round_id']];px=op*(1+self.s.SLIP)
        try:q,bf,risk,fs,par=self.s.size(sid,day,px,floor,nd*D('.02'),nd*D('.0025'),st['prior20_capacity'])
        except (self.s.RuleUnavailable,KeyError,ValueError):
            self._unknown(st,'DATED_RULE_AT_ENTRY_UNKNOWN',day);return None
        qr,_,_=self.s.getmeta(sid,day)
        capped=qr.buy_floor(min(q,int(st['close_q'])))
        return dict(kind='INIT',st=st,day=day,q=capped,source_formula_q=q,close_q=st['close_q'],price=px,floor=floor,
            open=op,z=dict(z),schedule=fs,par=par,rule=qr,budget=nd*D('.02'),riskmax=nd*D('.0025'),proof=None)
    def _add_proposal(self,st,day,proof_reason):
        rid=st['round_id'];proof,reason=proof_reason
        cp=self.pending_cp.get(rid)
        if proof is None:
            st['addpending']=None;st['add_attempts']+=1
            if reason in ('OPEN_round_not_profitable','OPEN_at_or_below_ADD_floor'):st['add_profit_floor_rejects']+=1
            if cp is not None:self.cp_attempts.add((rid,cp['cp']['consumption_id']))
            self.audit.append(dict(type='ADD_REJECTED',day=day,round_id=rid,reason=reason));return None
        self.cp_attempts.add((rid,proof['cp']['consumption_id']))
        nd=self.caps[rid];z=self.s.raw[st['sid']].get(day,{})
        prepared=self._callback('source_prepare_add',INIT=nd*D('.02'),SLOT=nd*D('.04'),RISK=nd*D('.0025'))(
            self.states,st['sid'],st,day,self.last_close,z)
        if prepared is None:return None
        qr,fs,par=self.s.getmeta(st['sid'],day)
        return dict(kind='ADD',st=st,day=day,q=prepared['q'],source_formula_q=prepared['q'],close_q=None,
            price=prepared['price'],floor=prepared['floor'],open=prepared['open'],z=dict(z),
            schedule=fs,par=par,rule=qr,budget=prepared['budget'],riskmax=prepared['remaining_risk'],proof=proof)
    def reserve_proposal(self,p,book):
        st=p['st'];rid=st['round_id'];sid=st['sid'];q=p['q'];trials=[]
        pool='probe' if p['kind']=='INIT' else self.pools[rid]
        if self._live_orders(sid=sid):q=0;trials.append(dict(q=0,reasons=['stock_order_pending']))
        while q>0:
            fee=self.s.fee(q,p['price'],p['schedule'],'buy',p['par'])
            risk=max(ZERO,D(q)*(p['price']-p['floor']*(1-self.s.SLIP))+fee+self.s.fee(q,p['floor']*(1-self.s.SLIP),p['schedule'],'sell',p['par']))
            exposure=Exposure(sid,rid,st['sector'],pool,q,p['price'],p['floor'],fee,'live')
            reasons=book.reasons(exposure)
            if exposure.capital+fee>p['budget']:reasons.append('round_buy_budget')
            if risk>p['riskmax']:reasons.append('round_fee_inclusive_risk')
            trials.append(dict(q=q,fee=fee,fee_risk=risk,reasons=reasons))
            if not reasons:
                errors=book.reserve(exposure)
                if errors:raise StateInvariantError(str(errors))
                oid=rid+'|'+str(p['day'].date())+'|'+p['kind']
                if oid in self.orders:raise StateInvariantError('duplicate reservation')
                order=dict(p,order_id=oid,round_id=rid,sid=sid,q=q,fee=fee,risk=risk,pool=pool,exposure=exposure,status='live')
                self.orders[oid]=order
                self.audit.append(dict(type='RESERVED',day=p['day'],order_id=oid,round_id=rid,kind=p['kind'],
                    original_formula_q=p['source_formula_q'],initial_close_q=p['close_q'],before_shared_q=p['q'],shared_q=q,
                    minimum_buy_quantity=p['rule'].buy_minimum,trials=trials,reserved_cash=book.reserved_cash,
                    effective_nav=book.snapshot.nav-book.unbooked_buy_fees))
                return oid
            q=p['rule'].buy_floor(q-1)
        self.audit.append(dict(type='BUDGET_REJECTED',day=p['day'],round_id=rid,kind=p['kind'],trials=trials,
            original_formula_q=p['source_formula_q'],initial_close_q=p['close_q'],before_shared_q=p['q'],shared_q=0,
            minimum_buy_quantity=p['rule'].buy_minimum))
        if p['kind']=='INIT':
            self.s.record(st,'SHARED_BUDGET_KNOWN_NOFILL',p['day']);self.states.pop(sid)
        else:st['add_size_rejects']+=1
        return None
    def commit(self,order_id):
        o=self.orders[order_id]
        if o['status']=='filled':return o['fill_action_id']
        if o['status']!='live':raise StateInvariantError('cannot commit nonlive order')
        st=o['st'];before=len(self.s.actions);cash_before=self.cash()
        if o['kind']=='INIT':
            if st['state']!='BUY_PENDING' or self._active_layers(o['round_id']):raise StateInvariantError('INIT ownership changed')
            self._callback('source_commit_entry')(st,o['day'],o['q'],o['price'],o['fee'],o['risk'],o['floor'],o['open'],o['z'])
            kind='core'
        else:
            if st['state']!='HELD' or st['added'] or o['proof']['round_id']!=o['round_id']:raise StateInvariantError('ADD ownership changed')
            self._callback('source_commit_add')(st,o['day'],o['q'],o['fee'],o['price'],o['floor'],o['proof']['open_net'])
            kind='add'
        emitted=self._record_new_actions(before,o['day'])
        if len(emitted)!=1:raise StateInvariantError('one fill must emit exactly one action')
        uid=emitted[0]['execution_action_id']
        first=uid if kind=='core' else min(self._active_layers(o['round_id']),key=lambda x:x.opened).first_fill_id
        self.layers.append(Layer(uid,o['round_id'],o['sid'],kind,o['q'],o['day'],D(o['q'])*o['price']+o['fee'],first))
        self.pools[o['round_id']]=o['pool'];o['status']='filled';o['fill_action_id']=uid
        assert self.cash()==cash_before-D(o['q'])*o['price']-o['fee']
        self.audit.append(dict(type='CONDITIONAL_FILLED',day=o['day'],order_id=order_id,action_id=uid,cash=self.cash()))
        self.reconcile(o['day'],'OPEN')
        return uid
    def open_phase(self,day):
        day=self.s.pd.Timestamp(day)
        if self.last_open is not None and day<=self.last_open:raise StateInvariantError('OPEN replay forbidden; commit alone is idempotent')
        if self.last_close is None or day!=self.s.cal[self.s.cal>self.last_close][0]:raise StateInvariantError('not immediate next common OPEN')
        start_actions=len(self.s.actions);start_audit=len(self.audit)
        held_order=self.open_exits(day)
        # Initial quote validation occurs before allocation; it creates no order.
        initial=[]
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']=='BUY_PENDING':
                if st['signal_day']!=self.last_close:raise StateInvariantError('old birth receipt replay')
                p=self._entry_proposal(st,day)
                if p is not None:initial.append(p)
        snapshot=self.snapshot(day,'OPEN')
        verdicts,prepared_promotions=self.prepare_promotions(held_order,day,snapshot)
        adds=[]
        for rid in held_order:
            st=self.s.archives[rid]
            if self.states.get(st['sid'],{}).get('state')=='HELD' and st.get('addpending') is not None:
                p=self._add_proposal(st,day,verdicts.get(rid,(None,'no_current_proof')))
                if p is not None:adds.append(p)
        # A preparation UNKNOWN may invalidate NAV; re-evaluate without new fills.
        self.commit_promotions(prepared_promotions,day,self.snapshot(day,'OPEN'))
        book=ReserveBook(self.snapshot(day,'OPEN'))
        initial.sort(key=lambda p:(-p['st']['PVR_score'],p['st']['sid']))
        order_ids=[]
        for p in adds+initial:
            oid=self.reserve_proposal(p,book)
            if oid is not None:order_ids.append(oid)
        self.audit.append(dict(type='ALL_RESERVATIONS_COMPLETE',day=day,order_ids=order_ids,
            cash_before_fills=self.cash(),reserved_cash=book.reserved_cash,unbooked_buy_fees=book.unbooked_buy_fees))
        for oid in order_ids:self.commit(oid)
        self.last_open=day;self.completed_opens.append(str(day.date()))
        reconciliation=self.reconcile(day,'OPEN')
        return dict(day=day,actions=copy.deepcopy(self.s.actions[start_actions:]),
                    audit=copy.deepcopy(self.audit[start_audit:]),reconciliation=reconciliation)
    def _checkclose(self,r):
        nd=self.close_nd;sid=r['sid'];day=r['day']
        key=(self.evidence_domain,r['event_id'],sid,str(day),self.seq.get(sid,0)+1,str(nd),'INIT_2_RISK_025')
        if key in self.closecache:return self.closecache[key]
        if nd is None:return {'close_check':'SHARED_NAV_UNCERTIFIED'}
        self.s.load(sid);z=self.s.raw[sid].get(day,{})
        if not self.s.flags(z) or not self.s.finite(z.get('raw_close')) or z['raw_close']<=0 or not self.s.finite(z.get('adjustment_factor')) or z['adjustment_factor']<=0:
            result={'close_check':'INVALID_CLOSE_UNKNOWN'}
        else:
            floor=D(str(r['i_floor']))/D(str(z['adjustment_factor']));op=D(str(z['raw_close']));cap=self.s.capacity[sid].get(day,self.s.np.nan)
            if not self.s.finite(cap):result={'close_check':'PRIOR_VOLUME_UNKNOWN_AT_CLOSE'}
            elif op<=floor:result={'close_check':'CLOSE_AT_OR_BELOW_PROTECTION'}
            else:
                try:
                    q,bf,risk,_,_=self.s.size(sid,day,op*(1+self.s.SLIP),floor,nd*D('.02'),nd*D('.0025'),int(cap))
                    result=dict(close_check='PASS' if q>0 else 'MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE',close_q=q,close_fee=float(bf),close_plan_risk=float(risk),close_floor_raw=float(floor),prior20_capacity=int(cap))
                except (self.s.RuleUnavailable,KeyError,ValueError) as e:result=dict(close_check='DATED_RULE_UNKNOWN_AT_CLOSE',reason=str(e))
        self.closecache[key]=result;return result
    def _select_close(self,day):
        if day not in self.groups:return
        env=dict(self.s.queue.__globals__);env['checkclose']=self._checkclose
        queue=types.FunctionType(self.s.queue.__code__,env)
        for industry,g in self.groups[day].groupby('sector',sort=True):
            slots=0;rank=0
            for r in queue(g,self.states,ARM):
                sid=r['sid'];dec={k:r[k] for k in ['event_id','window','day','sid','name','industry','sector','event_type','PVR_score','I_qualified','PVR_known']}
                dec.update(arm=ARM,selected=False,queue_rank=self.s.np.nan,stock_state_before=self.states.get(sid,{}).get('state','FLAT'))
                if sid in self.states:dec.update(decision='BLOCKED_'+self.states[sid]['state'],blocking_round_id=self.states[sid]['round_id'])
                elif not self.s.true(r['I_qualified']):dec['decision']='I_INELIGIBLE'
                elif not self.s.true(r['PVR_known']) or not self.s.finite(r['PVR_score']):dec['decision']='PVR_UNKNOWN'
                else:
                    rank+=1;dec['queue_rank']=rank;check=self._checkclose(r);dec.update(check)
                    if check['close_check']!='PASS':dec['decision']='CLOSE_'+check['close_check']
                    elif slots>=2:dec['decision']='PASS_NOT_TOP2'
                    else:
                        slots+=1;self.seq[sid]=self.seq.get(sid,0)+1
                        rid=f"{r['window']}|{ARM}|{sid}|{self.seq[sid]}"
                        st=self.s.new_state(r,ARM,rid,check);self.states[sid]=st;self.caps[rid]=self.close_nd
                        dec.update(decision='SELECTED_PENDING',selected=True,selected_rank=slots,round_id=rid,round_Nd=self.close_nd)
                self.s.decisions.append(dec)
    def close_phase(self,day):
        day=self.s.pd.Timestamp(day)
        if self.last_close is not None and day<=self.last_close:raise StateInvariantError('CLOSE replay forbidden')
        self._stage(day,'CLOSE')
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']=='HELD':
                self.s.held_close(self.states,sid,st,day)
                if self.states.get(sid,{}).get('state')=='HELD':self._capture_cp(st,day)
        self.s.register(self.states,ARM,day)
        before=self.snapshot(day,'CLOSE');self.close_nd=before.nav
        if before.certified:self.daily_nav=before.nav
        self._select_close(day)
        cash_receivable=self.cash()+self.receivable()
        self.s.pay_day(ARM,day)
        assert self.cash()+self.receivable()==cash_receivable
        self.s.finalize()
        self.last_close=day
        audit=self.reconcile(day,'CLOSE')
        self.audit.append(dict(type='CLOSE_SNAPSHOT',day=day,certified=before.certified,Nd=before.nav,
            cash_before_pay=before.cash,cash_after_pay=self.cash(),receivable=self.receivable(),
            pending_initials=sum(x['state']=='BUY_PENDING' for x in self.states.values())))
        return audit
    def reconcile(self,day,phase):
        live_by_stock={}
        # Ephemeral aggregation: same positive active layers and same Decimal/cash paths.
        # No cached index survives this reconciliation call.
        active_qty_by_round_kind={}
        for layer in self.layers:
            if layer.qty>0:
                key=(layer.round_id,layer.kind)
                active_qty_by_round_kind[key]=active_qty_by_round_kind.get(key,0)+layer.qty
        for rid,st in self.s.archives.items():
            for kind in ('core','add'):
                q=active_qty_by_round_kind.get((rid,kind),0)
                if q!=int(st.get(kind,0)):raise StateInvariantError(('archive/layer quantity mismatch',rid,kind,q,st.get(kind,0)))
            qty=int(st.get('core',0))+int(st.get('add',0))
            if qty:
                if st['sid'] in live_by_stock:raise StateInvariantError('overlapping live rounds for stock')
                live_by_stock[st['sid']]=rid
        if self.cash()<0:raise StateInvariantError('negative actual cash')
        ids=[a['execution_action_id'] for a in self.s.actions]
        if len(ids)!=len(set(ids)):raise StateInvariantError('duplicate action identity')
        cash_from_actions=self.seed_cash
        for a in self.s.actions:
            amount=D(str(a['q']))*D(str(a['price']))
            cash_from_actions+=-amount-D(str(a['fee'])) if a['side'].startswith('buy') else amount-D(str(a['fee']))
        paid=sum((D(str(x.get('dividend_paid',0))) for x in self.s.archives.values()),ZERO)
        if abs(cash_from_actions+paid-self.cash())>D('0.0000001'):raise StateInvariantError('action cash ledger does not reconcile')
        snap=self.snapshot(day,phase)
        return dict(day=day,phase=phase,cash=self.cash(),gross_inventory=sum((x.capital for x in snap.holdings),ZERO),
                    receivable=self.receivable(),NAV=snap.nav,certified=snap.certified,unknown=snap.unknown,
                    live_rounds=len(live_by_stock),layers=sum(x.qty>0 for x in self.layers),
                    live_orders=len(self._live_orders()),unique_actions=len(ids),cash_and_qty_reconciled=True,
                    proxy='OBSERVED_OPEN_PLUS_MINUS_5BP_NOT_EXECUTABILITY_PROOF')
    def capture_runtime(self):
        own=('states','seq','layers','orders','action_ids','caps','pools','pending_cp','cp_attempts','promotion_seen',
             'closecache','audit','phase','day','last_close','last_open','close_nd','daily_nav','completed_opens')
        source=('rounds','actions','decisions','blocks','ranking_audit','bridges','registrations','claim_ledger','marks','archives','claims','snapshots','CURRENT_PHASE')
        return copy.deepcopy({'own':{k:getattr(self,k) for k in own},'source':{k:getattr(self.s,k) for k in source}})
    def restore_runtime(self,saved):
        saved=copy.deepcopy(saved)
        for k,v in saved['own'].items():setattr(self,k,v)
        for k,v in saved['source'].items():setattr(self.s,k,v)
