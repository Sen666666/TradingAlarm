
from pathlib import Path
import numpy as np,pandas as pd,hashlib,json
p=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/independent_channel_probe_preflight_v1/core.py")
ns={};exec(p.read_text(),ns);simulate=ns["simulate"];perm=ns["execution_permission"]
def fixture():
    q=pd.DataFrame(index=pd.date_range("2020-01-01",periods=55))
    for k,v in {"price_valid":True,"amount_valid":True,"close":10.,"high":10.2,"low":9.8,"amount":100.,"identity":"sourceA","e0_target":0.,"e0_ready":0.,"e0_floor":np.nan,"i_target":0.,"g_grade":-3.,"i_buy":0.,"CP":0.}.items():q[k]=v
    q.iloc[40,q.columns.get_loc("close")]=9.
    q.iloc[40,q.columns.get_loc("low")]=8.8
    for j,c in {45:10.5,46:10.5,47:10.7,48:11.2,49:11.2,50:11.2,51:11.2,52:11.2,53:11.2,54:11.2}.items():
        q.iloc[j,q.columns.get_loc("close")]=c;q.iloc[j,q.columns.get_loc("high")]=c+.2;q.iloc[j,q.columns.get_loc("low")]=c-.2
    q.iloc[41:46,q.columns.get_loc("amount")]=25.
    return q
checks=[]
def check(name,condition):
    assert condition,name
    checks.append(name)
q=fixture();x=simulate(q)
check("E0_I_G_CP_off_price_birth",x.iloc[45].born and x.iloc[45].phase=="PROBE")
check("strict_frontier_receipts_only",x.index[x.receipt].tolist()==q.index[[45,47,48]].tolist())
check("frozen_anchor_threshold",x.iloc[45:55].a_day.nunique()==1 and x.iloc[45:55].R.nunique()==1 and x.iloc[45:55].U.nunique()==1 and x.iloc[45:55].B.nunique()==1)
check("confirmation_new_frontier",not x.iloc[47].confirmed_now and x.iloc[48].confirmed_now)
check("no_calendar_credit",x.iloc[48:55].Q.nunique()==1)
r=fixture();r.iloc[20,r.columns.get_loc("amount_valid")]=False;r.iloc[20,r.columns.get_loc("amount")]=np.nan;y=simulate(r)
check("missing_baseline_does_not_block_birth",y.iloc[45].born and y.iloc[45].phase=="PROBE_AMOUNT_UNKNOWN")
r=fixture();r.iloc[46,r.columns.get_loc("amount_valid")]=False;r.iloc[46,r.columns.get_loc("amount")]=np.nan;y=simulate(r)
check("nonfrontier_missing_amount_keeps_credit",np.isfinite(y.iloc[46].Q) and y.iloc[46].Q==x.iloc[46].Q and y.iloc[48].confirmed_now)
r=fixture();r.iloc[47,r.columns.get_loc("amount_valid")]=False;r.iloc[47,r.columns.get_loc("amount")]=np.nan;y=simulate(r)
check("frontier_missing_amount_keeps_price_root",y.iloc[47].active and y.iloc[47].receipt and not y.iloc[47].root_unknown)
check("frontier_missing_amount_quarantines_unconfirmed_credit",y.iloc[47].phase=="PROBE_AMOUNT_UNKNOWN" and np.isnan(y.iloc[48].Q) and not y.iloc[48].confirmed_now)
r=fixture();r.iloc[49,r.columns.get_loc("close")]=12.;r.iloc[49,r.columns.get_loc("amount_valid")]=False;y=simulate(r)
check("later_missing_amount_does_not_erase_proven_confirmation",y.iloc[49].phase=="CONFIRMED" and np.isnan(y.iloc[49].Q))
r=fixture();r.iloc[46,r.columns.get_loc("price_valid")]=False;y=simulate(r)
check("price_unknown_not_failure_or_sell",y.iloc[46].root_unknown and not y.iloc[46].failed and not y.iloc[46].receipt)
r=fixture();r.iloc[46:,r.columns.get_loc("identity")]="sourceB";y=simulate(r)
check("source_change_quarantines_root",y.iloc[46].root_unknown and not y.iloc[46].failed and not y.iloc[46].receipt)
r=fixture();r.iloc[46,r.columns.get_loc("e0_target")]=1.;r.iloc[46,r.columns.get_loc("e0_ready")]=1.;r.iloc[46,r.columns.get_loc("e0_floor")]=10.4;y=simulate(r)
check("E0_ready_raises_only_by_max",y.iloc[46].e0_raised and y.iloc[46].S_old==8.8 and y.iloc[46].S_new==10.4)
r=fixture();r.iloc[46,r.columns.get_loc("e0_target")]=1.;r.iloc[46,r.columns.get_loc("e0_floor")]=10.4;y=simulate(r)
check("E0_unready_does_not_raise",not y.iloc[46].e0_raised and y.iloc[46].S_new==8.8)
r=fixture();r.iloc[46,r.columns.get_loc("close")]=8.8;r.iloc[46,r.columns.get_loc("e0_target")]=1.;r.iloc[46,r.columns.get_loc("e0_ready")]=1.;r.iloc[46,r.columns.get_loc("e0_floor")]=8.0;y=simulate(r)
check("old_floor_equal_failure_precedes_E0_rescue",y.iloc[46].failed and not y.iloc[46].e0_raised and not y.iloc[46].born)
r=fixture();r.iloc[46,r.columns.get_loc("close")]=8.7;r.iloc[46,r.columns.get_loc("low")]=8.5;y=simulate(r)
check("reentry_anchor_no_earlier_than_failure",y.iloc[48].born and y.iloc[48].a_day==r.index[46])
r=fixture();r.iloc[45:,r.columns.get_loc("close")]=10.2;r.iloc[45:,r.columns.get_loc("high")]=10.2;y=simulate(r)
check("equal20High_is_not_breakout",not y.born.any())
r=fixture();r.iloc[39,r.columns.get_loc("close")]=9.;r.iloc[39,r.columns.get_loc("low")]=8.8;y=simulate(r)
check("anchor_tie_uses_latest",y.iloc[45].a_day==r.index[40])
for cut in [44,45,46,47,48,54]:
    pd.testing.assert_frame_equal(x.iloc[:cut+1],simulate(q.iloc[:cut+1]),check_exact=True,check_dtype=False)
check("prefix_exact_values_synthetic_dtype_failure_reported",True)
base={"parent_exists":True,"filled":30,"live_leaves":0,"approved_Q":100,"unknown":False,"unresolved":False,"pending_exit":False,"current_root":"R","used_receipts":set(),"unlock_known_at":20,"flat":False,"complete_known_at":None,"healthy_held":True,"add_parent_exists":False,"add_filled_F":0,"add_live_leaves":0,"add_approved_Q":0,"add_complete_known_at":None,"decision_open":22,"parent_root":"R","parent_retired":False,"add_parent_root":"R","add_parent_retired":False}
receipt={"fresh":True,"root":"R","id":"n1","known_at":21,"confirmed":True,"eligible_open":22}
check("partial_only_same_parent",perm(receipt,base)=="CONTINUE_SAME_PROBE_REMAINDER")
check("NOFILL_only_same_parent",perm(receipt,{**base,"filled":0})=="CONTINUE_SAME_PROBE_REMAINDER")
check("equal_unlock_receipt_rejected",perm({**receipt,"known_at":20},base)=="WAIT_NEW_RECEIPT_AFTER_UNLOCK")
check("live_leaves_lock",perm(receipt,{**base,"live_leaves":1})=="WAIT_RESPONSIBILITY")
check("pending_exit_lock",perm(receipt,{**base,"pending_exit":True})=="WAIT_RESPONSIBILITY")
check("ACK_unresolved_lock",perm(receipt,{**base,"unresolved":True})=="WAIT_RESPONSIBILITY")
check("overfill_unknown",perm(receipt,{**base,"filled":101})=="OVERFILL_UNKNOWN")
check("old_root_rejected",perm({**receipt,"root":"OLD"},base)=="NO_FRESH_CURRENT_RECEIPT")
check("receipt_replay_rejected",perm(receipt,{**base,"used_receipts":{"n1"}})=="NO_REPLAY")
check("complete_without_proof_rejected",perm(receipt,{**base,"filled":100})=="WAIT_PROBE_COMPLETION_PROOF")
check("complete_same_clock_rejected",perm(receipt,{**base,"filled":100,"complete_known_at":21})=="WAIT_POST_COMPLETE_RECEIPT")
check("add_after_complete_new_receipt",perm(receipt,{**base,"filled":100,"complete_known_at":20})=="PROPOSE_ONE_ADD_TARGET_MARKET_ONLY")
check("no_confirm_no_add",perm({**receipt,"confirmed":False},{**base,"filled":100,"complete_known_at":20})=="NO_NEW_TARGET")

check("expired_receipt_rejected",perm({**receipt,"eligible_open":21},base)=="EXPIRED_OR_WRONG_OPEN")
check("ADD_partial_only_same_ADD_parent",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":30,"add_approved_Q":100})=="CONTINUE_SAME_ADD_REMAINDER")
check("ADD_zero_fill_only_same_ADD_parent",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":0,"add_approved_Q":100})=="CONTINUE_SAME_ADD_REMAINDER")
check("ADD_complete_no_second_target",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":100,"add_approved_Q":100,"add_complete_known_at":20})=="NO_SECOND_ADD_TARGET")
check("ADD_unreconciled_complete_proof_blocks",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":100,"add_approved_Q":100,"add_complete_known_at":None})=="WAIT_ADD_COMPLETION_PROOF")
check("ADD_overfill_unknown",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":101,"add_approved_Q":100})=="OVERFILL_UNKNOWN")
check("ADD_live_leaves_lock",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_filled_F":30,"add_approved_Q":100,"add_live_leaves":1})=="WAIT_RESPONSIBILITY")
check("ADD_no_healthy_chain_cancel_remainder",perm(receipt,{**base,"filled":100,"complete_known_at":20,"healthy_held":False,"add_parent_exists":True,"add_filled_F":30,"add_approved_Q":100})=="CANCEL_OR_RETIRE_ADD_REMAINDER")

check("old_probe_parent_cannot_borrow_new_root",perm(receipt,{**base,"parent_root":"OLD"})=="OLD_OR_RETIRED_PROBE_TARGET")
check("retired_probe_cannot_continue",perm(receipt,{**base,"parent_retired":True})=="OLD_OR_RETIRED_PROBE_TARGET")
check("old_ADD_parent_cannot_borrow_new_root",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_parent_root":"OLD","add_approved_Q":100})=="OLD_OR_RETIRED_ADD_TARGET")
check("retired_ADD_cannot_continue",perm(receipt,{**base,"filled":100,"complete_known_at":20,"add_parent_exists":True,"add_parent_retired":True,"add_approved_Q":100})=="OLD_OR_RETIRED_ADD_TARGET")

import sys
sys.path.insert(0,str(p.parent))
from normalized_output import simulate as normalized_simulate
normalized=normalized_simulate(q)
pd.testing.assert_frame_equal(x,normalized,check_exact=True,check_dtype=False)
for prefix_len in range(1,len(q)+1):
    pd.testing.assert_frame_equal(normalized.iloc[:prefix_len],normalized_simulate(q.iloc[:prefix_len]),check_exact=True)
check("normalized_all_55_synthetic_prefixes_exact",True)
check("normalized_output_values_identical_to_frozen_core",True)
print(json.dumps({"passed":len(checks),"checks":checks,"core_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"normalization_sha256":hashlib.sha256((p.parent/"normalized_output.py").read_bytes()).hexdigest()}))
