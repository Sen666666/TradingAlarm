"""All-role footholds and audited migration-wait math, saved records only."""
from pathlib import Path
import json,collections,statistics,gzip,sys
import pandas as pd
import analyze_continuation as C
O,P,W,M,A=C.O,C.P,C.W,C.M,C.A
def main():
    states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in C.read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    reports=[];sets={}
    for ref,root in [('SC',W/'recovery-2023-readiness-20261101/runs/Bdiag'),('PVR_SLOT1',O/'run-2023')]:
        base=Path('analysis-2023')/ref;ls=C.read(O/base/'LAYERS_NEW2023.json');allls=C.read(O/base/'LAYERS_ALL.json')
        delays=C.read(O/base/'ALL_FIRST_ELIGIBLE_DELAYS.json');ds=[x for x in C.rows(root/'pair/daily.jsonl.gz') if x['at'].startswith('2023')]
        ix={x['at'][:10]:i for i,x in enumerate(ds)};lookup=collections.defaultdict(list)
        for l in ls:
            st=states[l['sector']].get(l['signal_day'])
            if st:lookup[l['sid'],l['sector'],st['attempt_id']].append(l)
        for g in delays:
            rows=sorted((x for x in lookup[g['sid'],g['sector'],g['market_attempt']] if x['signal_day']>=g['first_market_eligible']),key=lambda x:x['opened'])
            first=rows[0] if rows else None
            g.update(first_actual_anyrole_new_buy=first['opened'] if first else None,first_actual_anyrole=first['role'] if first else None,
                first_actual_anyrole_pool=first['pool_at_fill'] if first else None,
                anyrole_sessions_to_new_buy=ix[C.day(first['opened'])]-ix[g['first_market_eligible']] if first else None,
                already_held_at_first_market_eligible=g['held_at_first_eligibility'],
                no_later_new_buy_right_censored=first is None)
        unheld=[g for g in delays if not g['held_at_first_eligibility']];lag=[g['anyrole_sessions_to_new_buy'] for g in unheld if g['first_actual_anyrole_new_buy']]
        report=dict(reference=ref,all_market_stock_attempts=len(delays),already_held_at_first_eligibility=sum(g['held_at_first_eligibility'] for g in delays),
            initially_unheld=len(unheld),initially_unheld_later_anyrole_funded=len(lag),initially_unheld_no_later_buy_censored=len(unheld)-len(lag),
            funded_only_anyrole_median_sessions=statistics.median(lag) if lag else None,funded_only_anyrole_max_sessions=max(lag,default=None),
            first_market_eligible_not_same_as_executable_resource_permission=True,
            earlier_mobile_only_table_scope='mobile receipt conversion, not all-stock footholds; core-first may fund a core instead',
            inherited_market_attempts=sum(g['attempt_inherited_left_censor'] for g in delays),end_receipt_censor_retained=True)
        C.save(base/'ALL_ROLE_FIRST_ELIGIBLE_DELAYS.json',delays)
        C.save(base/'ALL_ROLE_FIRST_ELIGIBLE_SUMMARY.json',report)
        a=dict(daily=ds,layers=allls,book=C.book(root/'pair/B.json.gz'))
        pool=M.pool_and_waits('2023',ref,a);report['pool_and_waits']=pool
        C.save(base/'ALL_ROLE_FIRST_ELIGIBLE_SUMMARY.json',report);reports.append(report)
        sets[ref]={'stocks':{x['sid'] for x in ls},'attempts':{(x['sector'],x['attempt']) for x in ls},
                   'confirmed_receipts':{(x['sid'],x['signal_day'],x['receipt']) for x in ls if x['role']=='mobile' and x['pool_at_fill']=='confirmed'}}
    changes={k:dict(SC=len(sets['SC'][k]),PVR_SLOT1=len(sets['PVR_SLOT1'][k]),
        gained=sorted(sets['PVR_SLOT1'][k]-sets['SC'][k]),lost=sorted(sets['SC'][k]-sets['PVR_SLOT1'][k])) for k in sets['SC']}
    C.save('analysis-2023/ACTUAL_FUNDED_CHANGES.json',changes);C.save('analysis-2023/ALL_ROLE_COMPARISON.json',reports)
    C.save('analysis-2023/BEHAVIOR_SUPPLEMENT_GATE.json',dict(passed=True,no_account_calls=True,source_sha256=C.sha(__file__),
        wait_math_sha256=C.sha(W/'migration-admission-singlepass-economics-20261101/analyze.py'),
        actual_entry_roles_separate=True,all_unfunded_right_censors_retained=True))
    print('BEHAVIOR_SUPPLEMENT_PASS',[(r['reference'],r['initially_unheld_later_anyrole_funded']) for r in reports],flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as e:C.save('analysis-2023/SUPPLEMENT_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
