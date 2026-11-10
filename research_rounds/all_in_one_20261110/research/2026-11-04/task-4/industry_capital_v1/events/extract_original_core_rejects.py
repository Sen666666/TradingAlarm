"""Original CORE sector-gate event extraction only. No marks or Account.
Phase one saves the complete native-log mother before any enrichment.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,gzip,hashlib,json,time
O=Path(__file__).resolve().parent;W=O.parents[1]
BOOKS=W/'new_price_trend_v1/funding/runs'
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stream(p):
 with gzip.open(p,'rt')as f:
  for line in f:yield json.loads(line)
def write_rows(n,rows):
 with gzip.open(O/n,'wt')as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,default=str)+'\n')
def category(tags):
 sector=tags&{'sector_capital','sector_risk'};other=tags-sector
 if not other:return 'sector_capital_only'if sector=={'sector_capital'}else'sector_risk_only'if sector=={'sector_risk'}else'both_sector_only'
 return ('both_sector'if len(sector)==2 else next(iter(sector)))+'_plus_other_gates'
def mother():
 start=time.monotonic();rows=[];counts=defaultdict(Counter);sources={};progress=[]
 opens={(r['window'],r['OPEN']):r['signal_day']for r in json.loads((W/'cash_release_v1/ALL_MARKET_OPEN_LIQUIDITY_STOCKS.json').read_text())}
 for window in ['long','strong']:
  p=BOOKS/(window+'_OFF')/'pair/funding.jsonl.gz';sources[str(p)]=sha(p)
  for number,r in enumerate(stream(p)):
   if number%1000==0 and time.monotonic()-start>90:
    write_rows('CORE_SECTOR_REJECT_MOTHER.partial.jsonl.gz',rows);save('MOTHER_STATUS.json',dict(complete=False,seconds=time.monotonic()-start,window=window,index=number,events_saved=len(rows),limit_seconds=100));return
   if r['role']!='core' or '09:30:00'not in r['at']:continue
   counts[window]['CORE_OPEN_funding_rows']+=1;counts[window]['CORE_OPEN_'+r['result']]+=1
   tags=set(r['result'].split(','))
   if not tags&{'sector_capital','sector_risk'}:continue
   signal=opens[window,r['at'][:10]];key='|'.join([window,signal,r['sid'],'core'])
   x=dict(key=key,window=window,signal_day=signal,OPEN=r['at'][:10],at=r['at'],sid=r['sid'],role='core',
          native_raw_result=r['result'],failure_tags=sorted(tags),classification=category(tags),raw_funding_row=r,
          funding_stream_index=number,first_unique_failure='NOT_INFERRED_FROM_MERGED_TAGS',
          qualification_and_original_size_pass='Source control-flow: intent reached native OPEN route after LR.preview',
          attempted_quantity_log='No quantity is emitted for rejected route; dated minimum is inferred diagnostic evaluation from unchanged source, not logged submitted size',
          route='CORE_probe_only_at_admission',new_account=False)
   rows.append(x);counts[window]['selected_sector_reject_events']+=1;counts[window][x['classification']]+=1
  progress.append(dict(window=window,complete=True,seconds=time.monotonic()-start,selected=sum(x['window']==window for x in rows)))
  save('MOTHER_PROGRESS.json',progress)
 assert len({r['key']for r in rows})==len(rows)
 write_rows('CORE_SECTOR_REJECT_MOTHER.jsonl.gz',rows)
 save('CORE_SECTOR_REJECT_MOTHER_SUMMARY.json',dict(complete=True,events=len(rows),counts={k:dict(v)for k,v in counts.items()},sources=sources,seconds=time.monotonic()-start,limit_seconds=100,new_accounts=0,new_quotes=0,new_market_marks=0,scope='Original actual OPEN route reject rows; multi-gate sets are not unique first cause; counts are dependent stock-days'))
 print('MOTHER_COMPLETE',len(rows),time.monotonic()-start,flush=True)
def bind():
 start=time.monotonic();rows=list(stream(O/'CORE_SECTOR_REJECT_MOTHER.jsonl.gz'));bywindow=defaultdict(list);snapshots={};sources={};counts=Counter()
 for x in rows:bywindow[x['window']].append(x)
 for window,events in bywindow.items():
  root=BOOKS/(window+'_OFF')/'pair';p=root/'B.json.gz';sources[str(p)]=sha(p)
  with gzip.open(p,'rt')as f:b=json.load(f)
  ds={r['at'][:10]:r for r in stream(root/'daily.jsonl.gz')};dec={r['at'][:10]:r for r in b['decisions']}
  wanted={(x['signal_day'],x['sid'])for x in events};ops={}
  for n,r in enumerate(stream(root/'opportunities.jsonl.gz')):
   if n%1000==0 and time.monotonic()-start>85:
    write_rows('CORE_SECTOR_REJECT_BINDING.partial.jsonl.gz',rows);save('BINDING_STATUS.json',dict(complete=False,seconds=time.monotonic()-start,window=window,index=n,limit_seconds=100));return
   if (r['day'],r['sid'])in wanted:ops[r['day'],r['sid']]=r
  fills={int(j['layer']):j for j in b['journal']if j['kind']=='real_buy_fill'}
  buys_today=defaultdict(set)
  for t in b['trades']:
   if t['side']=='buy':buys_today[t['at'][:10]].add(int(t['layer']))
  for x in events:
   signal,day,sid=x['signal_day'],x['OPEN'],x['sid'];op=ops[signal,sid];intents=[i for i in dec[signal]['intents']if i['sid']==sid and i['role']=='core'];assert len(intents)==1
   i=intents[0];assert op['core_Q']is True and op['held']is False and not op['barriers']and 'core'in op['roles']
   x.update(original_intent=i,original_opportunity=op,decision_NAV=dec[signal]['nav'],industry=op['sector'],snapshot_key='|'.join([window,signal,day,op['sector']]),
            requested_maximum_semantics='Frozen i.cap/i.budget are maxima; no rejected actual order quantity was reserved or logged')
   sk=x['snapshot_key']
   if sk not in snapshots:
    prev={int(z['id']):z for z in ds[signal]['layers']if z['sector']==op['sector']}
    surviving=[z for z in ds[day]['layers']if z['sector']==op['sector']and int(z['id'])not in buys_today[day]]
    old=[]
    for z in surviving:
     lid=int(z['id']);assert lid in prev,(window,day,lid,'unknown old layer')
     pz=prev[lid];j=fills[lid]
     old.append(dict(layer=lid,sid=z['sid'],role=z['role'],qty_after_original_actions_and_protection_exits=z['qty'],
       protection_adjusted_at_OPEN=pz['last_core_line']if z['kind']=='core'else pz['floor'],
       protection_source='previous CLOSE last_core_line for CORE, floor for MOBILE; native split leaves adjusted protection unchanged',
       unit_cost_raw_at_OPEN=z['unit_cost'],unit_cost_scope='Native gross cost per share; not fee-inclusive remaining economic cost',
       pool_at_previous_CLOSE=pz['pool'],pool_at_candidate='UNKNOWN_POSSIBLE_SAME_OPEN_MIGRATION',
       original_entry_fill=j,previous_CLOSE_raw_layer=pz,next_CLOSE_raw_layer=z))
    snapshots[sk]=dict(window=window,signal_day=signal,OPEN=day,sector=op['sector'],
       previous_CLOSE_same_sector_layers=list(prev.values()),surviving_existing_layers_at_S0=old,
       source_clock='S0 after original existing protection sales/actions, before all new admissions. Later pre-candidate reserves/migrations remain unknown.',
       CLOSE_account=dict((k,ds[signal][k])for k in ['available','order_reserved','nav','on','pool_probe','pool_confirmed','pending_sells']),
       exact_pre_candidate_sc_sr_nav='UNKNOWN_WITHOUT_EVENT_SNAPSHOT',
       industry_release_amount='UNKNOWN: total sector reject tag gives no numeric sc/sr or release amount; do not equate requested cap with releasable capacity')
   counts[window]+=1
  save('BINDING_PROGRESS.json',dict(window=window,events_bound=sum('original_intent'in x for x in rows),seconds=time.monotonic()-start))
 write_rows('CORE_SECTOR_REJECT_BOUND.jsonl.gz',rows);save('ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json',snapshots)
 save('CORE_BINDING_SUMMARY.json',dict(complete=True,events=len(rows),by_window=dict(counts),snapshots=len(snapshots),seconds=time.monotonic()-start,limit_seconds=100,new_accounts=0,new_market_marks=0,sources=sources))
 print('BIND_COMPLETE',len(rows),len(snapshots),time.monotonic()-start,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['mother','bind']);a=p.parse_args();mother()if a.phase=='mother'else bind()
