"""New-window definition/data loader. No old runner or historic loop is invoked."""
import types,sys,hashlib
from pathlib import Path
from cohort_config import O,ORIGINAL_BASE,CONFIG

def load_engine(window):
    assert window in CONFIG
    p=O/('base_engine_'+window+'.py')
    s=types.ModuleType('_extension_original_2024_'+window)
    # Original __file__ intentionally retains source-data/evidence routes. Source
    # bytes actually executed are separately frozen as base_engine_<window>.py.
    s.__file__=str(ORIGINAL_BASE/'engine.py');sys.modules[s.__name__]=s
    exec(compile(p.read_text(),str(p),'exec'),s.__dict__)
    assert not s.rounds and not s.actions and not s.claims
    assert s.WINDOW==window and len(s.EVENTS)==165
    assert str(s.INIT)=='24000' and str(s.SLOT)=='48000' and str(s.RISK)=='3000'
    for path in [p,O/'cohort_config.py',O/'baseline_regression.py',O.parent/'MISSING_WINDOW_AB_EVENTS.csv']:
        s.hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return s
