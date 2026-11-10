from pathlib import Path
import pandas as pd, numpy as np, json, hashlib
O=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/false_i_buy_case_comparison")
O.mkdir(exist_ok=True)
M=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json")
m={x["symbol"]:x["refs"] for x in json.loads(M.read_text())}
d=pd.read_csv(O.parent/"ACTUAL_FIRST_MOBILE_GATE_ATTRIBUTION.csv")
d=d[(d.account=="PVR")&(~d.accepted)&d.closed]
sel=pd.concat([d[(d.year==2024)&(d.round_pnl>0)].nlargest(2,"round_pnl"),d[d.quarter=="2022Q1"].nsmallest(2,"round_pnl")])
assert sel.sid.tolist()==["000506.SZ","688582.SH","002385.SZ","300182.SZ"]
sel.to_csv(O/"FROZEN_CASES.csv",index=False)
pieces=[]; summaries=[]; notes=[]; hashes={}
for _,case in sel.iterrows():
 sid,day=case.sid,case.signal_day
 f=pd.read_parquet(m[sid]["facts"]);cp=pd.read_parquet(m[sid]["CP1"]);inp=pd.read_parquet(m[sid]["CP1_input"])
 assert f.index.equals(cp.index)
 inp=inp.reindex(f.index)
 for key in ["facts","CP1","CP1_input"]:
  p=Path(m[sid][key]); hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 t=f.index.get_loc(day);x=f.close
 z=f.copy()
 for col in cp:z["cp_"+col]=cp[col]
 z["amount"]=inp.amount;z["native_down"]=inp.e0_down
 z["ret1"]=x.pct_change(fill_method=None);z["amount_prior21median_ratio"]=inp.amount/inp.amount.shift().rolling(21).median()
 z["prior20_close_high"]=x.shift().rolling(20).max();z["prior63_close_high"]=x.shift().rolling(63).max()
 z["distance_prior20"]=x/z.prior20_close_high-1;z["distance_prior63"]=x/z.prior63_close_high-1
 z["relative_observation"]=np.arange(len(z))-t;z["sid"]=sid
 z["credit_threshold_ratio"]=cp.credit/(np.sqrt(5)*cp.scale)
 z["displacement_threshold_ratio"]=cp.displacement/(np.sqrt(5)*cp.scale)
 a=t
 while a>0 and cp.iloc[a-1].anchor==cp.iloc[t].anchor:a-=1
 # Diagnostic proposal replay of this receipt only, not account simulation.
 R=x.iloc[t];floor=cp.candidate.iloc[t];count=0;confirm=None;invalid=None
 for j in range(t+1,min(t+11,len(f))):
  if f.segment_id.iloc[j]!=f.segment_id.iloc[t] or not inp.e0_valid.iloc[j] or x.iloc[j]<=floor:
   invalid=str(f.index[j].date());break
  count=count+1 if x.iloc[j]>R else 0
  if cp.receipt.iloc[j]:
   if count>=2:confirm=str(f.index[j].date());break
   R=x.iloc[j];floor=cp.candidate.iloc[j];count=0
 summaries.append(dict(sid=sid,signal_day=day,round_pnl=case.round_pnl,anchor_day=str(f.index[a].date()),anchor_raw=f.raw_close.iloc[a],signal_raw=f.raw_close.iloc[t],distance20=z.distance_prior20.iloc[t],distance63=z.distance_prior63.iloc[t],volume_ratio=z.amount_prior21median_ratio.iloc[t],displacement_ratio=z.displacement_threshold_ratio.iloc[t],credit_ratio=z.credit_threshold_ratio.iloc[t],strict_new_receipt_day=confirm,invalidation_day=invalid))
 q=z.iloc[t-20:t+11].copy()
 daily=[]
 for date,row in q.iterrows():
  flags=[]
  if bool(row.native_down):flags.append("native下行事件")
  reason=row.cp_reset_reason
  if pd.notna(reason):flags.append(str(reason))
  if bool(row.cp_receipt):flags.append("原CP1新证书")
  if bool(row.g_fresh_up):flags.append("G新上转")
  if not bool(row.e0_target):flags.append("E0未目标")
  if not flags:flags.append("状态延续")
  annotation="；".join(flags)
  daily.append(annotation)
  notes.append(f"{sid} {date.date()} ({int(row.relative_observation):+d}观察): 原价{row.raw_close:.2f}，涨跌{row.ret1:+.2%}，额/前21中位{row.amount_prior21median_ratio:.3f}，距前20/63收盘高{row.distance_prior20:+.2%}/{row.distance_prior63:+.2%}；G={row.g_grade:g}，i_buy={row.i_buy}；{annotation}。")
 q["daily_annotation"]=daily;pieces.append(q)
pd.concat(pieces).to_csv(O/"DAILY_20_BEFORE_10_AFTER.csv",index_label="day")
pd.DataFrame(summaries).to_csv(O/"SIGNAL_SUMMARY_AND_CONFIRMATION_DIAGNOSTIC.csv",index=False)
(O/"DAILY_EXPLANATIONS.txt").write_text("\n".join(notes),encoding="utf-8")
(O/"SOURCE_HASHES.json").write_text(json.dumps(hashes,indent=2))
print(pd.DataFrame(summaries).to_string(index=False))
