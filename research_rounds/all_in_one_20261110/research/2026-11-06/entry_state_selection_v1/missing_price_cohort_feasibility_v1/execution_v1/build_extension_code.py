from pathlib import Path
import hashlib,json,ast
O=Path(__file__).resolve().parent;R=O.parent.parent;J=R/'independent_channel_joint_economic_v1';B=R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(n,x):
 with (O/n).open('x') as f:f.write(x)
for n in ['joint_policy.py','execution_book.py','reporting.py','report_adapter.py']:put(n,(J/n).read_text())
put('cohort_config.py',f'''from pathlib import Path
O=Path(__file__).resolve().parent
R=Path({str(R)!r})
ORIGINAL_J=R/'independent_channel_joint_economic_v1'
ORIGINAL_BASE=R/'m3_stock_birth_during_sector_v1/cash_equity_baseline_2024_v1'
CONFIG={{'2023':('2023-01-01','2023-12-31'),'2024JanAug':('2024-01-01','2024-08-31')}}
TEMPLATE_ID='ORIGINAL_2024_AB_PRICE_165_NET80_STRICT_UNKNOWN_V1'
END='2026-06-30'
''')
# Fixed source translation only. Preserve old paths for all dependency hashes and evidence.
for w,(lo,hi) in {'2023':('2023-01-01','2023-12-31'),'2024JanAug':('2024-01-01','2024-08-31')}.items():
 s=(B/'engine.py').read_text();old="WINDOW='2024_924';START=pd.Timestamp('2024-09-01');BIRTH_END=pd.Timestamp('2024-12-31')";new=f"WINDOW={w!r};START=pd.Timestamp({lo!r});BIRTH_END=pd.Timestamp({hi!r})";assert s.count(old)==1;s=s.replace(old,new)
 old="ev=pd.read_csv(E/'SEALED_ALL_BIRTH_EVENTS.csv',parse_dates=['day','previous_common_day'],low_memory=False)";new=f"ev=pd.read_csv(Path({str(O.parent/'MISSING_WINDOW_AB_EVENTS.csv')!r}),parse_dates=['day','previous_common_day'],low_memory=False)";assert s.count(old)==1;s=s.replace(old,new);put('base_engine_'+w+'.py',s)
put('baseline_regression.py','''"""New-window definition/data loader. No old runner or historic loop is invoked."""
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
''')
put('market_adapter.py','''"""Exact original market adapter plus frozen missing-date native cache input."""
import importlib.util,sys
import pandas as pd
from cohort_config import O,ORIGINAL_J
spec=importlib.util.spec_from_file_location('_extension_original_market_adapter',ORIGINAL_J/'market_adapter.py')
original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
canonical_root=original.canonical_root
class MarketAdapter(original.MarketAdapter):
    def _load_qual(self,sid):
        if sid in self._qual:return
        super()._load_qual(sid)
        extra=pd.read_parquet(self._source(O/'NATIVE_QUAL_EXTRA.parquet'),filters=[('sid','==',sid)]).set_index('day')
        assert not self._qual[sid].index.intersection(extra.index).size
        self._qual[sid]=pd.concat([self._qual[sid],extra]).sort_index()
        assert not self._qual[sid].index.has_duplicates
''')
s=(J/'joint_engine.py').read_text();s=s.replace('from gates import PROTOCOL_SHA256, require_economic_authorization, claim_run_once','from gates import PROTOCOL_SHA256, require_economic_authorization, claim_run_once\nfrom cohort_config import CONFIG')
changes={"self.window = '2022' if window == '2022' else '2024_924'":"self.window = window\n        assert window in CONFIG", "self.start = pd.Timestamp('2022-01-01' if window == '2022' else '2024-09-01')":"self.start = pd.Timestamp(CONFIG[window][0])", "self.birth_end = pd.Timestamp('2022-12-31' if window == '2022' else '2024-12-31')":"self.birth_end = pd.Timestamp(CONFIG[window][1])", "p=O.parent/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'":"p=O/'PRICE_CANDIDATES.parquet'", "win='2022' if self.window=='2022' else '2024'":"win=self.window", "path=O.parent/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'":"path=O/'PRICE_CANDIDATES.parquet'"}
for old,new in changes.items():assert s.count(old)==1,(old,s.count(old));s=s.replace(old,new)
needle='            self.process_day(day,prevday,groups_ab.get(day,[]),groups_price.get(day,[]))';assert s.count(needle)==1;s=s.replace(needle,needle+"\n            if k%50==0:print('COHORT_DAY',self.window,str(day.date()),'states',len(self.states),'rounds',len(self.s.rounds),flush=True)")
put('joint_engine.py',s)
put('CODE_TRANSLATION_QA.json',json.dumps(dict(original_joint_sha256=sha(J/'joint_engine.py'),original_base_sha256=sha(B/'engine.py'),byte_identical_modules={n:sha(O/n) for n in ['joint_policy.py','execution_book.py','reporting.py','report_adapter.py']},joint_exact_text_replacements=changes,base_changes=['WINDOW/START/BIRTH_END','ev CSV input path'],no_economic_function_formula_edit=True),indent=2)+'\n')
