"""Read frozen OHLCV and append a separate price-clock/volume-clock clarification."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from prepare_ohlcv import OHLC, total_return_ohlcv


ROOT = Path(__file__).resolve().parent
RESEARCH = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research")
THS = {
    "HK00002": "UHKMHK0002", "HK09618": "UHKMHK9618", "HK00700": "UHKMHK0700",
    "HK03033": "UHKTHK3033", "HK00101": "UHKMHK0101", "HK03690": "UHKMHK3690",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    output = ROOT / "observation-mask-addendum.json"
    if output.exists():
        raise FileExistsError("Refusing to overwrite validation addendum")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    freeze = json.loads((ROOT / "freeze.json").read_text())
    assert sha(ROOT / "manifest.json") == freeze["manifest_sha256"]
    assert sha(ROOT / "prepare_ohlcv.py") == freeze["script_sha256"]
    assert all(sha(Path(path)) == expected for path, expected in manifest["dependencies"].items())
    results = []
    prefix_checks = 0
    for item in manifest["series"]:
        symbol = item["symbol"]
        path = ROOT / item["output"]
        assert sha(path) == item["output_sha256"]
        f = pd.read_csv(path, index_col="date", parse_dates=True)
        finite_prices = np.isfinite(f[OHLC]).all(axis=1) & f[OHLC].gt(0).all(axis=1)
        geometry = (
            f.low.le(f[["open", "close", "high"]].min(axis=1) + 1e-12)
            & f.high.ge(f[["open", "close", "low"]].max(axis=1) - 1e-12)
        )
        price_valid = finite_prices & geometry & f.observed_bar & ~f.synthetic_event_bar
        price_valid &= f.source_anomaly.fillna("").eq("")
        volume_valid = np.isfinite(f.volume) & f.volume.gt(0)
        placeholders = []
        reference = None
        if symbol in THS:
            ref = RESEARCH / f"data/ths-index-history-9603-20261018/canonical/{THS[symbol]}.csv"
            dates = set(pd.read_csv(ref).date)
            reference = {"path": str(ref), "sha256": sha(ref)}
            for date, row in f.loc[f.raw_volume.eq(0)].iterrows():
                prior = f.raw_close.iloc[f.index.get_loc(date) - 1]
                flat = len({row["raw_" + c] for c in OHLC}) == 1
                same_prior = row.raw_close == prior
                absent = str(date.date()) not in dates
                # A zero volume alone never decides price validity.
                if flat and same_prior and absent:
                    price_valid.loc[date] = False
                    placeholders.append({
                        "date": str(date.date()), "raw_volume": 0,
                        "raw_ohlc_equal_previous_close": True,
                        "absent_from_other_saved_ths_source": True,
                        "decision": "exclude this sourced carry-forward placeholder from price observations",
                    })
        factor = f.adjustment_factor
        assert np.isfinite(factor).all() and factor.gt(0).all()
        for col in OHLC:
            np.testing.assert_allclose(f[col], f["raw_" + col] * factor, rtol=1e-10, atol=1e-10)
        np.testing.assert_allclose(f.volume, f.raw_volume * f.volume_factor, rtol=1e-10, atol=1e-8)
        meta = item["metadata"]
        if meta["kind"] in ("ETF", "HK ETF", "HK stock"):
            raw = f[["raw_" + col for col in OHLC + ["volume"]]].rename(
                columns=lambda name: name.removeprefix("raw_")
            )
            dividends = meta.get("dividends", []) + meta.get("in_kind_signal_adjustments", [])
            for cut in (min(75, len(f)), len(f) // 2, len(f) - 1):
                prefix = total_return_ohlcv(raw.iloc[:cut], dividends, meta.get("splits", []))
                np.testing.assert_allclose(
                    prefix[OHLC + ["volume"]], f.iloc[:cut][OHLC + ["volume"]],
                    rtol=1e-10, atol=1e-8,
                )
                prefix_checks += 1
        results.append({
            "symbol": symbol,
            "price_observed_rows": int(price_valid.sum()),
            "volume_known_rows": int(volume_valid.sum()),
            "range_defined_rows": int((price_valid & f.high.gt(f.low)).sum()),
            "exclude_price_dates": [str(d.date()) for d in f.index[~price_valid]],
            "volume_unknown_dates": [str(d.date()) for d in f.index[~volume_valid]],
            "placeholders": placeholders, "other_source_reference": reference,
            "old_valid_flag_happens_to_match_price_mask_in_this_frozen_dataset": bool(price_valid.equals(f.valid)),
        })
    result = {
        "manifest_sha256": sha(ROOT / "manifest.json"),
        "script_sha256": sha(Path(__file__)),
        "frozen_csv_unchanged": True, "source_hashes_unchanged": True,
        "common_daily_OHLC_factor_verified": True,
        "dated_event_adjustment_prefix_checks": prefix_checks,
        "price_mask": "finite positive OHLC, valid high/low geometry, observed source bar, not synthetic_event_bar, not explicitly quarantined source anomaly or verified carry-forward placeholder; independent of volume availability",
        "volume_mask": "finite positive volume means available volume evidence; missing/zero without independent placeholder evidence does not remove a valid price observation",
        "range_mask": "price_mask and high>low; H=L means close-in-range and spread-based ratios unavailable, not fabricated",
        "important": "CSV valid/geometry_valid were frozen with a stricter joint-volume convention. Use this addendum's price-clock rule in the next observer; do not generalize the old flag to future volume-missing data.",
        "series": results,
    }
    with output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({
        "series": len(results), "adjustment_prefix_checks": prefix_checks,
        "placeholders_excluded": sum(len(r["placeholders"]) for r in results),
        "all_joint_flags_equal_current_price_mask": all(
            r["old_valid_flag_happens_to_match_price_mask_in_this_frozen_dataset"] for r in results
        ),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
