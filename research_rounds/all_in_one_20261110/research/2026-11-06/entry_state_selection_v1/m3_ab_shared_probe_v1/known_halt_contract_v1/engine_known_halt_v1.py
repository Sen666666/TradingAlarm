"""New conditional accounting contract, not a baseline-equivalent bugfix.
No synthetic bars. Stale inventory is informational, never certified or executable.
"""
from pathlib import Path
import sys,copy
from dataclasses import dataclass,asdict
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'indexed_execution_v1'))
import engine_indexed_v1 as base
from engine_indexed_v1 import D,ZERO,Exposure,Snapshot,ReserveBook,StateInvariantError,ARM,bridge
from halt_evidence_v1 import HaltEvidence
HALT='KNOWN_FULL_DAY_SUSPENSION'
@dataclass(frozen=True)
class HaltSnapshot(Snapshot):
    stale_marks:tuple=()
    indicative_nav:D|None=None
    risk_paused:bool=False
    @property
    def current_price_certified(self):return self.certified and not self.stale_marks
class ExecutionBridge(base.ExecutionBridge):
    def __init__(self,*args,halt_evidence=None,**kw):
        super().__init__(*args,**kw)
        self.halts=halt_evidence or HaltEvidence()
        if self.evidence_domain=='REAL_FROZEN_SOURCE' and self.halts.synthetic:raise StateInvariantError('Synthetic halt evidence cannot enter real replay')
        self.source_hashes.update(self.halts.hashes)
        self.last_valid_close={};self.confirmed_halt_sessions=set();self.risk_recovery_pending=False
    def _equity_conflict(self,sid,day):
        # A missing raw OPEN cannot certify even an admitted factor bridge.
        if (sid,day) in self.s.EVENT_AT:return 'HALT_EQUITY_COORDINATE_UNKNOWN'
        if hasattr(self.s,'unadmitted_action_at') and self.s.unadmitted_action_at(sid,day):return 'HALT_UNADMITTED_ACTION_UNKNOWN'
        # 2022 lacks the 2024 unadmitted-action adapter. Inspect existing sealed
        # local event registry, never assume a halt proves no corporate action.
        for e in self.s.local_actions(sid).get('events',[]):
            if self.s.pd.Timestamp(e['effective_date'])==day:return 'HALT_LOCAL_ACTION_COORDINATE_UNKNOWN'
        return None
    def _expire_add(self,st,day):
        rid=st['round_id'];p=self.pending_cp.pop(rid,None)
        if st.get('addpending') is not None:
            st['addpending']=None;st['add_attempts']+=1
            self.audit.append(dict(type='ADD_EXPIRED_KNOWN_HALT',day=day,round_id=rid))
        if p is not None:self.cp_attempts.add((rid,p['cp']['consumption_id']))
    def _halt(self,st,day,evidence):
        sid=st['sid'];z=self.s.raw[sid].get(day,{})
        if self.s.finite(z.get('raw_open')) and z['raw_open']>0:
            self._unknown(st,'HALT_EVIDENCE_OPEN_CONFLICT',day);return
        conflict=self._equity_conflict(sid,day)
        if conflict:self._unknown(st,conflict,day);return
        self._expire_add(st,day)
        st['state']=HALT;st['halt_session']=day;self.risk_recovery_pending=True
        self.confirmed_halt_sessions.add((sid,day))
        self.audit.append(dict(type=HALT,day=day,round_id=st['round_id'],evidence_id=evidence['evidence_id'],known_at=evidence['known_at'],core=st['core'],add=st['add'],exitpending=st.get('exitpending'),addexitpending=st.get('addexitpending')))
    def open_exits(self,day):
        self._stage(day,'OPEN');self.s.accrue_day(ARM,day)
        held=[]
        for sid in list(self.states):
            st=self.states[sid]
            if st['state'] not in ('HELD',HALT):continue
            ev=self.halts.get(sid,day)
            if ev is not None:self._halt(st,day,ev);continue
            resumed=st['state']==HALT
            if resumed:st['state']='HELD'
            rid=st['round_id'];held.append(rid)
            self._check_exit_t1(st,day)
            if not self.s.before_held(self.states,sid,st,day):continue
            n=len(self.s.actions)
            self._callback('source_exit_only')(self.states,sid,st,day,self.last_close)
            self._record_new_actions(n,day)
            if resumed and self.states.get(sid,{}).get('state')!='UNKNOWN':
                self.audit.append(dict(type='RESUMED_RAW_OPEN',day=day,round_id=rid,prior_valid_signal_day=self.last_valid_close.get(rid),raw_open=self.s.raw[sid].get(day,{}).get('raw_open'),conditional_execution_only=True))
        return held
    def _entry_proposal(self,st,day):
        ev=self.halts.get(st['sid'],day)
        if ev is None:return super()._entry_proposal(st,day)
        z=self.s.raw[st['sid']].get(day,{})
        if self.s.finite(z.get('raw_open')) and z['raw_open']>0:
            self._unknown(st,'HALT_EVIDENCE_OPEN_CONFLICT',day);return None
        if not self._zero_liability_initial_unknown(st['round_id'],st):
            self._unknown(st,'HALT_INITIAL_HAS_UNRESOLVED_LIABILITY',day);return None
        self.s.record(st,'KNOWN_HALT_NEXT_OPEN_TICKET_EXPIRED_NOFILL',day)
        self.audit.append(dict(type='INITIAL_EXPIRED_KNOWN_HALT',day=day,round_id=st['round_id'],evidence_id=ev['evidence_id']))
        st['state']='EXPIRED_KNOWN_HALT';self.states.pop(st['sid'])
        return None
    def _floor_day(self,rid,sid,day,phase):
        if phase=='CLOSE' and self.states.get(sid,{}).get('state')!=HALT:return day
        prior=self.s.cal[self.s.cal<day];normal=prior[-1] if len(prior) else None
        if phase=='OPEN' and (sid,normal) not in self.confirmed_halt_sessions:return normal
        last=self.last_valid_close.get(rid)
        if last is None:return None
        gaps=self.s.cal[(self.s.cal>last)&(self.s.cal<day if phase=='OPEN' else self.s.cal<=day)]
        if not all((sid,d) in self.confirmed_halt_sessions for d in gaps):return None
        return last
    def snapshot(self,day,phase):
        day=self.s.pd.Timestamp(day);holdings=[];unknown=[];stale=[]
        for rid,st in self.s.archives.items():
            sid=st['sid'];state=self.states.get(sid,{})
            if state.get('state')=='UNKNOWN' and state.get('round_id')==rid:
                if self._zero_liability_initial_unknown(rid,st):continue
                unknown.append(dict(sid=sid,round_id=rid,reason=state.get('unknown_reason'),core=st.get('core'),add=st.get('add'),receivable=st.get('receivable',0)));continue
            qty=int(st.get('core',0))+int(st.get('add',0))
            if not qty:continue
            halted=state.get('state')==HALT and state.get('round_id')==rid and state.get('halt_session')==day
            floor_day=self._floor_day(rid,sid,day,phase)
            mark_day=self.last_valid_close.get(rid) if halted else day
            z=self.s.raw[sid].get(mark_day,{})
            field='raw_close' if halted or phase=='CLOSE' else 'raw_open'
            if not self.s.finite(z.get(field)) or z[field]<=0 or self.s.lineage(z)!=st.get('origin') or not self.s.finite(z.get('adjustment_factor')) or not self.s.np.isclose(z['adjustment_factor'],st.get('factor'),rtol=1e-11):
                unknown.append(dict(sid=sid,round_id=rid,reason='MARK_SOURCE_OR_FACTOR_UNKNOWN',qty=qty));continue
            floor=self.s.facts[sid].get(floor_day,{}).get('i_floor')
            if not self.s.finite(floor) or floor<=0 or rid not in self.pools:
                unknown.append(dict(sid=sid,round_id=rid,reason='FLOOR_OR_POOL_UNKNOWN',qty=qty));continue
            if halted:stale.append(dict(sid=sid,round_id=rid,source_day=mark_day,mark=D(str(z[field])),qty=qty,reason=HALT,liquidatable=False,protective_signal_day=floor_day))
            for kind,fl in [('core',D(str(floor))/st['fac']),('add',st.get('addfloor'))]:
                q=int(st.get(kind,0))
                if not q:continue
                if fl is None or not D(str(fl)).is_finite() or D(str(fl))<=0:
                    unknown.append(dict(sid=sid,round_id=rid,reason='ADD_FLOOR_UNKNOWN',qty=q));continue
                holdings.append(Exposure(sid,rid,st['sector'],self.pools[rid],q,D(str(z[field])),D(str(fl)),ZERO,'held'))
        indicative=None if unknown else self.cash()+self.receivable()+sum((x.capital for x in holdings),ZERO)
        paused=bool(stale) or (phase=='OPEN' and self.risk_recovery_pending)
        nav=None if paused else indicative
        return HaltSnapshot(self.cash(),self.receivable(),nav,self.daily_nav,tuple(holdings),tuple(o['exposure'] for o in self._live_orders()),tuple(unknown),self.evidence_domain+':'+phase,tuple(stale),indicative,paused)
    def close_phase(self,day):
        day=self.s.pd.Timestamp(day)
        if self.last_close is not None and day<=self.last_close:raise StateInvariantError('CLOSE replay forbidden')
        self._stage(day,'CLOSE')
        for sid in list(self.states):
            st=self.states[sid]
            if st['state']==HALT:
                z=self.s.raw[sid].get(day,{})
                if st.get('halt_session')!=day or (self.s.finite(z.get('raw_close')) and z['raw_close']>0):self._unknown(st,'HALT_EVIDENCE_CLOSE_CONFLICT',day)
                continue
            if st['state']=='HELD':
                self.s.held_close(self.states,sid,st,day)
                if self.states.get(sid,{}).get('state')=='HELD':
                    self.last_valid_close[st['round_id']]=day;self._capture_cp(st,day)
        # Registration uses exactly the native ownership clock/amounts. It is a
        # temporary read-only state view, not a raw-bar or strategy-state mutation.
        view={sid:dict(st,state='HELD') if st.get('state')==HALT else st for sid,st in self.states.items()}
        self.s.register(view,ARM,day)
        before=self.snapshot(day,'CLOSE');self.close_nd=before.nav
        if before.certified:
            self.daily_nav=before.nav
            if self.risk_recovery_pending:
                self.risk_recovery_pending=False
                self.audit.append(dict(type='RECOVERY_COMPLETE_VALID_CLOSE',day=day,earliest_new_risk='NEXT_COMMON_OPEN'))
        self._select_close(day)
        cash_receivable=self.cash()+self.receivable();self.s.pay_day(ARM,day)
        assert self.cash()+self.receivable()==cash_receivable
        self.s.finalize();self.last_close=day
        audit=self.reconcile(day,'CLOSE')
        self.audit.append(dict(type='CLOSE_SNAPSHOT',day=day,certified=before.certified,Nd=before.nav,valuation='UNAUTHENTICATED_STALE_INFORMATION_ONLY' if before.stale_marks else 'CURRENT_RAW_MARK',stale_marks=before.stale_marks,cash_before_pay=before.cash,cash_after_pay=self.cash(),receivable=self.receivable(),pending_initials=sum(x['state']=='BUY_PENDING' for x in self.states.values())))
        return audit
    def reconcile(self,day,phase):
        out=super().reconcile(day,phase);snap=self.snapshot(day,phase)
        out.update(new_risk_allowed=snap.certified,indicative_NAV_NOT_CERTIFIED=snap.indicative_nav if snap.risk_paused else None,risk_recovery_pending=self.risk_recovery_pending,accounting_NAV_certified=snap.certified,current_price_NAV_certified=snap.current_price_certified,NAV_stale=bool(snap.stale_marks),stale_marks=snap.stale_marks,valuation_convention='LAST_VALID_CLOSE_ONLY_FOR_EVIDENCE_SUPPORTED_FULL_DAY_HALT')
        if snap.stale_marks:
            out['indicative_inventory_NOT_CERTIFIED']=out['gross_inventory'];out['gross_inventory']=None
        out['NAV_gap_reason']='KNOWN_HALT_STALE_MARK' if snap.stale_marks else 'RESUME_OPEN_RECOVERY_LOCK' if snap.risk_paused else 'ASSET_OR_SOURCE_UNKNOWN' if snap.unknown else None
        return out
    def capture_runtime(self):
        r=super().capture_runtime();r['halt']=copy.deepcopy(dict(last_valid_close=self.last_valid_close,confirmed_halt_sessions=self.confirmed_halt_sessions,risk_recovery_pending=self.risk_recovery_pending));return r
    def restore_runtime(self,r):
        super().restore_runtime(r)
        for k,v in copy.deepcopy(r['halt']).items():setattr(self,k,v)
