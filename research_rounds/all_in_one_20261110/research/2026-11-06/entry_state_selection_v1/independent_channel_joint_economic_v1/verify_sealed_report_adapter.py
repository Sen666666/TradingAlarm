"""Read-only real original AB ledger check. No engine import or economic runner.

Prints audit JSON; intentionally does not write results or calculate PRICE.
The duplicated arm below is the exact same sealed AB ledger used solely to
exercise the report's two-arm schema, not a newly evaluated strategy.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import pandas as pd
from report_adapter import read_sealed_baseline, adapt_engine
from reporting import build_report


def verify():
    root=Path(__file__).resolve().parent
    pool=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    roster=sorted(r['symbol'] for r in json.loads(pool.read_text()))
    assert len(roster)==len(set(roster))==1709
    result=[]
    for window in ('2022','2024'):
        directory=root/('baseline_regression_'+window)
        expected=json.loads((directory/'REGRESSION_OUTPUT_HASHES.json').read_text())
        hashes={}
        for filename in ('ROUNDS.csv','ACTIONS.csv','CLAIMS.json'):
            hashes[filename]=hashlib.sha256((directory/filename).read_bytes()).hexdigest()
            assert hashes[filename]==expected[filename],filename
        s=read_sealed_baseline(directory,[])
        a=adapt_engine(s,roster,window,'baseline',baseline=True)
        b=adapt_engine(s,roster,window,'same_sealed_ab',baseline=True)
        fields=('actions','claims','states','terminal_marks','coverage','core_diagnostics','closed_cash_checks')
        r=build_report(roster,['2022' if window=='2022' else '2024_924'],
            ['baseline','same_sealed_ab'],['AB','PRICE'],**{k:a[k]+b[k] for k in fields})
        unknown=[x for x in r['lane_rows'] if x['arm']=='baseline' and x['lane']=='AB' and x['unknown_liability']]
        assert all(x['known_total_pnl'] is None for x in unknown)
        assert all(d['joint_minus_baseline'] in (0,None) for d in r['differences'])
        result.append(dict(window=window,result='PASS_SEALED_AB_ONLY',fixed_roster=1709,
            input_sha256=hashes,rounds=len(s.rounds),native_actions=len(s.actions),
            normalized_actions=len(a['actions']),claims=len(a['claims']),
            closed_round_reconciliations=len(a['closed_cash_checks']),
            unknown_stock_count=len(unknown),unknown_known_realized_plus_income=sum(x['identifiable_pnl'] for x in unknown),
            unknown_remaining_cost=sum(x['remaining_cost'] for x in unknown),
            states=dict(Counter(x['status'] for x in a['states'] if x['lane']=='AB')),
            known_zero_price_lane_count=sum(x['status']=='NEVER_ENTERED' for x in a['states'] if x['lane']=='PRICE'),
            limitations=['No original engine loaded: independent dated CORE fee and rights-source coverage intentionally unavailable.',
                        'No original permit collection supplied: this check does not certify permits.',
                        'No PRICE economics evaluated.'],
            blockers=dict(Counter(x.split(':')[0] for x in a['blockers']))))
    return result


if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
