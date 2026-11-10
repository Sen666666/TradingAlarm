"""Prepared, unexecuted bridge to the two original pure industry functions.

No Account/Runner/COM imports and no model calculation at module import.
The caller must obtain a separate grant before invoking run_industry().
"""
from pathlib import Path
from types import SimpleNamespace
import ast
import collections
import hashlib
import json
import math

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
TRACE_PATH = W / 'cp1-evidence-trace-20261031/trace.py'
STAGE_PATH = W / 'industry-mobile-stage-20261031/stage.py'
MODEL_PATH = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py')
COMPACT_KEYS = [
    'canonical_series', 'scale_id', 'source_segment', 'original_E0_episode_id',
    'confirmed_day', 'receipt_id', 'decision_evidence_key',
    'formation_start_exclusive', 'formation_end_inclusive',
    'anchor_observation_id', 'confirmation_observation_id',
    'previous_market_receipt_id', 'original_candidate', 'original_scale',
    'scale_frozen_at', 'new_advance_price_event_ids',
    'new_log_price_displacement', 'original_credit', 'evidence_signature',
    'trace_unknown',
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _original_definitions(path, names, environment):
    """Compile original AST nodes verbatim, without their module-level imports."""
    tree = ast.parse(Path(path).read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    assert len(nodes) == len(names) and {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), environment)


def _interfaces(cp1_model, arm, method_identity, end):
    freeze = json.loads((HERE / 'SOURCE_FREEZE.json').read_text())
    for path, expected in freeze['original_source_sha256'].items():
        assert sha(path) == expected, ('original_source_changed', path)
    assert Path(cp1_model.__file__).resolve() == MODEL_PATH.resolve()
    assert callable(cp1_model.ge)
    trace_env = dict(np=np, pd=pd, math=math, json=json, hashlib=hashlib, collections=collections,
                     BEGIN='1900-01-01', END=end,
                     SCALE=('CP1-original:' + sha(MODEL_PATH)[:16]) if arm == 'real'
                     else 'CP1-predictive-volume-neutral:' + method_identity,
                     __builtins__=__builtins__)
    _original_definitions(TRACE_PATH, {'ident', 'norm', 'trace'}, trace_env)
    # Stage calls only T.ident/T.norm and the frozen CP1 arithmetic M.ge.
    trace_api = SimpleNamespace(ident=trace_env['ident'], norm=trace_env['norm'], M=cp1_model)
    stage_env = dict(pd=pd, np=np, math=math, T=trace_api, __builtins__=__builtins__)
    _original_definitions(STAGE_PATH, {'Stage', 'run'}, stage_env)
    return trace_env, stage_env


def run_industry(sid, features, cp1_model, *, arm, method_identity, end='2026-06-30'):
    """Future authorized caller only: consume one arm's own full-warm features.

    features is the original assemble() dictionary (facts/q/CP1/evidence).
    No original episode IDs, account levels or observation calendar are accepted.
    """
    assert arm in ('real', 'neutral')
    assert sid.startswith('URFI') and isinstance(method_identity, str) and method_identity
    facts, q, cp, evidence = (features[k] for k in ('facts', 'q', 'CP1', 'evidence'))
    assert not q.empty, 'empty industry requires NA bypass, never a fabricated state'
    assert q.index.is_unique and q.index.is_monotonic_increasing
    assert all(q.index.equals(x.index) for x in (facts, cp, evidence))
    assert q.index.max() <= pd.Timestamp(end)
    # For industries only: e0_valid is E0 target, not stock G1_I target.
    pd.testing.assert_series_equal(q.e0_valid, facts.e0_target.astype(bool),
                                   check_exact=True, check_dtype=False, check_names=False)
    pd.testing.assert_series_equal(q.i_floor, facts.e0_floor,
                                   check_exact=True, check_dtype=False, check_names=False)
    events = evidence[['event']].copy()
    episode_target = facts.e0_target.astype(bool).copy()
    trace_cp = cp.copy(deep=True)
    observed_m = None
    if arm == 'neutral':
        assert 'effective_amount_multiplier' in cp
        np.testing.assert_array_equal(cp.effective_amount_multiplier.to_numpy(), np.ones(len(cp)))
        observed_m = cp.m.copy()  # diagnostic; never consumed by the neutral trace.
        trace_cp['m'] = cp.effective_amount_multiplier
    trace_env, stage_env = _interfaces(cp1_model, arm, method_identity, end)
    canonical = sid if arm == 'real' else 'PREDICTIVE_VOLUME_NEUTRAL:' + method_identity + ':' + sid
    receipts, increments, checks = trace_env['trace'](canonical, q, trace_cp, events, episode_target)
    ids = {r['confirmed_day']: r['receipt_id'] for r in receipts}
    assert len(ids) == len(receipts)
    # Original run derives its own episode from this arm's E0 validity; no base
    # entered/episode output is needed. It also preserves original source logic.
    rows = stage_env['run'](canonical, q, cp, ids)
    return dict(rows=rows, receipts=receipts, increments=increments,
                checks=checks, observed_amount_multiplier=observed_m,
                arm=arm, canonical_series=canonical, scale_id=trace_env['SCALE'],
                episode_source='this arm facts.e0_target / q.e0_valid; original trace and Stage algorithms',
                financial_state_owned=False)


def assert_real_saved_reference(result, state_path, receipt_path):
    """Future true gate: exact old full state and all saved compact receipts."""
    assert result['arm'] == 'real'
    reference = pd.read_parquet(state_path).to_dict('records')
    norm_env = dict(np=np, pd=pd, math=math, json=json, hashlib=hashlib, __builtins__=__builtins__)
    _original_definitions(TRACE_PATH, {'norm'}, norm_env)
    norm = norm_env['norm']
    assert norm(result['rows']) == norm(reference), 'old industry full state mismatch'
    saved = json.loads(Path(receipt_path).read_text())
    produced = {r['confirmed_day']: r for r in result['receipts']}
    assert len({r['confirmed_day'] for r in saved}) == len(saved)
    for old in saved:
        assert set(old) == set(COMPACT_KEYS), 'unexpected old compact receipt schema'
        new = produced[old['confirmed_day']]
        assert norm({k: new[k] for k in COMPACT_KEYS}) == norm(old), 'old compact receipt identity mismatch'
    return dict(full_state_rows_exact=len(reference), saved_compact_receipts_exact=len(saved))
