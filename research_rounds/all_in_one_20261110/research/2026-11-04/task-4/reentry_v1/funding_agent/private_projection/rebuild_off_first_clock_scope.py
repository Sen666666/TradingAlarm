"""13 complete original OPEN private OFFs. No Runner, Account, ON, or fills."""
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy,gzip,hashlib,inspect,json,sys,textwrap,time,traceback
import numpy as np,pandas as pd
OUT=Path(__file__).resolve().parent;FUND=OUT.parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
sys.path.insert(0,str(BASE));import component as P
J=P.J;LR=J.LR
def read(p):return json.loads(Path(p).read_text())
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def exact(a,b,name):
 if P.digest(a)!=P.digest(b):
  save('FIRST_DIFFERENCE.json',dict(name=name,actual=a,expected=b));raise AssertionError(name)
def eff(xs,day):return next(x for x in reversed(xs)if x['from']<=day and(x.get('to')is None or day<x['to']))
def hydrate(v):
 return P.State(cash=v['cash'],receivables=v['receivables'],lots=[P.MOD.Lot(**x)for x in v['lots']],
  orders={k:P.MOD.Order(**x)for k,x in v['orders'].items()},sectors={k:P.MOD.Sector(**x)for k,x in v['sectors'].items()},prices=v['prices'],
  consumed=v['consumed'],stock_requests=v['stock_requests'],sector_by_sid=v['sector_by_sid'],decision_nav=D(v['decision_nav']),pending_sells=v['pending_sells'],
  available_exact=D(v['available_exact']),historical_shared_loss=v['historical_shared_loss'],core_epoch={k:tuple(x)for k,x in v['core_epoch'].items()},remove_confirmed60=True)
def main():
 prep=time.monotonic();sources={str(Path(__file__)):sha(__file__)}
 s0path=FUND/'PREOPEN_EXACT_STATE.json';prepath=FUND/'PRE_CANDIDATE_EXACT_STATE.json'
 s0={k[:10]:v for k,v in read(s0path).items()};native_pre={(z['at'][:10],z['intent']['sid'],z['intent']['role']):z for z in read(prepath)}
 rows=read(FUND/'ALL16_RECEIPTS_WITH_REAL_RESOURCES.json');signals=sorted({z['signal_day']for z in rows if z['exact_open_responsibility']})
 opens={z['signal_day']:z['next_open']for z in rows if z['exact_open_responsibility']}
 root=BASE/'runs/2025_26/pair'
 with gzip.open(root/'B.json.gz','rt')as f:book=json.load(f)
 with gzip.open(root/'funding.jsonl.gz','rt')as f:funding=list(map(json.loads,f))
 decisions=[x for x in book['decisions']if x['at'][:10]in signals]
 assert len(decisions)==13 and sum(len(x['intents'])for x in decisions)==4172
 smpath=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');sm={x['symbol']:x for x in read(smpath)}
 market=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared');mpath=market/'manifest.json';mr={x['series_id']:x for x in read(mpath)['series']}
 rpath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=read(rpath)
 for p in [s0path,prepath,root/'B.json.gz',root/'funding.jsonl.gz',smpath,mpath,rpath,BASE/'component.py',P.W/'probe-batch-local-preview-20261101/planner.py']:sources[str(p)]=sha(p)
 for p,h in read(BASE/'runs/2025_26/RUN_METADATA.json')['source_freeze'].items():assert sha(p)==h;sources[p]=h
 cache={};batches={};missing=[]
 for dec in decisions:
  signal=dec['at'][:10];opening=opens[signal];at=J.M.N.iso(opening+'T09:30:00+08:00');clock=LR.A.Clock(J.M.N.iso(dec['at'].replace(' ','T')),at,pd.Timestamp(signal).date());intents=[]
  for original in dec['intents']:
   assert time.monotonic()-prep<90,'read-only preparation exceeded90seconds'
   sid=original['sid']
   if sid not in cache:
    fp=Path(sm[sid]['refs']['facts']);rp=Path(mr[sid]['raw']['path']);cp=Path(sm[sid]['refs']['receipts'])
    expected=sm[sid]['output_sha256'].get(str(fp));assert expected is not None and sha(fp)==expected,('facts source SHA',sid)
    assert sha(rp)==mr[sid]['raw']['sha256'];assert sha(cp)==sm[sid]['output_sha256'][str(cp)]
    for p in [fp,rp,cp]:sources[str(p)]=sha(p)
    f=pd.read_parquet(fp,columns=['factor']);raw=pd.read_parquet(rp,columns=['trade_date','open']);raw.index=pd.to_datetime(raw.trade_date)
    cache[sid]=(f,raw,{x['receipt_id']:x for x in read(cp)})
   f,raw,receipts=cache[sid];day=pd.Timestamp(opening);i=copy.deepcopy(original)
   for k in ['budget','floor','risk_budget']:
    if k in i:i[k]=D(i[k])
   i['epoch']=tuple(i['epoch'])if i['epoch']is not None else None;i['clock']=clock;i['quote']=NS(par_value=D(rules['security_metadata'][sid]['par_value']))
   i['CP1_trace']=receipts[i['CP1_id']]if i['role']=='mobile'else None
   if i['role']=='mobile':assert i['CP1_trace']['confirmed_day']==signal
   if day not in raw.index or not np.isfinite(raw.loc[day,'open'])or raw.loc[day,'open']<=0:x,why=None,'missing_open'
   else:
    factor=D(str(f.iloc[f.index.searchsorted(day,side='right')-1].factor));qr=eff(rules['quantity_versions'][sid],opening)['rule'];rule=LR.L.QuantityRule(**qr)
    venue=eff(rules['venue_versions'][sid],opening)['venue'];fs=eff(rules['fee_versions'][venue],opening)['schedule'];fee=LR.L.FeeSchedule(fs['schedule_id'],tuple(LR.L.FeeComponent(**c)for c in fs['components']))
    x,why=LR.preview(i,D(str(raw.loc[day,'open'])),factor,rule,fee)
    if x:x['known_open']=D(str(raw.loc[day,'open']))
   i['_preview']=x;i['_preview_failure']=why;intents.append(i)
  state=hydrate(s0[opening]['state']);exact(state.view(),s0[opening]['state'],'rehydrate exact S0 '+opening);batches[opening]=(state,intents,at)
 assert len(cache)==1213 and LR.SLIP==D('.0005')
 save('INPUT_SOURCES_SHA256.json',sources);save('PREPARATION.json',dict(passed=True,seconds=time.monotonic()-prep,OPENs=13,intents=4172,stocks=1213,Runner_constructed=False,Account_constructed=False,new_restores=0,new_financial_events=0,ON_started=False))
 print('PREPARED',round(time.monotonic()-prep,3),flush=True)
 computed=time.monotonic();checks=[];target_checks=[]
 fields=['cash','available_exact','receivables','nav','lots','orders','sectors','prices','consumed','stock_requests','decision_nav','pending_sells','historical_shared_loss','core_epoch']
 def observe_pre(a,i,at):
  assert time.monotonic()-computed<180,'entire private OFF+ON compute budget exhausted'
  k=(str(at.date()),i['sid'],i['role']);original=native_pre.get(k)
  if original is None:return
  v=a.budget.view();v['available_exact']=a.available
  for field in fields:exact(v[field],original['state'][field],'native pre-candidate '+str(k)+' '+field)
  exact(P.B.intent_view(i)['preview'],original['intent']['preview'],'native LR preview '+str(k))
  target_checks.append(dict(opening=k[0],sid=k[1],role=k[2],all_budget_read_fields_exact=True,preview_price_floor_rule_schedule_min_max_exact=True))
 src=textwrap.dedent(inspect.getsource(P.plan));needle="        b.context=key;b.phase='evaluation';pre=copy.deepcopy(b);pre_available=a.available"
 assert src.count(needle)==1
 derived=src.replace(needle,needle+'\n        observe_pre(a,i,at)');assert derived.replace('\n        observe_pre(a,i,at)','')==src
 (OUT/'original_plan_readonly_observer.py').write_text(derived);env=dict(P.__dict__,observe_pre=observe_pre);exec(compile(derived,str(OUT/'original_plan_readonly_observer.py'),'exec'),env)
 for opening,(state,intents,at)in sorted(batches.items()):
  begin=time.monotonic();result=env['plan'](state,intents,at,True)
  expected=[{k:v for k,v in x.items()if k not in ['account','at']}for x in funding if x['at'][:10]==opening]
  actual=J.W.canon([x for x in result['attempts']if not x.get('skip')]);exact(actual,expected,'whole original funding sequence '+opening)
  for order in result['orders']:
   reserve=next(x for x in book['audit']if x['kind']=='reserve'and x['at'][:10]==opening and x['sid']==order['sid'])
   exact(str(order['gross']),reserve['gross_budget_cny'],'gross '+order['key']);exact(str(order['fee']),reserve['fee_reserved_cny'],'fee '+order['key'])
  summary=dict(opening=opening,passed=True,intents=len(intents),source_input_sha256=result['input_sha256'],full_funding_records=len(expected),orders=len(result['orders']),
   full_pool_quantity_fee_rejection_sequence_exact=True,inputs_unchanged=result['inputs_unchanged'],seconds=time.monotonic()-begin,cumulative_compute_seconds=time.monotonic()-computed)
  checks.append(summary);save('OFF_'+opening+'.json',{k:v for k,v in result.items()if k!='final_state'});save('PREVIEWS_'+opening+'.json',[P.B.intent_view(i)for i in intents])
  save('OFF_IDENTITY.json',dict(passed=len(checks)==13,completed_OPENs=len(checks),checks=checks,target_prechecks=target_checks,compute_seconds=time.monotonic()-computed,compute_budget_seconds=180,ON_started=False))
  print('OFF EXACT',opening,len(intents),len(result['orders']),round(time.monotonic()-computed,3),flush=True)
 assert len(target_checks)==15 and all(sha(p)==h for p,h in sources.items())
 save('COMPLETION.json',dict(passed=True,OPENs=13,intents=4172,stocks=1213,native_pre_target_checks=15,source_unchanged=True,ON_started=False,
  compute_seconds=time.monotonic()-computed,remaining_OFF_ON_budget_seconds=180-(time.monotonic()-computed),source_preparation_seconds=time.monotonic()-prep-(time.monotonic()-computed),new_accounts=0,new_restores=0,new_financial_events=0,independent_OFF_review_required_before_ON=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:save('FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),ON_started=False,new_accounts=0,new_restores=0));raise
