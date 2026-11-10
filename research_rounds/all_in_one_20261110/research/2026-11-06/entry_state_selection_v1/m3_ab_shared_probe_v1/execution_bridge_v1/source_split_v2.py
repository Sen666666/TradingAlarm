"""AST derivation only; no original engine execution on import."""
from pathlib import Path
import ast, copy, hashlib, types

def segment_hash(text,node):
    return hashlib.sha256(ast.get_source_segment(text,node).encode()).hexdigest()

def build(source_path):
    text=Path(source_path).read_text()
    tree=ast.parse(text)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    held=functions['held_open'];entry=functions['entry_open']
    def is_add_pending(n):
        return isinstance(n,ast.If) and ast.unparse(n.test)=="st['addpending'] is not None"
    add_node=next(n for n in held.body if is_add_pending(n))
    index=held.body.index(add_node)
    assert index==len(held.body)-1
    # Exact source prefix validates data, executes whole/ADD exits, no ADD code.
    exits=copy.deepcopy(held);exits.name='source_exit_only';exits.body=copy.deepcopy(held.body[:index])
    # Exact original entry mutations after all original validation/size succeeds.
    entry_start=next(i for i,n in enumerate(entry.body) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='st.update')
    commit_entry=ast.FunctionDef(name='source_commit_entry',
        args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=x) for x in ['st','d','q','px','bf','risk','fl','op','z']],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=copy.deepcopy(entry.body[entry_start:]),decorator_list=[])
    # Preserve original ADD prep through size rejection; replace mutation tail with return.
    success=next(i for i,n in enumerate(add_node.body) if isinstance(n,ast.Assert))
    prep=copy.deepcopy(held);prep.name='source_prepare_add'
    prep.body=[
        *ast.parse("op = D(str(z['raw_open'])); sp = op * (1-SLIP)").body,
        ast.parse("_, fs, pa = getmeta(sid,d)").body[0],
        copy.deepcopy(add_node)]
    prep.body[-1].body=copy.deepcopy(add_node.body[:success])+ast.parse(
        "return dict(q=aq, fee=af, risk=ar, price=px, floor=fl, prior_net=prior_net, budget=budget, remaining_risk=remaining, open=op)").body
    prep.args.args.append(ast.arg(arg='z'))
    commit_add=ast.FunctionDef(name='source_commit_add',
        args=ast.arguments(posonlyargs=[],args=[ast.arg(arg=x) for x in ['st','d','aq','af','px','fl','prior_net']],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=copy.deepcopy(add_node.body[success:]),decorator_list=[])
    nodes=[exits,commit_entry,prep,commit_add]
    namespace={}
    for node in nodes:
        ast.fix_missing_locations(node)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source_path)+':bounded_derivation','exec'),namespace)
    return {'codes':{n.name:namespace[n.name].__code__ for n in nodes},
            'provenance':{'source_sha256':hashlib.sha256(text.encode()).hexdigest(),
                          'held_open_sha256':segment_hash(text,held),'entry_open_sha256':segment_hash(text,entry),
                          'derived_source':{n.name:ast.unparse(n) for n in nodes}}}

def bind(code,module,**overrides):
    # Isolated per-call globals, never patch the original module's fixed budgets.
    env=dict(module.__dict__);env.update(overrides)
    return types.FunctionType(code,env)
