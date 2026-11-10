from pathlib import Path
import pandas as pd,numpy as np,json
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1")
r=pd.read_parquet(R/"closed_price_supervised_pilot_support_v1/ALL_ORIGINAL_PRICE_ROWS.parquet")
for c in ["status_day","last_known_mark_day"]:r[c]=pd.to_datetime(r[c])
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
def measure(day,rolling=True):
 cut=cal.get_loc(day)
 p=r[(r.t<cut)&(r.t>=cut-504 if rolling else True)].copy()
 enter=p.entered&p.entry_day.lt(day)
 closed=p.complete&p.exit_day.lt(day)
 frozen=enter&~p.complete&p.status_day.lt(day)
 noentry=~p.entered&p.status_day.lt(day)
 q0=noentry&p.status.eq("PRECHECK_Q0_NO_SUBMIT")
 op=enter&~closed&~frozen
 mature=p.ordinary&p.exit_day.lt(day)
 tr=p[mature&p.feature_known]
 return dict(cut=str(day.date()),rolling=rolling,start=str(cal[max(0,cut-504)].date()) if rolling else "ALL_PRIOR_BIRTHS",n=len(p),entered=int(enter.sum()),mature_ordinary=int(mature.sum()),train_n=len(tr),W=int(tr.net_pnl.gt(0).sum()),L=int(tr.net_pnl.le(0).sum()),tail30=int(tr.net_return_on_buy_cash.ge(.3).sum()),tail50=int(tr.net_return_on_buy_cash.ge(.5).sum()),tail100=int(tr.net_return_on_buy_cash.ge(1).sum()),R3=int((tr.net_pnl/tr.entry_risk).ge(3).sum()),R5=int((tr.net_pnl/tr.entry_risk).ge(5).sum()),left_Rminus1=int((tr.net_pnl/tr.entry_risk).le(-1).sum()),closed_nonordinary=int((closed&~p.ordinary).sum()),active_held=int(op.sum()),held_unknown=int(frozen.sum()),q0=int(q0.sum()),no_entry_unknown=int((noentry&~q0).sum()),pending=int((~enter&~noentry).sum()),train_dates=tr.signal_day.nunique(),train_stocks=tr.sid.nunique(),train_roots=tr.price_root.nunique(),train2022=int(tr.window_label.eq("2022").sum()),train2024=int(tr.window_label.eq("2024").sum()))

import hashlib
O=R/"distribution_objective_feasibility_v1"
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths=[R/"closed_price_supervised_pilot_support_v1/ALL_ORIGINAL_PRICE_ROWS.parquet",R/"closed_price_supervised_pilot_support_v1/PROTOCOL.json",R/"closed_price_supervised_pilot_support_v1/run_pilot.py",H]
actions=[];gates=[];frozen=[]
for w in ["2022","2024"]:
 E=R/f"independent_channel_joint_economic_v1/economic_{w}";J=E/"joint"
 for name in ["ACTIONS.csv","PROFIT_GATES.csv","ROUNDS.csv","CLAIM_LEDGER.csv","REGISTRATIONS.csv"]:
  paths.append(J/name)
 paths.append(E/"FROZEN_RESPONSIBILITIES.json")
 a=pd.read_csv(J/"ACTIONS.csv",float_precision="round_trip");a=a[a.round_id.isin(r.round_id)];a["day"]=pd.to_datetime(a.day);a["dq"]=np.where(a.side.str.startswith("buy"),a.q,-a.q);a["cash"]=np.where(a.side.str.startswith("buy"),-a.q*a.price-a.fee,a.q*a.price-a.fee);a["buy_cash"]=np.where(a.side.str.startswith("buy"),a.q*a.price+a.fee,0);actions.append(a)
 p=pd.read_csv(J/"PROFIT_GATES.csv",float_precision="round_trip");p=p[p.round_id.isin(r.round_id)&p.phase.eq("CLOSE")];p["day"]=pd.to_datetime(p.day);gates.append(p)
 f=pd.DataFrame(json.loads((E/"FROZEN_RESPONSIBILITIES.json").read_text()));f=f[f.owner_lane.eq("PRICE")];f["day"]=pd.to_datetime(f.day);frozen.append(f)
a=pd.concat(actions,ignore_index=True);pg=pd.concat(gates,ignore_index=True);fr=pd.concat(frozen,ignore_index=True)
hashes={str(p):sha(p) for p in paths}
assert fr.round_id.is_unique
u=r[r.status.str.contains("UNKNOWN")].set_index("round_id").sort_index()
ff=fr.set_index("round_id").sort_index()
assert list(u.index)==list(ff.index)
assert (u.status_day==ff.day).all()
assert len(r)==3621 and int(r.entered.sum())==3593 and int(r.ordinary.sum())==2914
assert int((r.ordinary&r.feature_known).sum())==2593
labels=["Y_le_minus1","Y_minus1_to_0","Y_0_to_1","Y_1_to_3","Y_gt_3"]
bins=[-np.inf,-3000,0,3000,9000,np.inf]
def bc(g):
 return dict(zip(labels,pd.cut(g.net_pnl,bins=bins,right=True).value_counts(sort=False).astype(int).tolist()))
months=list(pd.period_range("2022-01","2022-12",freq="M"))+list(pd.period_range("2024-08","2025-11",freq="M"))
days=[cal[cal.to_period("M")==mo][0] for mo in months]
monthly=[];bincounts=[];latecounts=[];asof=[]
for day in days:
 cut=cal.get_loc(day)
 prior=r[r.t.lt(cut)].copy()
 p=prior[prior.t.ge(cut-504)]
 q=measure(day)
 assert q["n"]==q["mature_ordinary"]+q["closed_nonordinary"]+q["active_held"]+q["held_unknown"]+q["q0"]+q["no_entry_unknown"]+q["pending"]
 monthly.append(q)
 mature=p[p.ordinary&p.exit_day.lt(day)]
 tr=mature[mature.feature_known]
 bincounts.append(dict(cut=str(day.date()),scope="PDC_KNOWN",n=len(tr),**bc(tr)))
 bincounts.append(dict(cut=str(day.date()),scope="ALL_ORDINARY",n=len(mature),**bc(mature)))
 lt=p[p.ordinary&p.feature_known&p.exit_day.ge(day)]
 latecounts.append(dict(cut=str(day.date()),WARNING="RETROSPECTIVE_ONLY_NEVER_TRAIN_AT_THIS_CUT",n=len(lt),**bc(lt)))
 z=prior[["round_id","window_label","sid","signal_day","P","D","C","feature_known","price_root"]].copy()
 z["cut"]=day;z["in_504_signal_window"]=prior.t.ge(cut-504)
 enter=prior.entered&prior.entry_day.lt(day);closed=prior.complete&prior.exit_day.lt(day);unk=prior.status.str.contains("UNKNOWN")&prior.status_day.lt(day);noentry=~prior.entered&prior.status_day.lt(day);mat=prior.ordinary&prior.exit_day.lt(day)
 z["state_asof"]=np.select([mat,closed&~prior.ordinary,enter&unk,noentry&prior.status.eq("PRECHECK_Q0_NO_SUBMIT"),noentry&unk,enter],["ORDINARY_NET_LABEL_MATURE_PROXY","CLOSED_NONORDINARY_LABEL_CLOCK_UNSUPPORTED","HELD_RESPONSIBILITY_UNKNOWN","KNOWN_Q0_NO_ENTRY","ENTRY_UNKNOWN_NO_CONFIRMED_FILL","ACTIVE_HELD"],default="ENTRY_PENDING")
 z["entry_day_asof"]=prior.entry_day.where(enter)
 z["entry_risk_asof"]=prior.entry_risk.where(enter)
 z["label_known_at_proxy"]=prior.label_known_at_proxy.where(mat)
 z["label_net_cash"]=prior.net_pnl.where(mat)
 z["label_Y_net_over_fixed3000"]=prior.net_pnl.where(mat)/3000
 z["label_R_net_over_entryrisk"]=(prior.net_pnl/prior.entry_risk).where(mat)
 z["label_return_net_over_fullbuycash"]=prior.net_return_on_buy_cash.where(mat)
 z["label_bin_fixed3000"]=pd.cut(z.label_net_cash,bins=bins,right=True,labels=labels).astype("string")
 z["unknown_known_day"]=prior.status_day.where(unk)
 z["unknown_reason_asof"]=prior.status.where(unk)
 pa=a[a.day.lt(day)].groupby("round_id").agg(prefix_qty=("dq","sum"),prefix_trade_cash=("cash","sum"),prefix_buy_cash=("buy_cash","sum"),prefix_fees=("fee","sum"),last_action_asof=("day","max"))
 pp=pg[pg.day.lt(day)].sort_values(["round_id","day"]).groupby("round_id").tail(1).set_index("round_id")[["day","net_equity","receivable"]].rename(columns={"day":"last_close_mark_day_asof","net_equity":"last_net_equity_mark_asof","receivable":"last_receivable_mark_asof"})
 z=z.join(pa,on="round_id").join(pp,on="round_id")
 assert z.loc[~mat,"label_net_cash"].isna().all()
 assert z.loc[mat,"label_known_at_proxy"].lt(day).all()
 assert z.last_close_mark_day_asof.dropna().lt(day).all()
 asof.append(z)
earliest=None
for day in cal[(cal>="2022-01-01")&(cal<="2022-07-01")]:
 q=measure(day)
 if q["train_n"]>=300 and q["W"]>=50 and q["L"]>=50 and q["train_dates"]>=60 and q["train_stocks"]>=100 and q["train_roots"]>=200:
  earliest=q;break
horizon=[]
rr=r.copy();rr["entry_t"]=cal.get_indexer(rr.entry_day);rr["exit_t"]=cal.get_indexer(rr.exit_day);rr["status_t"]=cal.get_indexer(rr.status_day)
for w,g in rr[rr.entered].groupby("window_label"):
 for h in [20,60,120,252]:
  end=g.entry_t+h-1;cl=g.complete&g.exit_t.le(end);un=~g.complete&g.status_t.le(end)
  horizon.append(dict(window=w,H_sessions=h,entered=len(g),ordinary_closed=int((cl&g.ordinary).sum()),ordinary_PDC=int((cl&g.ordinary&g.feature_known).sum()),closed_nonordinary=int((cl&~g.ordinary).sum()),frozen_UNKNOWN=int(un.sum()),still_held=int((~cl&~un).sum()),meaning="ORIGINAL_CONTRACT_STATE_AT_H_NOT_H_FORCED_SALE"))
summary=[]
for w,g in r.groupby("window_label"):
 tr=g[g.ordinary&g.feature_known];late=tr[tr.exit_day.ge(str(int(w)+1))]
 summary.append(dict(window=w,births=len(g),entered=int(g.entered.sum()),completed=int(g.complete.sum()),ordinary=int(g.ordinary.sum()),ordinary_PDC=len(tr),eval_financial_known=int(g.eval_financial_known.sum()),feature_known=int(g.feature_known.sum()),q0=int(g.status.eq("PRECHECK_Q0_NO_SUBMIT").sum()),held_UNKNOWN=int((g.entered&~g.complete).sum()),entry_UNKNOWN=int((~g.entered&g.status.str.contains("UNKNOWN")).sum()),ordinary_PDC_tail30=int(tr.net_return_on_buy_cash.ge(.3).sum()),ordinary_PDC_after_birth_year=len(late),late_W=int(late.net_pnl.gt(0).sum()),late_tail30=int(late.net_return_on_buy_cash.ge(.3).sum()),final_fixed3000_bins=bc(tr)))
qa=dict(status="READ_ONLY_SAVED_LEDGER_AVAILABILITY_AUDIT_NO_FIT",models_fit=0,economic_runs=0,original_inputs_unchanged=True,asof_rows=sum(len(z) for z in asof),monthly_cuts=len(days),all_proxy_labels_strict_before_cut=True,unavailable_label_values_blank=True,state_partition_reconciles=True,first_unknown_day_matches_frozen_responsibilities_rows=len(fr),earliest_one_label_proxy=str(r.loc[r.ordinary&r.feature_known,"label_known_at_proxy"].min()),earliest_previous_pilot_count_support=earliest,not_a_distribution_support_approval=True,summary=summary)
assert all(sha(p)==h for p,h in hashes.items())
outputs=["LABEL_AVAILABILITY_MONTHLY.csv","LABEL_FIXED3000_BIN_SUPPORT.csv","LABEL_LATE_TERMINAL_DIAGNOSTIC_ONLY.csv","LABEL_ASOF_ROWS.parquet","LABEL_FIXED_HORIZON_SUPPORT.csv","LABEL_QA.json","LABEL_INPUT_HASHES.json"]
O.mkdir(exist_ok=True)
assert not any((O/n).exists() for n in outputs),"REFUSE_OVERWRITE"
pd.DataFrame(monthly).to_csv(O/outputs[0],index=False)
pd.DataFrame(bincounts).to_csv(O/outputs[1],index=False)
pd.DataFrame(latecounts).to_csv(O/outputs[2],index=False)
pd.concat(asof,ignore_index=True).to_parquet(O/outputs[3],index=False)
pd.DataFrame(horizon).to_csv(O/outputs[4],index=False)
(O/outputs[5]).write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n")
(O/outputs[6]).write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+"\n")
assert all(sha(p)==h for p,h in hashes.items())
print(json.dumps(qa,ensure_ascii=False,indent=2))
