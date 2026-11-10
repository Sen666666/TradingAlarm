"""Read saved research records only. No account/strategy imports or financial runs."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import gzip,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent
E=O.parent/'equal_entry_validation_v1'
A=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/runs/BASELINE')
C=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
inputs={}
def sha(p):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();inputs[str(p)]=h;return h
def jread(p):
 sha(p);return json.loads(Path(p).read_text())
def jgz(p):
 sha(p);return json.load(gzip.open(p,'rt'))
def lines(p):
 sha(p)
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def write(name,v):
 (O/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str)+'\n')
selpath=E/'SEALED_SELECTIONS_BEFORE_LABELS.parquet'
sha(selpath);sel=pd.read_parquet(selpath)
seal=jread(E/'RANK_SEAL.json')
assert inputs[str(selpath)]==seal['selection_sha256']
all_summary=[];all_joins=[];all_timeline=[];all_state=[];native_top=[]
for win,day,nxt,lo,hi in [('2022_2024','2024-09-24','2024-09-25','2024-09-23','2024-10-08'),('strong','2026-01-15','2026-01-16','2026-01-14','2026-01-20')]:
 root=A/win;book=jgz(root/'pair/B.json.gz');meta=jread(root/'RUN_METADATA.json');fixed=set(meta['input_identity'].get('fixed_ids',meta['input_identity'].get('fixed_stock_ids')))
 checks=[dict(path=p,expected=h,current=sha(p),equal=sha(p)==h) for p,h in meta['source_freeze'].items()]
 assert all(r['equal'] for r in checks);write(win+'_SOURCE_FREEZE_CHECK.json',checks)
 daily=[r for r in lines(root/'pair/daily.jsonl.gz') if lo<=r['at'][:10]<=hi]
 dec=next(r for r in book['decisions'] if r.get('at','').startswith(day))
 before=next(r for r in daily if r['at'].startswith(day))
 after=next(r for r in daily if r['at'].startswith(nxt))
 ints=sorted(dec['intents'],key=lambda r:(r['rank'],r['role']!='core'))
 by={}
 for r in ints:by.setdefault(r['sid'],[]).append(r)
 order=list(by)
 ranks={r['sid']:r for r in lines(root/'pair/rank-policy.jsonl.gz') if r['day']==day}
 opp={r['sid']:r for r in lines(root/'pair/opportunities.jsonl.gz') if r['day']==day}
 funding=[r for r in lines(root/'pair/funding.jsonl.gz') if lo<=r['at'][:10]<=hi]
 tomorrowfund=[r for r in funding if r['at'].startswith(nxt+' 09:30:')]
 tomorrowtrades=[r for r in book['trades'] if r.get('at','').startswith(nxt+' 09:30:')]
 events=[dict(record_class=k,original_index=n,**r) for k in ['audit','journal','trades','decisions'] for n,r in enumerate(book[k]) if lo<=str(r.get('at',''))[:10]<=hi]
 write(day+'_ORIGINAL_WINDOW_EVENTS.json',events);write(day+'_ORIGINAL_WINDOW_DAILY.json',daily);write(day+'_ORIGINAL_WINDOW_FUNDING.json',funding)
 write(day+'_FROZEN_NATIVE_INTENTS.json',ints)
 selected=sel[sel.day.eq(day)].copy()
 summ=dict(day=day,next_open=nxt,native_before_snapshot_at=before['at'],native_after_snapshot_at=after['at'],window=win,native_fixed_pool=len(fixed),native_intent_roles=len(ints),native_intent_stocks=len(by),native_held_stocks=len(before['positions']),native_open_layers=len(before['layers']),native_layer_roles=dict(Counter(r.get('role',r.get('kind')) for r in before['layers'])),native_cash_before=before['available'],native_nav_before=before['nav'],native_cash_after=after['available'],native_nav_after=after['nav'],next_buy_fills=sum(r['side']=='buy' for r in tomorrowtrades),next_sell_fills=sum(r['side']=='sell' for r in tomorrowtrades),next_buy_gross=str(sum((D(r['gross_cny']) for r in tomorrowtrades if r['side']=='buy'),D(0))),next_buy_fees=str(sum((D(r['fees_cny']) for r in tomorrowtrades if r['side']=='buy'),D(0))),next_sell_net=str(sum((D(r['gross_cny'])-D(r['fees_cny']) for r in tomorrowtrades if r['side']=='sell'),D(0))),next_funding_results=dict(Counter(r['result'] for r in tomorrowfund)))
 for strategy,g in selected.groupby('strategy'):
  ids=set(g.sid);summ[strategy]=dict(selected=len(g),in_fixed_pool=len(ids&fixed),in_native_intents=len(ids&set(by)),already_held=len(ids&set(before['positions'])),next_native_buy_ids=sorted(ids&{r['security_id'] for r in tomorrowtrades if r['side']=='buy'}))
 for r in selected.to_dict('records'):
  sid=r['sid'];fund=[x for x in tomorrowfund if x['sid']==sid];tr=[x for x in tomorrowtrades if x['security_id']==sid];op=opp.get(sid,{})
  all_joins.append(dict(day=day,strategy=r['strategy'],rank=r['rank'],sid=sid,stratum=r['stratum'],canonical_pvr=r['pvr'],in_fixed_pool=sid in fixed,held_qty=before['positions'].get(sid,0),native_intent_roles=','.join(x['role'] for x in by.get(sid,[])),native_stock_priority=order.index(sid)+1 if sid in by else None,native_pvr=ranks.get(sid,{}).get('PVR'),native_core_Q=op.get('core_Q'),native_mobile_Q=op.get('mobile_Q'),native_barriers=json.dumps(op.get('barriers'),ensure_ascii=False),next_funding=json.dumps(fund,ensure_ascii=False),next_native_trades=json.dumps(tr,ensure_ascii=False)))
 for sid in order[:20]:
  native_top.append(dict(**ranks[sid],native_stock_priority=order.index(sid)+1,held_qty=before['positions'].get(sid,0),next_funding=[x for x in tomorrowfund if x['sid']==sid],next_trades=[x for x in tomorrowtrades if x['security_id']==sid]))
 for d in daily:
  all_state.append({k:v for k,v in d.items() if k not in ['positions','layers']}|dict(held_stocks=len(d['positions']),open_layers=len(d['layers']),roles=dict(Counter(x.get('role',x.get('kind')) for x in d['layers']))))
 for sid in sorted(set(selected.sid)):
  p=C/(sid+'.parquet');sha(p);f=pd.read_parquet(p,columns=['day','source_row_present','price__open','price__close','native__e0_ready','native__i_target','native__i_buy']);f['day']=f.day.dt.strftime('%Y-%m-%d')
  for r in f[f.day.between(lo,hi)].to_dict('records'):all_timeline.append(dict(sid=sid,target_day=day,**r))
 all_summary.append(summ)
write('SUMMARY.json',all_summary);write('NATIVE_TOP20_TWO_DATES.json',native_top)
pd.DataFrame(all_joins).to_csv(O/'FROZEN_E31_TO_NATIVE_JOIN.csv',index=False)
pd.DataFrame(all_state).to_csv(O/'ORIGINAL_DAILY_STATE.csv',index=False)
pd.DataFrame(all_timeline).to_csv(O/'FROZEN_SELECTED_KNOWLEDGE_PATH.csv',index=False)
write('INPUT_SHA256.json',inputs)
write('COMPLETION.json',dict(status='SAVED_ACCOUNT_PAPER_TRACE_NOT_NEW_PORTFOLIO_COMPARISON',account_runs=0,strategy_imports=0,parameter_searches=0,original_files_changed=0,selection_rows_joined=len(all_joins),source_hashes_checked=len(inputs)))
print(json.dumps(all_summary,ensure_ascii=False,indent=2))

