"""Unique G2 entrypoint: one fixed joint arm, sealed baseline, posterior reports.

Importing this module never loads engines or runs history. No retry, parameter
override, alternate strategy, or PRICE sample-run option exists.
"""
from pathlib import Path
from dataclasses import asdict, is_dataclass
from enum import Enum
from collections import Counter
import argparse
import json
import math
import time

from gates import O, sha, require_economic_authorization


def clean(value):
    if is_dataclass(value):return clean(asdict(value))
    if isinstance(value, Enum):return value.value
    if isinstance(value, dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    if hasattr(value,'item'):
        try:return clean(value.item())
        except (ValueError,TypeError):pass
    return value


def save(path,value):
    with Path(path).open('x') as f:
        json.dump(clean(value),f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
        f.write('\n')


def verify_inputs(approved, consumer=None):
    plan={str(Path(p).resolve()):h for p,h in approved['input_sha256'].items()}
    for p,h in plan.items():assert sha(p)==h,('FINAL_INPUT_DRIFT',p)
    for name,h in approved['code_sha256'].items():assert sha(O/name)==h,('FINAL_CODE_DRIFT',name)
    if consumer is not None:
        for p,h in consumer.s.hashes.items():
            assert plan.get(str(Path(p).resolve()))==h,('UNPLANNED_OR_CHANGED_AB_INPUT',p)
        consumer.market.verify_sources()


def core_summary(report):
    stocks=report['stock_rows']
    index={(x['sid'],x['arm']):x for x in stocks}
    common=report['summary'][0]['common_covered_sids']
    paired=[(index[sid,'baseline'],index[sid,'joint']) for sid in common]
    deltas=[r for r in report['differences'] if r['common_covered']]
    buys=[a for a in report.get('normalized_actions',[]) if a['side']=='BUY' and a['q']>0]
    entered={arm:{a['sid'] for a in buys if a['arm']==arm} for arm in ('baseline','joint')}
    round_counts={arm:Counter({sid:len({a['round_id'] for a in buys if a['arm']==arm and a['sid']==sid})
        for sid in entered[arm]}) for arm in ('baseline','joint')}
    summary=dict(fixed_stocks=len(stocks)//2, common_comparable_stocks=len(common),
        common_at_least_one_entered=sum(sid in entered['baseline'] or sid in entered['joint'] for sid in common),
        common_both_never_entered=sum(sid not in entered['baseline'] and sid not in entered['joint'] for sid in common),
        noncomparable_stocks=len(stocks)//2-len(common),
        common_baseline_net=sum(b['known_total_pnl'] for b,j in paired),
        common_joint_net=sum(j['known_total_pnl'] for b,j in paired),
        common_joint_minus_baseline=sum(d['joint_minus_baseline'] for d in deltas),
        common_price_contribution=sum(d['lane_contributions']['PRICE'] for d in deltas),
        common_ab_path_delta=sum(d['lane_contributions']['AB'] for d in deltas),
        arm_unknown_stocks={a:sum(x['unknown_liability'] for x in stocks if x['arm']==a) for a in ('baseline','joint')},
        arm_financial_uncovered_stocks={a:sum(not x['financial_covered'] for x in stocks if x['arm']==a) for a in ('baseline','joint')},
        arm_never_entered_stocks={a:sum(x['never_entered'] for x in stocks if x['arm']==a) for a in ('baseline','joint')},
        actual_entered_stocks={arm:len(sids) for arm,sids in entered.items()},
        joint_newly_entered_stocks=len(entered['joint']-entered['baseline']),
        joint_no_longer_entered_stocks=len(entered['baseline']-entered['joint']),
        repeated_participation_stocks={arm:sum(n>1 for n in counts.values()) for arm,counts in round_counts.items()},
        actual_entered_rounds={arm:sum(counts.values()) for arm,counts in round_counts.items()},
        original_ab_permits_exact=report['permit_exact_verified'],
        pvr_funnel=report['pvr_stage_diagnostics'],
        report_blockers=report['adapter_blockers'],
        economic_model='CONDITIONAL_NEXT_COMMON_OPEN_FULL_FILL_PROXY_NOT_ACCOUNT_RETURN',
        real_orders='NOT_PROVIDED',real_ACK='NOT_PROVIDED',real_fill='NOT_PROVIDED',
        historical_tradability='UNKNOWN',zero_partial_scope='SYNTHETIC_RESPONSIBILITY_TESTS_ONLY')
    assert math.isclose(summary['common_joint_minus_baseline'],summary['common_price_contribution']+summary['common_ab_path_delta'],abs_tol=1e-6)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True)
    args=p.parse_args();start=time.monotonic()
    approved=require_economic_authorization(args.window)
    assert approved.get('entrypoint')=='run_economic.py', 'UNIQUE_ENTRYPOINT_REQUIRED'
    dest=O/('economic_'+args.window)
    assert not dest.exists(),'NEVER_OVERWRITE_AN_ECONOMIC_ATTEMPT'
    dest.mkdir()
    save(dest/'STARTED.json',dict(window=args.window,authorization_sha256=approved['authorization_sha256'],
        protocol_sha256=approved['protocol_sha256'],entrypoint='run_economic.py',
        evidence_model='CONDITIONAL_NEXT_COMMON_OPEN_FULL_FILL_PROXY'))
    print('G2_STARTED',args.window,flush=True)
    try:
        from joint_engine import run_joint
        from baseline_regression import BASE,CONFIG
        from report_adapter import read_sealed_baseline,build_comparison
        import pandas as pd
        joint=run_joint(args.window)
        verify_inputs(approved,joint)
        joint.s.dump(dest/'joint')
        save(dest/'PRICE_AUDIT.json',joint.price_audit)
        save(dest/'OFFER_AUDIT.json',joint.offer_audit)
        save(dest/'AB_DECISION_AUDIT.json',joint.ab_decision_audit)
        save(dest/'FROZEN_RESPONSIBILITIES.json',joint.frozen_responsibilities)
        save(dest/'EXECUTION_BOOKS.json',{rid:dict(responsibility=b.responsibility(),parents=b.parents,
            orders=b.orders,lots=b.lots,events=b.events) for rid,b in joint.books.items()})
        save(dest/'ECONOMIC_LOOP_COMPLETE.json',dict(window=args.window,elapsed_seconds=time.monotonic()-start,
            rounds=len(joint.s.rounds),actions=len(joint.s.actions),statuses=dict(Counter(r['status'] for r in joint.s.rounds)),
            source_checks_passed=True,report_pending=True))
        print('G2_LOOP_COMPLETE',args.window,len(joint.s.rounds),len(joint.s.actions),flush=True)
        folder,leaf,_,_=CONFIG[args.window]
        baseline=read_sealed_baseline(BASE/folder/leaf,joint.s.ev,evidence_engine=joint.s)
        roster=pd.read_csv(O.parent/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').sid.astype(str).tolist()
        assert len(roster)==len(set(roster))==1709
        report=build_comparison(baseline,joint,roster,args.window)
        verify_inputs(approved,joint)
        fatal={'ORIGINAL_AB_PERMITS_NOT_EXACT','RETAINED_AB_PATH_MISMATCH_REQUIRES_REVIEW'}
        assert not fatal.intersection(report['adapter_blockers']),('ACCOUNTING_OR_STRATEGY_REPORT_BLOCKER',report['adapter_blockers'])
        save(dest/'COMPARISON_REPORT.json',report)
        summary=core_summary(report)
        save(dest/'CORE_SUMMARY.json',summary)
        save(dest/'COMPLETE.json',dict(window=args.window,elapsed_seconds=time.monotonic()-start,
            code_and_input_unchanged=True,root_authorization_sha256=approved['authorization_sha256'],
            report_sha256=sha(dest/'COMPARISON_REPORT.json'),core_summary_sha256=sha(dest/'CORE_SUMMARY.json')))
        print('G2_CORE_READY',args.window,json.dumps(clean(summary),ensure_ascii=False,default=str),flush=True)
    except BaseException as exc:
        save(dest/'FAILED_NO_RETRY.json',dict(error=repr(exc),elapsed_seconds=time.monotonic()-start,
            do_not_rerun=True,conclusions_publishable=False))
        raise


if __name__=='__main__':main()
