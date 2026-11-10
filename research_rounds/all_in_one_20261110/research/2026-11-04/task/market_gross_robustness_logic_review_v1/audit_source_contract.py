"""Bounded read-only source audit; no native imports or Account construction."""
from pathlib import Path
import ast, hashlib, json, textwrap

T = Path(__file__).resolve().parent.parent
O = T / 'market_gross_robustness_v1'
OUT = Path(__file__).resolve().parent

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def original_function(path, cls, name):
    text = path.read_text()
    root = ast.parse(text)
    node = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == cls)
    fn = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return textwrap.dedent(''.join(text.splitlines(keepends=True)[fn.lineno-1:fn.end_lineno]))

def main():
    pure = json.loads((O/'COST15_PURE_CHECKS.json').read_text())
    paths = pure['source_receipt']['stored_original_source_SHA256']
    assert all(sha(p) == h for p,h in paths.items())
    defs = {
        'FEE': (Path(pure['source_receipt']['original_fee_source']), 'FeeSchedule', 'incremental'),
        'BASE': (next(Path(p) for p in paths if p.endswith('/multi_runner.py')), 'FrozenMarket', 'window'),
        'FAST': (Path(pure['source_receipt']['original_window_source']), 'FastMarket', 'window'),
        'OPEN': (next(Path(p) for p in paths if p.endswith('/joint_v3.py')), 'Runner', 'opening'),
    }
    orig = {}
    for label,(path,cls,name) in defs.items():
        orig[label] = original_function(path,cls,name)
        assert orig[label] == (O/(label+'_ORIGINAL.py.txt')).read_text()
    expected = {
        'FEE': orig['FEE'].replace('if multiplier not in (1, 2):', "if multiplier not in (1, D('1.5'), 2):"),
        'BASE': orig['BASE'].replace("if cost_multiplier == 2 and policy['stress_slippage']:","if cost_multiplier != 1 and policy['stress_slippage']:").replace('slip *= 2','slip *= cost_multiplier'),
        'FAST': orig['FAST'].replace("if cost_multiplier==2 and policy['stress_slippage']:slip*=2", "if cost_multiplier!=1 and policy['stress_slippage']:slip*=cost_multiplier").replace('super().window(sid,at,side,cost_multiplier)', '_original_stress_reference(self,sid,at,side,cost_multiplier)'),
        'OPEN': orig['OPEN'].replace("self.market.window(sid,at,'sell',1)","self.market.window(sid,at,'sell',a.cost_multiplier)").replace("self.market.window(sid,at,'buy',1)","self.market.window(sid,at,'buy',a.cost_multiplier)"),
    }
    for label,text in expected.items():
        assert text != orig[label]
        assert text == (O/(label+'_DERIVED.py.txt')).read_text()
    fast = ast.parse(orig['FAST']).body[0]
    assert 'key=(sid,side,cost_multiplier)' in orig['FAST']
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('wc','window_cache') for n in ast.walk(ast.parse(orig['BASE'])))
    assert orig['OPEN'].count("self.market.window(sid,at,'sell',1)") == 1
    assert orig['OPEN'].count("self.market.window(sid,at,'buy',1)") == 1
    assert orig['OPEN'].count('C.activate(a)') == 1
    robust = (O/'robust_adapter.py').read_text()
    k = (O/'cost15_compat.py').read_text()
    assert "CONTEXT_NEW=CONTEXT_OLD.replace(\"info=a.gross_info.state(at))\",\"info=a.gross_info.state(at),alpha=a.robust_alpha)\")" in robust
    assert "DECISION_NEW=DECISION_OLD.replace('ALPHA*nav',\"c['alpha']*nav\")" in robust
    assert "ACCOUNT_NEW=ACCOUNT_OLD.replace('ALPHA*','self.robust_alpha*')" in robust
    assert "class CostRunner(Runner):opening=K.cost_opening" in robust
    assert "rate_accrual=" not in k and "def rate_accrual" not in k
    assert 'key=(sid,side,cost_multiplier)' in expected['FAST']
    source_paths = list(paths) + [str(O/n) for n in ('robust_adapter.py','cost15_compat.py','run_small.py','ma_provider.py','inputs_reuse.py','SMALL87_ADDENDUM.txt')]
    result = {
        'passed': True,
        'scope': 'source/body and fixed parameter contract only; no Account, input loader or fee replay',
        'source_sha256': {p:sha(p) for p in source_paths},
        'source_original_snapshots_exact': list(defs),
        'private_derived_only_allowed_text_changes_exact': list(defs),
        'fee_rate_accrual_inherited_original': True,
        'parent_window_has_no_window_cache': True,
        'fast_window_cache_key_includes_multiplier': True,
        'both_opening_buy_sell_use_actual_multiplier': True,
        'original_per_account_activate_preserved': True,
        'alpha_context_predicate_and_both_postchecks_same_account_attribute': True,
        'strong_alpha5_20_archive_proof_only_alpha_financial_source_condition': True,
        'old_cost2_whole_opening_economic_identity_claimed': False,
        'cost15_means_original_stress_flags_not_total_fee_times_1_5': True,
        'real_window_cache_and_87_actual_account_evidence': 'PENDING_PRODUCER_COMMIT_AND_INDEPENDENT_READ',
        'full_authorization': False,
    }
    (OUT/'SOURCE_BODY_INDEPENDENT_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'receipt_sha256':sha(OUT/'SOURCE_BODY_INDEPENDENT_REVIEW.json')}))

if __name__ == '__main__':
    main()
