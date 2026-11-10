"""Isolated replay runtime. Original code/input/output paths are read only.

Reuse the exact frozen loop AST after removing ONLY its obsolete authorization
and original-run-lock statements. The new entrypoints own authorization/locks.
No historical simulation occurs at import.
"""
from pathlib import Path
import ast, hashlib, json, sys, textwrap
O=Path(__file__).resolve().parent
R=O.parent
SOURCE=R/'independent_channel_joint_economic_v1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def verify_original():
    a=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')
    seal=read(SOURCE/'FINAL_RUN_SEAL.json')
    assert a['code_sha256']==seal['code_sha256']
    for name,h in a['code_sha256'].items():assert sha(SOURCE/name)==h,('FROZEN_CODE_CHANGED',name)
    for p,h in a['input_sha256'].items():assert sha(p)==h,('FROZEN_INPUT_CHANGED',p)
    for p,h in seal['files'].items():
        target=Path(p) if Path(p).is_absolute() else SOURCE/p
        assert sha(target)==h,('FROZEN_OUTPUT_CHANGED',p)
    return a

def select_source():
    source=(SOURCE/'joint_engine.py').read_text()
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='JointConsumer')
    return source,node

def make_loop():
    import joint_engine as j
    source,cls=select_source()
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run_authorized')
    removed=method.body[:3]
    assert isinstance(removed[0],ast.Assign) and ast.unparse(removed[0].targets[0])=='win'
    assert isinstance(removed[1],ast.Assign) and ast.unparse(removed[1].value.func)=='require_economic_authorization'
    assert isinstance(removed[2],ast.Expr) and ast.unparse(removed[2].value.func)=='claim_run_once'
    method.body=method.body[3:]
    method.name='isolated_loop'
    # Signature keeps authorization argument unused; no old lock/gate executes.
    env=dict(vars(j))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(SOURCE/'joint_engine.py')+':isolated_gate_owner','exec'),env)
    return env['isolated_loop']

def make_consumer(window,mode='baseline'):
    from baseline_regression import load_engine
    from market_adapter import MarketAdapter
    from joint_engine import JointConsumer
    a=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')
    if mode=='baseline':cls=JointConsumer
    elif mode=='dmi':
        from priority import DmiConsumer
        cls=DmiConsumer
    else:raise ValueError('NO_OTHER_ARMS')
    return cls(load_engine(window),MarketAdapter(expected_sources=a['input_sha256']),window)

def run_isolated(consumer):
    return make_loop()(consumer,None)

def dump_consumer(consumer,dest):
    from run_economic import save
    consumer.s.dump(dest/'joint')
    save(dest/'PRICE_AUDIT.json',consumer.price_audit)
    save(dest/'OFFER_AUDIT.json',consumer.offer_audit)
    save(dest/'AB_DECISION_AUDIT.json',consumer.ab_decision_audit)
    save(dest/'FROZEN_RESPONSIBILITIES.json',consumer.frozen_responsibilities)
    save(dest/'EXECUTION_BOOKS.json',{rid:dict(responsibility=b.responsibility(),parents=b.parents,orders=b.orders,lots=b.lots,events=b.events) for rid,b in consumer.books.items()})
    save(dest/'MARKET_SOURCES.json',consumer.market.verify_sources())
    save(dest/'ECONOMIC_LOOP_COMPLETE.json',dict(rounds=len(consumer.s.rounds),actions=len(consumer.s.actions),loop_complete=True,report_pending=True))
