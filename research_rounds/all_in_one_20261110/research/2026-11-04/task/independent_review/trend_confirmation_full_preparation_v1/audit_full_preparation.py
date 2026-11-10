"""Read saved technical outputs only; never import an account or feature engine.

The small AST exercise evaluates only cache boundary/state methods with no price
rows.  Financial evidence is exact equality to independently audited books.
"""
from pathlib import Path
import argparse, ast, copy, gzip, hashlib, json

O = Path(__file__).resolve().parent
W = O.parents[1]
T = W / 'trend_confirmation_native_v1'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text())

def payload(p):
    text = gzip.decompress(Path(p).read_bytes()).decode()
    return [json.loads(v) for v in text.splitlines()] if str(p).endswith('.jsonl.gz') else json.loads(text)

def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def methods(path, cls):
    tree = ast.parse(Path(path).read_text())
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return node, {n.name:n for n in node.body if isinstance(n, ast.FunctionDef)}

def compare_pair(left, right):
    names = sorted(p.name for p in (left/'pair').glob('*.gz'))
    assert len(names) == 12 and names == sorted(p.name for p in (right/'pair').glob('*.gz'))
    hashes = {}
    for name in names:
        a, b = payload(left/'pair'/name), payload(right/'pair'/name)
        assert a == b, ('saved actual output mismatch', name, str(left), str(right))
        hashes[name] = canonical_sha(a)
    return hashes

def source_semantics():
    old = T/'source-history/trend_size_plugin_two_small_v1.py'
    new = T/'trend_size_plugin.py'
    _, om = methods(old, 'Runner'); _, nm = methods(new, 'Runner')
    for key in ('planning', 'assert_native_wiring', 'dump_joint'):
        assert ast.dump(om[key], include_attributes=False) == ast.dump(nm[key], include_attributes=False), key
    before_fix = T/'source-history/trend_size_plugin_full_schema_before_episode_index_fix.py'
    _, prior = methods(before_fix, 'Runner')
    assert prior.keys() == nm.keys()
    for key in prior:
        if key != 'restore':
            assert ast.dump(prior[key], include_attributes=False) == ast.dump(nm[key], include_attributes=False), key
    cls, cm = methods(new, 'FeatureCache'); _, old_cm = methods(old, 'FeatureCache')
    # With equal old.end and new.input_limit, consumed price/source slices and
    # all resulting feature calculations are identical.  New assertions guard
    # the two permitted domains before accessing prices.
    at = copy.deepcopy(cm['at'])
    assert all(isinstance(n, ast.Assert) for n in at.body[:2])
    at.body = at.body[2:]
    class Normalize(ast.NodeTransformer):
        def visit_Attribute(self, node):
            self.generic_visit(node)
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'input_limit':
                node.attr = 'end'
            return node
    at = Normalize().visit(at)
    assert ast.dump(at, include_attributes=False) == ast.dump(old_cm['at'], include_attributes=False)

    # Evaluate only non-numeric contract methods, without imports, initialization,
    # actual features, or account events.
    env = {}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(new), 'exec'), env)
    Cache = env['FeatureCache']; obj = Cache.__new__(Cache)
    obj.__dict__.update(end='2024-12-31', input_limit='2022-01-07',
                        values={'sentinel': 'derived only'}, sources={'immutable': 'sha'}, records={})
    state = obj.__getstate__()
    assert state['values'] == {} and obj.values != {}
    assert state['end'] == obj.end and state['input_limit'] == obj.input_limit and state['sources'] == obj.sources
    restored = Cache.__new__(Cache); restored.__setstate__(state)
    assert restored.values == {} and restored.end == obj.end and restored.input_limit == obj.input_limit
    rejected = {}
    for day, key in [('2025-01-01', 'outside_full_end'), ('2022-01-10', 'outside_physical_prefix')]:
        try:
            obj.at('no_source_should_be_read', day)
        except AssertionError as e:
            rejected[key] = str(e)
        else:
            raise AssertionError(('cache boundary accepted', day))
    legacy = Cache.__new__(Cache)
    try:
        legacy.__setstate__({'end':'2022-01-14', 'values':{}})
    except AssertionError as e:
        rejected['missing_legacy_input_limit'] = str(e)
    else:
        raise AssertionError('legacy unbounded state accepted')
    return dict(old_planning_native_wiring_and_dump_AST_exact=True,
                all_non_restore_Runner_methods_AST_exact_to_actual_direct9_source=True,
                actual_direct9_not_rerun_under_explicit_root_restore_only_scope=True,
                old_feature_at_equal_after_only_two_domain_assertions_and_slice_name_normalization=True,
                strong_old_end_Jul11_equals_new_input_limit_Jul11=True,
                independent_zero_row_boundary_and_state_checks=rejected,
                preserved_full_end_source_contract_and_derived_values_omitted=True,
                feature_or_account_events_run_by_reviewer=0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--head', type=Path, required=True)
    parser.add_argument('--resume', type=Path, required=True)
    args = parser.parse_args()
    direct = T/'full-schema-direct9-v1'; head = args.head; resume = args.resume
    old = T/'small-2022-v1'
    evidence = {}; manifests = {}; source_hashes = {}
    for window in ('long','strong'):
        p = T/'full-preparation'/window/'FULL_SOURCE_MANIFEST.json'
        m = read(p); manifests[window] = sha(p)
        assert m['cost_guard'] is False and m['original_ACT20_BREAK63'] is True
        assert m['arms'] == ['B','UNIFORM50','A_ONLY','A_OR_B']
        assert m['fresh_initial_cash'] == 1000000 and m['own_continuous_state_no_annual_reset'] is True
        previous_path = T/'full-preparation/history'/f'{window}-before-episode-index-restore-fix/FULL_SOURCE_MANIFEST.json'
        previous = read(previous_path)
        normalized = copy.deepcopy(m)
        plugin_key = str((T/'trend_size_plugin.py').resolve())
        normalized['sources'][plugin_key] = previous['sources'][plugin_key]
        assert normalized == previous, ('scope or non-restore source changed',window)
        evidence[str(previous_path)] = sha(previous_path)
        for path, expected in m['sources'].items():
            assert sha(path) == expected, ('source changed', path)
            source_hashes[path] = expected
        evidence[str(p)] = sha(p)
    semantics = source_semantics()
    fix_freeze = T/'FULL_PREPARATION_RESTORE_FIX_SOURCE_FREEZE.json'
    fix = read(fix_freeze)
    assert fix['full_manifests'] == manifests
    for path, expected in fix['files'].items():
        assert sha(path) == expected, ('restore-fix freeze changed',path)
    evidence[str(fix_freeze)] = sha(fix_freeze)
    first_failure = O/'FIRST_RESTART_FAILURE_AND_MINIMAL_REPAIR_REVIEW.json'
    assert read(first_failure)['passed'] is False
    evidence[str(first_failure)] = sha(first_failure)
    original_direct_exact = compare_pair(direct, old)
    restart_direct_exact = compare_pair(direct, resume)
    prior_manifest = T/'full-preparation/history/long-before-episode-index-restore-fix/FULL_SOURCE_MANIFEST.json'
    assert sha(prior_manifest) == 'af6283b684d51a0e7b90f5d180ad80f787e23564f8a53c1ca9cc5be50a167de0'
    assert read(direct/'STARTED.json')['full_schema'] == read(prior_manifest)
    assert read(direct/'WINDOW_RESULT.json')['source_post_exact'] is True
    assert read(direct/'WINDOW_RESULT.json')['days'] == 9
    old_source = T/'source-history/trend_size_plugin_full_schema_before_episode_index_fix.py'
    assert sha(old_source) == read(prior_manifest)['sources'][str((T/'trend_size_plugin.py').resolve())]
    edge = O/'RESTORE_ONLY_AST_AND_ZERO_ACCOUNT_EDGE_CHECKS.json'
    assert read(edge)['passed'] is True
    assert read(edge)['source_SHA256'][str((T/'trend_size_plugin.py').resolve())] == sha(T/'trend_size_plugin.py')
    evidence[str(prior_manifest)] = sha(prior_manifest)
    evidence[str(old_source)] = sha(old_source)
    evidence[str(edge)] = sha(edge)
    for path in (head/'pair').glob('*.jsonl.gz'):
        h, d = payload(path), payload(direct/'pair'/path.name)
        assert h == d[:len(h)], ('head physical prefix mismatch', path.name)
    for arm in ('B','UNIFORM50','A_ONLY','A_OR_B'):
        h, d = payload(head/'pair'/f'{arm}.json.gz'), payload(direct/'pair'/f'{arm}.json.gz')
        for key in ('trades','journal','audit','decisions'):
            assert h[key] == d[key][:len(h[key])], ('head book prefix mismatch',arm,key)
    for run, end, days in [(head,'2022-01-07',4),(resume,'2022-01-14',9)]:
        started, result, contract = [read(run/name) for name in ('STARTED.json','WINDOW_RESULT.json','FEATURE_CACHE_CONTRACT.json')]
        assert started['mode'] == 'technical' and started['physical_inputs'] is True
        assert started['actual_end'] == end and started['full_authorization'] is None
        assert started['full_schema'] == read(T/'full-preparation/long/FULL_SOURCE_MANIFEST.json')
        assert result['passed'] is True and result['source_post_exact'] is True and result['days'] == days
        assert contract['fixed_end'] == '2024-12-31' and contract['available_through'] == end
        assert contract['checkpoint_derived_values_omitted'] is True
        cp, prov = read(run/'checkpoint.json'), read(run/'checkpoint.provenance.json')
        assert sha(run/'checkpoint.pkl') == cp['sha256'] == prov['checkpoint_sha256']
        assert cp['source_freeze'] == started['full_schema']['sources']
        for name in ('STARTED.json','WINDOW_RESULT.json','FEATURE_CACHE_CONTRACT.json','checkpoint.json','checkpoint.provenance.json'):
            evidence[str(run/name)] = sha(run/name)
    # Source union above also contains strong's score binding; each checkpoint
    # is checked against its own long manifest, never against a mixed window.
    hp, rp = read(head/'PROCESS_IDENTITY.json'), read(resume/'PROCESS_IDENTITY.json')
    assert hp['pid'] != rp['pid']
    for run, proc in [(head,hp),(resume,rp)]:
        assert read(run/'PROCESS_EXIT.json')['success'] is True
        assert proc['driver_SHA256'] == sha(T/'run_trend_window.py')
        assert proc['launcher_SHA256'] == sha(T/'technical_process_launcher.py')
        assert '--technical' in proc['argv'] and '--execute' not in proc['argv']
        evidence[str(run/'PROCESS_IDENTITY.json')] = sha(run/'PROCESS_IDENTITY.json')
        evidence[str(run/'PROCESS_EXIT.json')] = sha(run/'PROCESS_EXIT.json')
    assert '--resume' not in hp['argv'] and '--resume' in rp['argv']
    target = Path(rp['argv'][rp['argv'].index('--resume')+1]).resolve()
    assert target == (head/'checkpoint.pkl').resolve()
    assert read(resume/'STARTED.json')['resume'] is not None
    restart = read(resume/'DERIVED_CACHE_RESTART.json')
    assert restart == dict(fixed_end='2024-12-31',available_through='2022-01-14',derived_cache_empty=True,
        original_history_rebuild_not_restart_seed=True,resume_after='2022-01-07 15:10:00+08:00',real_accounts_and_pending_preserved=True)
    assert read(head/'checkpoint.provenance.json')['engine_identity'] == read(resume/'checkpoint.provenance.json')['engine_identity']
    old_audit = W/'independent_review/trend_confirmation_native_v1/weak_v1_saved_audit/AUDIT.json'
    strong_audit = W/'independent_review/trend_confirmation_native_v1/strong_v1_saved_audit/AUDIT.json'
    for p in (old_audit,strong_audit,W/'independent_review/trend_confirmation_flags_v1/FEATURE_SOURCE_AND_RECEIPT_AUDIT.json'):
        evidence[str(p)] = sha(p)
    assert (old/'FAILURE.json').is_file(), 'weak strict source failure must remain preserved'
    for arm in ('B','UNIFORM50','A_ONLY','A_OR_B'):
        assert read(direct/'WINDOW_RESULT.json')['NAV'][arm] == read(old_audit)['arms'][arm]['terminal_NAV']
    gate = dict(passed=True,status='PASS_PREPARED_FULL_SOURCE_AND_BOUNDED_TECHNICAL_RESTART_ONLY',
        full_source_manifest_SHA256=manifests,
        source_semantics=semantics,
        both_full_manifests_only_restore_plugin_SHA_changed=True,
        long_actual_new_full_schema_scope=dict(direct_closes=9,head_closes=4,separate_process_resumed_total_closes=9,
            direct_source='preserved pre-restore-fix actual direct9; all non-restore Runner methods AST exact under root accepted no-third-run scope',
            head_pid=hp['pid'],resume_pid=rp['pid'],physical_prefix=True,
            all_12_saved_pair_outputs_exact_to_prior_independently_audited_weak_small=original_direct_exact,
            all_12_saved_pair_outputs_restart_exact=restart_direct_exact,
            head_four_closes_native_transaction_and_all_jsonl_prefix_exact=True,
            actual_flags_m_plans_orders_trades_cash_quantities_fees_NAV_and_native_book_state_exact=True,
            NONE_old_gold_prefix_preserved_by_exact_equality_to_prior_audit=True),
        strong_scope=dict(new_full_schema_native_run=False,new_full_schema_restart=False,
            prior_nine_close_native_and_independent_CA_AR_financial_audit=True,
            source_projection_equivalence_only=True),
        original_weak_strict_source_failure_preserved=True,
        first_full_schema_restart_failure_preserved_and_fixed_by_input_index_only=True,
        four_fixed_arms_no_new_parameter_or_cost_guard=True,
        economic_full_authorized_by_this_gate=False,
        root_separate_exact_manifest_and_gate_SHA_authorization_required=True,
        source_SHA256=source_hashes,evidence_SHA256=evidence,
        reviewer_source_SHA256=sha(__file__),
        limitations=['Technical readiness is not economic performance or candidate promotion.',
            'Long actual restart scope is first nine CLOSEs; future annual boundaries and future CA paths remain subject to full economic result audit.',
            'Strong new full-schema entry is source-equivalent to the prior audited Jul1-Jul11 native sample; no second strong account run or restart is claimed.',
            'No actual partial fill was observed in the two earlier samples; original callbacks remain unchanged.',
            'Current 1709 development snapshot has survivor selection and is not PIT/OOS or Hong Kong evidence.',
            'Producer lazy input post hashes plus prior feature-source receipt are reused; this reviewer does not rescan all price files or recompute features.'])
    output = O/'FULL_PREPARATION_TECHNICAL_GATE.json'
    assert not output.exists(), 'preserve existing review receipt'
    output.write_text(json.dumps(gate,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=gate['passed'],gate=str(output),SHA256=sha(output),
                         manifests=manifests,head_pid=hp['pid'],resume_pid=rp['pid']),indent=2))

if __name__ == '__main__':
    main()
