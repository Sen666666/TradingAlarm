"""Thin stock-day export of original qualified pending, not fills or features."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,hashlib,time
HERE=Path(__file__).resolve().parent;E=HERE.parents[1];ROOT=E/'trend_exit_controls_v1';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
if __name__=='__main__':
 begin=time.monotonic();target=HERE/'PRIMARY_CANDIDATES.jsonl';assert not target.exists();count=Counter();events=Counter();seen={};windows={}
 expected=read(HERE/'results_v1/UNIVERSE_COUNTS_AND_CLOCK_AUDIT.json')
 with target.open('x') as output:
  for win in ['2022_2024','strong']:
   pair=ROOT/'runs/BASELINE'/win/'pair';book=read(pair/'B.json.gz',gz=True);rank=read(pair/'rank-policy.jsonl.gz',gz=True,lines=True);intents={};decision_at={x['at'][:10]:x['at'] for x in book['decisions']};finalday=max(decision_at)
   for d in book['decisions']:
    for i in d['intents']:k=(d['at'][:10],i['sid']);intents.setdefault(k,{})[i['role']]=i
   reserved=set();filled=set()
   for j in book['journal']:
    if j['kind']=='real_reserve':reserved.add((j['budget_order'].split('|')[1][:10],j['sid'],j['role']))
    elif j['kind']=='real_buy_fill':filled.add((j['signal_at'][:10],j['sid'],j['role']))
   rr=Counter();previous=None
   for r in rank:
    day=r['day'];sid=r['sid'];assert r['account']=='B';assert previous is None or previous<=day;previous=day;ii=intents[day,sid];assert set(ii)==set(r['roles'])
    core=ii.get('core');mobile=ii.get('mobile');epoch=core.get('epoch') if core is not None else None;cp=mobile.get('CP1_id') if mobile is not None else None
    corekey=None if core is None or epoch is None else json.dumps([win,sid,'core',epoch],separators=(',',':'));mobilekey=None if mobile is None or cp is None else json.dumps([sid,'mobile',cp],separators=(',',':'))
    unknown=[]
    if core is not None and corekey is None:unknown.append('CORE_native_epoch_missing')
    if mobile is not None and mobilekey is None:unknown.append('mobile_canonical_CP_missing')
    q=dict(window=win,day=day,decision_at=decision_at[day],sid=sid,roles=r['roles'],original_PVR=r['PVR'],original_PVR_ready=r['PVR_ready'],original_H1_rank=r['original_H1_rank'],original_PVR_priority_rank=r['priority_rank'],original_H1_slot=r['original_slot'],original_PVR_slot=r['final_slot'],canonical_CP1_receipt_id=cp,native_CORE_watch_epoch=epoch,CORE_source_event_key=corekey,mobile_source_event_key=mobilekey,source_event_UNKNOWN_reasons=unknown,
     original_funding_diagnostic={role:dict(actual_reserved=(day,sid,role) in reserved,actual_filled=(day,sid,role) in filled,right_censored_no_next_OPEN=day==finalday) for role in r['roles']})
    for role,k in [('CORE',corekey),('mobile',mobilekey)]:
     if k is None:q[role+'_event_firstseen_in_PRIMARY']=None;q[role+'_event_firstseen_day_in_PRIMARY']=None
     else:
      first=k not in seen
      if first:seen[k]=day;events[win+'|'+role]+=1
      assert seen[k]<=day;q[role+'_event_firstseen_in_PRIMARY']=first;q[role+'_event_firstseen_day_in_PRIMARY']=seen[k]
    output.write(json.dumps(q,ensure_ascii=False,separators=(',',':'))+'\n');count[win]+=1;rr['stock_days']+=1;rr['role_rows']+=len(r['roles']);rr['PVR_UNKNOWN']+=not r['PVR_ready'];rr['source_event_UNKNOWN']+=bool(unknown)
   assert rr['stock_days']==expected[win]['pending_rank_stock_days'];assert rr['role_rows']==expected[win]['pending_intent_role_rows'];assert len(filled)==expected[win]['actual_fill_intent_keys'];windows[win]=dict(rr)
 assert sum(count.values())==133713
 SRC[str(Path(__file__).resolve())]=sha(__file__)
 save(HERE/'PRIMARY_CANDIDATES_MANIFEST.json',dict(status='PASS_133713_ORIGINAL_QUALIFIED_PENDING_STOCKDAYS',file=str(target.resolve()),file_sha256=sha(target),bytes=target.stat().st_size,windows=windows,total_stock_days=133713,total_actual_fills_parallel_only=3436,source_events_firstseen_counts=dict(events),new_accounts=0,numerical_feature_exports=0,elapsed_seconds=time.monotonic()-begin,
  unit='One original stock/decision CLOSE. Original same-stock core/mobile roles remain one stock-day; role event keys and funding diagnostics remain parallel.',
  causal_clock='All input candidate fields are original planning/rank state at decision CLOSE before nextOPEN route/reservation. Funding diagnostics are later outcomes only, never eligibility/feature input/filter.',
  source_event_basis='CORE key uses the original saved native watch epoch scoped by continuous baseline window; it is not a newly fabricated full-history I-canonical ID. Mobile key uses stock+original canonical CP receipt. Missing original IDs remain UNKNOWN, never inferred from later exits.',
  firstseen='Only chronological prefix of this PRIMARY file. CORE/mobile firstseen means first legal positive-size original pending occurrence in PRIMARY, not first full opportunity, source onset, actual fill, or future campaign. Same-stock two-role events are simultaneous and nonexclusive; no preferred role is chosen. Neither stock-days nor deduplicated events are independent trades.',
  funding='Diagnostic only. Actual reserve/fill booleans sourced from original journal keys; unfilled records all remain. Last native CLOSE without following OPEN is separately right-censored, not a financing failure.',
  feature_scope='Root-frozen existing8stock+industry context only; no run/flip/rawsigma/age axis or eta added.',source_sha256=SRC))
 print('PRIMARY_COMPLETE',sum(count.values()),dict(count),dict(events),round(time.monotonic()-begin,3))
