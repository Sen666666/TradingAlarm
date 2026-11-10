"""Explicit, import-safe no_budget bridge to sealed original A_UNION_B consumers.
Importing this module reads no original data and executes no consumer.
Only load_original() loads source; only replay_no_budget() advances it.
Shared account execution is deliberately absent.
"""
from pathlib import Path
import ast, hashlib, json, types, sys

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
EVENT_ROOT = ROOT / 'm3_stock_birth_during_sector_v1'
HERE = Path(__file__).resolve().parent
ENGINES = {
    '2022': ('relative_priority_equity_run_2022_v1', 'dynamic'),
    '2024_924': ('cash_equity_baseline_2024_v1', 'economic'),
}
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verified_manifest():
    seal = json.loads((HERE/'SOURCE_MANIFEST.json').read_text())
    for p,h in seal['sha256'].items():
        if sha(p) != h:
            raise RuntimeError('Source changed: ' + p)
    return seal
def load_original(window):
    if window not in ENGINES:
        raise ValueError('Only latest sealed 2022/2024 equity consumers. 2026 is diagnostic only.')
    seal = verified_manifest()
    directory,_ = ENGINES[window]
    source = EVENT_ROOT/directory/'engine.py'
    module = types.ModuleType('_original_ab_' + window)
    module.__file__ = str(source)
    sys.modules[module.__name__] = module
    # Exact source text, no dynamic-budget/global-constant monkeypatch.
    exec(compile(source.read_text(),str(source),'exec'),module.__dict__)
    assert tuple(str(getattr(module,k)) for k in ('NAV','INIT','SLOT','RISK')) == ('1200000','24000','48000','3000')
    module._no_budget_source_sha256 = sha(source)
    module._no_budget_window = window
    module._no_budget_runs = 0
    return module
def replay_no_budget(module, stop=None):
    """Replay original per-stock baseline, no shared capital or new close_q cap."""
    if module._no_budget_runs:
        raise RuntimeError('One replay per loaded source module; no silent reused state/cache')
    module._no_budget_runs += 1
    module.reset(True,'FULL')
    cutoff = module.END if stop is None else module.pd.Timestamp(stop)
    module.run_window('A_UNION_B',stop=cutoff)
    assert tuple(str(getattr(module,k)) for k in ('NAV','INIT','SLOT','RISK')) == ('1200000','24000','48000','3000')
    return module
def original_comparator(module):
    source = EVENT_ROOT/'relative_priority_equity_run_2022_v1/run.py'
    text = source.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='compare_table')
    env={'pd':module.pd,'np':module.np}
    exec(compile(ast.get_source_segment(text,node),str(source)+':definition_only','exec'),env)
    return env['compare_table']
def table_rows(module):
    return {name:getattr(module,attr) for name,attr in (
        ('ROUNDS','rounds'),('ACTIONS','actions'),('DECISIONS','decisions'),
        ('RANKING_AUDIT','ranking_audit'),('END_STATES','blocks'),
        ('REGISTRATIONS','registrations'),('CLAIM_LEDGER','claim_ledger'),
        ('PROFIT_GATES','marks'))}
def compare_original(module, stop=None):
    compare=original_comparator(module)
    directory,baseline=ENGINES[module._no_budget_window]
    keys={
        'ROUNDS':['round_id'],'ACTIONS':['round_id','day','side'],
        'DECISIONS':['event_id'],'RANKING_AUDIT':['event_id'],
        'END_STATES':['round_id'],'REGISTRATIONS':['arm','economic_event_id'],
        'CLAIM_LEDGER':['round_id','economic_event_id','day','event'],
        'PROFIT_GATES':['round_id','day','phase','caller'],
    }
    checks={}
    for name,rows in table_rows(module).items():
        if stop is not None and name in ('ROUNDS','END_STATES'):
            continue  # prefix-censor records cannot equal sealed full-run terminals
        expected=module.pd.read_csv(EVENT_ROOT/directory/baseline/(name+'.csv'),low_memory=False)
        expected=expected[expected.arm.eq('A_UNION_B')]
        if stop is not None:
            date_col='inventory_snapshot_day' if name=='REGISTRATIONS' else 'day'
            expected=expected[module.pd.to_datetime(expected[date_col])<=module.pd.Timestamp(stop)]
        actual=module.pd.DataFrame(rows)
        if actual.empty and expected.empty:
            checks[name]={'rows':0,'match':True,'empty':'explicit'}
        else:
            checks[name]=compare(actual,expected,keys[name])
    return checks
def export_new(module,destination,checks):
    destination=Path(destination);destination.mkdir(exist_ok=False)
    for name,rows in table_rows(module).items():
        with (destination/(name+'.csv')).open('x') as f:
            module.pd.DataFrame(rows).to_csv(f,index=False)
    payloads={'COMPARE_QA.json':checks,'CLAIMS.json':list(module.claims.values()),
              'BRIDGES.json':module.bridges,'CONSUMED_SOURCE_HASHES.json':module.hashes}
    for name,value in payloads.items():
        with (destination/name).open('x') as f:
            json.dump(value,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
    for p,h in module.hashes.items():
        assert sha(p)==h,('source drift',p)
    return {p.name:sha(p) for p in destination.iterdir() if p.is_file()}
