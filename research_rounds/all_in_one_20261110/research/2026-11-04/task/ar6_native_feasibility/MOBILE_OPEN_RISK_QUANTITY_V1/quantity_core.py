"""Pure nominal quantity screen; only original maximum_quantity AST is evaluated."""
from decimal import Decimal as D
from types import SimpleNamespace
from pathlib import Path
import ast,hashlib
LR_PATH=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py')
LR_SHA='2e7cfbdded269ae5430c9146d0b1f5c2b2281e5a5c774fdffb088b620d72bff4'
raw=LR_PATH.read_bytes();assert hashlib.sha256(raw).hexdigest()==LR_SHA
node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)and n.name=='maximum_quantity')
env={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(LR_PATH)+'::pure-maximum-quantity-only','exec'),env)
maximum_quantity=env['maximum_quantity']
def pure_quantity(role,q0,minimum,step,R=None,width=None,unknown=()):
 if role=='core':return dict(qnew=q0,qbase=q0,status='CORE_UNCHANGED',reasons=[])
 if unknown:return dict(qnew=0,qbase=None,status='UNKNOWN_NO_NEW_MOBILE',reasons=list(unknown))
 if R is None or not R.is_finite()or R<=0:return dict(qnew=0,qbase=None,status='UNKNOWN_NO_NEW_MOBILE',reasons=['nonpositive_or_unknown_plan_R'])
 if width is None or not width.is_finite()or width<=0:return dict(qnew=0,qbase=None,status='UNKNOWN_NO_NEW_MOBILE',reasons=['nonpositive_or_unknown_execution_risk_width'])
 rule=SimpleNamespace(buy_minimum=minimum,buy_step=step)
 base=maximum_quantity(rule,q0,lambda q:True)
 qnew=maximum_quantity(rule,q0,lambda q:D(q)*width<=R)
 return dict(qnew=qnew,qbase=base,status='KNOWN_PRIMARY_FIXED_PRICE',reasons=[])
