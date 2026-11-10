"""Frozen original input loaders and file/initialization safety only."""
from pathlib import Path
import sys
import native_rank as N
J, L, IO, O, W = N.J, N.L, N.IO, N.O, N.W
WINDOWS = {'2022': ('2022-01-01','2022-12-30','2022-01-05'),
           '2025_26': ('2025-07-01','2026-06-30','2025-07-02')}

def initialize(factory, root, action):
    try: return factory()
    except BaseException as e:
        IO.write_json(Path(root)/'failure/INITIALIZATION_ERROR.json',
                      dict(action=action, type=type(e).__name__, reason=str(e)))
        raise

def inputs(window):
    start, end, cut = WINDOWS[window]
    sys.path.insert(0, str(W/'q2-normal-continuation-20261031'))
    import continuation as E
    if window == '2022':
        Y = J.W.load('PVR_SLOT1_frozen_2022_input_loader', W/'2022-normal-reference-20261031/adapter.py')
        old = Y.save
        try:
            Y.save = lambda path, value: IO.write_json(O/'input-readiness'/window/Path(path).name, J.W.canon(value))
            value = Y.inputs()
        finally: Y.save = old
    else:
        J.START, J.END = start, end
        value = E.inputs('universe')
    J.START, J.END = start, end
    return value

def canonical_identity(identity):
    return {k:v for k,v in identity.items() if k != 'seconds'}

def freeze():
    result = N.source_freeze()
    local = ['export_scores.py','test_rank.py','execution_support.py','preflight.py','run_trial.py',
             'CONTRACT.txt','AUTHORIZATION_SCOPE.txt']
    other = [W/'pvr-current-v3-information-capital-20261101/original_score_function.py',
             W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',
             W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',
             W/'universe-cp1-inputs-20261031/FREEZE.json',
             W/'q2-normal-continuation-20261031/continuation.py',
             W/'2022-normal-reference-20261031/adapter.py',
             W/'2022-normal-reference-20261031/inputs/MANIFEST.json',
             W/'2022-normal-reference-20261031/inputs/COMPLETION.json',
             J.M.O/'recovery.csv', J.M.P/'h1.npz']
    for p in [O/n for n in local]+other:
        result[str(p.resolve())] = N.sha(p)
    return result

def kwargs(cp, states, ir):
    return dict(stock_cp=cp, industry_states=states, industry_receipts=ir)

def physical_inputs(shared, receipts, cp, states, ir, cut):
    return (J.W.physical(shared, cut),
            {s:{d:x for d,x in rs.items() if d<=cut} for s,rs in receipts.items()},
            dict(stock_cp={s:f.loc[:cut] for s,f in cp.items()},
                 industry_states={s:[x for x in rs if x['day']<=cut] for s,rs in states.items()},
                 industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut}))
