"""Approved local ordering sample and three full ACT paths, cumulative time cap."""
from pathlib import Path
import sys,json,time,hashlib,importlib.util,shutil,gzip,signal
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/pvr-local-finite-capital-20261029';OLD=ROOT/'research_rounds/pvr-act-comparison-20261027';PV=ROOT/'research_rounds/pvr-incremental-order-20261029'
sys.path.insert(0,str(O/'code'))
from local_adapter import Adapter,industry_order
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
started=time.monotonic();budget=read(O/'COMPUTE_BUDGET.json');remaining=300-budget['used_seconds'];assert remaining>0
def timeout(*_):raise TimeoutError('Frozen cumulative 300s calculation budget exhausted')
signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,remaining)
status='failed';error=None;times={}
try:
    assert read(O/'BASELINE_VERIFICATION.json')['passed']
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
    risk=pd.read_parquet(PV/'risk-set.parquet');ref=pd.read_csv(O/'potential-queues.csv');ref.date=ref.date.astype(str);ref=ref.sort_values(['date','sector','position']);qref={(d,s):list(g.symbol) for (d,s),g in ref.groupby(['date','sector'],sort=True)}
    for (day,sector),g in risk.groupby(['date','sector'],sort=True):
        rank,_=industry_order(g.to_dict('records'));assert rank==qref[(str(day.date()),sector)],(day,sector)
    times['input_and_policy_identity_seconds']=time.monotonic()-started
    spec=importlib.util.spec_from_file_location('frozen_pvr_experiment',OLD/'code/experiment.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P);original=P.setup('RS');R=P.R;A=P.A
    target=O/'local';target.mkdir(exist_ok=False);shutil.copy2(OLD/'execution-rules-v2.json',target/'execution-rules-v2.json')
    t=time.monotonic();adapter=Adapter(P,risk[risk.date.le('2024-08-30')],O/'sample-admission-trace.jsonl.gz');adapter.install()
    try:R.run(target/'technical/short-v2',modes=['I'],stresses=['base'],end='2024-08-30',cutoff='2024-08-30',technical=True)
    finally:adapter.uninstall()
    A.CORE=OLD/'input';A.PREP=Path(read(OLD/'input.json')['snapshot']['path']);A.HERE=target;A.main('short')
    sample_trace=rows(O/'sample-admission-trace.jsonl.gz');sample_cases=pd.read_csv(O/'potential-industry-heads.csv');sample_cases=sample_cases[sample_cases.changed].head(6)
    for case in sample_cases.itertuples():
        g=risk[risk.date.eq(case.date)&risk.sector.eq(case.sector)];rank,ss=industry_order(g.to_dict('records'));assert rank[0]==case.chosen
    save(O/'SAMPLE_VERIFICATION.json',dict(passed=True,policy_all_4941_industry_days_matches_preflight=True,chronological_samples=sample_cases.to_dict('records'),native_sample_accounting=read(target/'technical/short-analysis/accounting.json'),counters=dict(adapter.counts),same_state_recommendation_changes=sum(r['changed'] for c in sample_trace for r in c['recommendations']),physical_input_cutoff='2024-08-30',future_risk_rows_removed=True))
    times['sample_and_audit_seconds']=time.monotonic()-t
    print(json.dumps(dict(stage='sample_passed',seconds=times['sample_and_audit_seconds'],recommendation_changes=sum(r['changed'] for c in sample_trace for r in c['recommendations']),counters=dict(adapter.counts)),ensure_ascii=False),flush=True)
    t=time.monotonic();adapter=Adapter(P,risk,O/'admission-trace.jsonl.gz');adapter.install()
    try:R.run(target/'accounts-v2',modes=['I'],stresses=['base','cost2','delay1'],end='2026-10-27',technical=False)
    finally:adapter.uninstall()
    times['full_replay_including_load_seconds']=time.monotonic()-t
    t=time.monotonic();A.main('full');times['full_native_audit_seconds']=time.monotonic()-t
    sample=rows(target/'technical/short-v2/daily.jsonl.gz');full=rows(target/'accounts-v2/daily.jsonl.gz');expected=[r for r in full if r['account']=='I__S0_base' and r['at'][:10]<='2024-08-30'];assert sample==expected,'physical financial prefix daily mismatch'
    sf=read(target/'technical/short-v2/I__S0_base.json')['fills'];ff=read(target/'accounts-v2/I__S0_base.json')['fills'];assert sf==[f for f in ff if f['at'][:10]<='2024-08-30']
    sd=rows(target/'technical/short-v2/decisions.jsonl.gz');fd=rows(target/'accounts-v2/decisions.jsonl.gz');assert sd==[r for r in fd if r['account']=='I__S0_base' and r['at'][:10]<='2024-08-30']
    save(O/'LOCAL_VERIFICATION.json',dict(passed=True,physical_prefix_daily_rows=len(sample),physical_prefix_fills=len(sf),physical_prefix_decisions=len(sd),counters=dict(adapter.counts),accounting=read(target/'analysis/accounting.json'),funding=read(target/'analysis/funding.json'),times=times))
    status='complete';print(json.dumps(dict(stage='local_full_complete',seconds=time.monotonic()-started,times=times,counters=dict(adapter.counts)),ensure_ascii=False),flush=True)
except BaseException as exc:error=repr(exc);raise
finally:
    signal.setitimer(signal.ITIMER_REAL,0);spent=time.monotonic()-started;budget['used_seconds']+=spent;budget['stages'].append(dict(stage='local_sample_and_full',status=status,seconds=spent,error=error));save(O/'COMPUTE_BUDGET.json',budget)
