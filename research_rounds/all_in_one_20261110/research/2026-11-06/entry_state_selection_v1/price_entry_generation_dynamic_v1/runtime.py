"""Isolated original JointConsumer loop; no economic work on import."""
from pathlib import Path
import ast,hashlib,json,sys
O=Path(__file__).resolve().parent; R=O.parent; SOURCE=R/'independent_channel_joint_economic_v1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.write('\n')
def verify_original():
    a=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json');seal=read(SOURCE/'FINAL_RUN_SEAL.json')
    assert a['code_sha256']==seal['code_sha256']
    for n,h in a['code_sha256'].items():assert sha(SOURCE/n)==h,('ORIGINAL_CODE_CHANGED',n)
    for p,h in a['input_sha256'].items():assert sha(p)==h,('ORIGINAL_INPUT_CHANGED',p)
    for p,h in seal['files'].items():assert sha(Path(p) if Path(p).is_absolute() else SOURCE/p)==h,('ORIGINAL_OUTPUT_CHANGED',p)
    return a

def select_source():
    s=(SOURCE/'joint_engine.py').read_text();cls=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=='JointConsumer');return s,cls

def make_loop():
    import joint_engine as j
    s,cls=select_source();m=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='run_authorized')
    removed=m.body[:3]
    assert ast.unparse(removed[0].targets[0])=='win'
    assert ast.unparse(removed[1].value.func)=='require_economic_authorization'
    assert ast.unparse(removed[2].value.func)=='claim_run_once'
    m.body=m.body[3:];m.name='isolated_loop';env=dict(vars(j))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[m],type_ignores=[])),str(SOURCE/'joint_engine.py')+':isolated_gate_owner','exec'),env)
    return env['isolated_loop']

def run_isolated(c):return make_loop()(c,None)
def make_consumer(window):
    from baseline_regression import load_engine
    from market_adapter import MarketAdapter
    from entry_gate import GateConsumer
    a=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')
    return GateConsumer(load_engine(window),MarketAdapter(expected_sources=a['input_sha256']),window)
def dump_consumer(c,dest):
    from run_economic import save as oldsave
    c.s.dump(dest/'joint')
    for name,value in [('PRICE_AUDIT',c.price_audit),('OFFER_AUDIT',c.offer_audit),('AB_DECISION_AUDIT',c.ab_decision_audit),('FROZEN_RESPONSIBILITIES',c.frozen_responsibilities),('EXECUTION_BOOKS',{rid:dict(responsibility=b.responsibility(),parents=b.parents,orders=b.orders,lots=b.lots,events=b.events) for rid,b in c.books.items()}),('ENTRY_GATE_AUDIT',c.entry_gate_audit)]:oldsave(dest/(name+'.json'),value)
    oldsave(dest/'MARKET_SOURCES.json',c.market.verify_sources())
    oldsave(dest/'ECONOMIC_LOOP_COMPLETE.json',dict(rounds=len(c.s.rounds),actions=len(c.s.actions),loop_complete=True,report_pending=True))
