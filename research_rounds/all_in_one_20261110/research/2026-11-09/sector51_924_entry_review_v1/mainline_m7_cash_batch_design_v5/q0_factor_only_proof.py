"""Pure proof checker only. NOT connected to cash/event/execution admission."""
from decimal import Decimal as D
class NotProven(Exception):pass
def prove_zero_entitlement(state,event,expected_prior_days):
 def require(ok,reason):
  if not ok:raise NotProven(reason)
 require(state['inception']=={'new_simulated_account':True,'cash_only':True,'predecessor_positions':False,'inherited_claims':False,'inherited_receivable':'0'},'NO_PROVEN_CASH_ONLY_ACCOUNT_INCEPTION')
 require(event['event_type']=='PURE_CASH' and D(event['split_ratio'])==1,'STRUCTURAL_OR_UNKNOWN_EVENT')
 require(event['record_ownership_semantics']=='ordinary_cash_record_date_strictly_before_ex_date','UNKNOWN_ENTITLEMENT_SEMANTICS')
 require(event['source_bridge_verified'] and event['same_lineage'] and event['exact_event_identity_verified'],'UNPROVEN_EXACT_SOURCE_EVENT')
 require([r['day'] for r in state['ledger']]==expected_prior_days,'INCOMPLETE_ACCOUNT_LIFETIME_LEDGER')
 sid=event['sid'];ex=event['ex_date']
 require(bool(expected_prior_days) and all(d<ex for d in expected_prior_days),'NOT_PREOPEN_EX_DATE_PROOF')
 require(not any(r.get('sid')==sid and int(r.get('qty',0))>0 for r in state['orders']),'EVER_TRADED_OR_HELD')
 require(not any(r.get('sid')==sid and int(r.get('qty',0))>0 for r in state['holdings']),'EVER_HELD')
 require(not any(a.get('sid')==sid for a in state['archive'].values()),'PRIOR_ROUND_EXISTS')
 require(sid not in state['active'],'ACTIVE_POSITION_OR_ROUND_EXISTS')
 require(not any(k[0]==sid and int(v.get('q',0))>0 for k,v in state['snapshots'].items()),'RECORD_HOLDING_EXISTS')
 require(not any(k[0]==sid for k in state['claims']),'CLAIM_EXISTS_EVEN_IF_PAID')
 require(not any(r.get('sid')==sid and (D(str(r.get('cash_delta',0)))!=0 or D(str(r.get('receivable_delta',0)))!=0 or int(r.get('record_qty',0))>0) for r in state['equity']),'ENTITLEMENT_EVIDENCE_EXISTS')
 return {'sid':sid,'ex_date':ex,'event_id':event['event_id'],'proof':'ZERO_EVERY_POSSIBLE_RECORD_SNAPSHOT_IN_NEW_SIMULATION','cash_entitlement':'0','no_record_or_pay_date_inferred':True,'scope':'this exact event only','runtime_admission_enabled':False}
