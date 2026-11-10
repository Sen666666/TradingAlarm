"""One Jan21 original-native technical prefix, eta score source only. No full run."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from bisect import bisect_right
import sys,json,gzip,hashlib,copy,math,time
import pandas as pd
O=Path(__file__).resolve().parent;S=O.parent;E=S.parent;T=E/'trend_exit_controls_v1'
sys.path.insert(0,str(T));import load_inputs as V
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
CUT='2022-01-21';OUT=O/'eta_native_prefix_2022Jan21';RECEIPT=O/'PVR_ETA_NATIVE_PREFIX_AUDIT.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with(gzip.open(p,'rt')if p.suffix=='.gz'else p.open())as f:return [json.loads(x)for x in f]if'.jsonl'in p.name else json.load(f)
def stripped(i):return {k:v for k,v in i.items()if k not in ['quote','clock','CP1_trace','rank','original_H1_rank','priority_rank','PVR_score','PVR_ready','priority_policy']}
def expected_order(intents,at):
 ordered=sorted(intents,key=lambda x:(x['rank'],x['role']!='core'));original=[];ranks={}
 for x in ordered:
  if x['sid']not in ranks:original.append(x['sid']);ranks[x['sid']]=x['rank']
 assert len(set(ranks.values()))==len(ranks)
 value={sid:at(sid)for sid in original};ready=[s for s in original if value[s]is not None];pos={s:i for i,s in enumerate(original)}
 ready.sort(key=lambda s:(-round(value[s],12),pos[s]));it=iter(ready);final=[s if value[s]is None else next(it)for s in original]
 return {s:ranks[original[i]]for i,s in enumerate(final)},value,original,final

def main():
 started=time.monotonic();assert not OUT.exists()and not RECEIPT.exists();OUT.mkdir(parents=True)
 freeze=S/'pvr_eta_v1/HYPOTHESIS_FREEZE.json';manifest=S/'mechanism_design/SCORES_MANIFEST.json';launcher=S/'pvr_eta_v1/run_eta_account.py';gate=O/'pvr_consistency/LAUNCHER_STATIC_AUDIT.json'
 gz=read(gate);assert gz['status']=='PASS_SOURCE_ONLY_LAUNCHER_STATIC_REVIEW_NATIVE_PREFIX_SEPARATE'
 for p,h in gz['source_sha256'].items():assert sha(p)==h
 assert read(freeze)['before_new_account_results'] is True
 source={str(p.resolve()):sha(p)for p in [Path(__file__),freeze,manifest,launcher,gate,Path(V.__file__)]};source.update(gz['source_sha256'])
 # Root launcher's exact order: original inputs reset original score, then eta.
 shared,receipts,cp,states,ir,identity=V.inputs('2022_2024');original_scores=N.SCORES;original_score_sha=original_scores.manifest_sha256
 # Same original physical-prefix helper used in previously audited prefixes.
 shared=J.W.physical(shared,CUT);receipts={s:{d:q for d,q in rr.items()if d<=CUT}for s,rr in receipts.items()};cp={s:q.loc[:CUT]for s,q in cp.items()};states={s:[q for q in rr if q['day']<=CUT]for s,rr in states.items()};ir={k:q for k,q in ir.items()if q['confirmed_day']<=CUT}
 N.configure_scores(manifest);selected=N.SCORES.manifest_sha256;assert selected==sha(manifest)
 r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 assert r.rank_mode=='PVR_SLOT1'and r.rank_scores_manifest_sha256==selected
 assert r.planning.__func__ is N.Runner.planning and r.opening.__func__ is J.Runner.opening and r.route.__func__ is A.P.ROUTES[True]
 r.assert_native_wiring();a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==D(1000000)and not a.trades and not a.positions
 for name in ['reserve_quantity','fill_buy','fill_exit','cancel_buy','split','sync','assert_budget_view','expire_day_buys']:assert getattr(a,name).__func__ is getattr(J.Account,name)
 sources=A.source_freeze();sources.update(source);r.source_freeze=sources
 captures=[];calls=Counter();query_days=set();priority_code=N.priority_plan.__code__;score_code=N.FrozenScores.at.__code__
 def profile(frame,event,arg):
  if frame.f_code is priority_code:
   if event=='call':calls['priority_plan_call']+=1;captures.append(dict(day=frame.f_locals['day'],intents=copy.deepcopy([{k:v for k,v in i.items()if k not in ['quote','clock','CP1_trace']}for i in frame.f_locals['intents']])))
   elif event=='return':calls['priority_plan_return']+=1;captures[-1]['returned']=copy.deepcopy(arg)
  elif frame.f_code is score_code and event=='call':query_days.add(frame.f_locals['day']);calls['native_score_query']+=1
 sys.setprofile(profile)
 try:
  with IO.atomic_runner_outputs(r,L,OUT,canonicalize=J.W.canon):assert r.run_prepared(OUT,300,end=CUT)
 finally:sys.setprofile(None)
 assert len(r.daily)==14 and calls['priority_plan_call']==calls['priority_plan_return']==14
 assert len({x['day']for x in captures})==14 and all(d<=CUT for d in query_days)
 direct={};checks=Counter();changes=[];same_day={d['at'][:10]:d for d in a.decisions}
 for c in captures:
  day=c['day']
  def score(sid):
   if sid not in direct:
    f=pd.read_parquet(manifest.parent/'scores'/f'{sid}.parquet');direct[sid]={str(t.date()):float(v)for t,v in f.score.items()}
   v=direct[sid].get(day);return v if v is not None and math.isfinite(v)else None
  expected,values,original,final=expected_order(c['intents'],score);old,_,_,oldfinal=expected_order(c['intents'],lambda sid:original_scores.at(sid,day))
  assert expected==c['returned'][0]
  logs=c['returned'][1];by={x['sid']:x for x in logs}
  for sid in original:
   z=by[sid];assert z['priority_rank']==expected[sid]and z['original_H1_rank']==next(x['rank']for x in c['intents']if x['sid']==sid)
   assert z['PVR']==values[sid]and z['PVR_ready']==(values[sid]is not None)
   if values[sid]is None:assert z['original_slot']==z['final_slot'];checks['UNKNOWN_fixed_slots']+=1
   checks['stock_slots_checked']+=1
  for i in same_day[day]['intents']:
   prior=next(x for x in c['intents']if x['sid']==i['sid']and x['role']==i['role']);assert stripped(i)==stripped(prior)
   assert i['rank']==expected[i['sid']]and i['PVR_score']==values[i['sid']]
   checks['unchanged_nonranking_intents']+=1
  if final!=oldfinal:changes.append(dict(day=day,original_H1=original,old_PVR=oldfinal,eta=final,eta_values=values))
 book=read(OUT/'pair/B.json.gz');fills={x['receipt']['receipt_id']:x for x in book['audit']if x.get('kind')=='fill'};requests={x['event_id']:x for x in book['audit']if x.get('kind')=='exit_request'};buys={x['layer']:x for x in book['trades']if x['side']=='buy'}
 for t in book['trades']:
  assert t['at'][11:19]=='09:30:00';p=D(t['raw_open'])*(D(1)+D('.0005')if t['side']=='buy'else D(1)-D('.0005'));assert p==D(t['price'])
  f=fills[t['receipt_id']];assert sum((D(v)for v in f['fee_components'].values()),D(0))==D(t['fees_cny']);checks['actual_fill_price_fee']+=1
  if t['side']=='buy':assert t['signal_at']<t['at'];checks['buy_clock']+=1
  else:
   rq=requests[f['order_id']];assert rq['at']<t['at'];checks['sell_request_clock']+=1
   for part in t['parts']:
    b=buys[part['layer']];sellable=shared[1].lag('A',J.M.N.iso(b['at']),shared[1].protocol['sellable_lag_sessions']['A']);assert J.M.N.iso(t['at'])>=sellable;checks['sold_part_Tplus1']+=1
 oldgate=E/'dec2022_authorization_v1/independent_review/H2_NATIVE_POSITIVE_PREFIX_AUDIT.json';oldrec=read(oldgate);assert oldrec['status']=='PASS_PHYSICAL_POSITIVE_NATIVE_PREFIX'
 oldbookpath=oldgate.parent/'h2_physical_prefix/ORIGINAL_NATIVE/pair/B.json.gz';oldbook=read(oldbookpath)
 assert oldrec['results']['ORIGINAL_NATIVE']['closes']==14
 def buykey(t):return(t['security_id'],t['at'],'core'if t['kind']=='core'else'mobile')
 oldbuys={buykey(t):t for t in oldbook['trades']if t['side']=='buy'};newbuys={buykey(t):t for t in book['trades']if t['side']=='buy'}
 onlynew=[k for k in newbuys if k not in oldbuys];onlyold=[k for k in oldbuys if k not in newbuys];qtychange=[dict(key=k,old_qty=oldbuys[k]['shares'],eta_qty=v['shares'])for k,v in newbuys.items()if k in oldbuys and v['shares']!=oldbuys[k]['shares']]
 assert changes and(onlynew or onlyold or qtychange),'No real priority/funding action demonstrated'
 # A mobile may fund after an unfunded CORE. It cannot jump a reservable CORE.
 for i,z in enumerate(r.funding):
  if z.get('result')!='reserved'or z['role']!='mobile':continue
  day=z['at'].date().isoformat();prev=max(d for d in same_day if d<day);pending=same_day[prev]['intents'];both=[q for q in pending if q['sid']==z['sid']and q['role']=='core']
  if both:assert any(x['sid']==z['sid']and x.get('role')=='core'and x['at']==z['at']and x['result']!='reserved'for x in r.funding[:i]);checks['core_before_mobile_contract']+=1
 assert all(sha(p)==h for p,h in sources.items());r.assert_native_wiring()
 result=dict(status='PASS_ORIGINAL_NATIVE_ETA_SINGLE_PRIORITY_PREFIX',prefix_end=CUT,original_closes=14,new_short_prefixes=1,new_full_accounts=0,selected_eta_manifest=str(manifest),selected_eta_manifest_sha256=selected,original_manifest_sha256=original_score_sha,source_sha256=sources,checks=dict(checks),profile_counts=dict(calls),priority_plan_exactly_once_per_CLOSE=True,original_native_methods_identical=True,physical_price_CP_industry_cutoff=CUT,eta_future_array_causality_audited_separately=True,score_query_max_day=max(query_days),old_baseline_prefix_receipt=str(oldgate),old_baseline_prefix_receipt_sha256=sha(oldgate),old_prefix_book_sha256=sha(oldbookpath),eta_trades=len(book['trades']),eta_ending_NAV=book['ending_NAV'],old_prefix_ending_NAV=oldbook['ending_NAV'],changed_priority_days=len(changes),changed_actual_buy_contracts=dict(eta_only=len(onlynew),original_only=len(onlyold),same_contract_different_quantity=len(qtychange)),examples=dict(priority=changes[:2],eta_only=onlynew[:4],original_only=onlyold[:4],quantity=qtychange[:4]),not_effectiveness_evidence=True)
 with RECEIPT.open('x')as f:json.dump(J.W.canon(result),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({k:result[k]for k in ['status','eta_trades','changed_priority_days','changed_actual_buy_contracts','new_full_accounts']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
