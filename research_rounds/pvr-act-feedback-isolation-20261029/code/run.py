"""Post-hoc exogenous ACT calendar diagnostic, four paths only."""
from pathlib import Path
import sys,json,time,hashlib,importlib.util,gzip,shutil,signal
from decimal import Decimal as D
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/pvr-act-feedback-isolation-20261029';PRIOR=ROOT/'research_rounds/pvr-local-finite-capital-20261029';OLD=ROOT/'research_rounds/pvr-act-comparison-20261027'
sys.path.insert(0,str(PRIOR/'code'))
from local_adapter import Adapter
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
stage=sys.argv[1];started=time.monotonic();budget=read(O/'COMPUTE_BUDGET.json') if (O/'COMPUTE_BUDGET.json').exists() else dict(limit_seconds=300,used_seconds=0,stages=[]);left=300-budget['used_seconds'];assert left>0
def timeout(*_):raise TimeoutError('Cumulative300s diagnostic budget exhausted')
signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,left);status='failed';error=None
try:
    for p,expected in read(O/'INPUT_IDENTITY.json')['sha256'].items():assert sha(p)==expected,p
    spec=importlib.util.spec_from_file_location('old_frozen_pvr',OLD/'code/experiment.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P);P.setup('RS');E=P.E;R=P.R;A=P.A
    calendar={r['at']:r for r in read(O/'EXOGENOUS_CALENDAR.json')['checkpoints']};oldstep=E.risk_policy.step
    def fixed_step(a,at,mode):
        assert mode=='ACT20_BREAK';src=calendar[str(at)]
        if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
        state=dict(a.risk_state);day=pd.Timestamp(at.date());i=E.risk_policy.RECOVERY.index.searchsorted(day,side='right')-1
        if i<0:fast=False;br=False
        else:r=E.risk_policy.RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if E.risk_policy.RECOVERY.index[i]==day else False
        flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
        state['peak']=max(state['peak'],a.current_nav) if state['on'] else state['peak'];dd=1-a.current_nav/state['peak'];event=src['event']
        if state['on']:
            assert event!='resume'
            if event=='pause':state.update(on=False,saw_off=not fast)
        else:
            assert event!='pause';state['saw_off']=state['saw_off'] or not fast
            if event=='resume':
                assert flat,(str(at),'recorded resume calendar reaches non-flat diagnostic arm; stop rather than change semantics')
                assert br,(str(at),'source resume must satisfy frozen breakout')
                state.update(on=True,peak=a.current_nav,episode=state['episode']+1,saw_off=False)
        state['previous_fast']=fast;assert state['on']==src['on'] and state['episode']==src['episode']
        a.risk_state=state
        # Preserve the original risk log schema; boundary is documented externally.
        a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**state)
    E.risk_policy.step=fixed_step
    if stage=='replication':name='original-base';stresses=['base'];local=False
    elif stage=='original-cost2':
        assert read(O/'REPLICATION_VERIFICATION.json')['passed'];name=stage;stresses=['cost2'];local=False
    elif stage=='local':
        assert read(O/'REPLICATION_VERIFICATION.json')['passed'];name=stage;stresses=['base','cost2'];local=True
    else:raise ValueError(stage)
    target=O/name;target.mkdir(exist_ok=False);shutil.copy2(OLD/'execution-rules-v2.json',target/'execution-rules-v2.json');adapter=None
    if local:
        risk=pd.read_parquet(ROOT/'research_rounds/pvr-incremental-order-20261029/risk-set.parquet');adapter=Adapter(P,risk,O/'local-admission-trace.jsonl.gz');adapter.install()
    try:R.run(target/'accounts-v2',modes=['I'],stresses=stresses,end='2026-10-27',technical=False)
    finally:
        if adapter:adapter.uninstall()
        E.risk_policy.step=oldstep
    A.CORE=OLD/'input';A.PREP=Path(read(OLD/'input.json')['snapshot']['path']);A.HERE=target;A.main('full')
    daily=rows(target/'accounts-v2/daily.jsonl.gz');checks=[]
    for sc in stresses:
        aid='I__S0_'+sc;obj=read(target/'accounts-v2'/f'{aid}.json');risklogs=[r for r in obj['audit_log'] if r['kind']=='risk_checkpoint'];ds=[r for r in daily if r['account']==aid];assert len(risklogs)==len(calendar)==681
        paused_days=0;held_exit_checks=0
        for r,d in zip(risklogs,ds):
            src=calendar[r['at']];assert r['event']==src['event'] and r['on']==src['on']
            if not r['on']:
                paused_days+=1;assert not d['pending_buys'],(aid,r['at'],'paused arm retains buy order')
                held={sid for sid,q in d['positions'].items() if q};assert held<=set(d['pending_sells']),(aid,r['at'],'pause did not latch forced exits',held,d['pending_sells']);held_exit_checks+=len(held)
            if r['event']=='resume':assert r['flat']
        checks.append(dict(account=aid,calendar_daily_rows=681,paused_days=paused_days,held_forced_exit_checks=held_exit_checks,full_on_and_actions_exact=True,resume_flat_checked=True))
    save(target/'CALENDAR_VERIFICATION.json',dict(passed=True,checks=checks,original_exit_and_entry_override_unmodified=True,accounting=read(target/'analysis/accounting.json')))
    if stage=='replication':
        aid='I__S0_base';oldroot=PRIOR/'baseline/accounts-v2';ref=[r for r in rows(oldroot/'daily.jsonl.gz') if r['account']==aid];assert daily==ref,'calendar base daily replication mismatch'
        dd=rows(target/'accounts-v2/decisions.jsonl.gz');od=[r for r in rows(oldroot/'decisions.jsonl.gz') if r['account']==aid];assert dd==od,'calendar base decisions mismatch';assert read(target/'accounts-v2'/f'{aid}.json')==read(oldroot/f'{aid}.json'),'calendar base full account mismatch'
        save(O/'REPLICATION_VERIFICATION.json',dict(passed=True,daily_rows_exact=len(ref),decisions_exact=len(dd),full_account_exact=True,calendar_semantics=checks,independent_accounting=read(target/'analysis/accounting.json')))
    status='complete';print(json.dumps(dict(stage=stage,passed=True,seconds=time.monotonic()-started,checks=checks)),flush=True)
except BaseException as exc:error=repr(exc);raise
finally:
    signal.setitimer(signal.ITIMER_REAL,0);spent=time.monotonic()-started;budget['used_seconds']+=spent;budget['stages'].append(dict(stage=stage,status=status,seconds=spent,error=error));save(O/'COMPUTE_BUDGET.json',budget)
