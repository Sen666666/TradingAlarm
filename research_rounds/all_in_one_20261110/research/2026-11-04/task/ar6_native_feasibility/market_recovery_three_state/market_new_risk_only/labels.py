from pathlib import Path
import json,hashlib,time
from collections import Counter
import pandas as pd
O=Path(__file__).resolve().parent;BASE=O.parent/'structural_walk_daily_support_v2'
REC=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/mainline-absolute-Q4-20261031/recovery.csv')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 start=time.monotonic();assert not(O/'RESULTS.json').exists(),'no automatic repeat'
 freeze=json.loads((O/'SOURCE_FREEZE.json').read_text())
 for p,h in freeze.items():assert sha(p)==h,p
 rows=json.loads((BASE/'DAILY.json').read_text());calendar=pd.read_csv(REC,usecols=['date']).date.tolist()
 assert len(rows)==3273 and [r['day']for r in rows]==calendar
 out=[]
 for i,r in enumerate(rows):
  state=r['market_structural_state'];nxt=calendar[i+1]if i+1<len(calendar)else None
  category={None:'NA_NO_MARKET_STATE','D':'ZERO_NEW_OPEN_ADD','P':'PROBE_CATEGORY_UNSIZED','C':'CONDITIONAL_INCREMENT_CATEGORY_UNSIZED'}[state]
  known=bool(r['price_known']and r['breadth_known']and r['prior64_ready'])
  old=r['old_ACT_context'];historical_H=None if old is None else not bool(old['on'])
  x={**r,'decision_close':r['at'],'asof':r['at'],'macrostate_before':r['state_before'],'macrostate_after':state,
   'next_market_planned_OPEN':None if nxt is None else nxt+' 09:30:00+08:00','next_market_date':nxt,
   'next_OPEN_is_market_calendar_only':True,'next_OPEN_endpoint_censored':nxt is None,
   'macro_new_risk_category':category,'new_risk_label':category,
   'macro_zero_new_risk_permission':True if state=='D'else None,
   'macro_P_C_cap_or_executable_permission':None,
   'fresh_evidence_grant_status':'UNKNOWN_NO_NEW_GRANT'if not known else'KNOWN_INPUT_BUT_P_C_FUNDS_RULE_UNFROZEN',
   'cancel_unfilled_buy_intents_asof_CLOSE':'REQUEST_CANCEL_AWAIT_ACK'if state=='D'else'NO_MACRO_D_CANCEL_REQUEST',
   'pending_fills_are_assumed_zero':False,
   'old_inventory_macro_action':'NO_MACRO_FORCED_SELL_USE_ORIGINAL_I_CP1_EXIT',
   'historical_H_context_only':historical_H,'historical_ACT_not_new_path':True,
   'post_H_permission_path':'BLOCKED_NOT_SIMULATED_REQUIRES_REAL_FLAT_CANCEL_ACK_FRESH_POST_H_P',
   'all_roles_same_macro_label':True,'floating_profit_loss_used':False}
  out.append(x)
 save('DAILY.json',out)
 pd.DataFrame([{**r,'old_ACT_context':json.dumps(r['old_ACT_context'],ensure_ascii=False)}for r in out]).to_csv(O/'DAILY.csv',index=False)
 ws=json.loads((BASE/'WINDOWS.json').read_text());keep={'L01','L02','L03','2023Jul_false','2024SepOct','strong'};summary=[]
 for w in ws:
  if w['label']not in keep:continue
  subset=[r for r in out if w['lo']<=r['day']<=w['hi']]
  summary.append(dict(label=w['label'],lo=w['lo'],hi=w['hi'],closes=len(subset),macro_counts=dict(Counter(r['macrostate_after']for r in subset)),
   old_H_context_closes=sum(r['historical_H_context_only']is True for r in subset),
   key_turns=[r for j,r in enumerate(subset)if j==0 or r['event']!='none']))
 save('WINDOWS_AND_KEY_TURNS.json',summary)
 save('H_ABSTRACT_CONTRACT_NOT_A_PATH.json',dict(if_new_H='ZERO_NEW_RISK_AND_QUEUE_ORIGINAL_FULL_EXITS',before_new_P=['REAL_FLAT','CANCEL_ACK_RECONCILED','POST_H_FRESH20_EVIDENCE'],C_reentry='REQUIRES_POST_H_ACTUAL_TRIAL_FEEDBACK_UNSPECIFIED',historical_H_drives_new_state=False,new_H_path_computed=False))
 for p,h in freeze.items():assert sha(p)==h,p
 save('RESULTS.json',dict(passed=True,seconds=time.monotonic()-start,rows=len(out),fixed_windows=len(summary),macro_only_new_risk_labels=True,old_inventory_forced_by_macro=False,new_models=0,new_accounts=0,new_state_walks=0,new_risk_ledger=False,original_v2_unchanged=True,P_C_executable_permissions_not_inferred=True,no_automatic_followup=True))
 print(json.dumps(dict(rows=len(out),windows=[{k:v for k,v in w.items()if k!='key_turns'}for w in summary]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
