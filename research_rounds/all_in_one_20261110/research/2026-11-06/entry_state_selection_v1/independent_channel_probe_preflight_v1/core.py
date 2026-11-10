"""Pure market-state functions. No orders, holdings, economic labels or I gate."""
import numpy as np
import pandas as pd

def simulate(q):
 rows=[];root=None;last_failure=None;segment_start=None;lastid=None
 for j,(d,r) in enumerate(q.iterrows()):
  valid=bool(r.price_valid)
  fresh_segment=valid and (segment_start is None or r.identity!=lastid)
  z=dict(day=d,valid=valid,amount_valid=bool(r.amount_valid),C=r.close,E0=r.e0_target,I=r.i_target,G=r.g_grade,i_buy=r.i_buy,CP=r.CP,born=False,failed=False,root_unknown=False,root_day=pd.NaT,active=False,a_day=pd.NaT,U=np.nan,B=np.nan,R=np.nan,Q=np.nan,F=np.nan,S_old=np.nan,S_new=np.nan,e0_raised=False,new_frontier=False,receipt=False,receipt_id=None,phase="NO_ROOT",confirmed_now=False,confirmed_at=pd.NaT,volume_credit_known=False,blocked="NONE")
  if root is not None:z.update(root_day=q.index[root["birth"]],S_old=root["S"],S_new=root["S"])
  if not valid or fresh_segment:
   if root is not None:z["root_unknown"]=True;z["phase"]="UNKNOWN_PRICE_ROOT"
   root=None;last_failure=None;segment_start=j if valid else None
   z["S_new"]=np.nan
  lastid=r.identity if valid else None
  if not valid:z["blocked"]="INVALID_PRICE_SOURCE";rows.append(z);continue
  if root is not None:
   z.update(active=True,a_day=q.index[root["a"]],U=root["U"],B=root["B"],R=root["R"],Q=root["Q"],F=root["F"],phase=root["phase"],confirmed_at=root["confirmed_at"],volume_credit_known=np.isfinite(root["Q"]))
   if r.close<=root["S"]:
    z.update(failed=True,active=False,phase="FAILED",S_new=np.nan,blocked="CLOSE_FAILED_OLD_FLOOR")
    root=None;last_failure=j;rows.append(z);continue
   v=float(np.log(r.close/root["Ca"]));delta=max(0.,v-root["F"])
   root["F"]=max(root["F"],v)
   if delta>0:
    if np.isfinite(root["Q"]) and bool(r.amount_valid):
     root["Q"]+=min(1.,float(np.sqrt(r.amount/root["B"])))*delta
    else:root["Q"]=np.nan
   # Proven confirmation is historical evidence; missing later amount cannot erase it.
   if root["phase"]!="CONFIRMED":
    if np.isfinite(root["Q"]) and root["Q"]>=root["R"]:
     root["phase"]="CONFIRMED";root["confirmed_at"]=d;z["confirmed_now"]=True
    elif not np.isfinite(root["Q"]):root["phase"]="PROBE_AMOUNT_UNKNOWN"
   if r.e0_ready==1 and r.e0_target==1 and np.isfinite(r.e0_floor) and 0<r.e0_floor<r.close:
    old=root["S"];root["S"]=max(root["S"],float(r.e0_floor));z["e0_raised"]=root["S"]>old
   fresh=delta>0
   rid=f"{q.index[root['birth']].date()}|{d.date()}" if fresh else None
   z.update(Q=root["Q"],F=root["F"],S_new=root["S"],phase=root["phase"],confirmed_at=root["confirmed_at"],volume_credit_known=np.isfinite(root["Q"]),new_frontier=fresh,receipt=fresh,receipt_id=rid)
   rows.append(z);continue
  if j-segment_start<20:z["blocked"]="LESS_THAN20_CONTIGUOUS_PRIOR_PRICE_BARS";rows.append(z);continue
  astart=max(j-20,last_failure if last_failure is not None else segment_start)
  hist=q.close.iloc[astart:j].to_numpy(float)
  a=astart+int(np.flatnonzero(hist==hist.min())[-1])
  U=float(q.high.iloc[j-20:j].max());ca=float(q.close.iloc[a])
  z.update(a_day=q.index[a],U=U)
  if not r.close>U:z["blocked"]="NO20_HIGH_BREAK";rows.append(z);continue
  # Price creates the root regardless of amount history. All anchors freeze now.
  B=float(q.amount.iloc[a-21:a].median()) if a-segment_start>=21 and q.amount_valid.iloc[a-21:a].all() else np.nan
  F=0.;Q=0. if np.isfinite(B) else np.nan
  for k in range(a+1,j+1):
   v=float(np.log(q.close.iloc[k]/ca));delta=max(0.,v-F);F=max(F,v)
   if delta>0:
    if np.isfinite(Q) and bool(q.amount_valid.iloc[k]):Q+=min(1.,float(np.sqrt(q.amount.iloc[k]/B)))*delta
    else:Q=np.nan
  R=float(np.log(U/ca));S=float(q.low.iloc[a:j+1].min())
  assert R>=-1e-12 and F>R
  if np.isfinite(Q):assert -1e-12<=Q<=F+1e-12
  phase="CONFIRMED" if np.isfinite(Q) and Q>=R else "PROBE" if np.isfinite(Q) else "PROBE_AMOUNT_UNKNOWN"
  confirmed_at=d if phase=="CONFIRMED" else pd.NaT
  root=dict(birth=j,a=a,U=U,Ca=ca,B=B,R=R,Q=Q,F=F,S=S,phase=phase,confirmed_at=confirmed_at)
  z.update(born=True,active=True,root_day=d,a_day=q.index[a],U=U,B=B,R=R,Q=Q,F=F,S_old=np.nan,S_new=S,new_frontier=True,receipt=True,receipt_id=f"{d.date()}|{d.date()}",phase=phase,confirmed_now=phase=="CONFIRMED",confirmed_at=confirmed_at,volume_credit_known=np.isfinite(Q),blocked="NEW_PRICE_ROOT")
  rows.append(z)
 x=pd.DataFrame(rows).set_index("day")
 for c in ["root_day","a_day","confirmed_at"]:x[c]=pd.to_datetime(x[c]).astype("datetime64[ns]")
 for c in ["C","E0","I","G","i_buy","CP","U","B","R","Q","F","S_old","S_new"]:x[c]=pd.to_numeric(x[c],errors="coerce").astype(float)
 return x

def execution_permission(receipt,context):
 """Conditional execution admission at the immediate next common OPEN.
 Context is real authenticated order/fill evidence, not inferred from daily OHLC.
 Atomic target registration and broker submissions remain outside this pure check.
 """
 probe_over=context["parent_exists"] and context["filled"]+context["live_leaves"]>context["approved_Q"]
 add_over=context["add_parent_exists"] and context["add_filled_F"]+context["add_live_leaves"]>context["add_approved_Q"]
 if probe_over or add_over:return "OVERFILL_UNKNOWN"
 if context["unknown"] or context["unresolved"] or context["pending_exit"] or context["live_leaves"]>0 or context["add_live_leaves"]>0:return "WAIT_RESPONSIBILITY"
 if context["parent_exists"] and (context["parent_retired"] or context["parent_root"]!=context["current_root"]):return "OLD_OR_RETIRED_PROBE_TARGET"
 if context["add_parent_exists"] and (context["add_parent_retired"] or context["add_parent_root"]!=context["current_root"]):return "OLD_OR_RETIRED_ADD_TARGET"
 if receipt["eligible_open"]!=context["decision_open"]:return "EXPIRED_OR_WRONG_OPEN"
 if not receipt["fresh"] or receipt["root"]!=context["current_root"]:return "NO_FRESH_CURRENT_RECEIPT"
 if receipt["id"] in context["used_receipts"]:return "NO_REPLAY"
 if context["unlock_known_at"] is not None and receipt["known_at"]<=context["unlock_known_at"]:return "WAIT_NEW_RECEIPT_AFTER_UNLOCK"
 if not context["parent_exists"]:
  if context["add_parent_exists"]:return "INCONSISTENT_EXECUTION_CHAIN"
  return "PROPOSE_INITIAL_SMALL_TARGET" if context["flat"] else "UNKNOWN_UNCERTIFIED_HOLDING"
 if context["filled"]<context["approved_Q"]:
  return "INCONSISTENT_EXECUTION_CHAIN" if context["add_parent_exists"] else "CONTINUE_SAME_PROBE_REMAINDER"
 if context["complete_known_at"] is None:return "WAIT_PROBE_COMPLETION_PROOF"
 if receipt["known_at"]<=context["complete_known_at"]:return "WAIT_POST_COMPLETE_RECEIPT"
 if context["add_parent_exists"]:
  if context["add_filled_F"]<context["add_approved_Q"]:
   return "CONTINUE_SAME_ADD_REMAINDER" if context["healthy_held"] and receipt["confirmed"] else "CANCEL_OR_RETIRE_ADD_REMAINDER"
  if context["add_complete_known_at"] is None:return "WAIT_ADD_COMPLETION_PROOF"
  return "NO_SECOND_ADD_TARGET"
 if context["healthy_held"] and receipt["confirmed"]:return "PROPOSE_ONE_ADD_TARGET_MARKET_ONLY"
 return "NO_NEW_TARGET"
