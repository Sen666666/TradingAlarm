"""Independent PVS-B1 audit; reads frozen inputs/results, writes only beside self.

Reference update uses standard-library lists, conditional-Gaussian covariance
P-pH(HpH+R)^-1Hp and raw second moments, rather than the implementation's
Joseph covariance and centered between-component covariance.
"""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import math
import statistics
import sys

sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
HERE = OUT.parents[1]
ROOT = HERE.parents[1]
RHO = 2 ** (-1 / 5)
F = [[1., 1., 0.], [0., 1., 0.], [0., 0., RHO]]
H = [1., 0., 1.]
PRIOR = [19 / 21, 1 / 21, 1 / 21]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def mv(a, b):
    return [dot(row, b) for row in a]


def transpose(a):
    return list(map(list, zip(*a)))


def mm(a, b):
    return [[dot(row, col) for col in transpose(b)] for row in a]


def reference_update(mean, covariance, observed, sigma, activity):
    predicted_mean = mv(F, mean)
    predicted_covariance = mm(mm(F, covariance), transpose(F))
    coefficients = [
        [.01, 1 / 21 ** 2, .01],
        [activity, activity / 25, .01],
        [.01, 1 / 21 ** 2, 4 * activity],
    ]
    means, covariances, log_weights, zs = [], [], [], []
    residual = observed - dot(H, predicted_mean)
    for prior, coefficient in zip(PRIOR, coefficients):
        p = [[predicted_covariance[i][j] + (coefficient[i] * sigma ** 2 if i == j else 0.) for j in range(3)] for i in range(3)]
        ph = mv(p, H)
        variance = dot(H, ph) + .25 * sigma ** 2
        conditional_mean = [predicted_mean[i] + ph[i] / variance * residual for i in range(3)]
        conditional_covariance = [[p[i][j] - ph[i] * ph[j] / variance for j in range(3)] for i in range(3)]
        means.append(conditional_mean)
        covariances.append(conditional_covariance)
        log_weights.append(math.log(prior) - .5 * (math.log(2 * math.pi * variance) + residual ** 2 / variance))
        zs.append(residual / math.sqrt(variance))
    unscaled = [math.exp(x - max(log_weights)) for x in log_weights]
    weights = [x / sum(unscaled) for x in unscaled]
    combined_mean = [sum(w * m[i] for w, m in zip(weights, means)) for i in range(3)]
    second_moment = [[sum(w * (p[i][j] + m[i] * m[j]) for w, m, p in zip(weights, means, covariances)) for j in range(3)] for i in range(3)]
    combined_covariance = [[second_moment[i][j] - combined_mean[i] * combined_mean[j] for j in range(3)] for i in range(3)]
    within = [[sum(w * p[i][j] for w, p in zip(weights, covariances)) for j in range(3)] for i in range(3)]
    between = [[combined_covariance[i][j] - within[i][j] for j in range(3)] for i in range(3)]
    return combined_mean, combined_covariance, weights, dot(weights, zs), between


def reference_frame(frame, joint=True):
    columns = ['strength', 'drift', 'drift_sigma', 'drift_sd', 'temporary', 'temporary_sigma', 'level', 'normal_weight', 'persistent_weight', 'transient_weight', 'activity', 'sigma', 'innovation_z', 'init', 'drift_21_pct', 'drift_z', 'total_21_log_forecast', 'total_21_strength']
    answer = pd.DataFrame(np.nan, index=frame.index, columns=columns)
    for _, group in frame.groupby('segment_id', sort=False):
        good = group.loc[group.valid_strength_observation]
        if len(good) < 65:
            continue
        prices = good.close.tolist()
        volumes = good.volume.tolist()
        # A different log implementation keeps this reconstruction independent.
        y = [math.log(p) - math.log(prices[0]) for p in prices]
        returns = [float('nan')] + [math.log(prices[i]) - math.log(prices[i - 1]) for i in range(1, len(prices))]
        mean = covariance = None
        for t in range(64, len(prices)):
            sigma = max(math.sqrt(sum(r * r for r in returns[t - 63:t]) / 63), 1e-8)
            activity = min(max(volumes[t] / statistics.median(volumes[t - 21:t]), .25), 4.) if joint else 1.
            if mean is None:
                mean = [y[t], 0., 0.]
                covariance = [[sigma ** 2, 0., 0.], [0., sigma ** 2 / 21 ** 2, 0.], [0., 0., sigma ** 2]]
                answer.loc[good.index[t], 'init'] = 1.
                continue
            mean, covariance, weights, z, _ = reference_update(mean, covariance, y[t], sigma, activity)
            sd = math.sqrt(max(covariance[1][1], 0.))
            total = 21 * mean[1] + (RHO ** 21 - 1) * mean[2]
            answer.loc[good.index[t]] = [
                100 * math.tanh(math.sqrt(21) * mean[1] / sigma), mean[1], mean[1] / sigma, sd,
                mean[2], mean[2] / sigma, mean[0], *weights, activity, sigma, z, 0.,
                100 * math.expm1(21 * mean[1]), mean[1] / sd, total,
                100 * math.tanh(total / (math.sqrt(21) * sigma)),
            ]
    return answer


def main():
    spec = importlib.util.spec_from_file_location('pvs_b1_audit_frozen_model', HERE / 'code/model.py')
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    freeze = json.loads((HERE / 'freeze.json').read_text())
    manifest = json.loads((HERE / 'inputs/manifest.json').read_text())
    checks = {}
    checks['frozen_code_identity'] = {name: digest(HERE / 'code' / name) == sha for name, sha in freeze['code'].items()}
    checks['frozen_input_identity'] = {Path(path).name: digest(path) == sha for path, sha in freeze['inputs'].items()}
    checks['frozen_protocol_identity'] = digest(HERE / 'PROTOCOL.md') == freeze['protocol_sha256']
    checks['frozen_manifest_identity'] = digest(HERE / 'inputs/manifest.json') == freeze['source_manifest_sha256']
    checks['preparation_manifest_protocol_matches_final_freeze'] = manifest['protocol_sha256'] == freeze['protocol_sha256']
    checks['e0_copied_state_identity'] = {x['asset']: digest(HERE / 'inputs' / (x['asset'] + '-e0-frozen.parquet')) == x['sources'][1]['sha256'] for x in manifest['series'] if len(x['sources']) > 1}
    registry = json.loads((ROOT / 'research_rounds/algorithm-baselines-20261024/registry.json').read_text())
    checks['e0_runtime_dependency_identity'] = {path: digest(ROOT / path) == registry['sha256'][path] for path in ['research_rounds/pv-participation-response-20261020/code/numeric.py', 'research_rounds/pv-participation-response-20261020/code/participation.py']}

    fixed = []
    covariance = [[.0004, .000015, -.00004], [.000015, .000004, .000001], [-.00004, .000001, .0003]]
    mean = [.04, .0017, -.012]
    for observed in [.008, .0417, .09]:
        for activity in [.25, 1., 4.]:
            ref = reference_update(mean, covariance, observed, .013, activity)
            actual = model.update(np.array(mean), np.array(covariance), observed, .013, activity)
            error = max(float(np.max(np.abs(np.asarray(actual[i]) - np.asarray(ref[i])))) for i in range(4))
            predicted_mean = mv(F, mean)
            predicted_covariance = mm(mm(F, covariance), transpose(F))
            residual = observed - dot(H, predicted_mean)
            prior_mixture_variance = dot(H, mv(predicted_covariance, H)) + .013 ** 2 * (.25 + PRIOR[0] * .02 + PRIOR[1] * (activity + .01) + PRIOR[2] * (.01 + 4 * activity))
            fixed.append(dict(observed=observed, activity=activity, max_abs_error=error, weights=ref[2], mean=ref[0], covariance=ref[1], between_trace=sum(ref[4][i][i] for i in range(3)), implemented_posterior_mode_weighted_z=ref[3], prior_predictive_mixture_z=residual / math.sqrt(prior_mixture_variance)))
    checks['fixed_nine_updates_max_error'] = max(x['max_abs_error'] for x in fixed)
    checks['between_covariance_nonzero_in_shock_cases'] = max(x['between_trace'] for x in fixed)
    checks['innovation_z_vs_prior_predictive_z_max_difference'] = max(abs(x['implemented_posterior_mode_weighted_z'] - x['prior_predictive_mixture_z']) for x in fixed)
    f21_mean = mean[:]
    for _ in range(21):
        f21_mean = mv(F, f21_mean)
    checks['total_displacement_vs_repeated_F21_error'] = abs(dot(H, f21_mean) - dot(H, mean) - (21 * mean[1] + (RHO ** 21 - 1) * mean[2]))

    dates = pd.date_range('2000-01-01', periods=280)
    returns = np.array([.001 + .007 * math.sin(t * .7) + (.04 if t == 111 else -.03 if t == 171 else 0.) for t in range(280)])
    close = 100 * np.exp(np.cumsum(returns))
    frame = pd.DataFrame(dict(close=close, volume=[1000 * (1 + .4 * math.cos(t / 7)) for t in range(280)], segment_id=0, valid_strength_observation=True), index=dates)
    full = model.strength_frame(frame)
    # Change today's close/volume only: sigma excludes today, activity denominator does too.
    changed = frame.copy()
    changed.loc[dates[150], 'close'] *= 7
    changed.loc[dates[150], 'volume'] *= 3
    altered = model.strength_frame(changed)
    checks['same_day_sigma_excludes_today'] = bool(full.loc[dates[150], 'sigma'] == altered.loc[dates[150], 'sigma'])
    checks['same_day_activity_uses_past_median'] = bool(abs(altered.loc[dates[150], 'activity'] - min(3 * full.loc[dates[150], 'activity'], 4)) < 1e-12)
    checks['prefix_before_changed_today_max_error'] = float(np.nanmax(np.abs(full.loc[:dates[149]].values - altered.loc[:dates[149]].values)))
    checks['first_init_observation'] = int(np.flatnonzero(full.init.eq(1))[0]) + 1
    checks['first_scored_observation'] = int(np.flatnonzero(full.strength.notna())[0]) + 1
    scaled = frame.copy()
    scaled['close'] *= 17
    scaled['volume'] *= 10000
    checks['price_and_volume_unit_scaling_max_strength_error'] = float((model.strength_frame(scaled).strength - full.strength).abs().max())
    clipped = frame.copy()
    clipped.loc[dates[[15, 95, 151]], 'valid_strength_observation'] = False
    clipped.loc[dates[[15, 95, 151]], 'close'] = np.nan
    omitted = model.strength_frame(clipped)
    reduced = model.strength_frame(clipped.loc[clipped.valid_strength_observation])
    checks['invalid_rows_all_unknown'] = bool(omitted.loc[~clipped.valid_strength_observation].isna().all().all())
    checks['invalid_rows_do_not_advance_clock_max_error'] = float(np.nanmax(np.abs(omitted.loc[reduced.index].values - reduced.values)))
    divided = frame.copy()
    divided.loc[dates[140]:, 'segment_id'] = 1
    divided_output = model.strength_frame(divided)
    second_only = model.strength_frame(divided.iloc[140:])
    checks['new_segment_independent_max_error'] = float(np.nanmax(np.abs(divided_output.iloc[140:].values - second_only.values)))
    checks['new_segment_init_observation'] = int(np.flatnonzero(divided_output.iloc[140:].init.eq(1))[0]) + 1
    checks['synthetic_reference_max_error'] = float(np.nanmax(np.abs(reference_frame(frame).values - full[reference_frame(frame).columns].values)))
    checks['synthetic_prefix_full_columns_max_error'] = max(float(np.nanmax(np.abs(model.strength_frame(frame.iloc[:n]).values - full.iloc[:n].values))) for n in [66, 112, 172, 250])
    checks['zero_noise_floor_finite'] = bool(model.strength_frame(frame.assign(close=100., volume=1000.)).dropna().apply(np.isfinite).all().all())

    real = []
    for x in manifest['series']:
        asset = x['asset']
        f = pd.read_parquet(x['path'])
        result = pd.read_parquet(HERE / 'results' / (asset + '.parquet'))
        ref = reference_frame(f)
        differences = (ref - result[ref.columns]).abs()
        mask_same = ref.isna().eq(result[ref.columns].isna()).all().all()
        valid = result.strength.notna()
        latent_residual = result.level + result.temporary - np.log(f.close / f.close.iloc[0])
        # All current inputs have one segment. For future multisegment inputs,
        # the coordinate above must be reset separately at each segment's origin.
        record = dict(asset=asset, rows=len(f), invalid=int((~f.valid_strength_observation).sum()), segments=int(f.segment_id.nunique()), monotonic=bool(f.index.is_monotonic_increasing), unique_index=bool(f.index.is_unique), segment_id_missing=int(f.segment_id.isna().sum()), masks_match=bool(mask_same), compared_values=int(ref.notna().sum().sum()), max_abs_error=float(differences.max().max()), max_strength_error=float(differences.strength.max()), min_cov_eigenvalue=float(result.cov_min_eigenvalue.min()), weight_sum_max_error=float((result[['normal_weight', 'persistent_weight', 'transient_weight']].sum(axis=1).loc[valid] - 1).abs().max()), main_vs_total_opposite_sign=int((result.strength * result.total_21_strength < 0).sum()), max_abs_latent_vs_close_log_residual=float(latent_residual.loc[valid].abs().max()))
        real.append(record)
    checks['real_reference_compared_values'] = sum(x['compared_values'] for x in real)
    checks['real_reference_max_error'] = max(x['max_abs_error'] for x in real)
    checks['real_reference_max_strength_error'] = max(x['max_strength_error'] for x in real)
    # Hard checks are deliberately different from descriptive limitations.
    assert all(checks['frozen_code_identity'].values())
    assert all(checks['frozen_input_identity'].values())
    assert checks['frozen_protocol_identity'] and checks['frozen_manifest_identity']
    assert all(checks['e0_copied_state_identity'].values())
    assert all(checks['e0_runtime_dependency_identity'].values())
    assert checks['fixed_nine_updates_max_error'] < 1e-12
    assert checks['between_covariance_nonzero_in_shock_cases'] > 0
    assert checks['same_day_sigma_excludes_today'] and checks['same_day_activity_uses_past_median']
    assert checks['first_init_observation'] == 65 and checks['first_scored_observation'] == 66
    assert checks['invalid_rows_all_unknown']
    assert checks['real_reference_max_error'] < 2e-7
    assert all(x['masks_match'] and x['unique_index'] and x['monotonic'] and x['segment_id_missing'] == 0 for x in real)
    payload = dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), audit_script_sha256=digest(__file__), frozen_code_sha256=freeze['code'], audited_result_sha256={x['asset']: digest(HERE / 'results' / (x['asset'] + '.parquet')) for x in manifest['series']}, account_runs=0, writes_restricted_to=str(OUT), checks=checks, independent_fixed_updates=fixed, real_input_reconstruction=real)
    (OUT / 'audit.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(checks=checks, real=real), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
