"""Read saved queues only. No engine import, strategy replay, sizing or economics."""
from pathlib import Path
import hashlib, json
import pandas as pd

R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
J=R/"independent_channel_joint_economic_v1"
O=Path(__file__).resolve().parent
assert not (O/"SUMMARY.json").exists(), "No overwrite"
sources={}
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def source(p):
    sources[str(p)]=sha(p)
    return p
def csv(p):
    return pd.read_csv(source(p),float_precision="round_trip",low_memory=False)
def read(p):
    return json.loads(source(p).read_text())
def save(name,value):
    (O/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+"\n")
def role_selected(group):
    """Only legal deduplicated candidates from the original same-state queue."""
    ordered=group.sort_values("joint_feasible_rank")
    a=ordered[ordered.owner_lane.eq("AB")]
    p=ordered[ordered.owner_lane.eq("PRICE")]
    if len(a) and len(p):
        return set([a.iloc[0].event_id,p.iloc[0].event_id])
    return set(ordered.head(2).event_id)

contract=dict(
    task="AB/PRICE single-role-slot static audit",
    baseline="independent_channel_joint_economic_v1 original PVR arm, NOT DMI arm",
    rule="Given a saved day-sector legal, stock-deduplicated queue ordered by original rank_key: if both lanes exist, select first AB and first PRICE; otherwise select original first two.",
    eligible_input="Original same-close FLAT, AB-priority per stock, original industry/PVR/size legality. No new candidate, state, threshold, market gate or OPEN fallback.",
    role_order="Original known finite PVR descending then sid; unknown PRICE after known then sid. AB unknown is ineligible. Preserve relative original order among selected.",
    mechanical_examples=[
        "2022 first date-sector with old PP top2 and some legal AB",
        "2022 first date-sector with old AA top2 and some legal PRICE",
        "Prior named loss: 浪潮信息 2022-01-05, exact own sector queue",
        "2024-09-23 communications exact queue including 海能达",
        "2024-09-25 wind power exact queue including 电气风电"
    ],
    fixed_case_scope="All saved offers for 海能达002583 and 电气风电688660 during 2024-09-20..2024-10-08, plus complete legal sector queues on their offered dates; no invented daily row where no offer exists.",
    boundary="Frozen old joint state only. Gross swaps are not new fills, state paths or economics. Old outcomes are posterior labels only. 2026江丰 has no dynamic queue in these birth windows and is NOT_EVALUABLE.",
    economics_calls=0, consumer_calls=0, strategy_imports=0, parameter_search=0)
save("CONTRACT.json",contract)

summaries={}; group_tables=[]; delta_tables=[]; displaced_tables=[]; fixed_tables=[]; offer_tables=[]
for y,sub in [(2022,"relative_priority_equity_run_2022_v1/dynamic"),(2024,"cash_equity_baseline_2024_v1/economic")]:
    q=csv(J/f"economic_{y}/joint/RANKING_AUDIT.csv")
    d=csv(J/f"economic_{y}/joint/DECISIONS.csv")
    pd.testing.assert_frame_equal(q,d,check_exact=True)
    b=csv(R/"m3_stock_birth_during_sector_v1"/sub/"DECISIONS.csv")
    b=b[b.arm.eq("A_UNION_B")]
    a=pd.DataFrame(read(J/f"economic_{y}/AB_DECISION_AUDIT.json"))
    offers=pd.DataFrame(read(J/f"economic_{y}/OFFER_AUDIT.json"))
    offers.day=offers.day.str[:10]
    rounds=csv(J/f"economic_{y}/joint/ROUNDS.csv")
    q["year"]=y
    q["original_selected"]=q.joint_feasible_rank.le(2)
    assert (q.original_selected==q.selected).all()
    q["role_selected"]=False
    rows=[]
    for (day,sector),g in q.groupby(["day","sector"],sort=True):
        g=g.sort_values("joint_feasible_rank")
        assert g.sid.is_unique and g.event_id.is_unique
        assert list(g.joint_feasible_rank)==list(range(1,len(g)+1))
        assert g.stock_state_before.eq("FLAT").all() and g.close_check.eq("PASS").all()
        aa=g[g.owner_lane.eq("AB")]
        assert list(aa.original_ab_feasible_rank)==list(range(1,len(aa)+1))
        new=role_selected(g)
        q.loc[g.index,"role_selected"]=g.event_id.isin(new)
        old=set(g.loc[g.original_selected,"event_id"])
        assert len(new)==len(old)==min(2,len(g))
        if len(aa):
            assert aa.iloc[0].event_id in new
        rows.append(dict(year=y,day=day,sector=sector,n=len(g),ab=len(aa),price=int(g.owner_lane.eq("PRICE").sum()),
            old_ab=int((g.original_selected&g.owner_lane.eq("AB")).sum()),
            old_price=int((g.original_selected&g.owner_lane.eq("PRICE")).sum()),
            changed=(old!=new),removed=len(old-new),added=len(new-old)))
    gr=pd.DataFrame(rows); gr["mixed"]=gr.ab.gt(0)&gr.price.gt(0)
    group_tables.append(gr)
    changes=q[q.original_selected.ne(q.role_selected)].copy()
    changes["change"]=changes.role_selected.map({True:"ADDED",False:"REMOVED"})
    delta_tables.append(changes)
    ab_direct=q[q.owner_lane.eq("AB")&q.original_ab_feasible_rank.le(2)&~q.original_selected].copy()
    ab_direct=ab_direct.merge(b[["event_id","decision","stock_state_before"]],on="event_id",how="left",suffixes=("_joint","_baseline"),validate="one_to_one")
    displaced_tables.append(ab_direct)
    retained=set(q.loc[q.owner_lane.eq("AB")&q.original_selected,"event_id"])
    lost=b[b.decision.eq("SELECTED_PENDING")&~b.event_id.isin(retained)]
    lm=lost[["event_id"]].merge(a[["event_id","decision_before_joint","blocking_round_id","original_ab_feasible_rank"]],on="event_id",how="left",validate="one_to_one")
    lm["blocking_lane"]=lm.blocking_round_id.map(rounds.set_index("round_id").owner_lane)
    sc=lambda lane,change:int((changes.owner_lane.eq(lane)&changes.change.eq(change)).sum())
    op=int((q.original_selected&q.owner_lane.eq("PRICE")).sum())
    only=gr[gr.price.gt(0)&gr.ab.eq(0)]
    summaries[str(y)]=dict(
        legal_queue_rows=len(q),industry_days=len(gr),mixed_industry_days=int(gr.mixed.sum()),changed_industry_days=int(gr.changed.sum()),
        original_selected=int(q.original_selected.sum()),role_selected=int(q.role_selected.sum()),
        original_PRICE_selected=op,
        PRICE_removed=sc("PRICE","REMOVED"),PRICE_added=sc("PRICE","ADDED"),PRICE_net_change=sc("PRICE","ADDED")-sc("PRICE","REMOVED"),
        AB_removed=sc("AB","REMOVED"),AB_added=sc("AB","ADDED"),
        original_AB_rank_1_removed=int((changes.owner_lane.eq("AB")&changes.change.eq("REMOVED")&changes.original_ab_feasible_rank.eq(1)).sum()),
        original_AB_rank_2_removed=int((changes.owner_lane.eq("AB")&changes.change.eq("REMOVED")&changes.original_ab_feasible_rank.eq(2)).sum()),
        single_PRICE_industry_days=len(only),single_PRICE_selected=int(only.old_price.sum()),
        single_PRICE_one_candidate_days=int(only.n.eq(1).sum()),single_PRICE_two_or_more_candidate_days=int(only.n.ge(2).sum()),
        single_PRICE_selected_from_one_candidate=int(only.loc[only.n.eq(1),"old_price"].sum()),
        single_PRICE_selected_from_two_or_more_candidates=int(only.loc[only.n.ge(2),"old_price"].sum()),
        direct_same_state_AB_displaced=len(ab_direct),direct_AB_displacement_industry_days=len(ab_direct[["day","sector"]].drop_duplicates()),
        direct_AB_displacement_days=int(ab_direct.day.nunique()),direct_AB_displacement_stocks=int(ab_direct.sid.nunique()),
        direct_AB_displaced_baseline_decision=ab_direct.decision_baseline.value_counts().to_dict(),
        baseline_selected_not_retained=len(lm),
        baseline_lost_joint_reason=lm.groupby(["decision_before_joint","blocking_lane"],dropna=False).size().rename("n").reset_index().to_dict("records"),
        direct_effect_scope="Fix the saved joint state, remove PRICE from this close queue, compare top2. Not a dynamic AB-only rerun or a financial causal effect.",
        added_unknown_PRICE=int((changes.owner_lane.eq("PRICE")&changes.change.eq("ADDED")&changes.PVR_known.eq(False)).sum()))
    if y==2022:
        fixed=[]
        for label,cond in [("MECHANICAL_FIRST_PP_WITH_AB",gr.mixed&gr.old_price.eq(2)),("MECHANICAL_FIRST_AA_WITH_PRICE",gr.mixed&gr.old_ab.eq(2))]:
            z=gr.loc[cond].sort_values(["day","sector"]).iloc[0]
            zq=q[q.day.eq(z.day)&q.sector.eq(z.sector)].copy();zq["case"]=label;fixed.append(zq)
        z=q[q.day.eq("2022-01-05")&q.sid.eq("000977.SZ")].iloc[0]
        zq=q[q.day.eq(z.day)&q.sector.eq(z.sector)].copy();zq["case"]="FIXED_2022_LOSS_LANGCHAO";fixed.append(zq)
        fixed_tables+=fixed
        rr=rounds[rounds.sid.eq("000977.SZ")&rounds.signal_day.eq("2022-01-05")]
        summaries[str(y)]["fixed_old_loss_label_only"]=rr[["sid","signal_day","status","net_pnl"]].to_dict("records")
    else:
        f=offers[offers.sid.isin(["002583.SZ","688660.SH"])&offers.day.between("2024-09-20","2024-10-08")].copy()
        f["year"]=y;offer_tables.append(f)
        for (day,sector),g in f.groupby(["day","sector"]):
            zq=q[q.day.eq(day)&q.sector.eq(sector)].copy()
            if len(zq):
                zq["case"]="FIXED_924_WINDOW_COMPLETE_SECTOR_QUEUE";fixed_tables.append(zq)
        named=q[q.sid.isin(["002583.SZ","688660.SH"])&q.day.between("2024-09-20","2024-10-08")]
        summaries[str(y)]["named_saved_selection_projection"]=named[["day","sid","owner_lane","original_ab_feasible_rank","joint_feasible_rank","original_selected","role_selected"]].to_dict("records")
    assert sc("PRICE","REMOVED")==sc("AB","ADDED")
    assert sc("AB","REMOVED")==sc("PRICE","ADDED")

for name,tables in [("QUEUE_GROUPS.csv",group_tables),("STATIC_SELECTION_CHANGES.csv",delta_tables),
                    ("DIRECT_SAME_STATE_AB_DISPLACEMENT.csv",displaced_tables),("FIXED_CASE_QUEUES.csv",fixed_tables),("FIXED_CASE_OFFERS.csv",offer_tables)]:
    pd.concat(tables,ignore_index=True).to_csv(O/name,index=False)
for name in ["joint_engine.py","joint_policy.py","execution_book.py","PROTOCOL_DRAFT.md","READOUT.md"]:
    source(J/name)
source(R/"account_integration_audit_v1/READOUT.md")
source(R/"breadth_member_quality_v1/READOUT.md")
save("SUMMARY.json",summaries)
save("SOURCE_SHA256.json",sources)
assert all(sha(Path(p))==digest for p,digest in sources.items())
save("QA.json",dict(status="PASS_READ_ONLY_STATIC_QUEUE_AUDIT",source_files_unchanged=True,
    rankings_equal_saved_decisions=True,unique_stock_per_queue=True,contiguous_original_ranks=True,
    AB_rank_is_recomputed_within_saved_joint_state=True,per_queue_selected_cardinality_equal=True,
    best_AB_never_removed=True,all_original_AB_removed_are_second_AB=True,
    economic_calls=0,consumer_calls=0,engine_imports=0,files_modified_outside_output_directory=0,
    limitations=["Static saved-state projection only","No new OPEN, parent, ADD, holding, exit or economics",
        "No 2026 dynamic queue available in these 2022/24 birth-window outputs",
        "Formal partial PROBE remainder contract is not a historical partial-fill observation"]))
save("OUTPUT_SHA256.json",{p.name:sha(p) for p in sorted(O.iterdir()) if p.is_file() and p.name!="OUTPUT_SHA256.json"})
print(json.dumps(summaries,ensure_ascii=False,indent=2,default=str))
