"""Finish receipts from the completed sole eta prefix; no new financial run."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import importlib.util,sys,json,gzip,pickle,hashlib,math,copy
import pandas as pd
O=Path(__file__).resolve().parent;S=O.parent;E=S.parent;P=O/'eta_native_prefix_2022Jan21'
sys.path.insert(0,str(E/'trend_exit_controls_v1'));import load_inputs as V
N,J,A=V.N,V.J,V.A
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with(gzip.open(p,'rt')if p.suffix=='.gz'else p.open())as f:return[json.loads(x)for x in f]if'.jsonl'in p.name else json.load(f)
def order(intents,score):
 original=[];ranks={}
 for i in sorted(intents,key=lambda i:(i['original_H1_rank'],i['role']!='core')):
  if i['sid']not in ranks:original.append(i['sid']);ranks[i['sid']]=i['original_H1_rank']
 assert len(set(ranks.values()))==len(ranks)
 values={s:score(s)for s in original};ready=[s for s in original if values[s]is not None];pos={s:j for j,s in enumerate(original)};ready.sort(key=lambda s:(-round(values[s],12),pos[s]));it=iter(ready);final=[s if values[s]is None else next(it)for s in original]
 return {s:ranks[original[j]]for j,s in enumerate(final)},values,original,final
def main():
 out=O/'PVR_ETA_NATIVE_PREFIX_AUDIT.json';assert not out.exists()
 done=read(P/'DONE.json');assert done['completed'];ck=read(P/'checkpoint.json');assert sha(P/'checkpoint.pkl')==ck['sha256']
 for p,h in ck['source_freeze'].items():assert sha(p)==h,('changed execution source',p)
 payload=pickle.loads((P/'checkpoint.pkl').read_bytes());selected=payload['runner']['rank_scores_manifest_sha256'];manifest=S/'mechanism_design/SCORES_MANIFEST.json';assert selected==sha(manifest)
 assert A.Runner.planning is N.Runner.planning and A.Runner.opening is J.Runner.opening and A.Runner.route is A.P.ROUTES[True]
 engine=read(P/'checkpoint.provenance.json')['engine_identity']['functions']
 for name,fn in [('planning',N.Runner.planning),('opening',J.Runner.opening),('route',A.P.ROUTES[True])]:assert engine[name]['code_sha256']==V.IO._code_fingerprint(fn.__code__)
 book=read(P/'pair/B.json.gz');daily=read(P/'pair/daily.jsonl.gz');logs=read(P/'pair/rank-policy.jsonl.gz');funding=read(P/'pair/funding.jsonl.gz');assert len(daily)==len(book['decisions'])==14
 oldbind=read(O/'PVR_ETA_OLD_PREFIX_BINDING.json');assert sha(oldbind['old_book'])==oldbind['expected_sha256_from_prior_final_binding'];oldbook=read(oldbind['old_book'])
 original_scores=N.FrozenScores(V.D.O/'SCORES_MANIFEST.json');direct={};groups=defaultdict(list)
 for z in logs:groups[z['day']].append(z)
 C=Counter();changes=[]
 for dec in book['decisions']:
  day=dec['at'][:10];intents=dec['intents'];reported=groups[day];assert len(reported)==len({z['sid']for z in reported})
  def at(sid):
   if sid not in direct:
    f=pd.read_parquet(manifest.parent/'scores'/f'{sid}.parquet');direct[sid]={str(t.date()):float(v)for t,v in f.score.items()}
   v=direct[sid].get(day);return v if v is not None and math.isfinite(v)else None
  keys,values,original,final=order(intents,at);old,_,_,oldfinal=order(intents,lambda sid:original_scores.at(sid,day));by={z['sid']:z for z in reported};assert set(by)==set(original)
  for sid in original:
   z=by[sid];assert z['priority_rank']==keys[sid]and z['PVR']==values[sid]and z['PVR_ready']==(values[sid]is not None)
   if values[sid]is None:assert z['original_slot']==z['final_slot'];C['UNKNOWN_fixed_slot']+=1
   else:assert -1<=values[sid]<=1
   C['stock_priority_slots']+=1
  for i in intents:assert i['rank']==keys[i['sid']]and i['PVR_score']==values[i['sid']];C['frozen_role_contract_rank_fields']+=1
  if oldfinal!=final:changes.append(dict(day=day,original_H1=original,old_PVR=oldfinal,eta=final,values=values))
 fills={r['receipt']['receipt_id']:r for r in book['audit']if r.get('kind')=='fill'};reqs={r['event_id']:r for r in book['audit']if r.get('kind')=='exit_request'};buys={r['layer']:r for r in book['trades']if r['side']=='buy'}
 for t in book['trades']:
  assert t['at'][11:19]=='09:30:00';expected=D(t['raw_open'])*(D(1)+D('.0005')if t['side']=='buy'else D(1)-D('.0005'));assert D(t['price'])==expected
  f=fills[t['receipt_id']];assert sum((D(v)for v in f['fee_components'].values()),D(0))==D(t['fees_cny']);C['actual_price_fee_checked']+=1
  if t['side']=='buy':assert t['signal_at']<t['at'];C['buy_clock_checked']+=1
  else:
   assert reqs[f['order_id']]['at']<t['at'];C['sell_request_clock_checked']+=1
   for p in t['parts']:assert buys[p['layer']]['at'][:10]<t['at'][:10];C['sold_part_minimum_Tplus1_date_checked']+=1
 decisions={r['at'][:10]:r for r in book['decisions']}
 for j,z in enumerate(funding):
  if z.get('result')!='reserved'or z.get('role')!='mobile':continue
  prev=max(d for d in decisions if d<z['at'][:10]);both=[i for i in decisions[prev]['intents']if i['sid']==z['sid']and i['role']=='core']
  if both:assert any(q.get('role')=='core'and q['sid']==z['sid']and q['at']==z['at']and q['result']!='reserved'for q in funding[:j]);C['CORE_before_mobile_funding_checked']+=1
 def key(t):return(t['security_id'],t['at'],'core'if t['kind']=='core'else'mobile')
 old={key(t):t for t in oldbook['trades']if t['side']=='buy'};new={key(t):t for t in book['trades']if t['side']=='buy'};newonly=[k for k in new if k not in old];oldonly=[k for k in old if k not in new];qty=[dict(key=k,old=old[k]['shares'],eta=t['shares'])for k,t in new.items()if k in old and t['shares']!=old[k]['shares']]
 assert changes and(newonly or oldonly or qty)
 note={'status':'FINANCIAL_PREFIX_COMPLETED_POSTPROCESS_TYPE_ERROR_ONLY','error':"TypeError: datetime.datetime not subscriptable at same_day construction after actual run and after assert len14/profile14/score_query_dates had all passed",'financial_prefix_rerun':False,'executed_script':str(O/'audit_eta_native_prefix.py'),'executed_script_sha256':sha(O/'audit_eta_native_prefix.py'),'financial_DONE':str(P/'DONE.json'),'postprocessor':str(Path(__file__)),'no_trade_method_modified':True}
 with(P/'POSTPROCESS_NOTE.json').open('x')as f:json.dump(note,f,ensure_ascii=False,indent=2);f.write('\n')
 sources=dict(ck['source_freeze']);sources[str(Path(__file__).resolve())]=sha(__file__);sources[str((O/'PVR_ETA_OLD_PREFIX_BINDING.json').resolve())]=sha(O/'PVR_ETA_OLD_PREFIX_BINDING.json')
 result=dict(status='PASS_ORIGINAL_NATIVE_ETA_SINGLE_PRIORITY_PREFIX',new_short_prefixes=1,new_full_accounts=0,prefix_end='2022-01-21',CLOSEs=14,selected_eta_manifest=str(manifest),selected_eta_manifest_sha256=selected,source_sha256=sources,original_native_method_code_identities_checked=True,all_account_callbacks_unchanged_asserted_before_run=True,priority_plan_measured_calls=14,priority_plan_count_evidence='Runtime sys.setprofile call/return invariant asserted equal14 before the documented postprocessor exception; unchanged executed source and complete DONE retained.',priority_ranklog_no_duplicate_sid_per_CLOSE=True,nonrank_intents_unchanged='Original unchanged apply_priority before/after nonrank assertion executed; no signal/holding/funding function overridden.',physical_price_CP_industry_prefix='2022-01-21',eta_future_array_prefix_audit_separate=True,checks=dict(C),changed_priority_days=len(changes),actual_buy_contract_changes=dict(eta_only=len(newonly),old_only=len(oldonly),same_key_different_quantity=len(qty)),eta_trades=len(book['trades']),eta_ending_NAV=book['ending_NAV'],old_prefix_ending_NAV=oldbook['ending_NAV'],examples=dict(priority=changes[:1],eta_only=newonly[:4],old_only=oldonly[:4],quantities=qty[:4]),old_prefix_binding=oldbind,financial_prefix_rerun=False,postprocess_note=str(P/'POSTPROCESS_NOTE.json'),not_effectiveness_evidence=True)
 with out.open('x')as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({k:result[k]for k in ['status','changed_priority_days','actual_buy_contract_changes','eta_trades','eta_ending_NAV','old_prefix_ending_NAV','new_full_accounts']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
