"""Finite numerical witnesses only; no universe, account, labels or optimization."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
SCORE_SOURCE = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py')
D10_SOURCE = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/market_gross_rule_and_outcome_explanation_v1/READOUT.txt')
ns = {'pd': pd, 'np': np}
exec(compile(SCORE_SOURCE.read_text(), str(SCORE_SOURCE), 'exec'), ns)
score = ns['score']
W = .9 ** np.arange(20, -1, -1)
W /= W.sum()
L_W = 1 / np.square(W).sum()


def finite_features(e):
    """Illustrative proposed observation, not a deployed score/provider."""
    e = np.asarray(e, float)
    if len(e) != 21 or not np.isfinite(e).all():
        return dict(E=None, P=None, Q=None, L_plus=None, d=None, J=None, eta=None)
    E = float(W @ e)
    a = W * np.maximum(e, 0)
    P = float(a.sum())
    Q = float(a @ a)
    # Q=0 means known absence of positive e, not missing observations.
    L = P * P / Q if Q > 0 else 0.
    d = min(1., L / L_W)
    J = E * d if E > 0 else E
    A = float(W @ np.abs(e))
    return dict(E=E, P=P, Q=Q, L_plus=L, d=d, J=J,
                eta=E / A if A > 0 else None)


def fixture(target_e, q=.01, last_amount_ratio=1.):
    """Causal positive-price/amount bars that generate requested b=0 e.

    100 fixed warmup returns ensure every target's lagged median |r| is q:
    at most 20 target returns have entered a 63-return scale history.
    The last-amount option requires target_e to instead specify u, and is
    used only in the separate one-bar u/b collision witness.
    """
    target_e = np.asarray(target_e, float)
    assert len(target_e) == 21 and (np.abs(target_e) < 1).all()
    returns = np.r_[np.repeat(q, 100), 1.4826*q*np.arctanh(target_e)]
    closes = 100 * np.exp(np.r_[0., np.cumsum(returns)])
    f = pd.DataFrame({'close': closes, 'amount': 1e6},
                     index=pd.bdate_range('2000-01-03', periods=len(closes)))
    f.iloc[-1, f.columns.get_loc('amount')] *= last_amount_ratio
    f['observed_bar'] = True
    f['price_eligible'] = True
    f['source_invalid'] = False
    f['synthetic_event_bar'] = False
    f['segment_id'] = 0
    return f


def measure(name, f):
    z = score(f)
    last = z.iloc[-1]
    ex = finite_features(z.e.iloc[-21:].to_numpy())
    y = np.log(f.close)
    ex.update(name=name, rows=len(f), original_E=float(last.E),
              original_score=float(last.score), current_r=float(last.r),
              current_scale=float(last.scale), current_u=float(last.u),
              current_b=float(last.b), current_e=float(last.e),
              raw_log_return_21=float(y.iloc[-1]-y.iloc[-22]),
              raw_abs_log_variation_21=float(y.diff().iloc[-21:].abs().sum()),
              distance_to_previous_20_high=float(f.close.iloc[-1]/f.close.iloc[-21:-1].max()-1),
              candidate_score=float(50+50*np.tanh(2*ex['J'])),
              score_round12=float(round(last.score,12)))
    output = f.join(z, rsuffix='_pvr')
    output.to_csv(OUT / (name+'.csv'), float_format='%.17g')
    return ex, z


def main():
    cases = {}
    zs = {}
    fs = {}
    constant = np.repeat(.08, 21)
    pulse = np.zeros(21); pulse[-1] = .08/W[-1]
    recent = np.zeros(21); recent[-1] = .02/W[-1]
    stale = np.zeros(21); stale[-11] = .02/W[-11]
    chop = np.r_[np.repeat(.45,19),-.9,.85]
    smooth_same_E = np.repeat(W@chop,21)
    definitions = {
        'distributed': (constant,.01,1.), 'single_latest_pulse': (pulse,.01,1.),
        'recent_pulse': (recent,.01,1.), 'older_pulse': (stale,.01,1.),
        'scale_low': (constant,.005,1.), 'scale_high': (constant,.025,1.),
        'chop_below_high': (chop,.01,1.), 'smooth_new_high': (smooth_same_E,.01,1.),
        'amount_neutral': (np.r_[np.zeros(20),.4],.01,1.),
        'amount_rising': (np.r_[np.zeros(20),(-1+np.sqrt(1.64))/.8],.01,3.),
        'amount_falling': (np.r_[np.zeros(20),.5],.01,1/3),
        'zero_e': (np.zeros(21),.01,1.),
        'negative_constant': (np.repeat(-.08,21),.01,1.),
        'strong_first_pulse': (np.r_[np.zeros(20),.9],.01,1.),
        'small_distributed_drift': (np.repeat(.02,21),.01,1.),
        'fast_V': (np.r_[np.zeros(19),-.85,.95],.01,1.),
    }
    for name,(e,q,ratio) in definitions.items():
        fs[name] = fixture(e,q,ratio)
        cases[name],zs[name] = measure(name,fs[name])

    pairs = [
        ('distributed','single_latest_pulse','same E and eta; different positive time concentration'),
        ('recent_pulse','older_pulse','same E, eta and L; different time of last positive event'),
        ('scale_low','scale_high','same E/score; different absolute log return and variation'),
        ('chop_below_high','smooth_new_high','same E/score; different current position vs previous high'),
        ('amount_neutral','amount_rising','same e/E/score; different price move and amount ratio'),
        ('amount_neutral','amount_falling','same e/E/score; different price move and amount ratio'),
    ]
    comparisons=[]
    for a,b,claim in pairs:
        delta = abs(cases[a]['original_score']-cases[b]['original_score'])
        assert delta < 1e-10, (a,b,delta)
        comparisons.append(dict(a=a,b=b,claim=claim,score_abs_difference=delta,
                                native_round12_equal=cases[a]['score_round12']==cases[b]['score_round12']))

    assert abs(cases['distributed']['L_plus']-L_W)<1e-10
    assert abs(cases['single_latest_pulse']['L_plus']-1)<1e-10
    assert cases['chop_below_high']['distance_to_previous_20_high']<0
    assert cases['smooth_new_high']['distance_to_previous_20_high']>0
    assert abs(cases['scale_high']['current_scale']/cases['scale_low']['current_scale']-5)<1e-10
    assert cases['zero_e']['L_plus']==0 and cases['zero_e']['J']==0
    assert cases['negative_constant']['J']==cases['negative_constant']['E']
    assert finite_features(np.r_[np.zeros(20),np.nan])['J'] is None
    # A deliberate adverse ranking counterexample, not an efficacy claim.
    assert cases['strong_first_pulse']['original_E'] > cases['small_distributed_drift']['original_E']
    assert cases['strong_first_pulse']['J'] < cases['small_distributed_drift']['J']
    assert cases['fast_V']['distance_to_previous_20_high'] > 0
    assert cases['fast_V']['d'] < .07

    # Prefix and future perturbation: all PVR columns, not just final score.
    base = fs['chop_below_high']
    full = score(base)
    cuts = [84,100,110,len(base)-2]
    for cut in cuts:
        pd.testing.assert_frame_equal(score(base.iloc[:cut+1]),full.iloc[:cut+1],check_exact=True)
        changed = base.copy()
        changed.iloc[cut+1:,changed.columns.get_loc('close')] *= 1.7
        changed.iloc[cut+1:,changed.columns.get_loc('amount')] *= 7
        pd.testing.assert_frame_equal(score(changed).iloc[:cut+1],full.iloc[:cut+1],check_exact=True)

    # Stock PVR ignores extra sector series; this does NOT establish equal Q.
    up = base.assign(industry_close=np.exp(np.arange(len(base))*.01))
    down = base.assign(industry_close=np.exp(-np.arange(len(base))*.01))
    pd.testing.assert_frame_equal(score(up),score(down),check_exact=True)

    # Full source reset warmup, using a long numerical fixture.
    long = pd.DataFrame({'close':100*np.exp(np.arange(240)*.01),'amount':1e6,
                         'observed_bar':True,'segment_id':0},index=pd.bdate_range('2000-01-03',periods=240))
    broken=long.copy();broken.iloc[100,broken.columns.get_loc('observed_bar')]=False
    zb=score(broken)
    reset_ready=int(np.flatnonzero(zb.E.notna().to_numpy() & (np.arange(len(zb))>100))[0])
    assert reset_ready==101+84
    segmented=long.copy();segmented.iloc[100:,segmented.columns.get_loc('segment_id')]=1
    zseg=score(segmented)
    seg_ready=int(np.flatnonzero(zseg.E.notna().to_numpy() & (np.arange(len(zseg))>=100))[0])
    assert seg_ready==100+84

    grid=np.linspace(-1.5,1.5,10001)
    outer=50+50*np.tanh(2*grid)
    assert (np.diff(outer)>0).all()
    checks=dict(status='PASS',scope='finite numerical witnesses, not empirical strategy coverage',
                original_score_source=str(SCORE_SOURCE),original_score_sha256=hashlib.sha256(SCORE_SOURCE.read_bytes()).hexdigest(),
                latest_D10_source=str(D10_SOURCE),latest_D10_source_sha256=hashlib.sha256(D10_SOURCE.read_bytes()).hexdigest(),
                fixture_count=len(cases),same_score_pair_count=len(comparisons),
                max_same_score_pair_difference=max(x['score_abs_difference'] for x in comparisons),
                all_pair_native_round12_equal=all(x['native_round12_equal'] for x in comparisons),
                L_w=float(L_W),current_weight=float(W[-1]),oldest_weight=float(W[0]),
                prefix_and_future_perturbation_cuts=cuts,
                source_reset_ready_index=seg_ready,invalid_then_valid_ready_index=reset_ready,
                first_ordinary_ready_index=int(np.flatnonzero(full.E.notna().to_numpy())[0]),
                outer_strictly_monotone_grid_points=len(grid),
                outer_min_derivative_on_theoretical_bound=float(100/np.cosh(3)**2),
                inner_tanh_float_20=float(np.tanh(20.)),inner_tanh_float_30=float(np.tanh(30.)),
                inner_float_saturation_equal=bool(np.tanh(20.)==np.tanh(30.)),
                industry_metadata_invariance=True,unknown_window_is_unknown=True,
                known_no_positive_window_not_missing=True,no_account_or_universe_scan=True)
    (OUT/'COUNTEREXAMPLES.json').write_text(json.dumps(dict(cases=cases,pairs=comparisons),ensure_ascii=False,indent=2)+'\n')
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
