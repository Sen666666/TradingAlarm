from pathlib import Path
import sys,time,json,gzip,importlib.util,hashlib,copy
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/n1-structural-finite-20261029';SRC=ROOT/'research_rounds/broad-stage-reentry-20261029';t=time.monotonic()
sys.path.insert(0,str(SRC/'code'));sp=importlib.util.spec_from_file_location('finite_original_n1',SRC/'code/study.py');M=importlib.util.module_from_spec(sp);sys.modules[sp.name]=M;sp.loader.exec_module(M)
pp=importlib.util.spec_from_file_location('finite_new_protection',O/'code/policy.py');P=importlib.util.module_from_spec(pp);pp.loader.exec_module(P)
from types import SimpleNamespace as S
from decimal import Decimal as D
orig=M.advance;nc=sys.modules['policy'].new_candidates
b=dict(kind='trial',floor=D(12),entry_cost=D(10),opened='2024-01-02 09:30:00+08:00')
none=S(event=0,pivot_date=None,pivot=None);c0=S(receipt=False,candidate=None);yes=S(receipt=True,candidate=11)
x=copy.deepcopy(b);assert P.structural_advance(x,'2024-01-03',D(11),D(8),none,c0,orig,nc)=='structural_support_reset' and x['kind']=='trial'
x=copy.deepcopy(b);assert P.structural_advance(x,'2024-01-03',D(11),D(8),none,yes,orig,nc)=='promote' and x['kind']=='core' and x['floor']==8
for close in [D(11),D(13)]:
 a=dict(b,kind='mobile');bb=copy.deepcopy(a);assert P.structural_advance(a,'2024-01-03',close,D(8),none,yes,orig,nc)==orig(bb,'2024-01-03',close,D(8),none,yes) and a==bb
semantic=time.monotonic()-t;run=M.Pilot(only=['N1']);init=time.monotonic()-t;t1=time.monotonic();run.run('2024-02-08');elapsed=time.monotonic()-t1
old=json.loads((SRC/'results/N1.json').read_text());new=M.N.encoded(dict(trades=run.accounts['N1'].trades,layers=run.accounts['N1'].layers,audit=run.accounts['N1'].audit_log,decisions=run.accounts['N1'].decisions));finish='2024-02-08';actual={k:[x for x in old[k] if x.get('at',x.get('receipt',{}).get('at',x.get('receivable',{}).get('ex_at',''))))[:10]<=finish] for k in ['trades','audit','decisions']}
for k in ['trades','audit','decisions']:assert new[k]==actual[k],k
with gzip.open(SRC/'results/daily.jsonl.gz','rt') as f:days=[json.loads(l) for l in f if '"account": "N1"' in l]
expected=[r for r in days if r['at'][:10]<=finish];assert M.N.encoded(run.daily)==expected
n=len(run.daily);estimated=elapsed/n*681;result=dict(passed=True,semantic_seconds=semantic,initialization_seconds=init,prefix_simulation_seconds=elapsed,prefix_closes=n,prefix_fills=len(new['trades']),baseline_exact=True,estimated_single_path_seconds=estimated,estimated_seven_paths_seconds=estimated*7,total_preflight_seconds=time.monotonic()-t,semantic_checks=['trial_retained_without_confirmation','cost_confirmation_promotes_core','mobile_identical','original_planning_ACT_entry_add_reentry_unchanged'])
(O/'PREFLIGHT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False),flush=True)
