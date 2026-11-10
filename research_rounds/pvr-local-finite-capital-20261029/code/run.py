"""Scoped six-path ACT experiment. Original engine is never edited."""
from pathlib import Path
import sys, json, time, hashlib, importlib.util, shutil, gzip, signal

ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
O=ROOT/'research_rounds/pvr-local-finite-capital-20261029'
OLD=ROOT/'research_rounds/pvr-act-comparison-20261027'
def read(p): return json.loads(Path(p).read_text())
def save(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
stage=sys.argv[1]; started=time.monotonic()
budget=read(O/'COMPUTE_BUDGET.json') if (O/'COMPUTE_BUDGET.json').exists() else dict(limit_seconds=300,used_seconds=0,stages=[])
remaining=budget['limit_seconds']-budget['used_seconds']; assert remaining>0, budget
def timeout(*_): raise TimeoutError('Frozen cumulative 300s calculation budget exhausted')
signal.signal(signal.SIGALRM,timeout); signal.setitimer(signal.ITIMER_REAL,remaining)
status='failed'; error=None
try:
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
    spec=importlib.util.spec_from_file_location('frozen_pvr_experiment',OLD/'code/experiment.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
    original=P.setup('RS');R=P.R;E=P.E;A=P.A
    if stage=='baseline':
        target=O/'baseline';target.mkdir(exist_ok=False);shutil.copy2(OLD/'execution-rules-v2.json',target/'execution-rules-v2.json')
        R.run(target/'accounts-v2',modes=['I'],stresses=['base','cost2','delay1'],end='2026-10-27',technical=False)
        A.CORE=OLD/'input';A.PREP=Path(read(OLD/'input.json')['snapshot']['path']);A.HERE=target;A.main('full')
        now=rows(target/'accounts-v2/daily.jsonl.gz');old=rows(OLD/'RS/accounts-v2/daily.jsonl.gz');assert now==old,'full daily rows differ'
        nd=rows(target/'accounts-v2/decisions.jsonl.gz');od=rows(OLD/'RS/accounts-v2/decisions.jsonl.gz');assert nd==od,'full decisions differ'
        ac=[]
        for scenario in ['base','cost2','delay1']:
            aid='I__S0_'+scenario;a=read(target/'accounts-v2'/f'{aid}.json');b=read(OLD/'RS/accounts-v2'/f'{aid}.json');assert a==b,(aid,'full account differs')
            ac.append(dict(account=aid,fills=len(a['fills']),all_account_fields_exact=True))
        save(O/'BASELINE_VERIFICATION.json',dict(passed=True,full_daily_rows_exact=len(now),full_decision_rows_exact=len(nd),accounts=ac,independent_accounting=read(target/'analysis/accounting.json'),funding=read(target/'analysis/funding.json')))
        print(json.dumps(dict(stage=stage,passed=True,days=len(now),accounts=ac,seconds=time.monotonic()-started)),flush=True)
    else:
        raise ValueError(stage)
    status='complete'
except BaseException as exc:
    error=repr(exc);raise
finally:
    signal.setitimer(signal.ITIMER_REAL,0)
    spent=time.monotonic()-started;budget['used_seconds']+=spent;budget['stages'].append(dict(stage=stage,status=status,seconds=spent,error=error));save(O/'COMPUTE_BUDGET.json',budget)
