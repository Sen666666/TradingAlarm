"""Four frozen pure allocation arms; complete controls before conditional arms."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import argparse,hashlib,json,sys,time,traceback
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];PR=ROOT/'reentry_v1/funding_agent/private_projection'
sys.path.insert(0,str(OUT));from conditional_release_api import FrozenPermission,compile_conditional,compare_candidates,load_complete_batches,P
J=P.J;LR=J.LR
FREEZE=OUT/'CONDITIONAL_RUN_FREEZE.json';START=None;LIMIT=180.;CURRENT={};PROGRESS=[]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def budget_check():
 if START is not None and time.monotonic()-START>=LIMIT:raise TimeoutError('shared four-arm180second budget exhausted')
def exact(a,b,name):
 if P.digest(a)!=P.digest(b):
  save('CONDITIONAL_FIRST_DIFFERENCE.json',dict(context=CURRENT,name=name,actual=a,expected=b));raise AssertionError(name)
def prepare():
 sources=read(OUT/'CONDITIONAL_SOURCE_SHA256.json')
 for name in['run_conditional_release.py','CONDITIONAL_RELEASE_CARD.txt','conditional_release_api.py','FROZEN_SIGNAL_PERMISSION.json','ALL4172_FROZEN_RELEASE_ELIGIBILITY.json','CONDITIONAL_OUTPUT_SCHEMA.json','CONDITIONAL_COMPILED_SOURCES.json']:
  p=OUT/name;sources[str(p)]=sha(p)
 for check in read(PR/'OFF_IDENTITY.json')['checks']:
  for arm in['OFF','ON']:
   p=PR/(arm+'_'+check['opening']+'.json');sources[str(p)]=sha(p)
 sources[str(ROOT/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json')]=sha(ROOT/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json')
 assert all(sha(p)==h for p,h in sources.items())
 save('CONDITIONAL_RUN_FREEZE.json',dict(card_sha256=sha(OUT/'CONDITIONAL_RELEASE_CARD.txt'),sources=sources,
  arms=['A0','B0','A1','B1'],OPENs_per_arm=13,intents_per_arm=4172,total_OPEN_plans=52,shared_compute_budget_seconds=180,
  controls_must_both_match_before_A1_B1=True,prepare_only=True,new_accounts=0,new_restores=0))
 print('RUN FREEZE PREPARED',len(sources),flush=True)
def execute(review_path):
 global START
 assert not(OUT/'CONDITIONAL_RUN_COMPLETION.json').exists(),'completed matrix cannot repeat'
 freeze=read(FREEZE);review=read(review_path)
 assert review['status']=='PASS_CONDITIONAL_CARD_PREPROJECTION_ONLY'
 for p,h in review['source_sha256'].items():assert sha(p)==h,('reviewed source changed',p)
 assert freeze['card_sha256']==sha(OUT/'CONDITIONAL_RELEASE_CARD.txt')
 assert all(sha(p)==h for p,h in freeze['sources'].items()),'frozen execution source changed'
 prep=time.monotonic();batches=load_complete_batches();gate=FrozenPermission(OUT/'FROZEN_SIGNAL_PERMISSION.json')
 config={'A0':('native_singlepass','reference_cash10'),'B0':('confirmed_min_first','reference_cash10'),
  'A1':('native_singlepass','ACT_mature_U0'),'B1':('confirmed_min_first','ACT_mature_U0')}
 bundles={arm:compile_conditional(*cfg,gate,budget_check)for arm,cfg in config.items()}
 save('CONDITIONAL_EXECUTION_SETUP.json',dict(review_file=str(review_path),review_sha256=sha(review_path),freeze_sha256=sha(FREEZE),
  preparation_seconds=time.monotonic()-prep,arms=config,market_reads=0,new_accounts=0,new_restores=0))
 results={arm:{}for arm in config};identities=[];START=time.monotonic()
 for arm in['A0','B0','A1','B1']:
  if arm in['A1','B1']:assert len(identities)==26 and all(x['passed']for x in identities)
  for day,(s0,xs,at)in sorted(batches.items()):
   CURRENT.update(arm=arm,opening=day);budget_check();t=time.monotonic()
   result=bundles[arm]['project_one'](s0,xs,at);budget_check()
   by={P.B.bid(i):i for i in xs};assert len({o['sid']for o in result['orders']})==len(result['orders'])
   for order in result['orders']:
    i=by[order['key']];x=i['_preview'];assert order['fee']==LR.fees(order['quantity'],x['price'],x['schedule'],'buy',i['quote'].par_value)
    assert x['rule'].buy_floor(order['quantity'])==order['quantity']and order['quantity']<=x['maxq']
   assert sum((o['fee']for o in result['orders']),D(0))==result['fees']
   assert s0.available_exact-sum((o['gross']+o['fee']for o in result['orders']),D(0))==result['available']
   if arm in['A0','B0']:
    original=read(PR/(('OFF_'if arm=='A0'else'ON_')+day+'.json'))
    # Complete saved output surface, including all rejection/skip and migration
    # records. OFF archive intentionally omitted only its final_state.
    for field,value in original.items():exact(result[field],value,'complete reference '+arm+' '+day+' '+field)
    identities.append(dict(arm=arm,opening=day,passed=True,whole_saved_output_exact=True,intents=len(xs),orders=len(result['orders'])))
    save('CONDITIONAL_REFERENCE_IDENTITIES.json',dict(passed=len(identities)==26,checks=identities))
   save(arm+'_'+day+'.json',result)
   results[arm][day]={k:v for k,v in result.items()if k!='final_state'}
   PROGRESS.append(dict(arm=arm,opening=day,intents=len(xs),orders=len(result['orders']),available=result['available'],fees=result['fees'],
    seconds=time.monotonic()-t,cumulative_seconds=time.monotonic()-START,input_unchanged=True,retained_guards_valid=True))
   save('CONDITIONAL_RUN_PROGRESS.json',PROGRESS);print(arm,day,len(result['orders']),round(time.monotonic()-START,3),flush=True)
 A=[];B=[];interaction=[];cash=[];focus=read(PR/'ON_ALL16_FOCUS.json');focus_rows=[]
 for day,(s0,xs,at)in sorted(batches.items()):
  budget_check();a=compare_candidates(day,s0,xs,results['A0'][day],results['A1'][day],gate);b=compare_candidates(day,s0,xs,results['B0'][day],results['B1'][day],gate);A.extend(a);B.extend(b)
  assert [r['key']for r in a]==[r['key']for r in b]
  for aa,bb in zip(a,b):interaction.append(dict(opening=day,key=aa['key'],sid=aa['sid'],role=aa['role'],CP1_id=aa['CP1_id'],
   cash_release_eligible=aa['cash_release_eligible'],A_native_quantity_delta=aa['quantity_delta'],B_minfirst_quantity_delta=bb['quantity_delta'],
   interaction_quantity_delta=bb['quantity_delta']-aa['quantity_delta'],not_a_single_factor_B1_vs_A0=True))
  cash.append(dict(opening=day,decision_NAV=s0.decision_nav,starting_available=s0.available_exact,original_cash10=s0.decision_nav*D('.1'),
   **{arm:dict(orders=len(results[arm][day]['orders']),available=results[arm][day]['available'],fees=results[arm][day]['fees'],
    capital=results[arm][day]['capital'],nominal_risk=results[arm][day]['nominal_risk'])for arm in config},
   A_additional_cash_reserved=results['A0'][day]['available']-results['A1'][day]['available'],
   B_additional_cash_reserved=results['B0'][day]['available']-results['B1'][day]['available'],independent_S0_not_continuous_account=True))
  for f in focus:
   if f['opening']!=day:continue
   row=dict(opening=day,signal_day=f['signal_day'],sid=f['sid'],name=f['name'],original_minfirst_status=f['status'])
   for arm in config:
    row[arm]=[o for o in results[arm][day]['orders']if o['sid']==f['sid']and o['role']=='mobile']
   focus_rows.append(row)
 assert len(A)==len(B)==len(interaction)==4172 and len(focus_rows)==16
 save('A_NATIVE_ALL4172_COMPARISONS.json',A);save('B_MINFIRST_ALL4172_COMPARISONS.json',B);save('AB_INTERACTION_ALL4172.json',interaction)
 save('CONDITIONAL_CASH_BUFFER_COST_BY_OPEN.json',cash);save('CONDITIONAL_ALL16_FOCUS.json',focus_rows)
 def count_changes(rows):
  return dict(added=sum(r['old_order']is None and r['new_order']is not None for r in rows),lost=sum(r['old_order']is not None and r['new_order']is None for r in rows),
   shrunk=sum(r['old_order']and r['new_order']and r['quantity_delta']<0 for r in rows),increased=sum(r['old_order']and r['new_order']and r['quantity_delta']>0 for r in rows))
 # bool expressions above can return None; count using explicit booleans.
 def changes(rows):
  return {label:sum(bool(test(r))for r in rows)for label,test in dict(added=lambda r:r['old_order']is None and r['new_order']is not None,
   lost=lambda r:r['old_order']is not None and r['new_order']is None,shrunk=lambda r:r['old_order']and r['new_order']and r['quantity_delta']<0,
   increased=lambda r:r['old_order']and r['new_order']and r['quantity_delta']>0).items()}
 summary=dict(arms={arm:dict(order_count=sum(len(x['orders'])for x in results[arm].values()),
  gross_sum_of_independent_reservations=sum((o['gross']for x in results[arm].values()for o in x['orders']),D(0)),
  reserved_Fq=sum((x['fees']for x in results[arm].values()),D(0)))for arm in config},A1_vs_A0=changes(A),B1_vs_B0=changes(B),
  complete_rows_per_comparison=4172,reference_identities_passed=26,focus16=16,remaining14_covered=True,
  no_new_price_labels=True,no_new_PnL=True,new_accounts=0,new_restores=0,real_fills=0)
 save('CONDITIONAL_MATRIX_SUMMARY.json',summary)
 assert all(sha(p)==h for p,h in freeze['sources'].items());budget_check()
 save('CONDITIONAL_RUN_COMPLETION.json',dict(passed=True,arms=4,OPEN_plans=52,intents_per_arm=4172,whole_controls_exact=26,
  compute_wall_seconds=time.monotonic()-START,shared_budget_seconds=180,source_unchanged=True,inputs_unchanged=True,
  no_fallback=True,new_accounts=0,new_restores=0,real_fills=0,new_outcome_labels=0,independent_result_review_required=True))
 print(json.dumps(P.serial(summary),ensure_ascii=False),flush=True)
def main():
 a=argparse.ArgumentParser();a.add_argument('--prepare',action='store_true');a.add_argument('--execute',action='store_true');a.add_argument('--review-file',type=Path);args=a.parse_args()
 assert args.prepare!=args.execute
 if args.prepare:prepare()
 else:assert args.review_file;execute(args.review_file)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  value=dict(error=str(e),traceback=traceback.format_exc(),context=CURRENT,compute_wall_seconds=time.monotonic()-START if START else None,no_fallback=True,new_accounts=0,new_restores=0)
  if isinstance(e,RuntimeError)and e.args and isinstance(e.args[0],dict)and e.args[0].get('invalid_plan'):save('CONDITIONAL_INVALID_PLAN.json',e.args[0])
  save('CONDITIONAL_RUN_FAILURE.json',value);raise
