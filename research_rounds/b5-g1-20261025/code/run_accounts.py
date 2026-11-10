"""Freeze once, then run only the four predeclared policies and three stresses."""
import sys
import pandas as pd
from g1util import *

def verify():
    f=read(HERE/'freeze.json');verify_hashes(f['sha256']);verify_hashes(read(HERE/'old-identity-before.json')['sha256']);return f

def freeze():
    assert read(HERE/'validation/checks.json')['passed']
    assert not (HERE/'accounts').exists()
    verify_hashes(read(HERE/'old-identity-before.json')['sha256'])
    paths=[HERE/'PROTOCOL.md',HERE/'RAW_REVIEW.md',HERE/'PRE_ACCOUNT_REVIEW.md',HERE/'cases.json']
    paths+=list((HERE/'code').glob('*.py'))
    for folder in ['inputs','replay','grading','prepared','validation']:
        paths += [p for p in (HERE/folder).rglob('*') if p.is_file()]
    paths += [ROOT/'research_rounds/temperature-regime-comparison-20261025/code/engine.py']
    write(HERE/'freeze.json',dict(recorded_at=now(),status='before_economic_accounts',new_score_candidates=1,mechanism_revisions_after_grades=0,accounts_run=0,planned_accounts=216,main_cases=11,continuous_cases=7,policies=POLICIES,scenarios=SCENARIOS,sha256={str(p.relative_to(ROOT)):sha(p) for p in paths},history='seen_development_overlapping',grade_is_ordinal=True,position_policy_changed=False))
    print(dict(frozen=len(paths),planned_accounts=216),flush=True)

def run():
    verify();out=HERE/'accounts';out.mkdir(exist_ok=False);rows=[];control=[];eng=engine();oldsummary=pd.read_csv(OLD/'results/v0/summary.csv',float_precision='round_trip')
    for c in read(HERE/'cases.json'):
        d=pd.read_parquet(HERE/'inputs'/f"{c['symbol']}.parquet").loc[c['start']:c['end']];ini=read(HERE/'prepared'/c['id']/'initial.json')
        for policy in POLICIES:
            s=pd.read_parquet(HERE/'prepared'/c['id']/f'{policy}.parquet')
            for sc,cfg in SCENARIOS.items():
                st,l,t,f,o=eng.backtest(d,s,ini[policy],c['symbol'],cfg,policy=policy,entry_event_column='buy_event' if policy in ['G1_I','G1_IX'] else None)
                key='__'.join([c['id'],policy,sc]);p=out/key;p.mkdir();l.to_parquet(p/'ledger.parquet');t.to_csv(p/'trades.csv',index=False);f.to_csv(p/'fills.csv',index=False);o.to_csv(p/'orders.csv',index=False)
                if policy=='E0':
                    oldp=OLD/'results/v0/accounts'/key
                    pd.testing.assert_frame_equal(l,pd.read_parquet(oldp/'ledger.parquet'),check_exact=True,check_freq=False)
                    pd.testing.assert_frame_equal(t,pd.read_csv(oldp/'trades.csv',float_precision='round_trip'),check_exact=True)
                    old=oldsummary.loc[oldsummary.key.eq(key)].iloc[0]
                    assert st['net_return']==old.net_return and st['max_drawdown']==old.max_drawdown
                    control.append(dict(key=key,ledger_exact=True,trades_exact=True,summary_exact=True))
                rows.append(dict(key=key,case=c['id'],symbol=c['symbol'],name=c['name'],type=c['type'],role=c['role'],start=c['start'],end=c['end'],policy=policy,scenario=sc,carry_in=ini[policy]['active'],**st))
        print(dict(completed=c['id']),flush=True)
    assert len(rows)==216 and len(control)==54
    pd.DataFrame(rows).to_csv(HERE/'summary.csv',index=False);pd.DataFrame(control).to_csv(HERE/'control-identity.csv',index=False)
    write(HERE/'economic-run.json',dict(recorded_at=now(),accounts=216,E0_control_replays=54,enhanced_accounts=162,formula_changes_after_results=0,freeze_sha256=sha(HERE/'freeze.json')))

if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='run':run()
    else:raise ValueError(sys.argv[1])
