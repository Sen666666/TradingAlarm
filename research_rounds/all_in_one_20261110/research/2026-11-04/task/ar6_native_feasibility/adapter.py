"""Fresh C10, one isolated account-risk6 ablation; no old files are patched.

Only execution is via explicit local grant; default object construction is zero
financial events. Original price, risk accounting, native ledger and scheduler
are inherited. Global source modules remain untouched.
"""
from pathlib import Path
import sys, ast, types, copy, json, hashlib, pickle, inspect
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sys.path.insert(0,str(ROOT/'g-s-C-month-continuation-20261102'))
import month_runtime as M
E=M.E; F=M.C.F; H=M.H; D=E.D; Z=D(0)
RIGHTS_ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-rights-Jan13-action-v3-20261102')
sys.path.insert(0,str(RIGHTS_ROOT))
import rights_wiring_v3 as RIGHTS
CAP=250000
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(p,x):E.IO.write_json(Path(p),x,encoder=E.encode)

def private_policy(enabled):
    """Clone only function globals; no monkeypatch of audited module objects."""
    C=E.C; B=C.B; J=C.J
    jt=ast.parse(Path(J.__file__).read_text()); edits=0
    for n in ast.walk(jt):
        if isinstance(n,ast.FunctionDef) and n.name=='check':
            for b in ast.walk(n):
                if isinstance(b,ast.If) and ast.unparse(b.test)=='gap < 0':
                    b.test=ast.parse("gap < 0 and not (ABLATION_ENABLED and label == 'account_risk6')",mode='eval').body;edits+=1
    assert edits==1
    jns=dict(J.__dict__,ABLATION_ENABLED=enabled)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in jt.body if isinstance(n,ast.FunctionDef)],type_ignores=[])),str(HERE/'adapter.py')+'::JF2','exec'),jns)
    pj=types.SimpleNamespace(**jns)
    bt=ast.parse(Path(B.__file__).read_text()); edits=0
    for n in bt.body:
        if isinstance(n,ast.FunctionDef) and n.name=='necessary_upper':
            bs=[]
            for b in n.body:
                bs.append(b)
                if isinstance(b,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bounds' for t in b.targets):
                    bs+=ast.parse("if ABLATION_ENABLED: bounds.pop('account_risk6')").body;edits+=1
            n.body=bs
    assert edits==1
    bns=dict(B.__dict__,J=pj,ABLATION_ENABLED=enabled)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in bt.body if isinstance(n,ast.FunctionDef)],type_ignores=[])),str(HERE/'adapter.py')+'::B','exec'),bns)
    pb=types.SimpleNamespace(**bns); cns=dict(C.__dict__,B=pb,J=pj)
    ct=ast.parse(Path(C.__file__).read_text())
    exec(compile(ast.fix_missing_locations(ast.Module(body=[n for n in ct.body if isinstance(n,ast.FunctionDef)],type_ignores=[])),str(HERE/'adapter.py')+'::C','exec'),cns)
    return types.SimpleNamespace(**cns)

POLICIES={False:private_policy(False),True:private_policy(True)}
def preview(enabled):
    original=E.Account._preview
    # Mixed-order Account inherits the exact V3 preview.
    source=Path(inspect.getsourcefile(original)); tree=ast.parse(source.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Account')
    node=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_preview')); edits=0
    for n in ast.walk(node):
        if isinstance(n,ast.If) and len(n.body)==1 and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Call) and isinstance(n.body[0].value.func,ast.Attribute) and n.body[0].value.func.attr=='append' and any(isinstance(x,ast.Constant) and x.value=='account_risk6' for x in ast.walk(n.body[0])):
            n.test=ast.BoolOp(op=ast.And(),values=[n.test,ast.UnaryOp(op=ast.Not(),operand=ast.Name(id='ABLATION_ENABLED',ctx=ast.Load()))]);edits+=1
    assert edits==1
    ns=dict(original.__globals__,ABLATION_ENABLED=enabled)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(HERE/'adapter.py')+'::preview','exec'),ns)
    return ns['_preview']
PREVIEWS={False:preview(False),True:preview(True)}

class Inputs(RIGHTS.NoSubscriptionInputsMixin,M.MonthInputs):
    def __init__(self,path):
        self.more_objects={};self.more_frames={};self.more_verified=set();super().__init__(path)
    def extra_ref(self,key):
        rec=self.m['continuation_extension'][key];p=self.root/rec['path']
        if key not in self.more_verified:E.require(sha(p)==rec['sha256'],'extension changed '+key);self.more_verified.add(key)
        return p
    def obj(self,key):
        base=super().obj(key)
        if key not in self.m.get('continuation_extension',{}):return base
        if key not in self.more_objects:
            more=read(self.extra_ref(key))
            if key=='metadata':
                v=copy.deepcopy(base)
                for sid,rs in more.items():v[sid]['structure_observations']+=rs
            else:v=copy.deepcopy(base)+more
            self.more_objects[key]=v
        return self.more_objects[key]
    def table(self,key):
        base=super().table(key)
        if key not in self.m.get('continuation_extension',{}):return base
        if key not in self.more_frames:self.more_frames[key]=pd.concat([base,pd.read_parquet(self.extra_ref(key))],ignore_index=True)
        return self.more_frames[key]

class Account(M.MonthAccount):
    def _preview(self,*a,**kw):return PREVIEWS[self.owner.ablation_enabled](self,*a,**kw)

def input_ref(window,branch):
    if window=='2022':
        x=read(ROOT/'g-s-C-R0-continuous-january-v1-20261102/INPUT_IDENTITY.json')[branch]
    elif branch=='full':x=read(ROOT/'g-s-C-August-continuation-v1-20261102/INPUT_IDENTITY.json')['inputs']['full']
    else:
        j=read(ROOT/'g-s-C-R0-continuous-july-v1-20261102/INPUT_IDENTITY.json')
        x=dict(path=j['physical_manifest'],sha256=j['physical_manifest_sha256'])
    E.require(sha(x['path'])==x['sha256'],'frozen input manifest changed')
    return x

class Runner(M.MonthRunner):
    def __init__(self,window,*,ablation_enabled,branch='full'):
        E.require(type(ablation_enabled) is bool and window in ('2022','2025_26') and branch in ('full','physical'),'explicit scope')
        self.ablation_enabled=ablation_enabled;self.branch=branch;self.execution_grant=None
        self._memo=None;self._memo_hits=0;self._memo_misses=0
        F.FixedRunner.__init__(self,'C10',window)
        self.original_inputs=self.inputs
        a=self.account;bank=a.canonical_registry;binding=a.canonical_binding
        ref=input_ref(window,branch);inputs=Inputs(ref['path'])
        E.require(inputs.m['files']==self.original_inputs.m['files'],'initial numeric input changed')
        provider=H.HistoricalMarket(inputs)
        a.market.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions;a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;self.inputs=inputs
        a.__class__=Account;a.owner=self
        a.canonical_generations={binding:bank};a.month_generations={d:binding for d in M.P.EXPECTED[window]}
        a.old_canonical_binding=binding;a.canonical_old_end=M.P.EXPECTED[window][-1]
        self.no_subscription_actions={};self.initial_nav=str(a.available)
        E.require(self.initial_nav=='1000000' and not a.layers and not self.authority.certificates,'original fresh1m required')
        self.assert_observers()
    def source_binding(self):
        x=F.FixedRunner.source_binding(self)
        for p in [Path(__file__),Path(M.__file__),Path(M.C.__file__),Path(RIGHTS.__file__),RIGHTS_ROOT/'fingerprint.py',RIGHTS_ROOT/'CONTRACT.txt']:
            x[str(p)]=sha(p)
        return x
    def binding(self):
        return dict(scope='FRESH_C10_ACCOUNT6_ONLY',window=self.window,ablation_enabled=self.ablation_enabled,branch=self.branch,source=self.source_binding(),engine=E.IO.runner_identity(self),account_class=E.IO._class_identity(type(self.account)),input_manifest=str(self.inputs.path),input_sha256=sha(self.inputs.path),initial_cash='1000000',execution_grant=self.execution_grant)
    def industry_input(self,at):
        if at.date().isoformat()<=M.P.EXPECTED[self.window][-1]:
            view=object.__new__(F.FixedRunner);view.__dict__.update(self.__dict__);view.inputs=self.original_inputs
            return F.FixedRunner.industry_input(view,at)
        return M.C.HorizonRunner.industry_input(self,at)
    def verify_native(self,c):return E.Runner.verify_native(self,c)
    def _solve(self,s,ds,e,bb):
        token=E.digest(dict(source=self.source_binding(),on=self.ablation_enabled,s=s,ds=ds,e=e,bb=bb))
        if self._memo and self._memo['key']==token:
            E.require(E.digest(self._memo['value'])==self._memo['sha'],'memo changed');self._memo_hits+=1;return copy.deepcopy(self._memo['value'])
        book=E.OffBook.loads(bb,trusted_sha256=hashlib.sha256(bb.encode()).hexdigest(),account_id=s['account_id'],source_binding=E.digest(s),actual_commitments=json.loads(bb)['body']['lines'])
        result=POLICIES[self.ablation_enabled].solve_C(s,ds,e,max_native_checks=CAP)
        working=copy.deepcopy(book);working.approve(book.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in result['donors']['rows']},target_binding=E.digest(dict(Q=result['Q'],receipts=[d['receipt_id'] for d in ds])))
        result=dict(result,budget_before=bb,budget_after=working.dumps())
        self._memo=dict(key=token,value=copy.deepcopy(result),sha=E.digest(result));self._memo_misses+=1
        return result
    def bind_grant(self,path):
        g=read(path);E.require(g['parent_approved'] and g['runtime_sha256']==sha(__file__) and g['window']==self.window and g['ablation_enabled']==self.ablation_enabled and g['branch']==self.branch,'grant source/scope mismatch')
        E.require(g['start']==('2022-01-04' if self.window=='2022' else '2025-07-01') and g['end']<=('2022-01-28' if self.window=='2022' else '2025-08-29'),'bounded window required')
        self.execution_grant=dict(path=str(Path(path).resolve()),sha256=sha(path))
    def execution_guard(self,day):
        E.require(self.execution_grant is not None,'PREPARATION ONLY: no account event authorized')
        g=read(self.execution_grant['path']);E.require(sha(self.execution_grant['path'])==self.execution_grant['sha256'] and g['runtime_sha256']==sha(__file__),'grant changed')
        E.require(g['start']<=day<=g['end'] and (day in self.inputs.days or day in M.P.EXPECTED[self.window]),'outside local bounded grant')
    def step(self,day,phase):
        self.execution_guard(day);return H.HistoricalRunner.step(self,day,phase)
    def corporate_actions(self,day):return RIGHTS.NoSubscriptionRunnerMixin.corporate_actions(self,day)
    def _rights_ordinary_dispatch(self,day):return M.P.HistoricalRunner.corporate_actions(self,day)
    def observable(self,at):
        x=F.FixedRunner.observable(self,at);x.update(no_subscription_actions=self.no_subscription_actions)
        return x
    @classmethod
    def restore(cls,path):
        p=Path(path);side=read(p.with_suffix('.provenance.json'));E.require(sha(p)==side['checkpoint_sha256'],'checkpoint bytes changed')
        r=pickle.loads(p.read_bytes());r.account.owner=r
        E.require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'restore source/policy/input changed')
        r.assert_observers()
        for c in r.authority.certificates.values():r.verify_native(c)
        return r
