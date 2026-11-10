"""Contract-only selector over GIVEN projections; not an M7 planner or executor.

No strategy/Data imports, prices, history, market data, or future fields.
q/y are OPEN-known conditional predicted quantities, not final matching fills.
The function returns one supplied projection unchanged. It never sizes orders.
"""
from dataclasses import dataclass
from typing import Mapping, Tuple, FrozenSet


class ContractInputError(ValueError):
    pass


@dataclass(frozen=True)
class Projection:
    retained_seeds: Tuple[str, ...]
    q: Mapping[str, int]
    y: Mapping[str, int]
    certified: bool
    plan_token: str
    close_admissible: bool = True


@dataclass(frozen=True)
class Selection:
    projection: Projection
    removed_seeds: Tuple[str, ...]
    evaluated_tokens: Tuple[str, ...]


def select_branch(
    branches: Tuple[Projection, ...],
    seed_priority: Tuple[str, ...],
    healthy_lots: FrozenSet[str],
    protected_receivers: FrozenSet[str],
    unknown_lots: FrozenSet[str] = frozenset(),
) -> Selection:
    """Seeds are highest-to-lowest priority; branches are full then suffix cuts.

    Preconditions: each supplied branch is a natural original-M7 projection of
    its own frozen CLOSE plan on the SAME causal phase/snapshot. That premise
    is not proved by this selector. Original atomic blockers must be resolved
    upstream; absence/unknown never becomes a trade permission here.
    """
    n = len(seed_priority)
    if len(set(seed_priority)) != n or len(branches) != n + 1:
        raise ContractInputError("Need one branch for each fixed suffix deletion.")
    if healthy_lots & unknown_lots:
        raise ContractInputError("UNKNOWN must not be classified as healthy.")
    for i, p in enumerate(branches):
        if p.retained_seeds != seed_priority[:n-i]:
            raise ContractInputError("Branch is not the frozen last-first path.")
        if p.certified is not True:
            raise ContractInputError("Original atomic/unknown blocker is not bypassable.")
        for quantities in (p.q, p.y):
            if any(type(v) is not int or v < 0 for v in quantities.values()):
                raise ContractInputError("Quantities must be known nonnegative integers.")
        if not protected_receivers <= p.q.keys() or not healthy_lots <= p.y.keys():
            raise ContractInputError("Missing constrained quantity is not zero.")
        if any(p.y.get(lot, 0) != 0 for lot in unknown_lots):
            raise ContractInputError("UNKNOWN lot received new optional sell permission.")
    shadow = branches[-1]
    if shadow.close_admissible is not True:
        raise ContractInputError("Certified empty-N shadow must be selectable.")
    evaluated = []
    for i, p in enumerate(branches):
        evaluated.append(p.plan_token)
        if p.close_admissible is not True:
            continue
        ok_supply = all(p.y[lot] <= shadow.y[lot] for lot in healthy_lots)
        ok_demand = all(p.q[r] >= shadow.q[r] for r in protected_receivers)
        if ok_supply and ok_demand:
            return Selection(p, tuple(reversed(seed_priority[n-i:])), tuple(evaluated))
    raise AssertionError("Empty-N branch equals its own shadow and must pass.")


def run_synthetics():
    import copy
    from dataclasses import fields
    checks = []
    def check(name, condition):
        assert condition, name
        checks.append(name)
    def p(seeds=(), q=None, y=None, label="p", certified=True):
        return Projection(tuple(seeds), q or {}, y or {}, certified, label)
    def rejects(fn):
        try:
            fn()
        except ContractInputError:
            return True
        return False
    H=frozenset({"h1","h2"})
    A=frozenset({"add1","event1"})
    P0=p(q={"add1":100,"event1":200,"residual1":300},y={"h1":100,"h2":0,"u1":0},label="shadow")
    z=select_branch((P0,),(),H,A)
    check("zero_N_returns_exact_P0_object", z.projection is P0 and not z.removed_seeds)
    full=p(("n1",),{"add1":100,"event1":200,"residual1":0},{"h1":100,"h2":0,"u1":0},"full")
    saved=copy.deepcopy((full,P0))
    out=select_branch((full,P0),("n1",),H,A,frozenset({"u1"}))
    check("nonbinding_full_unchanged",out.projection is full)
    check("RESIDUAL_has_no_floor",out.projection.q["residual1"] < P0.q["residual1"])
    check("no_reorder_clip_or_mutation",(full,P0)==saved and out.projection.y is full.y)
    bad_lot=p(("n1",),{"add1":100,"event1":200},{"h1":0,"h2":100},"bad_lot")
    check("per_lot_not_total_y",select_branch((bad_lot,P0),("n1",),H,A).projection is P0)
    bad_add=p(("n1",),{"add1":0,"event1":300},{"h1":100,"h2":0},"bad_add")
    check("per_receiver_not_total_q",select_branch((bad_add,P0),("n1",),H,A).projection is P0)
    bad_event=p(("n1",),{"add1":200,"event1":100},{"h1":100,"h2":0},"bad_event")
    check("EVENT_floor_independent",select_branch((bad_event,P0),("n1",),H,A).projection is P0)
    bad2=p(("n1","n2"),{"add1":0,"event1":200},{"h1":100,"h2":0},"both")
    first=select_branch((bad2,full,P0),("n1","n2"),H,A)
    check("fixed_lowest_seed_removed_first",first.projection is full and first.removed_seeds==("n2",))
    check("first_passing_branch_no_best_subset_search",first.evaluated_tokens==("both","full"))
    wrong=p(("n2",),{"add1":100,"event1":200},{"h1":100,"h2":0},"wrong")
    check("different_seed_subset_rejected",rejects(lambda:select_branch((bad2,wrong,P0),("n1","n2"),H,A)))
    missing=p(("n1",),{"add1":100},{"h1":100,"h2":0},"missing")
    check("missing_is_not_zero",rejects(lambda:select_branch((missing,P0),("n1",),H,A)))
    unknown_q=p(("n1",),{"add1":None,"event1":200},{"h1":100,"h2":0},"unknown_q")
    check("unknown_quantity_not_coerced",rejects(lambda:select_branch((unknown_q,P0),("n1",),H,A)))
    unknown_trade=p(("n1",),{"add1":100,"event1":200},{"h1":100,"h2":0,"u1":1},"unknown_trade")
    check("unknown_donor_no_new_permission",rejects(lambda:select_branch((unknown_trade,P0),("n1",),H,A,frozenset({"u1"}))))
    blocked=p(("n1",),{"add1":100,"event1":200},{"h1":100,"h2":0},"blocked",False)
    check("atomic_block_not_bypassed_by_empty_N",rejects(lambda:select_branch((blocked,P0),("n1",),H,A)))
    all_bad=select_branch((bad2,bad_add,P0),("n1","n2"),H,A)
    check("at_most_N_deletions",len(all_bad.removed_seeds)==2 and all_bad.projection is P0)
    # Actual M7 may have already sold money which no indivisible ADD can spend.
    # This literal relative rule intentionally inherits that baseline limitation.
    stranded0=p(q={"add1":0},y={"h1":100},label="stranded_shadow")
    stranded1=p(("n1",),{"add1":0,"seed1":100},{"h1":100},"stranded_full")
    check("inherited_stranded_cash_not_silently_repaired",
          select_branch((stranded1,stranded0),("n1",),frozenset({"h1"}),frozenset({"add1"})).projection is stranded1)
    closed=Projection(full.retained_seeds, full.q, full.y, True, "close_failed", False)
    check("CLOSE_failed_branch_cannot_revive_at_OPEN",
          select_branch((closed,P0),("n1",),H,A).projection is P0)
    check("projection_schema_has_no_future_field",
          {f.name for f in fields(Projection)}=={"retained_seeds","q","y","certified","plan_token","close_admissible"})
    check("selector_has_no_history_IO_market_data_dependency",
          not ({"open","read","load","Data","Engine","no_fill","raw_close","raw_high","raw_low","raw_volume"} & set(select_branch.__code__.co_names)))
    return {"result":"PASS_CONTRACT_SELECTOR_ONLY","checks":checks,"count":len(checks),
            "m7_interface_implemented":False,"strategy_imported":False,"history_run":False,
            "does_not_prove_input_projection_causality":True}


if __name__=="__main__":
    import json
    print(json.dumps(run_synthetics(),ensure_ascii=False,indent=2))
