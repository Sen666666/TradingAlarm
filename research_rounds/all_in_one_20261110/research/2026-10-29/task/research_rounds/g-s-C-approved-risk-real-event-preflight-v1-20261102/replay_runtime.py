"""Prepared fixed-next-OPEN diagnostic composition. NO implicit financial grant.

Load risk core FIRST and reuse its exact frozen mixed module for month input;
never import the mixed file twice and replace its pickle class registry.
"""
from pathlib import Path
import sys,copy,pickle,json,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent
RISK=W/'g-s-C-approved-risk-native-v1-20261102'
RISK_SHA='b447dcb43fa72e5d25ef79f15b21de3c8e5cd41ef64eee5fa86085f2418caeb7'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(RISK/'native_risk.py')!=RISK_SHA:raise ValueError('frozen reviewed-risk candidate changed; explicit rebind required')
sys.path.insert(0,str(RISK));import native_risk as R
if 'native_c' in sys.modules and sys.modules['native_c'] is not R.M:raise ValueError('different mixed module already loaded; fresh isolated process required')
sys.modules['native_c']=R.M
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'));import month_runtime as M
E=M.E

def read(p):return json.loads(Path(p).read_text())
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def old_view(r):
    v=object.__new__(M.MonthRunner);v.__dict__.update(r.__dict__);return v

def legacy_prefix(r):
    # Explicit original-policy view; identity changes are separately recorded.
    return M.C.prefix_view(old_view(r))

def snapshot(r):
    a=r.account
    return dict(prefix=legacy_prefix(r),native_order_meta=copy.deepcopy(a.order_meta),
        native_audit=copy.deepcopy(a.audit_log),completed=copy.deepcopy(a.completed),
        native_settlements=copy.deepcopy(a.settlements),native_dividends=copy.deepcopy(a.dividends),
        native_receipt_registry=copy.deepcopy(a.receipt_registry),core_epoch=copy.deepcopy(a.core_epoch),
        last_buy=copy.deepcopy(a.last_buy),canonical_binding=a.canonical_binding,
        canonical_generations=copy.deepcopy(a.canonical_generations),funding=copy.deepcopy(a.funding.exported()),
        policy=copy.deepcopy(a.policy.exported()),cash=a.available,
        phase=r.last_phase,last_completed=r.last_completed_event,source_input=sha(r.inputs.path))

class ReplayRiskBook(R.RiskBook):
    def __init__(self,r):
        super().__init__()
        # Completed historic orders/fills remain validated under original policy,
        # not retroactively subjected to an unapproved R0 change.
        self.legacy_orders=copy.deepcopy(r.authority.orders)
        self.legacy_fills=copy.deepcopy(r.authority.events)
        E.require(not r.account.buys,'active pre-import C buy needs explicit partial-risk import; not assumed')
        E.require(all(not x['remaining'] for x in self.legacy_orders.values()),'old live authority not grandfatherable')
    def verify_legacy(self,r):
        for oid,v in self.legacy_orders.items():E.require(r.authority.orders.get(oid)==v,'completed legacy order changed')
        for eid,v in self.legacy_fills.items():E.require(r.authority.events.get(eid)==v,'completed legacy fill changed')
    def register(self,r,cid):
        super().register(old_view(r),cid)
    def check(self,r):
        self.verify_legacy(r)
        E.require(set(r.authority.orders)-set(self.legacy_orders)==set(self.orders),'new C order missing R0 import mapping')
        E.require(set(r.authority.events)-set(self.legacy_fills)==set(self.fills),'new C fill missing R0 debit')
        v=old_view(r);v.authority=copy.copy(r.authority)
        v.authority.orders={k:x for k,x in r.authority.orders.items() if k not in self.legacy_orders}
        v.authority.events={k:x for k,x in r.authority.events.items() if k not in self.legacy_fills}
        super().check(v)

class ReplayAccount(R.Account,M.MonthAccount):
    """Same actual month market/facts/canonical/ACK; R0 before native callbacks."""
    pass

class ReplayRunner(R.Runner,M.MonthRunner):
    def __init__(self,*args,**kwargs):raise RuntimeError('explicit old-checkpoint import only; no new finance account')
    def source_binding(self):
        x=M.MonthRunner.source_binding(self)
        x.update({str(p):sha(p) for p in [RISK/'native_risk.py',HERE/'replay_runtime.py',HERE/'run_open.py',HERE/'REPLAY_INPUT_BINDING.json']})
        x['C_APPROVED_RISK_SWITCH_V1']=E.digest(dict(enabled=self.keep_approved_risk,scope='C-only fixed-next-OPEN'))
        return x
    def verify_native(self,cert):
        cid=cert['certificate_id']
        E.require(cid in self.replay_old_certificates and cert==self.replay_old_certificates[cid],'fixed OPEN cannot issue/rewrite a certificate')
        return M.MonthRunner.verify_native(old_view(self),cert)
    def plan(self,*a,**kw):raise ValueError('NO new CLOSE/plan allowed in fixed OPEN diagnostic')
    def assert_observers(self):
        super().assert_observers()
        if hasattr(self,'risk'):self.risk.verify_legacy(self)
    def binding(self):
        b=M.MonthRunner.binding(self)
        b.update(scope='RESEARCH_BRANCH_FIXED_NEXT_OPEN_ONLY_NOT_JUL1_CONTINUOUS',
                 approved_risk_switch=self.keep_approved_risk,diagnostic_import=self.replay_import,
                 future_execution_authorization=self.replay_authorization)
        return b
    def execution_guard(self,day):
        E.require(day==self.replay_import['next_day'],'outside one exact next OPEN')
        p=self.replay_authorization
        E.require(p is not None,'NO financial execution authorization: preparation only')
        E.require(sha(p['path'])==p['sha256'],'execution grant body changed')
        validate_authorization(self,p['path'])
    def bind_execution(self,path):
        before=E.digest(snapshot(self));g=validate_authorization(self,path)
        self.replay_authorization=dict(path=str(Path(path).resolve()),sha256=sha(path),case=self.replay_import['case'],keep_approved_risk=self.keep_approved_risk)
        E.require(E.digest(snapshot(self))==before,'authorization binding changed old account state')
    def step(self,day,phase):
        E.require(phase=='OPEN','only next OPEN, never CLOSE or later session')
        self.execution_guard(day)
        return M.H.HistoricalRunner.step(self,day,phase)
    def corporate_actions(self,day):
        self.execution_guard(day)
        return M.MonthRunner.corporate_actions(self,day)
    def observable(self,at):
        x=R.Runner.observable(self,at);x.update(fixed_open_diagnostic=copy.deepcopy(self.replay_import),financial_authorization=self.replay_authorization)
        return x
    @classmethod
    def restore(cls,path):
        p=Path(path);side=read(p.with_suffix('.provenance.json'));E.require(sha(p)==side['checkpoint_sha256'],'import checkpoint changed')
        r=pickle.loads(p.read_bytes());E.require(type(r) is cls,'wrong diagnostic class')
        E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'new composition identity mismatch')
        r.account.owner=r;r.assert_observers()
        for c in r.authority.certificates.values():r.verify_native(c)
        return r

def validate_authorization(r,path):
    a=read(path);cell=r.replay_import['case']+'|'+('on' if r.keep_approved_risk else 'off')
    E.require(a.get('parent_approved') is True and a.get('financial_events_authorized') is True,'explicit parent financial grant required')
    E.require(a['scope']=='C_R0_FIXED_NEXT_OPEN_DIAGNOSTICS_ONLY','wrong economic scope')
    E.require(a['runtime_sha256']==sha(__file__) and a['entry_sha256']==sha(HERE/'run_open.py') and a['risk_adapter_sha256']==RISK_SHA,'source authorization mismatch')
    E.require(a['input_binding_sha256']==sha(HERE/'REPLAY_INPUT_BINDING.json'),'input authorization mismatch')
    E.require(cell in a['cells'] and a['cells'][cell]['checkpoint_sha256']==r.replay_import['parent_checkpoint_sha256'] and a['cells'][cell]['next_day']==r.replay_import['next_day'],'unapproved cell/parent/date')
    return a

def import_case(case,enabled,out=None):
    data=read(HERE/'REPLAY_INPUT_BINDING.json');rec=data['cases'][case];p=Path(rec['checkpoint'])
    E.require(sha(p)==rec['checkpoint_sha256'] and sha(p.with_suffix('.provenance.json'))==rec['provenance_sha256'],'frozen original checkpoint changed')
    # Verify original complete source/provenance FIRST, before __class__ changes.
    r=M.MonthRunner.restore(p)
    E.require(r.window=='2025_26' and r.mode==rec['mode'] and str(r.last_completed_event)==rec['cursor'],'wrong original state')
    E.require(sha(r.inputs.path)==rec['input_manifest_sha256'],'old input identity changed')
    before=E.digest(snapshot(r));oldbinding=r.binding();a=r.account
    risk=ReplayRiskBook(r);oldcerts=copy.deepcopy(r.authority.certificates)
    r.__class__=ReplayRunner;a.__class__=ReplayAccount;a.owner=r
    r.keep_approved_risk=bool(enabled);r.risk=risk;r.replay_old_certificates=oldcerts
    a._risk_submit=None;a._risk_fill=None
    r.replay_import=dict(case=case,parent_checkpoint=str(p),parent_checkpoint_sha256=rec['checkpoint_sha256'],old_binding=oldbinding,old_cursor=rec['cursor'],next_day=rec['next_day'],old_snapshot_hash=before,
        tracked_authorizations='only current active positive C stock rows; historic completed orders explicitly legacy',new_policy_not_continuous_from_Jul1=True,no_reset=True)
    r.replay_authorization=None
    if enabled and r.active:r.risk.register(r,r.active['certificate_id'])
    E.require(E.digest(snapshot(r))==before,'risk import modified original economic/strategy prefix')
    r.assert_observers()
    for c in r.authority.certificates.values():r.verify_native(c)
    if out:
        out=Path(out);out.mkdir(parents=True,exist_ok=False);r.checkpoint(out/'IMPORT.pkl')
        save(out/'IMPORT.json',dict(financial_events=0,old_snapshot_hash=before,new_original_view_snapshot_hash=E.digest(snapshot(r)),exact_original_prefix=True,import_record=r.replay_import,binding=r.binding()))
    return r

def opening_comparison(r):
    """After future granted OPEN only: actual full batch vs saved original OPEN."""
    rec=read(HERE/'REPLAY_INPUT_BINDING.json')['cases'][r.replay_import['case']]
    baseline=M.MonthRunner.restore(rec['baseline_open'])
    exact=E.digest(snapshot(r))==E.digest(snapshot(baseline))
    if not r.keep_approved_risk:E.require(exact,'OFF actual whole-opening state/event stream differs from frozen baseline')
    cid=r.active['certificate_id'];a=r.account;ba=baseline.account
    rows=[]
    for sid,q in r.active['Q'].items():
        if not q:continue
        p=R.approved_payload(old_view(r),cid,sid)
        def actual(account):
            found=[(oid,m) for oid,m in account.supports.items() if m.get('C_certificate')==cid and m['original_intent']['sid']==sid]
            E.require(len(found)<=1,'multiple orders under one stock authorization')
            if not found:return dict(reserved=0,filled=0,order_id=None)
            oid,m=found[0];au=[x for x in account.audit_log if x.get('kind')=='reserve' and x.get('order_id')==oid]
            E.require(len(au)==1,'missing actual reserve')
            fs=[f for f in account.fills if f.receipt_id in account.inventory_map and account.capital_meta[account.inventory_map[f.receipt_id]['layer']]['order']==oid]
            return dict(order_id=oid,reserved=au[0]['target_shares'],filled=sum(f.shares for f in fs),reserve_record=au[0],amendments=[x for x in account.native_callbacks if x.get('kind')=='amend_before_fill' and x.get('order')==oid],fills=[asdict(f) for f in fs])
        rows.append(dict(approved=p,baseline=actual(ba),actual_branch=actual(a),risk_record=r.risk.approvals.get(cid+'|'+sid)))
    at=E.iso(rec['next_day']+'T09:30:00+08:00')
    all_new=[asdict(f) for f in a.fills if f.at>=at]
    return dict(scope='ONE actual next OPEN from original close; NOT Jul1-continuous return',off_complete_original_state_identity=exact if not r.keep_approved_risk else None,
        C_stock_authorizations=rows,all_new_actual_fills_including_T_core_and_sells=all_new,
        account_bridge=a.bridge(r.last_completed_event),baseline_bridge=ba.bridge(baseline.last_completed_event),
        new_actual_rejections=[x for x in a.rejections if x.get('at') is not None and x['at']>=at],unknown_time_rejections_preserved_in_checkpoint=sum(x.get('at') is None for x in a.rejections),remaining_buys={s:asdict(o) for s,o in a.buys.items()},remaining_exit_duties=a.exit_duties,
        all_batch_reservation_callbacks=[x for x in a.native_callbacks if x.get('kind')=='entire_C_batch_reserved_before_windows' and x.get('at')==at],
        no_historical_saved_PnL_multiplied_by_quantity_change=True)
