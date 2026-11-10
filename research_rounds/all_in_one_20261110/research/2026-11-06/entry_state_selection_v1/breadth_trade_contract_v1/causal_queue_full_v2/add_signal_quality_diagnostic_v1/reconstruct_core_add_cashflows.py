import pandas as pd,json,sys,hashlib,io,contextlib
from decimal import Decimal as D
from pathlib import Path
B=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025")
sys.path.insert(0,str(B/"code"))
from market_rules import version_on,market_identity_on
from sector_account import FeeComponent,FeeSchedule
rules=json.loads((B/"inputs-v2/market-rules.json").read_text()); proxies=json.loads((B/"inputs-v2/economic-protocol.json").read_text())["approved_proxy_ids"]
def fee(sid,day,q,p):
 identity=market_identity_on(rules,sid,day,proxies);v=version_on(rules["fee_versions"][identity["venue"]],day,proxies)["schedule"]
 fs=FeeSchedule(v["schedule_id"],tuple(FeeComponent(**x) for x in v["components"]))
 return sum(fs.incremental("sell",D(q)*p,{}, {},1,shares=q,par_value=D(str(rules["security_metadata"][sid]["par_value"]))).values(),D(0))
p="/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/dual_budget_ablation_v1/baseline/ALL_SHADOW_ROUNDS.csv"
df=pd.read_csv(p);df=df[(df.arm=="M3")&(df.event_type=="FALSE_TO_TRUE")&df.window.isin(["2022","2024_924"])]
rows=[]
for _,r in df.iterrows():
 aa=json.loads(r.actions) if isinstance(r.actions,str) else []
 if not any(a["side"]=="buy_add" for a in aa):continue
 cq=int(r.entry_q);aq=0;cn=-D(str(r.entry_q))*D(str(r.entry_price))-D(str(r.entry_fee));an=D(0);cost=D(0);cstand=None;first=None;nadd=0;shared=False;feeerr=D(0)
 for a in aa:
  q=int(a["q"]);price=D(a["price"]);f=D(a["fee"])
  if a["side"]=="buy_add":
   nadd+=1;aq+=q;an-=q*price+f;cost+=q*price+f;first=a["day"]
  elif a["side"]=="sell_add":
   assert q==aq;an+=q*price-f;aq=0
  elif a["side"]=="sell_all":
   assert q==cq+aq
   fc=f*D(cq)/D(q);fa=f-fc;cn+=cq*price-fc;an+=aq*price-fa;shared=aq>0
   standalone_fee=fee(r.sid,a["day"],cq,price);cstand=cn+fc-standalone_fee
   feeerr=max(feeerr,abs(f-fee(r.sid,a["day"],q,price)))
   cq=aq=0
 closed=r.status=="COMPLETE_CONDITIONAL_STOCK_ROUND"
 state="closed" if aq==0 else ("open" if r.status.startswith("OPEN_") else "unknown")
 rows.append(dict(window=r.window,sid=r.sid,name=r["name"],industry=r.industry,event_id=r.event_id,signal_day=r.day,add_day=first,status=r.status,round_state="closed" if closed else ("open" if r.status.startswith("OPEN_") else "unknown"),layer_state=state,add_net=float(an) if aq==0 else None,core_net=float(cn) if closed else None,core_standalone=float(cstand) if cstand is not None else None,add_cash=float(cost),add_return=float(an/cost) if aq==0 else None,round_net=r.net_pnl,identity_error=abs(float(cn+an)-r.net_pnl) if closed else None,cash_error=abs(float(cn+an)-r.cashflow_to_date),fee_error=float(feeerr),nadd=nadd,shared=shared))
z=pd.DataFrame(rows)
def stat(g):
 a=g.add_net.dropna();ret=g.add_return.dropna();win=a[a>0];loss=a[a<0];rw=ret[ret>0];rl=ret[ret<0]
 return dict(n=len(a),wins=len(win),losses=len(loss),zero=int((a==0).sum()),winrate=float((a>0).mean()),net=a.sum(),winning_net=win.sum(),losing_net=loss.sum(),mean_win=win.mean(),mean_loss=loss.mean(),dollar_payoff=win.mean()/-loss.mean(),profit_factor=win.sum()/-loss.sum(),mean_return=ret.mean(),mean_win_return=rw.mean(),mean_loss_return=rl.mean(),return_payoff=rw.mean()/-rl.mean(),buycash=g.loc[g.add_net.notna(),"add_cash"].sum())

OUT=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/breadth_trade_contract_v1/causal_queue_full_v2/add_signal_quality_diagnostic_v1")
z.to_csv(OUT/"CORE_ADD_CASHFLOW_BY_EVENT.csv",index=False,float_format="%.12f")
summaries={}
for w,g in z.groupby("window"):
 c=g[g.round_state=="closed"]
 summaries[w]={"n":len(g),"status_counts":{str(k):int(v) for k,v in g.groupby(["round_state","layer_state"]).size().items()},"closed_layer":stat(g),"closed_round_layer":stat(c),"unknown_round_closed_layer":stat(g[(g.round_state=="unknown")&(g.layer_state=="closed")]),"core_alloc_net":c.core_net.sum(),"core_only_net":c.core_standalone.sum(),"round_net":c.round_net.sum(),"core_fee_allocation_saving":(c.core_net-c.core_standalone).sum(),"qa":g[["identity_error","cash_error","fee_error","nadd"]].max().to_dict()}
(OUT/"CORE_ADD_SUMMARY.json").write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
buf=io.StringIO()
with contextlib.redirect_stdout(buf):
 for w,g in z.groupby("window"):
  print("WINDOW",w,"N",len(g));print("STATES",g.groupby(["round_state","layer_state"]).size().to_json())
  print("ALL_CLOSED_LAYERS",json.dumps(stat(g)))
  c=g[g.round_state=="closed"];print("CLOSED_ROUND_LAYERS",json.dumps(stat(c)))
  for basis in ["core_net","core_standalone"]:
   masks={"core_win_to_round_loss":(c[basis]>0)&(c.round_net<=0),"core_loss_to_round_win":(c[basis]<=0)&(c.round_net>0),"both_win_add_help":(c[basis]>0)&(c.round_net>0)&(c.round_net>c[basis]),"both_win_add_hurt":(c[basis]>0)&(c.round_net>0)&(c.round_net<c[basis]),"both_loss":(c[basis]<=0)&(c.round_net<=0)}
   print("CORE_BASIS",basis,"core_wins",int((c[basis]>0).sum()),"core_losses",int((c[basis]<0).sum()),"core_net",c[basis].sum(),"round_wins",int((c.round_net>0).sum()),"round_net",c.round_net.sum())
   for name,m in masks.items():
    h=c[m];print(name,json.dumps(dict(n=len(h),core=h[basis].sum(),add_alloc=h.add_net.sum(),increment=(h.round_net-h[basis]).sum(),round=h.round_net.sum())))
  print("SHARED",int(c.shared.sum()),"FEE_CORE_ALLOC_MINUS_STANDALONE",(c.core_net-c.core_standalone).sum(),"max",(c.core_net-c.core_standalone).max(),"classification_flips",int(((c.core_net>0)!=(c.core_standalone>0)).sum()))
  print("AUDIT",g[["identity_error","cash_error","fee_error","nadd"]].max().to_json())
  for keys in [["sid"],["signal_day","sid"],["add_day","sid"],["add_day"],["industry"],["event_id"]]:
   counts=g.groupby(keys).size();print("CLUSTER",keys,"unique",len(counts),"duplicate_groups",int((counts>1).sum()),"extra_rows",int((counts-1).clip(lower=0).sum()),"top",counts.nlargest(5).to_json())
  print("LARGEST_ABS_PNL_STOCK",c.groupby("sid").add_net.sum().abs().nlargest(5).to_json())
 print("CROSS_WINDOW_STOCKS",len(set(z[z.window=="2022"].sid)&set(z[z.window=="2024_924"].sid)))
 
(OUT/"CORE_ADD_KEY_RESULTS.txt").write_text(buf.getvalue())
qa={"input":p,"input_sha256":hashlib.sha256(Path(p).read_bytes()).hexdigest(),"rows":len(z),"cashflow_identity_max_abs_error":float(z.cash_error.max()),"closed_round_identity_max_abs_error":float(z.identity_error.max()),"sell_all_fee_recalculation_max_abs_error":float(z.fee_error.max()),"one_add_per_row":bool(z.nadd.eq(1).all()),"accounts_replayed":0,"corporate_actions_or_dividends_imputed":False}
assert qa["rows"]==730 and qa["one_add_per_row"]
assert max(qa["cashflow_identity_max_abs_error"],qa["closed_round_identity_max_abs_error"],qa["sell_all_fee_recalculation_max_abs_error"])<1e-7
(OUT/"CORE_ADD_QA.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2))
names=["reconstruct_core_add_cashflows.py","CORE_ADD_CASHFLOW_BY_EVENT.csv","CORE_ADD_SUMMARY.json","CORE_ADD_KEY_RESULTS.txt","CORE_ADD_QA.json","CORE_ADD_READOUT.md"]
(OUT/"CORE_ADD_OUTPUT_SHA256.json").write_text(json.dumps({n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in names},ensure_ascii=False,indent=2))
print(json.dumps(qa,ensure_ascii=False))
