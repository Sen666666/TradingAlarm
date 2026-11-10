"""Four immutable own-Jul31 checkpoints and future source-only event checks."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
from collections import defaultdict
import json,hashlib
P=Path(__file__).resolve().parent;W=P.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(p):return json.loads(Path(p).read_text())
def main():
 roots={'C10':W/'g-s-C-month-continuation-20261102/runs/2025_26-C10','C20':W/'g-s-C-month-continuation-20261102/runs/2025_26-C_BATCH20','C10_R0':W/'g-s-C-R0-continuous-july-v1-20261102/runs/C10','C20_R0':W/'g-s-C-R0-C20-budget250-v2-20261102/runs/C_BATCH20'}
 states={};f1hash=[]
 for k,r in roots.items():
  pr=rd(r/'PROGRESS.json');cp=Path(pr['checkpoint']);assert str(pr['cursor']).startswith('2025-07-31 15:10') and sha(cp)==pr['sha256'];side=rd(cp.with_suffix('.provenance.json'));assert side['checkpoint_sha256']==pr['sha256'];x=rd(cp.with_suffix('.json'));a=x['account'];b=a['balance'];sig=hashlib.sha256(json.dumps(x['f1'],sort_keys=True).encode()).hexdigest();f1hash.append(sig)
  states[k]=dict(checkpoint=str(cp),checkpoint_sha256=pr['sha256'],observable_sha256=sha(cp.with_suffix('.json')),engine=side['engine_identity'],NAV=b['nav'],available=b['available'],inventory=b['inventory'],dividend_receivable=b['dividend_receivable'],reserved=b['order_reserved'],stocks=len(b['quantities']),layers=sum(bool(z['qty']) for z in a['layers']),pending_intents=len(x['pending']),active_buys=len(a['buys']),exit_orders=len(a['exits']),ACT=a['policy']['act'],losses=a['policy']['losses'],consumed_receipts=len(a['policy']['consumed']),F1_hash=sig,F1seq=x['f1seq'],latest_certificate=x['active'],held_layers=[dict(layer=z,meta=a['capital_meta'][str(z['id'])]) for z in a['layers'] if z['qty']],exits=a['exits'],locks=a['policy']['locks'],buys=a['buys'],source_binding=side['binding']['source'],no_state_change=True)
 # No event is run. Keep future terms and immediate-vs-conditional distinctions.
 export=rd(P/'EXPORTED_INPUTS.json');m=rd(export['manifest']);terms=rd(P/'inputs'/m['continuation_extension']['actions']['path']);payments=rd(P/'inputs'/m['continuation_extension']['payments']['path']);by=defaultdict(list)
 for a in terms:by[a['effective_date']].append(a)
 mixed=[dict(day=d,rights=[a['sid'] for a in aa if a.get('classification')=='rights_issue_no_subscription'],ordinary=[a['sid'] for a in aa if a.get('classification')!='rights_issue_no_subscription']) for d,aa in by.items() if any(a.get('classification')=='rights_issue_no_subscription' for a in aa) and any(a.get('classification')!='rights_issue_no_subscription' for a in aa)]
 watches=[];immediate=[]
 for k,s in states.items():
  for a in terms:
   ratio=F(a['split_ratio']);held=[z for z in s['held_layers'] if z['layer']['sid']==a['sid']];cert=s['latest_certificate'];unsubmitted=(cert['Q'].get(a['sid'],0)>0 and a['sid'] not in s['buys'])
   if held or unsubmitted:
    q=[z['layer']['qty'] for z in held];fractional=[v for v in q if (F(v)*ratio).denominator!=1]
    v=dict(account=k,action=a,Jul31_held_raw_quantities=q,Jul31_positive_queued_C=cert['Q'].get(a['sid'],0) if unsubmitted else 0,Jul31_quantity_fractional_under_future_ratio=fractional,certainty='immediate no-intervening-session boundary' if a['effective_date']=='2025-08-01' else 'conditional only; future transactions can change inventory/authority')
    watches.append(v)
    if a['effective_date']=='2025-08-01' and (fractional or (ratio!=1 and unsubmitted)):immediate.append(v)
 oldm=rd(W/'g-s-C-month-continuation-20261102/inputs/2025_26/MANIFEST.json');prefix=[]
 for group in ['files','extensions','month_extension']:
  assert m[group]==oldm[group]
  for key,rec in oldm[group].items():
   a=W/'g-s-C-month-continuation-20261102/inputs/2025_26'/rec['path'];b=P/'inputs'/rec['path'];assert sha(a)==sha(b)==rec['sha256'];prefix.append(dict(group=group,key=key,sha256=rec['sha256']))
 common_ids=rd(W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json')['fixed_stock_ids'];assert common_ids==m['fixed_ids'];assert len(m['sectors'])==90
 out=dict(financial_events=0,states=states,all_four_market_F1_equal=len(set(f1hash))==1,original_input_prefix_byte_identity=prefix,same_old_PVR_stock_id_order=True,additional_sessions=export['additional_sessions'],source_action_count=len(terms),split_count=sum(D(a['split_ratio'])!=1 for a in terms),rights_count=sum(a.get('classification')=='rights_issue_no_subscription' for a in terms),unknown_payment_date_count=sum(a.get('paid_at') is None and D(a['cash_per_old_share'])!=0 for a in terms),payment_events=len(payments),mixed_rights_ordinary_days_known_unwired=mixed,current_hold_or_queued_action_watchlist=watches,immediate_boundary_blockers=immediate,actual_future_fractional_responsibilities_unknown_until_account_reaches_action=True,not_all_rare_events_implemented=True,needs_fourth_input_generation_loader=True,needs_explicit_same_account_source_import=True)
 (P/'STATE_AND_EVENT_PREFLIGHT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('FOUR_STATE_PREFLIGHT_READY','sourceactions',len(terms),'mixedrights',len(mixed),'immediateblocks',len(immediate))
 for k,s in states.items():print(k,s['NAV'],s['stocks'],s['pending_intents'],s['exit_orders'])
if __name__=='__main__':main()
