"""Attach original repaired SELECTED opportunity labels only. Not new entrant economics."""
from pathlib import Path
import json,hashlib,datetime
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;E=R/"m3_stock_birth_during_sector_v1"
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
seal=json.loads((O/"FEATURE_SEAL.json").read_text())
for fn in ["compute_features.py","SPECIFICATION_FREEZE.json","CANDIDATE_RANKS_PRELABEL.csv","STOCK_MONTH_FEATURES_PRELABEL.csv","QUEUE_CHANGES_PRELABEL.csv","QA_PRELABEL.json"]:
    assert sha((O/fn).read_bytes())==seal["files"][fn],fn
a=pd.read_csv(O/"CANDIDATE_RANKS_PRELABEL.csv",low_memory=False)
a=a[a.old_selected.eq(True)].copy().rename(columns={"status":"feature_status"})
paths=[E/"relative_priority_equity_run_2022_v1/report/CORE_AND_FULL_ROUNDS.csv",E/"cash_equity_baseline_2024_v1/report/CORE_AND_FULL_ROUNDS.csv"]
expected=["4992d25f92fcf72e0321c9f5285af3152ebe2c0c00d6936303bf11e02e51cfd7","560b468114913964a145d2f07f8167db453b0466558f41aed60c7382e44afd41"]
sources={}
for p,h in zip(paths,expected):assert sha(p.read_bytes())==h;sources[str(p)]=h
z=pd.concat([pd.read_csv(p,low_memory=False) for p in paths],ignore_index=True)
z=z[z.arm.eq("A_UNION_B")].copy()
assert len(a)==len(z)==4086 and a.event_id.is_unique and z.event_id.is_unique
assert set(a.event_id)==set(z.event_id)
z=z.set_index("event_id");a=a.set_index("event_id").loc[z.index]
for c in ["window","sid","sector","arm","round_id"]:
    assert a[c].astype(str).equals(z[c].astype(str)),c
assert a.day.astype(str).equals(z.signal_day.astype(str))
for c in ["PVR_score","close_q"]:assert np.allclose(a[c],z[c],equal_nan=True)
cols=["signal_day","entry_day","exit_day","status","entry_status","historical_tradability","account_run",
      "exit_reason","core_net","core_return","core_buy_cash","core_buy_fee","core_sell_fee","core_dividend_net80",
      "evidence_usable_closed","financial_coverage_status","coverage_reasons"]
out=a.join(z[cols],validate="one_to_one").reset_index()
out["original_tail50"]=out.evidence_usable_closed.eq(True)&out.core_return.ge(.5)
out["RM_removes_original_opportunity"]=~out.RM_selected.astype(bool)
out["RAW_removes_original_opportunity"]=~out.RAW_MOM11_selected.astype(bool)
out.to_csv(O/"ORIGINAL_SELECTED_OPPORTUNITY_RISK.csv",index=False)
out[out.original_tail50].to_csv(O/"ORIGINAL_TAIL50_OPPORTUNITY_RISK.csv",index=False)
res=[];top=[]
for w,g in out.groupby("window",sort=True):
    usable=g[g.evidence_usable_closed.eq(True)]
    tails=g[g.original_tail50]
    top10=usable.sort_values(["core_return","event_id"],ascending=[False,True]).head(10)
    top.append(top10)
    assert (len(usable),len(tails))==({"2022":(2616,44),"2024_924":(1312,64)}[str(w)])
    for arm,c in [("CH3_RM","RM_selected"),("RAW_MOM11","RAW_MOM11_selected")]:
        drop=g[~g[c].astype(bool)];udrop=drop[drop.evidence_usable_closed.eq(True)]
        td=tails[~tails[c].astype(bool)]
        r=dict(window=str(w),arm=arm,original_selected=len(g),removed_original_slots=len(drop),
            original_usable=len(usable),removed_usable=len(udrop),removed_execution_or_financial_unknown=int((~drop.evidence_usable_closed.eq(True)).sum()),
            original_tail50=len(tails),tail50_retained_static=len(tails)-len(td),tail50_removed_static=len(td),
            original_tail50_feature_unknown=int((~tails.known).sum()),tail50_removed_names=td[["day","sid","name","core_return","old_rank","RM_rank","RAW_MOM11_rank"]].to_dict("records"),
            original_top10_removed=int((~top10[c].astype(bool)).sum()),
            removed_original_positive=int(udrop.core_net.gt(0).sum()),removed_original_nonpositive=int(udrop.core_net.le(0).sum()),
            removed_usable_return_min=float(udrop.core_return.min()),removed_usable_return_median=float(udrop.core_return.median()),removed_usable_return_max=float(udrop.core_return.max()),
            removed_unknown_feature_slots=int((~drop.known).sum()),
            no_new_entrant_payoffs=True,not_strategy_win_rate_or_return=True)
        res.append(r)
    print("WINDOW",w,"TAILS",len(tails),"RM_DROP_RAW_KEEP",int((~tails.RM_selected&tails.RAW_MOM11_selected).sum()),
          "RAW_DROP_RM_KEEP",int((tails.RM_selected&~tails.RAW_MOM11_selected).sum()))
pd.concat(top).to_csv(O/"ORIGINAL_TOP10_PER_WINDOW_RISK.csv",index=False)
dump("ORIGINAL_OPPORTUNITY_RISK_SUMMARY.json",res)
dump("LABEL_CONNECTION_QA.json",dict(join_rows=len(out),exact_identity=True,hashes_verified=sources,
    original_source_dates_and_q_verified=True,labels_only_original_selected=True,all_nonselected_without_payoff=True,
    no_label_used_by_features=True,feature_seal_utc=seal["sealed_utc"],joined_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    no_new_lifecycle=True,no_account=True,no_parameter_search=True,
    caveat="Original outcomes indicate missed-opportunity risk only. Static retention is not dynamic lifecycle retention; entrants have no new payoff labels."))
print(json.dumps([{k:v for k,v in r.items() if k!="tail50_removed_names"} for r in res],ensure_ascii=False,indent=2))
