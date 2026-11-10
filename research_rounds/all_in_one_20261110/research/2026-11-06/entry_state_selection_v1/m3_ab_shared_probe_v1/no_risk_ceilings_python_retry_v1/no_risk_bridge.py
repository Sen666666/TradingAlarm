"""Research only: remove all monetary risk ceilings. Preserve capital and protection signals."""
from pathlib import Path
import ast,copy,hashlib,inspect,sys,textwrap,types
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tech407_admission_mask_ablation_v1'))
import mask_bridge as M
E=M.E
import limits_v3 as V
DERIVATION={}
def from_text(source,transform,env):
    tree=ast.parse(textwrap.dedent(source));name=tree.body[0].name
    transform(tree);ast.fix_missing_locations(tree);ns={}
    exec(compile(tree,str(HERE/'no_risk_bridge.py')+':derived','exec'),env,ns)
    DERIVATION[name]={'original_sha256':hashlib.sha256(source.encode()).hexdigest(),'derived_source':ast.unparse(tree)}
    return ns[name]
def derive(fn,transform,env):return from_text(textwrap.dedent(inspect.getsource(fn)),transform,env)
def remove_reasons(t):
    body=t.body[0].body
    for reason in ('probe_risk','sector_risk'):
        hits=[n for n in body if isinstance(n,ast.If) and any(isinstance(x,ast.Constant) and x.value==reason for x in ast.walk(n))]
        assert len(hits)==1;body.remove(hits[0])
    # Capital-only resources. No pooled risk aggregation/reservation exists in this book.
    for n in ast.walk(t):
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Tuple):
            names=ast.unparse(n.targets[0])
            if names in ('(pc, pr)','(sc, sr)','(stock, _)'):
                n.targets=[n.targets[0].elts[0]];n.value.func.attr='capital'
    assert not any(isinstance(n,ast.Name) and n.id in ('pr','sr') for n in ast.walk(t))
def remove_reservation_risk_audit(t):
    hits=[]
    for n in ast.walk(t):
        if isinstance(n,ast.Dict):
            for i,k in enumerate(n.keys):
                if isinstance(k,ast.Constant) and k.value=='probe_resources':hits.append((n,i))
    assert len(hits)==1
    n,i=hits[0];n.keys[i]=ast.Constant(value='probe_capital_reserved_and_held');n.values[i]=ast.parse("self.capital(pool='probe')",mode='eval').body
class NoRiskBook(V.ReserveBook):
    def capital(self,pool=None,sector=None,sid=None):
        rows=[x for x in self.snapshot.holdings if x.status=='held']+[x for x in self.orders if x.status in ('live','cancel_pending')]
        return sum((x.capital for x in rows if (pool is None or x.pool==pool) and (sector is None or x.sector==sector) and (sid is None or x.sid==sid)),V.ZERO)
    reasons=derive(V.ReserveBook.reasons,remove_reasons,V.__dict__)
    reserve=derive(V.ReserveBook.reserve,remove_reservation_risk_audit,V.__dict__)
def remove_size_risk(t):
    hits=[n for n in ast.walk(t) if isinstance(n,ast.BoolOp) and ast.unparse(n)=="D(q) * price + bf <= budget and risk <= riskmax"]
    assert len(hits)==1
    hits[0].values.pop();assert len(hits[0].values)==1
    # Replace one-value BoolOp, since compile rejects it.
    class Fix(ast.NodeTransformer):
        def visit_BoolOp(self,n):
            self.generic_visit(n);return n.values[0] if len(n.values)==1 else n
    Fix().visit(t)
    assert not any(isinstance(n,ast.Name) and n.id=='riskmax' for n in ast.walk(t))
def no_risk_arguments(t):
    class Drop(ast.NodeTransformer):
        def visit_BinOp(self,n):
            if ast.unparse(n)=="nd * D('.0025')":return ast.Constant(value=None)
            return self.generic_visit(n)
        def visit_Constant(self,n):
            if n.value=='INIT_2_RISK_025':return ast.Constant(value='INIT_2_NO_RISK_CEILING')
            if n.value=='MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE':return ast.Constant(value='MINIMUM_LOT_OR_CAPITAL_REJECT_AT_CLOSE')
            return n
    Drop().visit(t)
def remove_round_risk(t):
    hits=[]
    for n in ast.walk(t):
        if isinstance(n,ast.While):
            hits += [(n,x) for x in n.body if isinstance(x,ast.If) and ast.unparse(x.test)=="risk > p['riskmax']"]
    assert len(hits)==1;hits[0][0].body.remove(hits[0][1])
def remove_add_remaining(t):
    hits=0
    for n in ast.walk(t):
        if isinstance(n,ast.If):
            for a in list(n.body):
                if isinstance(a,ast.Assign) and ast.unparse(a.targets[0])=='exist':n.body.remove(a);hits+=1
                elif isinstance(a,ast.Assign) and ast.unparse(a.targets[0])=='remaining':a.value=ast.Constant(value=None);hits+=1
    assert hits==2
    assert not any(isinstance(n,ast.Name) and n.id in ('RISK','exist') for n in ast.walk(t))
_open_env=dict(E.__dict__);_open_env['ReserveBook']=NoRiskBook
class NoRiskBridge(E.ExecutionBridge):
    def __init__(self,module,*args,**kwargs):
        # Fresh research module only; original on-disk source and other arms untouched.
        source=module.SOURCE.read_text();node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='size')
        module.size=from_text(ast.get_source_segment(source,node),remove_size_risk,module.__dict__)
        super().__init__(module,*args,**kwargs)
        prep=self.split['provenance']['derived_source']['source_prepare_add']
        f=from_text(prep,remove_add_remaining,module.__dict__)
        self.split['codes']['source_prepare_add']=f.__code__
        self.split['provenance']['derived_source']['source_prepare_add']=DERIVATION['source_prepare_add']['derived_source']
    open_phase=derive(E.ExecutionBridge.open_phase,lambda t:None,_open_env)
    _entry_proposal=derive(E.ExecutionBridge._entry_proposal,no_risk_arguments,E.__dict__)
    _add_proposal=derive(E.ExecutionBridge._add_proposal,no_risk_arguments,E.__dict__)
    _checkclose=derive(E.ExecutionBridge._checkclose,no_risk_arguments,E.__dict__)
    reserve_proposal=derive(E.ExecutionBridge.reserve_proposal,remove_round_risk,E.__dict__)
def make_bridge(source,arm):
    assert arm=='no_risk_ceilings'
    return NoRiskBridge(source,seed_cash=E.D('1200000'))
merge_hashes=M.merge_hashes
