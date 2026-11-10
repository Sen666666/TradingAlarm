"""Independent exact arithmetic, saved-rank invariance and fixed-counterexample join."""
import csv
import hashlib
import json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'features/DAILY_CENTERED_FEATURES.csv'
OLD = ROOT.parent / 'shrinkage_breadth_v6/ALL_REMOVED_SPARSE_UPPER_TAIL_EVALUATION_ONLY.csv'
with OLD.open(encoding='utf-8-sig') as handle:
    old_rows = list(csv.DictReader(handle))
old = {(r['date'], r['sector_id_static']): r for r in old_rows}
assert len(old) == 62
joined = []
checks = Counter()
per_day = {}
with SRC.open(encoding='utf-8-sig') as handle:
    for r in csv.DictReader(handle):
        n, u1, u0 = (int(r[k]) for k in ['n', 'u1', 'u0'])
        dm = F(r['m1_exact']) - F(r['m0_exact'])
        du = u1 - u0
        d = F(du, n + 10) - F(n, n + 10) * dm
        assert d == F(r['D_center_exact'])
        assert d == F(r['D_shrunk_exact']) - dm
        assert d == F(n, n + 10) * (F(du, n) - dm)
        checks['main_exact_rows'] += 1
        if r['date'] in per_day:
            assert per_day[r['date']] == dm
        else:
            per_day[r['date']] = dm
        for new, previous in [
            ('p_D_center_exact', 'p_D_shrunk_exact'),
            ('D_center_order', 'D_shrunk_order'),
            ('D_center_score_tie_count', 'D_shrunk_score_tie_count'),
            ('D_center_mathematical_rank_min', 'D_shrunk_mathematical_rank_min'),
            ('Tcenter_score_exact', 'T10_score_exact'),
            ('Tcenter_order', 'T10_order'),
            ('Tcenter_selected', 'T10_selected'),
        ]:
            assert r[new] == r[previous], (r['date'], r['sector_id_static'], new)
        checks['main_saved_rank_and_T_identity_rows'] += 1
        n1 = int(r['market_n1']) - n
        a1 = int(r['market_up1']) - u1
        n0 = int(r['market_n0_ownU']) - int(r['N_U_previous5'])
        a0 = int(r['market_up0_ownU']) - int(r['old_ownU_up_lag5_recovered'])
        assert n1 > 0 and n0 > 0 and 0 <= a1 <= n1 and 0 <= a0 <= n0
        assert [a1, n1, a0, n0] == [int(r[k]) for k in [
            'loo_market_up1', 'loo_market_n1', 'loo_market_up0_ownU', 'loo_market_n0_ownU']]
        dlo = F(n, n + 10) * (F(du, n) - (F(a1, n1) - F(a0, n0)))
        assert dlo == F(r['D_center_excl_exact'])
        checks['LOO_exact_rows_and_correct_old_ownU_subtraction'] += 1
        checks['LOO_D_order_changed_rows'] += r['D_center_order'] != r['D_center_excl_order']
        checks['LOO_T_order_changed_rows'] += r['Tcenter_order'] != r['Tcenter_excl_order']
        checks['LOO_selected_changed_rows'] += r['Tcenter_selected'] != r['Tcenter_excl_selected']
        key = (r['date'], r['sector_id_static'])
        if key in old:
            o = old[key]
            assert r['n'] == o['n'] and r['T0_selected'] == 'True' and r['Tcenter_selected'] == 'False'
            keys = ['n', 'u0', 'u1', 'd_mkt', 'D_original', 'D_shrunk', 'D_center',
                    'D_original_order', 'D_shrunk_order', 'D_center_order', 'D_center_excl',
                    'D_center_excl_order', 'T0_order', 'T10_order', 'Tcenter_order',
                    'Tcenter_selected', 'Tcenter_excl_order', 'Tcenter_excl_selected']
            joined.append({**o, **{k: r[k] for k in keys}})
assert checks['main_exact_rows'] == 97650 and len(per_day) == 1085
assert len(joined) == 62
joined.sort(key=lambda r: (r['date'], r['sector_id_static']))
with (ROOT / 'FIXED_62_SPARSE_COUNTEREXAMPLES.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(joined[0]))
    writer.writeheader()
    writer.writerows(joined)
result = {
    'status': 'PASS_EXACT_ARITHMETIC_AND_SAVED_INVARIANCE_NOT_ALPHA',
    'rows': dict(checks), 'sessions': len(per_day),
    'fixed_old_sparse_counterexamples': len(joined),
    'of_these_main_centered_selected': sum(r['Tcenter_selected'] == 'True' for r in joined),
    'of_these_LOO_selected': sum(r['Tcenter_excl_selected'] == 'True' for r in joined),
    'new_labels': 0, 'new_accounts': 0,
    'bindings': {str(p.relative_to(ROOT.parent.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in [SRC, OLD, Path(__file__)]},
}
(ROOT / 'ROOT_INDEPENDENT_CHECK.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False))
