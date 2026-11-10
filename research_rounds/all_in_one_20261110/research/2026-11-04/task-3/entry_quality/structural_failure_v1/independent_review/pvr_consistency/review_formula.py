"""Independent algebra/prefix/slot tests, no account or candidate production code."""
from pathlib import Path
import ast
import hashlib
import json
import math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
R=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')
ORIGINAL=W/'pvr-current-v3-information-capital-20261101/original_score_function.py'
NATIVE=W/'pvr-slot1-native-readiness-20261101/native_rank.py'
SOURCES=[ORIGINAL,NATIVE,W/'pvr-slot1-native-readiness-20261101/CONTRACT.txt',
         W/'pvr-slot1-native-readiness-20261101/FINANCIAL_RESULTS.txt',
         W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/RESULTS_2023.txt',
         R/'path_efficiency_strength.py',R/'trend_path_shape.py',
         R/'results/strength-path-efficiency/decision.json',
         R/'results/trend-path-shape/README.md',
         Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/s-entry-volume-theory-20261028/ANALYSIS.txt')]
weights=.9**np.arange(20,-1,-1)
weights=weights/weights.sum()


def statistics(e):
    e=np.asarray(e,dtype=float)
    assert len(e)==21 and np.isfinite(e).all()
    n=float(weights@e); a=float(weights@np.abs(e))
    p=float(weights@np.maximum(e,0)); m=float(weights@np.maximum(-e,0))
    return dict(E=n, absolute_activity=a, eta=n/a if a>0 else None, P=p,M=m)


def eta_from_existing_e(frame):
    # The original e supplies its own valid/preparation/source clock. Reusing
    # those NaNs prevents this audit from inventing a faster preparation rule.
    a=frame.e.abs().rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
    return (frame.E/a).where(a.gt(0))


def main():
    checks=[]
    env={'np':np,'pd':pd}
    exec(compile(ORIGINAL.read_text(),str(ORIGINAL),'exec'),env)
    score=env['score']
    tree=ast.parse(NATIVE.read_text())
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='priority_plan')
    slotenv={'math':math}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(NATIVE),'exec'),slotenv)
    priority=slotenv['priority_plan']

    rng=np.random.default_rng(21)
    for _ in range(100):
        a=statistics(rng.uniform(-1.5,1.5,21))
        assert -1-1e-14 <= a['eta'] <= 1+1e-14
        assert abs(a['eta']-(2*a['P']/(a['P']+a['M'])-1))<1e-14
    checks.append(dict(name='signed_positive_mass_identity_and_bounds',vectors=100,pass_=True))
    small=statistics(np.full(21,.00001));large=statistics(np.full(21,.8))
    assert small['eta']==large['eta']==1 and large['E']>small['E']
    checks.append(dict(name='all_positive_micro_and_large_paths_tie_at_one',small=small,large=large,pass_=True))
    pulse=statistics([0.]*20+[1.])
    assert pulse['eta']==1
    checks.append(dict(name='one_positive_pulse_is_not_duration',pulse=pulse,pass_=True))
    allnegative=statistics(np.full(21,-.05)); assert allnegative['eta']==-1
    checks.append(dict(name='all_negative_amplitudes_tie_at_minus_one',pass_=True))
    zero=statistics(np.zeros(21)); assert zero['eta'] is None
    checks.append(dict(name='zero_denominator_unknown_not_neutral',original_E=zero['E'],pass_=True))
    consistent=statistics(np.full(21,.05));impulse=statistics([-.01]*20+[1.])
    assert impulse['E']>consistent['E'] and impulse['eta']<consistent['eta']
    checks.append(dict(name='nonredundant_rank_reversal',consistent=consistent,impulse=impulse,pass_=True))
    x=np.array([0.]*19+[-.5,.9]); y=np.array([0.]*20+[.45])
    a,b=statistics(x),statistics(y)
    assert abs(a['E']-b['E'])<1e-16 and a['eta']<b['eta']
    checks.append(dict(name='same_original_E_different_eta',mixed=a,positive=b,pass_=True))
    v=statistics([0.]*19+[-.9,1.2]); assert v['E']>0 and 0<v['eta']<.25
    checks.append(dict(name='V_recovery_can_be_positive_strength_but_low_eta',V=v,pass_=True))
    e=rng.uniform(-1,1,21)
    assert abs(statistics(e)['eta']-statistics(e*.01)['eta'])<1e-15
    checks.append(dict(name='e_amplitude_scale_invariance_does_not_mean_raw_return_invariance',pass_=True))

    t=np.arange(180)
    f=pd.DataFrame(dict(close=100*np.exp(np.cumsum(.002+.014*np.sin(t))),
                        amount=1e6*np.exp(.5*np.cos(t*.3)),
                        observed_bar=True,price_eligible=True,
                        source_invalid=False,synthetic_event_bar=False,segment_id=1),
                   index=pd.bdate_range('2022-01-03',periods=180))
    full=score(f); efull=eta_from_existing_e(full)
    assert full.score.first_valid_index()==f.index[84]
    for cut in (84,100,130):
        p=score(f.iloc[:cut+1]); ep=eta_from_existing_e(p)
        pd.testing.assert_frame_equal(p,full.iloc[:cut+1],check_exact=True)
        pd.testing.assert_series_equal(ep,efull.iloc[:cut+1],check_exact=True)
        changed=f.copy();changed.loc[f.index[cut+1]:,'close']*=8
        changed.loc[f.index[cut+1]:,'amount']*=.001
        z=score(changed)
        pd.testing.assert_frame_equal(z.iloc[:cut+1],full.iloc[:cut+1],check_exact=True)
        pd.testing.assert_series_equal(eta_from_existing_e(z).iloc[:cut+1],efull.iloc[:cut+1],check_exact=True)
    checks.append(dict(name='physical_prefix_and_future_mutation_3_cuts_original_E_and_eta',first_ready_observation=85,pass_=True))
    for field,value in [('amount',0),('source_invalid',True),('segment_id',2)]:
        altered=f.copy()
        if field=='segment_id':altered.loc[f.index[90]:,field]=value;ready=174
        else:altered.loc[f.index[90],field]=value;ready=175
        z=score(altered);ez=eta_from_existing_e(z)
        assert z.score.iloc[90:ready].isna().all()
        assert ez.iloc[90:ready].isna().all()
        assert pd.notna(z.score.iloc[ready]) and pd.notna(ez.iloc[ready])
    checks.append(dict(name='invalid_amount_invalid_quote_source_reset_full_preparation',cases=3,pass_=True))

    intents=[dict(sid='A',rank=3,role='core'),dict(sid='A',rank=3,role='mobile'),
             dict(sid='B',rank=9,role='mobile'),dict(sid='C',rank=20,role='core')]
    vals={'A':.3,'B':None,'C':.8}
    keys,log=priority(intents,lambda sid,day:vals[sid],'2022-01-01')
    assert keys==dict(A=20,B=9,C=3) and log[0]['roles']==['core','mobile']
    keys,_=priority(intents,lambda sid,day:1.,'2022-01-01')
    assert keys==dict(A=3,B=9,C=20)
    keys,_=priority(intents,lambda sid,day:None,'2022-01-01')
    assert keys==dict(A=3,B=9,C=20)
    checks.append(dict(name='original_pure_stock_slots_roles_H1_tie_and_unknown_slots',cases=3,pass_=True))
    assert len(checks)==12
    out=dict(status='PASS_FORMULA_NONREDUNDANCY_PREFIX_AND_ORIGINAL_SLOT_SEMANTICS_ONLY',
             production_feature_or_adapter_review='PENDING_DESIGNER_IMPLEMENTATION',
             checks=checks,
             bounded_dedup=dict(concept='Existing signed/unsigned weighted path-efficiency family, not a new principle.',
                               exact_original_PVR_includes_absolute_normalization=False,
                               old_KAMA='10-bar optional volume-weighted abs(sum(w*r))/sum(w*abs(r)) changes adaptive baseline and then entry/exit strength.',
                               old_path_shape='63-bar raw log net/absolute path changes strength and holding.',
                               candidate='Original nonlinear standardized amount-modulated e; original21 finite exponential clock; signed ratio used ONLY in stock priority.',
                               exact_same_completed_slot_only_intervention_found=False,
                               search_scope='Current repo efficiency implementations and bounded historical PVR/foundational/temperature/S-entry families; not proof of global novelty.'),
             necessary_remaining_checks=[
                 'Full original e/E/score equivalence and new eta arrays from original source, including all empty/source-invalid/unknown cases.',
                 'Actual current pending intent domain and one stock slot for both roles; no PVR-first then eta double sort.',
                 'Decompose true unequal-eta displacement versus eta-tie H1 fallback; include zero-denominator fixed-slot subset.',
                 'All opportunities rather than only original funded stocks, and actual shared cash/risk/sector/probe competition; changed slot alone not executed displacement.',
                 'Keep fixed original winners and main loss windows; future outcomes only labels, no winner exemption or tuning.',
                 'Use original tanh(score) rounding for baseline, raw eta rounding for candidate; do not silently normalize tie semantics.'
             ],
             no_claim='Not a performance, information-quality or executable funding gate; original specialist complete-account results read, not re-audited here.',
             source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES},
             script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             new_accounts=0,new_financial_events=0,new_production_modules=0)
    HERE.mkdir(exist_ok=True,parents=True)
    (HERE/'FORMULA_AND_DEDUP_REVIEW.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=out['status'],checks=len(checks),source_files=len(SOURCES),new_accounts=0)))


if __name__=='__main__':main()
