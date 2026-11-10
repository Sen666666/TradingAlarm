"""New 2022 shared-account adapter. Same-day integer capitalization and explicit
nonrefundable par20 research expense. No executable entrypoint. Original files untouched.
"""
from pathlib import Path
from decimal import Decimal as D
import ast,copy,hashlib,inspect,json,sys,textwrap,types
HERE=Path(__file__).resolve().parent;B=HERE.parent
sys.path.insert(0,str(B/'annual_2022_marked_nav_v1'))
import annual_bridge_v1 as A
sys.path.insert(0,str(B/'composite_equity_interface_v1'))
import compound_equity_v1 as M
bridge=A.bridge;sha=A.sha;digest=A.digest;merge_hashes=A.merge_hashes
ARM=A.ARM;HALT=A.HALT;AnnualHalts=A.AnnualHalts;blocking_unknowns=A.blocking_unknowns
ZERO=D(0)
COMPOUND_ID='000987.SZ|LOCAL_DISTRIBUTION_010'
POLICY_ID='EX_OPEN_NONREFUNDABLE_PAR20_RESEARCH_HAIRCUT'
def read(p):return json.loads(Path(p).read_text())
def normalized(x):return json.loads(json.dumps(x,sort_keys=True,default=str))

def structural_digest(value):
    """Stream the exact typed reference JSON, preserving all fields and dictionary order."""
    import dataclasses,datetime,math
    import pandas as pd
    import numpy as np
    def encoded(x):
        return json.dumps(x,ensure_ascii=False,separators=(",",":"))
    def sequence(items,kind):
        yield '["'+kind+'",['
        first=True
        for item in items:
            if not first:yield ','
            first=False
            yield from tokens(item)
        yield ']]'
    def tokens(x):
        if isinstance(x,pd.DataFrame):
            yield '["DataFrame",';yield encoded(list(map(str,x.dtypes)));yield ','
            yield from tokens(x.to_dict(orient="split"));yield ']';return
        if isinstance(x,pd.Series):
            yield '["Series",';yield encoded(str(x.dtype));yield ','
            yield from tokens(x.to_dict());yield ']';return
        if isinstance(x,pd.Index):
            yield '["Index",';yield encoded(str(x.dtype));yield ','
            yield from tokens(x.tolist());yield ']';return
        if isinstance(x,dict):
            yield '["dict",[';first=True
            for k,v in x.items():
                if not first:yield ','
                first=False;yield '[';yield from tokens(k);yield ',';yield from tokens(v);yield ']'
            yield ']]';return
        if isinstance(x,list):yield from sequence(x,"list");return
        if isinstance(x,tuple):yield from sequence(x,"tuple");return
        if isinstance(x,(set,frozenset)):
            parts=["".join(tokens(v)) for v in x]
            parts.sort(key=lambda text:json.dumps(json.loads(text),sort_keys=True))
            yield '["set",[';yield ','.join(parts);yield ']]';return
        if dataclasses.is_dataclass(x):
            yield '[';yield encoded(type(x).__module__+"."+type(x).__name__);yield ','
            yield from tokens(dataclasses.asdict(x));yield ']';return
        if x is pd.NA:yield '["pd.NA"]';return
        if isinstance(x,D):yield encoded(["Decimal",str(x)]);return
        if isinstance(x,(datetime.datetime,datetime.date)):yield encoded([type(x).__name__,x.isoformat()]);return
        if isinstance(x,np.generic):
            yield '[';yield encoded(str(x.dtype));yield ',';yield from tokens(x.item());yield ']';return
        if isinstance(x,np.ndarray):
            yield '["ndarray",';yield encoded(str(x.dtype));yield ',';yield from tokens(x.tolist());yield ']';return
        if isinstance(x,float) and not math.isfinite(x):yield encoded(["float",str(x)]);return
        if isinstance(x,(str,int,float,bool)) or x is None:yield encoded(x);return
        if isinstance(x,Path):yield encoded(["Path",str(x)]);return
        raise TypeError("Unsupported structural value "+str(type(x)))
    result=hashlib.sha256()
    for token in tokens(value):result.update(token.encode())
    return result.hexdigest()

def verify_sealed_members(seal_path,expected_sha):
    seal_path=Path(seal_path)
    if sha(seal_path)!=expected_sha:raise ValueError("Reviewed evidence seal drift: "+str(seal_path))
    sealed=read(seal_path);members=sealed["file_sha256"];root=seal_path.parent.resolve();out={}
    if not isinstance(members,dict) or not members:raise ValueError("Empty evidence members")
    for relative,h in members.items():
        p=(root/relative).resolve()
        if Path(relative).is_absolute() or not p.is_relative_to(root):raise ValueError("Unsafe evidence member path")
        if sha(p)!=h:raise ValueError("Reviewed evidence member drift: "+str(p))
        out[str(p)]=h
    return out

def verify_fixed_facts():
    bundle=read(HERE/'FACTS_DERIVED_CANDIDATES.json');policy=read(HERE/'RESEARCH_TAX_POLICY.json')
    release=read(HERE/'FACT_REVIEW_RELEASE.json')
    if release['status']!='PASS_FACTS_ONLY':raise ValueError('Independent facts release absent')
    sealed_members={}
    for p,h in release['reviewed_evidence_seals'].items():
        sealed_members=merge_hashes(sealed_members,verify_sealed_members(p,h))
    if len(release['reviewed_evidence_seals'])!=3 or len(sealed_members)!=82:
        raise ValueError('Expected exactly three reviewed packages and 82 members')
    if policy!={
        'policy_id':POLICY_ID,'recognition_phase':'EX_OPEN','rate':'0.20',
        'basis':'NEW_SHARES_TIMES_OFFICIALLY_EVIDENCED_PAR','nonrefundable':True,'actual_tax':False,
        'actual_tax_payment_time_claim':False,'cash_dividend_policy':'ORIGINAL_NET80_NO_SECOND_CASH_TAX',
        'debit':'OWNER_ROUND_CASH_ONCE_GLOBAL_CASH_AGGREGATES',
        'cost':'SEPARATE_RESEARCH_EXPENSE_NOT_ACTUAL_FEES_OR_BUY_COST','zero_mode_permitted':False,
        'excess_cash_policy':'FAIL_CLOSED_BEFORE_MUTATION_NO_RECEIVABLE_FUNDING'}:
        raise ValueError('Research stock-tax policy differs from exact contract')
    if bundle['new_pure_cash']!=read(B/'future_cash4_2022_evidence_v1/CASH4_CANDIDATES.json'):
        raise ValueError('Four cash facts drift')
    if len(bundle['new_pure_cash'])!=4 or len(bundle['new_compound'])!=1 or bundle['old_event_count']!=437 or bundle['maximum_distinct_economic_events']!=442:
        raise ValueError('Event domain changed')
    c=bundle['new_compound'][0]
    f=next(x for x in read(B/'compound_equity_2022_evidence_v1/SELECTED_5_OFFICIAL_FACTS.json') if x['sid']=='000987.SZ')
    par=read(c['par_value_fact_path'])
    required={'economic_event_id':f['economic_event_id'],'record_date':f['official_record_date'],
      'ex_date':f['official_ex_date'],'pay_date':f['official_pay_date'],
      'credit_date':f['share_credit_date_explicit'],'saleable_date':f['official_listing_date'],
      'd_cash':f['official_cash_per_old_share'],'d_source':f['cash_per_old_share_local'],
      'split_ratio':f['split_ratio_local'],'transfer_per_old_share':f['official_transfer_per_old_share'],
      'bonus_per_old_share':f['official_bonus_per_old_share'],'known_at_upper_bound':f['official_known_upper_bound'],
      'par_value':par['par_value'],'par_value_known_at':par['known_at_upper_bound']}
    if any(c[k]!=v for k,v in required.items()) or c['economic_event_id']!=COMPOUND_ID or c['sid']!='000987.SZ' or c['clock']['publication_date']!=f['official_announcement_date']:raise ValueError('Compound fact derivation drift')
    if D(c['par_value'])!=1 or c['par_value_known_at']>=c['ex_date']:raise ValueError('Par evidence or clock mismatch')
    hashes={str(HERE/n):sha(HERE/n) for n in ('FACTS_DERIVED_CANDIDATES.json','RESEARCH_TAX_POLICY.json','FACT_REVIEW_RELEASE.json')}
    for p in (B/'future_cash4_2022_evidence_v1/CASH4_CANDIDATES.json',B/'compound_equity_2022_evidence_v1/SELECTED_5_OFFICIAL_FACTS.json',Path(c['par_value_fact_path'])):
        hashes[str(p)]=sha(p)
    hashes=merge_hashes(hashes,sealed_members,release['reviewed_evidence_seals'])
    for obj in [*bundle['new_pure_cash'],c]:
        if any(k in obj for k in ('factor_old','factor_new','previous_close','previous_day','raw_open','raw_close')):
            raise ValueError('Future market coordinate in public fact')
        hashes.update(A.C.verify_artifacts(obj['clock']))
    for a in par['artifacts']:
        if sha(a['path'])!=a['sha256']:raise ValueError('Par evidence artifact drift')
        hashes[a['path']]=a['sha256']
    return bundle,policy,hashes

class ExtraTape:
    def __init__(self,b,bundle):
        self.b=b;self.s=b.s;self.cash=A.C.CandidateTape(b.s,bundle['new_pure_cash'])
        self.compound=copy.deepcopy(bundle['new_compound'][0]);self.audit=[]
        ids={e['economic_event_id'] for e in b.union_tape.old_events}|{x['economic_event_id'] for x in b.union_tape.candidate.candidates}
        newids=[c['economic_event_id'] for c in bundle['new_pure_cash']]+[self.compound['economic_event_id']]
        if len(ids)!=437 or len(set(newids))!=5 or ids&set(newids):raise ValueError('Not old437 plus five distinct events')
        self.protected_437_ids=tuple(sorted(ids))
    def compound_announcement(self,day):
        c=self.compound;ok,bound,reason=A.C.known_for_session(c['clock'],day)
        if not ok:return None
        s=self.s
        return dict(sid=c['sid'],economic_event_id=c['economic_event_id'],event_type='CASH_PLUS_CAPITALIZATION',
          evidence_version=digest(c),record_date=s.pd.Timestamp(c['record_date']),
          coordinate_snapshot_day=s.pd.Timestamp(c['record_date']),ex_date=s.pd.Timestamp(c['ex_date']),
          pay_date=s.pd.Timestamp(c['pay_date']),d_source=D(c['d_source']),d_cash=D(c['d_cash']),
          source_split=D(c['split_ratio']),transfer_per_old=D(c['transfer_per_old_share']),par_value=D(c['par_value']),
          entitlement_verified=True,coordinate_verified=False,origin='EXPLICIT_COMPOUND_PAR20_V1',
          entitlement_scope='OWN_REGISTER_Q_NET80_PLUS_NONREFUNDABLE_PAR20_RESEARCH_HAIRCUT_NOT_ACTUAL_TAX',
          public_known_upper_bound=bound.isoformat(),public_clock_basis=reason,
          evidence_domain='CURRENT_HISTORICAL_FACTS_NOT_PIT')
    def project(self,day,phase):
        # Parent has just projected its exact old 436+1 views. Preserve these bytes.
        s=self.s;names=('EVENTS','EVENT_BY_ID','EVENT_AT','BY_RECORD','BY_EX','BY_PAY','ALLOWED_EVENT_IDS')
        base={k:copy.deepcopy(getattr(s,k)) for k in names};base_digest=structural_digest(base)
        for c in self.cash.candidates:
            if day>=s.pd.Timestamp(c['ex_date']) and self.cash.announcement(c,day) is not None:s.load(c['sid'])
        visible=self.cash.project(day,phase)
        for e in visible:
            c=next(x for x in self.cash.candidates if x['economic_event_id']==e['economic_event_id'])
            e['d_ref']=c.get('d_ref_explicit_notice')
        extra_maps={k:copy.deepcopy(getattr(s,k)) for k in ('EVENT_AT','BY_RECORD','BY_EX','BY_PAY')}
        e=self.compound_announcement(day)
        if e is not None:
            visible.append(e);extra_maps['BY_RECORD'].setdefault(e['record_date'],[]).append(e)
            if day>=e['ex_date']:
                s.load(e['sid']);prev=s.cal[s.cal<e['ex_date']][-1]
                z=s.raw[e['sid']].get(e['ex_date'],{});p=s.raw[e['sid']].get(prev,{})
                def dec(v):
                    try:return D(str(v))
                    except Exception:return D('NaN')
                e.update(previous_day=prev,previous_close=dec(p.get('raw_close')),factor_old=dec(p.get('adjustment_factor')),
                         factor_new=dec(z.get('adjustment_factor')),coordinate_observed_at=(e['ex_date'],'OPEN'),
                         coordinate_scope='TIME_LOCAL_COMPOUND_FACTOR_TRANSLATION_ONLY')
                e['coordinate_verified']=bool(prev==e['record_date'] and self.b._coordinate_matches(e,z,p))
                extra_maps['EVENT_AT'][(e['sid'],e['ex_date'])]=e
                extra_maps['BY_EX'].setdefault(e['ex_date'],[]).append(e)
                extra_maps['BY_PAY'].setdefault(e['pay_date'],[]).append(e)
                self.audit.append(dict(type='TIME_LOCAL_COMPOUND_COORDINATE_CHECK',at=(day,phase),eid=e['economic_event_id'],valid=e['coordinate_verified']))
        for k,v in base.items():setattr(s,k,v)
        s.EVENTS=base['EVENTS']+visible
        s.EVENT_BY_ID=dict(base['EVENT_BY_ID'],**{e['economic_event_id']:e for e in visible})
        s.EVENT_AT=dict(base['EVENT_AT']);s.EVENT_AT.update(extra_maps['EVENT_AT'])
        for name in ('BY_RECORD','BY_EX','BY_PAY'):
            merged={d:list(v) for d,v in base[name].items()}
            for d,v in extra_maps[name].items():merged.setdefault(d,[]).extend(v)
            setattr(s,name,merged)
        s.ALLOWED_EVENT_IDS=set(base['ALLOWED_EVENT_IDS'])|{x['economic_event_id'] for x in visible}
        assert structural_digest(base)==base_digest and digest(s.EVENTS[:len(base['EVENTS'])])==digest(base['EVENTS'])
        assert len({x['economic_event_id'] for x in s.EVENTS})==len(s.EVENTS)<=442
        return visible

def _derive_reconcile():
    # Exactly original base cash and quantity reconciliation, one explicit research debit.
    src=textwrap.dedent(inspect.getsource(A.native.base.ExecutionBridge.reconcile))
    old="cash_from_actions+paid-self.cash()"
    assert src.count(old)==1
    src=src.replace(old,"cash_from_actions+paid-self.research_tax_total()-self.cash()")
    env=dict(A.native.base.__dict__);exec(compile(src,'new_explicit_research_cash_reconcile','exec'),env)
    basefn=env['reconcile']
    src=textwrap.dedent(inspect.getsource(A.native.ExecutionBridge.reconcile))
    old="super().reconcile(day,phase)";assert src.count(old)==1
    src=src.replace(old,"_tax_base_reconcile(self,day,phase)")
    env=dict(A.native.__dict__,_tax_base_reconcile=basefn);exec(compile(src,'new_halt_reconcile_with_research_debit','exec'),env)
    return env['reconcile']
_TAX_RECONCILE=_derive_reconcile()

class ExecutionBridge(A.ExecutionBridge):
    def __init__(self,s,*args,**kw):
        bundle,self.policy,new_hashes=verify_fixed_facts()
        super().__init__(s,*args,**kw)
        self.extra_tape=ExtraTape(self,bundle);self.source_hashes.update(new_hashes)
        self.source_hashes.update(self.extra_tape.cash.hashes)
        self.share_registrations={};self.share_ledger=[];self.research_tax_ledger=[];self.compound_applied=set()
        self._native_coordinate=s.coordinate_matches;self._native_before_held=s.before_held
        self._native_accrue_day=s.accrue_day
        s.coordinate_matches=self._coordinate_matches;s.before_held=self._before_held
        self._exit_code=self._derive_exit_code()
    def _stage(self,day,phase):
        super()._stage(day,phase)
        if hasattr(self,'extra_tape'):self.extra_tape.project(self.day,phase)
    def research_tax_total(self):
        return sum((D(str(x.get('research_stock_tax_total',0))) for x in self.s.archives.values()),ZERO)
    def _coordinate_matches(self,e,z,prev):
        if e.get('economic_event_id')!=COMPOUND_ID:return self._native_coordinate(e,z,prev)
        s=self.s
        if not all(s.finite(v) for v in (z.get('adjustment_factor'),prev.get('adjustment_factor'),prev.get('raw_close'))):return False
        fn=D(str(z['adjustment_factor']));fo=D(str(prev['adjustment_factor']));pc=D(str(prev['raw_close']))
        return bool(fn>0 and fo>0 and pc>e['d_source'] and abs(fn/e['factor_new']-1)<=D('1e-11')
                    and abs(fo/e['factor_old']-1)<=D('1e-11')
                    and abs(fo*e['source_split']*pc/(pc-e['d_source'])/fn-1)<=D('1e-11'))
    def _before_held(self,states,sid,st,day):
        e=self.s.EVENT_AT.get((sid,day))
        if e and e.get('economic_event_id')==COMPOUND_ID:
            if (COMPOUND_ID,st['round_id']) in self.compound_applied:return True
            self._unknown(st,'COMPOUND_NOT_ATOMICALLY_PREPARED',day);return False
        return self._native_before_held(states,sid,st,day)
    def _mechanical_event(self):
        c=self.extra_tape.compound
        return M.Event(c['economic_event_id'],digest(c),c['sid'],c['known_at_upper_bound'],c['record_date'],
          c['ex_date'],c['pay_date'],c['credit_date'],c['saleable_date'],c['d_cash'],c['d_source'],
          c['transfer_per_old_share'],c['split_ratio'],c['bonus_per_old_share'],domain='HISTORICAL_CONDITIONAL')
    def _register_compound_layers(self,day):
        c=self.extra_tape.compound
        if str(day.date())!=c['record_date'] or self.extra_tape.compound_announcement(day) is None:return
        snap=self.s.snapshots.get(('2022',ARM,c['sid'],COMPOUND_ID))
        if not snap or not snap.get('record_q'):return
        rid=snap['owner_round_id'];st=self.s.archives[rid]
        reg=M.register_layers(self._mechanical_event(),st,self.layers,day)
        if reg['record_q']!=snap['record_q'] or reg['core_record_q']!=snap['core_record_q']:raise ValueError('Original cash/stock registration mismatch')
        key=(COMPOUND_ID,rid)
        if key in self.share_registrations:raise ValueError('Duplicate compound registration')
        self.share_registrations[key]=reg
    def _prepare_compound(self,st,day):
        e=self._mechanical_event();reg=self.share_registrations.get((COMPOUND_ID,st['round_id']))
        if reg is None:raise M.Unsupported('COMPOUND_REGISTER_LAYER_UNKNOWN')
        prior=self.s.cal[self.s.cal<day][-1];z=self.s.raw[st['sid']].get(day,{});p=self.s.raw[st['sid']].get(prior,{})
        c=self.extra_tape.compound
        tax=M.TaxBinding(POLICY_ID,sha(HERE/'RESEARCH_TAX_POLICY.json'),'EXPLICIT_RESERVE',
          str(D(c['par_value'])*D(self.policy['rate'])),'REAL_NONREFUNDABLE_HAIRCUT_V1',
          'OWNER_ROUND_CASH_ONCE','WALLET_CASH_IN_NAV','SOURCE_CASH_MARK_PROFIT_ONLY_ORIGINAL_NOMINAL_RISK_UNCHANGED')
        obs=dict(day=day,previous_day=prior,raw_open=z.get('raw_open'),previous_raw_close=p.get('raw_close'),
          previous_factor=p.get('adjustment_factor'),factor=z.get('adjustment_factor'),
          previous_origin=self.s.lineage(p),origin=self.s.lineage(z))
        plan=M.prepare_ex(e,reg,st,self.layers,obs,tax,prior,len(self.s.actions),self.compound_applied)
        claim=self.s.claims.get(('2022',ARM,st['sid'],COMPOUND_ID))
        if claim is None or claim['owner_round_id']!=st['round_id'] or claim['recognized'] or claim['settled']:raise M.Unsupported('COMPOUND_CASH_CLAIM_STATE_UNKNOWN')
        for k in ('record_q','core_record_q','amount','core_amount'):
            if claim[k]!=plan['cash_claim'][k]:raise M.Unsupported('COMPOUND_CASH_SHARE_CLAIM_MISMATCH')
        expense=plan['stock_reserve_total']
        # Actual already settled wallet cash only. No same-day payment/receivable funding.
        if self.cash()<expense:raise M.Unsupported('INSUFFICIENT_SETTLED_CASH_FOR_RESEARCH_HAIRCUT')
        return plan
    def _commit_compound(self,plan,st,day):
        # Real commit is owned by this separately fact-gated adapter, not the synthetic API.
        check=dict(plan);h=check.pop('plan_hash')
        if M.digest(check)!=h or M._state_layer_fingerprint(st,self.layers)!=plan['state_layer_fingerprint']:raise ValueError('Stale/tampered compound plan')
        key=tuple(plan['key'])
        if key in self.compound_applied:raise ValueError('Duplicate compound commit')
        # A 64-hex field is not authorization: rebuild from the current independently
        # admitted facts, exact policy, source observations and actual owner state.
        expected=self._prepare_compound(st,day)
        if plan['plan_hash']!=expected['plan_hash']:raise ValueError('Plan differs from exact real event and tax contract')
        if plan['event']['event_id']!=COMPOUND_ID or plan['tax_binding']['policy_id']!=POLICY_ID or plan['tax_binding']['freeze_hash']!=sha(HERE/'RESEARCH_TAX_POLICY.json'):
            raise ValueError('Unreleased real tax/event binding')
        byid={x.layer_id:x for x in self.layers};unchanged=digest({k:v for k,v in st.items() if k not in ('core','add','fac','factor','addfloor','addpending','cash')})
        expense=plan['stock_reserve_total']
        for u in plan['updates']:
            layer=byid[u['layer_id']];layer.qty=u['qty_after'];st[u['kind']]+=u['new_q']
            self.share_ledger.append(dict(event_id=COMPOUND_ID,evidence_version=plan['event']['evidence_version'],
              round_id=u['round_id'],layer_id=u['layer_id'],sid=u['sid'],kind=u['kind'],day=day,
              action_index=plan['action_index'],old_q=u['record_q'],new_q=u['new_q'],qty_after=u['qty_after'],
              historical_layer_cost=u['cost'],old_attributed_cost=u['old_attributed_cost'],
              new_attributed_cost=u['new_attributed_cost'],first_fill_id=u['first_fill_id'],original_opened=u['opened'],
              saleable_from=day,trade_cash_delta=ZERO,trade_fee_delta=ZERO,research_stock_tax=u['reserve_delta']))
            self.research_tax_ledger.append(dict(event_id=COMPOUND_ID,round_id=u['round_id'],layer_id=u['layer_id'],
              sid=u['sid'],kind=u['kind'],day=day,phase='OPEN',action_index=plan['action_index'],
              new_shares=u['new_q'],par_value=self.extra_tape.compound['par_value'],rate=self.policy['rate'],
              amount=u['reserve_delta'],owner_round_cash_delta=-u['reserve_delta'],actual_tax=False,
              actual_fee=False,nonrefundable=True,policy_id=POLICY_ID))
        st['fac']=plan['new_factor'];st['factor']=float(plan['new_factor']);st.update(plan['protections'])
        st['cash']-=expense
        assert unchanged==digest({k:v for k,v in st.items() if k not in ('core','add','fac','factor','addfloor','addpending','cash')})
        st['research_stock_tax_total']=st.get('research_stock_tax_total',ZERO)+expense
        st['research_compound_applied']=True
        self.compound_applied.add(key)
        self.s.bridges.append(dict(arm=ARM,round_id=st['round_id'],day=day,economic_event_id=COMPOUND_ID,
            kind='HELD_COMPOUND_COORDINATE_AND_PAR20_RESEARCH_HAIRCUT',record_q=plan['registration']['record_q'],
            core_record_q=plan['registration']['core_record_q'],new_shares=sum(x['new_q'] for x in plan['updates']),
            old_factor=plan['registration'].get('factor_old'),new_factor=plan['new_factor'],protections=plan['protections'],
            research_stock_tax=expense,exitpending=st.get('exitpending'),addexitpending=st.get('addexitpending')))
    def _compound_open_preamble(self,day):
        e=self.s.EVENT_AT.get(('000987.SZ',day));blocked=set()
        if e and e.get('economic_event_id')==COMPOUND_ID:
            st=self.states.get('000987.SZ');snap=self.s.snapshots.get(('2022',ARM,'000987.SZ',COMPOUND_ID))
            if snap and snap.get('record_q'):
                if st is None or st.get('state')!='HELD' or st.get('round_id')!=snap['owner_round_id']:
                    owner=self.s.archives[snap['owner_round_id']]
                    self._unknown(owner,'COMPOUND_OWNER_STATE_UNSUPPORTED',day);blocked.add(COMPOUND_ID)
                else:
                    try:plan=self._prepare_compound(st,day)
                    except M.Unsupported as error:
                        self._unknown(st,str(error),day);blocked.add(COMPOUND_ID)
                    else:
                        saved=self.capture_runtime()
                        try:
                            self._commit_compound(plan,st,day)
                            self._native_accrue_day(ARM,day)
                            return
                        except BaseException:
                            self.restore_runtime(saved);raise
        # Known unsupported compound must not leave a half cash/share entitlement.
        original=self.s.BY_EX
        if blocked:self.s.BY_EX={d:[x for x in rows if x['economic_event_id'] not in blocked] for d,rows in original.items()}
        try:self._native_accrue_day(ARM,day)
        finally:self.s.BY_EX=original
    def open_exits(self,day):
        self._stage(day,'OPEN');self._compound_open_preamble(day)
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
    def _derive_exit_code(self):
        text=self.split['provenance']['derived_source']['source_exit_only'];tree=ast.parse(text);fn=tree.body[0]
        tried=next(n for n in fn.body if isinstance(n,ast.Try));assign=tried.body[0]
        assert isinstance(assign,ast.Assign) and isinstance(assign.targets[0],ast.Tuple)
        assert assign.targets[0].elts[0].id=='_';assign.targets[0].elts[0].id='qr'
        for n in fn.body:
            if not isinstance(n,ast.If):continue
            test=ast.unparse(n.test)
            if test=="st['exitpending']":
                guard="if st.get('research_compound_applied') and qr.sell_floor(st['core']+st['add'],st['core']+st['add'])!=st['core']+st['add']: return freeze_unknown(states,sid,st,'ODD_FULL_EXIT_PATH_UNKNOWN',d)"
            elif test=="st['addexitpending'] and st['add']":
                guard="if st.get('research_compound_applied') and qr.sell_floor(st['add'],st['core']+st['add'])!=st['add']: return freeze_unknown(states,sid,st,'ODD_ADD_EXIT_PATH_UNKNOWN',d)"
            else:continue
            n.body=ast.parse(guard).body+n.body
        ast.fix_missing_locations(tree);env={}
        exec(compile(tree,'original_exit_with_narrow_issued_odd_guards','exec'),env)
        self.issued_exit_source=ast.unparse(fn)
        return env['source_exit_only'].__code__
    def _callback(self,name,**overrides):
        if name=='source_exit_only' and hasattr(self,'_exit_code'):
            return types.FunctionType(self._exit_code,dict(self.s.__dict__,**overrides))
        return super()._callback(name,**overrides)
    def close_phase(self,day):
        result=super().close_phase(day);self._register_compound_layers(self.s.pd.Timestamp(day));return result
    def reconcile(self,day,phase):
        out=_TAX_RECONCILE(self,day,phase)
        expected=sum((D(x['amount']) for x in self.research_tax_ledger),ZERO)
        if expected!=self.research_tax_total():raise ValueError('Research tax ledger/archive mismatch')
        if expected:out.update(research_stock_tax_total=expected,research_tax_policy=POLICY_ID)
        qty=M.replay_quantity(self.s.actions,self.share_ledger)
        for rid,st in self.s.archives.items():
            if rid in qty and (qty[rid]['core'],qty[rid]['add'])!=(int(st.get('core',0)),int(st.get('add',0))):raise ValueError('Corporate/trade quantity mismatch')
        return out
    def capture_runtime(self):
        r=super().capture_runtime()
        r['compound']=copy.deepcopy(dict(share_registrations=self.share_registrations,share_ledger=self.share_ledger,
          research_tax_ledger=self.research_tax_ledger,compound_applied=self.compound_applied,
          extra_cash_audit=self.extra_tape.cash.audit,extra_compound_audit=self.extra_tape.audit))
        return r
    def restore_runtime(self,r):
        super().restore_runtime(r);c=copy.deepcopy(r['compound'])
        for k in ('share_registrations','share_ledger','research_tax_ledger','compound_applied'):setattr(self,k,c[k])
        self.extra_tape.cash.audit=c['extra_cash_audit'];self.extra_tape.audit=c['extra_compound_audit']
