"""Isolated one-constraint C10 ablation. No ledger mutation/order API."""
from pathlib import Path
import sys,ast,copy,types,inspect,hashlib
O=Path(__file__).resolve().parent;R=O.parent
sys.path.insert(0,str(R/'replacement-six-package-projection-v1-20261103'))
import extract as X
B=X.B;J=X.J;C=X.C

def functions(source,namespace,filename):
 tree=ast.parse(source);defs=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
 exec(compile(ast.fix_missing_locations(defs),filename,'exec'),namespace)
 return namespace

def factory(ablation_enabled):
 """AB=False exactly original; AB=True removes only account_risk6 veto."""
 jtree=ast.parse(Path(J.__file__).read_text());changed=0
 for node in ast.walk(jtree):
  if isinstance(node,ast.FunctionDef) and node.name=='check':
   for n in ast.walk(node):
    if isinstance(n,ast.If) and ast.unparse(n.test)=='gap < 0':
     n.test=ast.parse("gap < 0 and not (ABLATION_ENABLED and label == 'account_risk6')",mode='eval').body;changed+=1
 assert changed==1
 jns=dict(J.__dict__);jns['ABLATION_ENABLED']=ablation_enabled
 jdefs=ast.Module(body=[n for n in jtree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
 exec(compile(ast.fix_missing_locations(jdefs),str(O/'engine.py')+'::private_JF2','exec'),jns)
 privateJ=types.SimpleNamespace(**jns)
 btree=ast.parse(Path(B.__file__).read_text());changedB=0
 for node in btree.body:
  if isinstance(node,ast.FunctionDef) and node.name=='necessary_upper':
   body=[]
   for n in node.body:
    body.append(n)
    if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='bounds' for t in n.targets):
     body+=ast.parse("if ABLATION_ENABLED: bounds.pop('account_risk6')").body;changedB+=1
   node.body=body
 assert changedB==1
 bns=dict(B.__dict__);bns.update(J=privateJ,ABLATION_ENABLED=ablation_enabled)
 bdefs=ast.Module(body=[n for n in btree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
 exec(compile(ast.fix_missing_locations(bdefs),str(O/'engine.py')+'::private_original_order_B','exec'),bns)
 privateB=types.SimpleNamespace(**bns)
 cns=dict(C.__dict__);cns.update(B=privateB,J=privateJ)
 functions(Path(C.__file__).read_text(),cns,str(O/'engine.py')+'::private_original_C_wrapper')
 return types.SimpleNamespace(**cns),dict(account_bound_insertions=changedB,final_veto_edits=changed,
  JF2_AST=ast.dump(jdefs,include_attributes=False),B_AST=ast.dump(bdefs,include_attributes=False),
  ablation_enabled=ablation_enabled,underlying_sources={str(p):X.sha(p) for p in [Path(J.__file__),Path(B.__file__),Path(C.__file__)]})

def native_preview_factory(ablation_enabled):
 # Actual frozen override, not the earlier A/native_capital fallback.
 import textwrap
 source=Path(R/'g-s-C-native-synthetic-v3-20261102/native_c.py')
 tree=ast.parse(source.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Account')
 node=copy.deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_preview'));changed=0
 for n in ast.walk(node):
  if isinstance(n,ast.If) and any(isinstance(x,ast.Constant) and x.value=='account_risk6' for x in ast.walk(n)):
   # The enclosing role/partial branches also contain this literal in their
   # subtree; only the direct one-line append is the risk guard.
   if len(n.body)==1 and isinstance(n.body[0],ast.Expr) and isinstance(n.body[0].value,ast.Call) and isinstance(n.body[0].value.func,ast.Attribute) and n.body[0].value.func.attr=='append' and any(isinstance(x,ast.Constant) and x.value=='account_risk6' for x in ast.walk(n.body[0])):
    n.test=ast.BoolOp(op=ast.And(),values=[n.test,ast.UnaryOp(op=ast.Not(),operand=ast.Name(id='ABLATION_ENABLED',ctx=ast.Load()))]);changed+=1
 assert changed==1
 # Existing audited runtime loads the exact method's module/global types.
 original=X.A.E.Account._preview
 assert Path(inspect.getsourcefile(original)).resolve()==source.resolve(),('wrong frozen native preview',inspect.getsourcefile(original))
 ns=dict(original.__globals__);ns['ABLATION_ENABLED']=ablation_enabled
 module=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]));exec(compile(module,str(O/'engine.py')+'::native_preview_single_veto','exec'),ns)
 return ns['_preview'],dict(native_preview_guard_edits=changed,ablation_enabled=ablation_enabled,source=str(source.resolve()),source_sha256=X.sha(source),AST=ast.dump(module,include_attributes=False))
