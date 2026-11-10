"""Describe, validate, or run the finite first-ten frozen historical package.

Current-survivor/current-classification historical development only. Actual data
and economic assumptions require separate, hashed closeout/freeze evidence.
This module neither supplies missing evidence nor certifies its economic truth.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Sequence

ROUND_ID = "current-pool-20261022"
ROUND = Path(__file__).resolve().parents[1]
RESEARCH_BASIS = "current_pool_historical_development"
INITIAL_CAPITAL_CNY = 1_000_000.0


@dataclass(frozen=True)
class StrategyAllocation:
    gross_fraction: float = 0.90
    initial_budget_divisor: int = 6
    max_issuers: int = 6
    max_sectors: int = 3
    max_issuers_per_sector: int = 2
    budget_rule: str = "freeze_initial_budget_and_share_cap_no_daily_topup"


@dataclass(frozen=True)
class PassiveAllocation:
    gross_fraction: float = 0.90
    rebalance: str = "account_start_then_first_common_decision_each_year"
    weighting: str = "equal_target_cap_per_eligible_issuer"
    issuer_line_rule: str = "lowest_stable_security_id_among_eligible_lines"
    quantity_rule: str = "actual_dated_quantity_rules_unaffordable_lot_leaves_cash"
    execution_order: str = "next_executable_event_sells_before_buys"
    # Deliberately no strategy slot/sector caps and no fractional-share target.


@dataclass(frozen=True)
class Stress:
    name: str
    variable_components_multiplier: int = 1
    extra_executable_events: int = 0
    cost_scope: str = "variable_components_only_as_named_in_frozen_economic_protocol"
    delay_clock: str = "eligible_executable_events_not_calendar_days"


@dataclass(frozen=True)
class AccountSpec:
    account_id: str
    variant: str
    stress: Stress
    allocation: StrategyAllocation | PassiveAllocation
    initial_capital_cny: float = INITIAL_CAPITAL_CNY
    currency: str = "CNY"
    financing: bool = False
    shorting: bool = False


def first10_specs() -> tuple[AccountSpec, ...]:
    stresses = (Stress("base"), Stress("cost2", 2), Stress("delay1", 1, 1))
    strategies = tuple(
        AccountSpec(f"{variant}_{stress.name}", variant, stress, StrategyAllocation())
        for variant in ("T0", "T1", "S0") for stress in stresses
    )
    return strategies + (AccountSpec("B0_base", "B0", Stress("base"), PassiveAllocation()),)


def describe() -> dict:
    return {
        "round_id": ROUND_ID,
        "research_basis": RESEARCH_BASIS,
        "mode": "frozen_package_entry",
        "account_execution_available": True,
        "economic_account_runs": 0,
        "account_target_start": "2015-01-01",
        "history_warmup_target_start": "2013-01-01",
        "algorithm_policy": "unchanged_frozen_states_and_ranks_shared_by_all_accounts",
        "required_evidence": ["data_closeout", "economic_protocol_frozen"],
        "accounts": [asdict(spec) for spec in first10_specs()],
        "limits": [
            "Current surviving pool and current classification are selection assumptions, not PIT facts.",
            "No fee values, actual/proxy execution assumptions, or additional strategy are chosen here.",
            "Validated declarations and hashes do not themselves establish data or economic correctness.",
            "B0 target caps are not orders, fills, shares, or proof of affordable board lots.",
        ],
    }


@dataclass(frozen=True)
class PassiveLine:
    """Caller-certified eligible line at one annual common decision cutoff."""
    security_id: str
    issuer_id: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in (self.security_id, self.issuer_id)):
            raise ValueError("Stable security and issuer IDs required; unknown lines cannot be resolved here")


@dataclass(frozen=True)
class PassiveTargetCap:
    security_id: str
    issuer_id: str
    budget_cap_cny: float


@dataclass(frozen=True)
class AnnualTargetPlan:
    targets: tuple[PassiveTargetCap, ...]
    duplicate_issuer_lines: tuple[str, ...]
    target_total_cny: float
    residual_cash_before_costs_cny: float


def annual_target_caps(nav_cny: float, eligible_lines: Sequence[PassiveLine]) -> AnnualTargetPlan:
    """Plan B0's annual 90% equal caps, with no slot allocator or trades.

    The caller identifies the account start/annual common decision and supplies
    eligibility from the shared data range. Missing identities are an error,
    not silently removed. Actual dated lots/costs/settlement are applied later;
    one line's unused cap must not be redistributed by this planning function.
    """
    if (isinstance(nav_cny, bool) or not isinstance(nav_cny, (int, float))
            or not math.isfinite(nav_cny) or nav_cny <= 0):
        raise ValueError("Positive finite NAV required")
    if any(type(line) is not PassiveLine for line in eligible_lines):
        raise ValueError("Explicit eligible PassiveLine records required")
    if len({line.security_id for line in eligible_lines}) != len(eligible_lines):
        raise ValueError("Duplicate stable security ID")
    chosen, duplicate, issuers = [], [], set()
    for line in sorted(eligible_lines, key=lambda x: x.security_id):
        if line.issuer_id in issuers:
            duplicate.append(line.security_id)
        else:
            chosen.append(line)
            issuers.add(line.issuer_id)
    total = 0.90 * nav_cny if chosen else 0.0
    per_issuer = total / len(chosen) if chosen else 0.0
    targets = tuple(PassiveTargetCap(line.security_id, line.issuer_id, per_issuer)
                    for line in chosen)
    return AnnualTargetPlan(targets, tuple(duplicate), total, nav_cny - total)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_evidence(path: Path | None, kind: str, scope: Path) -> dict:
    if path is None:
        raise ValueError(f"Explicit {kind} evidence file required")
    path = Path(path).resolve()
    evidence = json.loads(path.read_text())
    allowed_status = ("closed", "data_pool_closed") if kind == "data_closeout" else ("frozen",)
    if (evidence.get("kind") != kind or evidence.get("round_id") != ROUND_ID
            or evidence.get("status") not in allowed_status):
        raise ValueError(f"Incorrect {kind} identity/status")
    if evidence.get("scope_sha256") != _sha(scope):
        raise ValueError(f"{kind} does not bind the current scope")
    recorded = datetime.fromisoformat(evidence.get("recorded_at", ""))
    if recorded.tzinfo is None or recorded.utcoffset() is None:
        raise ValueError("Evidence recorded_at must include timezone")
    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError(f"{kind} requires explicit artifact paths and SHA256 hashes")
    for name, digest in artifacts.items():
        if (not isinstance(name, str) or not name or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Malformed evidence artifact entry")
        artifact = path.parent / name
        if not artifact.is_file() or _sha(artifact) != digest:
            raise ValueError(f"Missing or changed evidence artifact: {name}")
    return {"path": str(path), "sha256": _sha(path), "kind": kind,
            "status": evidence['status'], "artifact_count": len(artifacts)}


def validate(*, data_closeout: Path | None = None,
             economic_protocol_frozen: Path | None = None,
             scope: Path = ROUND / "scope.json") -> dict:
    """Check explicit declarations and their files. Never start an account."""
    scope = Path(scope)
    scope_data = json.loads(scope.read_text())
    if (scope_data.get("algorithm_changes_allowed") != 0
            or scope_data.get("account_runs_before_data_closeout") != 0
            or scope_data.get("live_trading") is not False):
        raise ValueError("Scope must preserve the algorithm/data-closeout/offline boundaries")
    checks = [
        _read_evidence(data_closeout, "data_closeout", scope),
        _read_evidence(economic_protocol_frozen, "economic_protocol_frozen", scope),
    ]
    return dict(describe(), evidence_checks=checks,
                validation="declared_evidence_and_artifact_hashes_checked_no_accounts_run")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("describe", "validate", "run"))
    parser.add_argument("--data-closeout", type=Path)
    parser.add_argument("--economic-protocol-frozen", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == 'run':
            if args.package is None or args.output is None:
                raise ValueError('run requires an explicit frozen --package and new --output directory')
            result = run(args.package, args.output)
        else:
            result = describe() if args.mode == "describe" else validate(
                data_closeout=args.data_closeout,
                economic_protocol_frozen=args.economic_protocol_frozen)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


def run(package, output):
    # Lazy import avoids a cycle and keeps describe/validate strictly non-executing.
    from history_runner import run_frozen_package
    return run_frozen_package(package, output)


if __name__ == "__main__":
    raise SystemExit(main())
