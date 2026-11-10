"""Read-only independent audit; --archive writes only new files beside this script.

Never imports or reruns analyze.py, changes frozen state, reads outcome labels,
or runs an account. Joint completion is an audit of bound conservatism only.
"""
from pathlib import Path
import argparse
import collections
import csv
import datetime
import hashlib
import itertools
import json
import math
import statistics

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROJECT = ROOT.parent
EPS = 1e-8


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", action="store_true",
                        help="Create audit CSV/JSON once, only in this directory.")
    args = parser.parse_args()
    # Protect all pre-existing parent artifacts, not just files consumed below.
    before = {str(p): sha(p) for p in ROOT.iterdir() if p.is_file()}
    consumed = [ROOT / name for name in [
        "MEMBER_FEATURES.parquet", "DATE_CONTEXT.csv", "FEATURES_PRELABEL.csv",
        "FIXED_CASE_IDENTITIES.csv", "FEATURE_QA.json", "FEATURE_SEAL.json",
        "SOURCE_CHECKS.csv", "COMPLETENESS_QA_SUPPLEMENT.json",
        "EMPTY_SOURCE_FIELD_AUDIT.csv", "MISSING_PRICE_SUBREASONS.csv",
        "PROTOCOL.json", "analyze.py",
    ]]
    old_a = PROJECT / "lagged_amount_order_preflight_v1/FIXED_CASE_IDENTITIES.csv"
    old_b = PROJECT / "cross_window_entry_mechanism_v1/FIXED_CASES.csv"
    consumed.extend([old_a, old_b])
    rr = pd.read_parquet(ROOT / "MEMBER_FEATURES.parquet")
    dc = pd.read_csv(ROOT / "DATE_CONTEXT.csv")
    dc.day = pd.to_datetime(dc.day)
    fc = pd.read_csv(ROOT / "FEATURES_PRELABEL.csv")
    frozen = pd.read_csv(ROOT / "FIXED_CASE_IDENTITIES.csv")
    a = pd.read_csv(old_a)
    b = pd.read_csv(old_b)
    ka = set(zip(a.sid, a.signal_day))
    kb = set(zip(b.sid, b.day))
    actual_cases = set(zip(frozen.sid, frozen.day))
    assert len(a) == 40 and len(b) == 25
    assert actual_cases == ka | kb and len(actual_cases) == 63
    assert len(frozen) == 63 and not fc.duplicated(["sid", "day"]).any()
    assert set(zip(fc.sid, fc.day)) == actual_cases
    assert len(dc) == 42 and len(rr) == 1709 * 42

    known = rr[rr.known]
    m_error = max(abs((1 + .5 * math.tanh(math.log(float(x) / float(y)))) - m)
                  for x, y, m in zip(known.amount, known.amount_ref21, known.m))
    assert m_error < 1e-14
    assert all(.5 <= m <= 1.5 for m in known.m)
    assert all((r > 0) - (r < 0) == s for r, s in zip(known.r, known.direction))

    joint = []
    max_error = 0.0
    finite_count = 0
    for day, g in rr.groupby("day"):
        z = dc[dc.day.eq(day)].iloc[0]
        kg = g[g.known]
        up = kg[kg.direction.eq(1)]
        down = kg[kg.direction.eq(-1)]
        flat = kg[kg.direction.eq(0)]
        nu, nd, missing = len(up), len(down), 1709 - len(kg)
        su, sd = math.fsum(up.m), math.fsum(down.m)
        assert len(g) == 1709 and g.sid.nunique() == 1709
        assert (nu, nd, len(flat), missing) == (z.n_up, z.n_down, z.n_flat, z.M)
        row = dict(day=str(day.date()), frozen_state=z.state,
                   n_up=nu, n_down=nd, n_flat=len(flat), M=missing,
                   sum_up_fsum=su, sum_down_fsum=sd,
                   frozen_D_L=None, frozen_D_U=None,
                   inf_D=None, inf_up_k=None, inf_down_k=None,
                   sup_D=None, sup_up_k=None, sup_down_k=None,
                   interior_inf_witness_D=None, interior_sup_witness_D=None,
                   both_sign_witnesses=False, audit_result="EMPTY_KNOWN_DIRECTION_NOT_ENUMERATED")
        if not nu or not nd:
            assert z.state == "UNKNOWN" and z.reason == "EMPTY_KNOWN_DIRECTION"
            assert math.isnan(z.D)
            joint.append(row)
            continue
        finite_count += 1
        vals = dict(D=sd / nd - su / nu,
                    D_L=(sd + .5 * missing) / (nd + missing) - (su + 1.5 * missing) / (nu + missing),
                    D_U=(sd + 1.5 * missing) / (nd + missing) - (su + .5 * missing) / (nu + missing))
        for key, value in vals.items():
            error = abs(value - z[key])
            max_error = max(max_error, error)
            assert error < 1e-12
        assert vals["D_L"] <= vals["D"] <= vals["D_U"]
        state = "PRESSURE" if vals["D_L"] > 0 else "NO_PRESSURE" if vals["D_U"] <= 0 else "UNKNOWN"
        assert state == z.state

        # Every unknown is assigned once. k is the number assigned to up.
        # For minima, up gets 1.5 and down gets .5; maxima reverse them.
        # Assigning a flat unknown to either beneficial endpoint cannot worsen
        # the extremum, so enumerating all M assignments also covers flat cases.
        minima = []
        maxima = []
        for k in range(missing + 1):
            kd = missing - k
            minima.append(((sd + .5 * kd) / (nd + kd) - (su + 1.5 * k) / (nu + k), k))
            maxima.append(((sd + 1.5 * kd) / (nd + kd) - (su + .5 * k) / (nu + k), k))
        low, kl = min(minima)
        high, kh = max(maxima)
        # Strict interior m values are reachable with positive finite A/ref.
        lo_witness = (sd + (.5 + EPS) * (missing - kl)) / (nd + missing - kl) - (su + (1.5 - EPS) * kl) / (nu + kl)
        hi_witness = (sd + (1.5 - EPS) * (missing - kh)) / (nd + missing - kh) - (su + (.5 + EPS) * kh) / (nu + kh)
        assert vals["D_L"] - 1e-12 <= low <= high <= vals["D_U"] + 1e-12
        both = lo_witness < 0 < hi_witness
        result = "BOTH_SIGNS_FEASIBLE" if both else "EXCLUDES_D_POSITIVE" if high <= 0 else "ONLY_D_POSITIVE" if low > 0 else "OTHER"
        row.update(frozen_D_L=vals["D_L"], frozen_D_U=vals["D_U"],
                   inf_D=low, inf_up_k=kl, inf_down_k=missing - kl,
                   sup_D=high, sup_up_k=kh, sup_down_k=missing - kh,
                   interior_inf_witness_D=lo_witness, interior_sup_witness_D=hi_witness,
                   both_sign_witnesses=both, audit_result=result)
        joint.append(row)

    # Independent finite-grid completion test of the original outer bounds.
    tested = 0
    for nu, nd, mu, md, missing in itertools.product(
            range(1, 4), range(1, 4), [.5, .75, 1, 1.25, 1.5], [.5, .75, 1, 1.25, 1.5], range(5)):
        su, sd = nu * mu, nd * md
        lo = (sd + .5 * missing) / (nd + missing) - (su + 1.5 * missing) / (nu + missing)
        hi = (sd + 1.5 * missing) / (nd + missing) - (su + .5 * missing) / (nu + missing)
        for assignments in itertools.product([(0, 1), (1, .5), (1, 1.5), (-1, .5), (-1, 1.5)], repeat=missing):
            us = [v for s, v in assignments if s == 1]
            ds = [v for s, v in assignments if s == -1]
            value = (sd + sum(ds)) / (nd + len(ds)) - (su + sum(us)) / (nu + len(us))
            assert lo - 1e-14 <= value <= hi + 1e-14
            tested += 1

    supplement = json.loads((ROOT / "COMPLETENESS_QA_SUPPLEMENT.json").read_text())
    original_qa = json.loads((ROOT / "FEATURE_QA.json").read_text())
    blanks = pd.read_csv(ROOT / "EMPTY_SOURCE_FIELD_AUDIT.csv")
    missing_detail = pd.read_csv(ROOT / "MISSING_PRICE_SUBREASONS.csv")
    assert len(blanks) == 0 and supplement["empty_source_field_windows"] == 0
    assert finite_count == 41 and supplement["finite_dates"] == 41
    assert supplement["all_known_finite_D_inside_bounds"] is True
    assert original_qa["known_inside_outer_bounds"] is False
    assert sum(supplement["missing_subreason_counts"].values()) == 7405 == len(missing_detail)
    assert supplement["missing_subreason_counts"] == {
        "TARGET_BEFORE_FIRST_SOURCE_OBSERVATION": 6679,
        "INTERNAL_MISSING_COMMON_PRICE": 473,
        "WINDOW_BEFORE_FIRST_SOURCE_OBSERVATION": 253,
    }

    seal = json.loads((ROOT / "FEATURE_SEAL.json").read_text())
    seal_checks = {name: sha(ROOT / name) == h for name, h in seal.items()}
    assert all(seal_checks.values())
    # Small source-level checks, distinct from the parent's whole-source audit.
    sc = pd.read_csv(ROOT / "SOURCE_CHECKS.csv").set_index("sid")
    calendar_path = Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
    consumed.append(calendar_path)
    with np.load(calendar_path, allow_pickle=False) as npz:
        calendar = pd.DatetimeIndex(npz["dates"])
    sample_results = []
    for sid, day in [("600056.SH", "2022-03-03"), ("300666.SZ", "2024-09-30"),
                     ("000034.SZ", "2022-05-06"), ("301611.SZ", "2026-01-06")]:
        t = pd.Timestamp(day)
        ix = calendar.get_loc(t)
        path = Path(sc.loc[sid, "path"])
        consumed.append(path)
        q = pd.read_parquet(path).reindex(calendar[ix - 21:ix + 1])
        original = rr[rr.sid.eq(sid) & rr.day.eq(t)].iloc[0]
        assert len(q) == 22
        assert not q.source_kind.fillna("").str.strip().eq("").any()
        assert not q.source_path.fillna("").str.strip().eq("").any()
        sample = dict(sid=sid, day=day, known=bool(original.known), reason=original.reason)
        if original.known:
            ref = statistics.median(q.amount.tolist()[:-1])
            r = math.log(float(q.close.iloc[-1]) / float(q.close.iloc[-2]))
            m = 1 + .5 * math.tanh(math.log(float(q.amount.iloc[-1]) / ref))
            assert abs(ref - original.amount_ref21) < 1e-8
            assert abs(r - original.r) < 1e-14 and abs(m - original.m) < 1e-14
            sample.update(amount_ref=ref, r=r, m=m)
        else:
            assert original.reason == "FACTOR_CHANGE_WITHIN22"
            assert not np.isclose(q.adjustment_factor, q.adjustment_factor.iloc[-1], rtol=1e-11, atol=0).all()
            sample.update(factor_min=float(q.adjustment_factor.min()), factor_max=float(q.adjustment_factor.max()))
        sample_results.append(sample)

    finite_joint = [r for r in joint if r["inf_D"] is not None]
    excluded = [r for r in finite_joint if r["sup_D"] <= 0]
    assert len(finite_joint) == 41
    assert sum(r["both_sign_witnesses"] for r in finite_joint) == 40
    assert [r["day"] for r in excluded] == ["2024-12-03"]
    assert not any(r["inf_D"] > 0 for r in finite_joint)
    assert all(sha(path) == h for path, h in before.items())
    source_hashes = {str(p): sha(p) for p in sorted(set(consumed))}
    summary = dict(
        audit_scope="READ_ONLY_RECONSTRUCTION_NO_NEW_CANDIDATE_NO_LABELS_NO_ACCOUNTS",
        cases=len(frozen), dates=len(dc), member_rows=len(rr),
        overlap=sorted(ka & kb), known_rows=int(rr.known.sum()),
        unknown_rows=int((~rr.known).sum()),
        unknown_reasons=rr.loc[~rr.known, "reason"].value_counts().to_dict(),
        K_minmax=[int(dc.K.min()), int(dc.K.max())],
        M_minmax=[int(dc.M.min()), int(dc.M.max())],
        frozen_states=dc.state.value_counts().to_dict(),
        finite_D_rows=finite_count, known_point_positive_dates=int(dc.D.gt(0).sum()),
        known_point_nonpositive_dates=int(dc.D.le(0).sum()),
        empty_direction_dates=[r["day"] for r in joint if r["inf_D"] is None],
        aggregate_max_abs_error=max_error, all_known_m_max_abs_error=m_error,
        independent_discrete_outer_bound_tests=tested,
        original_QA_false_retained=True,
        QA_explanation="One NaN empty-direction row makes the original all-comparison false; all 41 finite rows are contained.",
        minimum_abs_finite_frozen_D_L=float(dc.D_L.abs().min()),
        minimum_abs_finite_frozen_D_U=float(dc.D_U.abs().min()),
        joint_completion_both_sign_dates=40,
        joint_completion_excludes_positive=excluded,
        joint_completion_only_positive_dates=0,
        joint_completion_min_abs_endpoint=min(min(abs(r["inf_D"]), abs(r["sup_D"])) for r in finite_joint),
        joint_completion_interior_epsilon=EPS,
        joint_completion_scope="Feasibility only under frozen unknown-direction and m-interval model; not reconstruction of absent raw observations or their partial constraints. Endpoints are infimum/supremum; strict interior sign witnesses are also shown.",
        no_frozen_state_replaced=True,
        completeness_supplement=supplement,
        empty_source_field_audit_rows=len(blanks),
        source_sample_checks=sample_results,
        sealed_file_count=len(seal_checks), sealed_hashes_all_match=True,
        all_preexisting_parent_artifacts_unchanged=True,
        source_hashes=source_hashes,
    )
    if args.archive:
        with (HERE / "JOINT_COMPLETION_BY_DATE.csv").open("x", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(joint[0]))
            writer.writeheader()
            writer.writerows(joint)
        with (HERE / "AUDIT_SUMMARY.json").open("x") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
        with (HERE / "AUDIT_SOURCE_HASHES.json").open("x") as stream:
            json.dump(source_hashes, stream, ensure_ascii=False, indent=2)
    else:
        archived = HERE / "JOINT_COMPLETION_BY_DATE.csv"
        if archived.exists():
            old = pd.read_csv(archived)
            new = pd.DataFrame(joint)
            pd.testing.assert_frame_equal(old, new, check_dtype=False, rtol=0, atol=1e-12)
            summary["archived_joint_table_matches"] = True
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
    print("\nJOINT_COMPLETION_BY_DATE")
    print(pd.DataFrame(joint).to_csv(index=False))


if __name__ == "__main__":
    main()
