"""Original opportunity/fill joins plus timestamped MOBILE-sale memory. No account imports."""
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D
from collections import defaultdict, Counter
from bisect import bisect_left
import gzip,json,hashlib,math,csv
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return json.load(f)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,D):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def stamp(s):return datetime.fromisoformat(s).timestamp()
protocol=read(O/'PROTOCOL.json')
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
cache={}
def facts(sid):
 if sid not in cache:
  m=sm[sid];p=Path(m['refs']['facts']);h=sha(p);assert h==m['output_sha256'][str(p)];SRC[str(p)]=h
  f=pd.read_parquet(p,columns=['segment_id','e0_target','i_target','i_buy','g_grade','g_ready','g_acute_down'])
  on=f.e0_target.fillna(False).astype(bool);opening=on&~on.groupby(f.segment_id).shift(fill_value=False)
  z=pd.Series(None,index=f.index,dtype=object)
  for dt in f.index[opening]:z.loc[dt]=f'{sid}|{int(f.loc[dt,"segment_id"])}|{dt.date()}'
  f['stock_structure']=z.groupby(f.segment_id).ffill().where(on,None)
  cache[sid]=f
 return cache[sid]
def grade_and_root(sid,day):
 f=facts(sid);d=pd.Timestamp(day)
 if d not in f.index:return dict(grade=None,grade_ready=False,root=None,I_target=None,I_buy=None,acute_down=None,native_cold=None)
 x=f.loc[d];g=float(x.g_grade) if pd.notna(x.g_grade) else None;ready=bool(x.g_ready) and g is not None
 return dict(grade=g,grade_ready=ready,root=x.stock_structure if pd.notna(x.stock_structure) else None,
  I_target=int(x.i_target) if pd.notna(x.i_target) else None,I_buy=bool(x.i_buy) if pd.notna(x.i_buy) else None,
  acute_down=bool(x.g_acute_down) if pd.notna(x.g_acute_down) else None,
  native_cold=bool(g<=-2 or x.g_acute_down) if ready else None)

def aggregate_layers(rows):
 def total(k):return sum((D(str(x[k])) for x in rows),D(0))
 return dict(actual_fill_layers=len(rows),unique_signals=len({(x['sid'],x['decision_at'],x['receipt']) for x in rows}),
  stocks=len({x['sid'] for x in rows}),original_net_contribution=total('net'),
  original_positive_net=sum((D(x['net']) for x in rows if D(x['net'])>0),D(0)),
  original_negative_net=sum((D(x['net']) for x in rows if D(x['net'])<0),D(0)),
  strict_realized=total('strict_realized'),open_unrealized=total('open_unrealized'),
  recognized_dividend_AR=total('recognized_dividend_AR'),buy_fees=total('buy_fee'),sell_fees=total('sell_fee'),
  actual_buycash=total('cost'),closed_layers=sum(bool(x['closed']) for x in rows),
  still_open_layers=sum(not bool(x['closed']) for x in rows))

signals=[];filled=[];sale_sources=[];summaries={};validation={};taibao=[]
for ref in ['2022_2024','strong']:
 base=Q/'trend_exit_controls_v1/runs/BASELINE'/ref/'pair'
 b=read(base/'B.json.gz',True);old=read(Q/'structural_failure_v1/state_semantics'/(ref+'_ROWS.json'))
 first='2022-01-01' if ref=='2022_2024' else '2026-01-01';last='2024-12-31' if ref=='2022_2024' else '2026-06-30'
 all_m=[x for x in old if x['role']=='mobile'];md=b['metadata'];history=defaultdict(list);root_history=defaultdict(list)
 for ti,t in enumerate(b['trades']):
  if t['side']!='sell':continue
  parts=[p for p in t.get('parts',[]) if p['kind']=='add' and p['shares']>0]
  if not parts:continue
  roots=sorted({md[str(p['layer'])].get('stock_structure') for p in parts if md[str(p['layer'])].get('stock_structure')})
  e=dict(window=ref,book_trade_index=ti,at=t['at'],timestamp=stamp(t['at']),sid=t['security_id'],receipt_id=t['receipt_id'],
   MOBILE_parts=[dict(p,stock_structure=md[str(p['layer'])].get('stock_structure')) for p in parts],
   MOBILE_stock_structures=roots,raw_receipt=t)
  history[t['security_id']].append(e)
  for root in roots:root_history[(t['security_id'],root)].append(e)
  sale_sources.append(e)
 for h in list(history.values())+list(root_history.values()):h.sort(key=lambda x:x['timestamp'])
 def memory(sid,root,at):
  ts=stamp(at);h=history.get(sid,[]);sh=root_history.get((sid,root),[]) if root else []
  j=bisect_left([e['timestamp'] for e in h],ts);k=bisect_left([e['timestamp'] for e in sh],ts)
  return dict(prior_any_mobile_sale=bool(j),prior_same_root_mobile_sale=bool(k) if root else None,
   last_prior_any_sale=h[j-1] if j else None,last_prior_same_root_sale=sh[k-1] if k else None,
   same_timestamp_any_sale_count=sum(e['timestamp']==ts for e in h))
 def gate(mem,g):
  if mem is None:return 'UNKNOWN_IDENTITY'
  if not mem:return 'NO_PRIOR_SALE_NO_ADDED_GATE'
  if not g['grade_ready']:return 'UNKNOWN_G1'
  return 'PASS_G1_GE2' if g['grade']>=2 else 'FAIL_G1_LT2'
 clocks={d['at'][:10]:d['at'] for d in b['decisions']};days=list(clocks);prev={days[i]:days[i-1] for i in range(1,len(days))}
 intents={}
 for d in b['decisions']:
  for i in d['intents']:
   if i['role']=='mobile':intents[(i['sid'],d['at'][:10],i['CP1_id'])]=i
 fund=defaultdict(list);close_size=defaultdict(list)
 p=base/'funding.jsonl.gz';SRC[str(p.resolve())]=sha(p)
 with gzip.open(p,'rt') as f:
  for fi,line in enumerate(f):
   x=json.loads(line)
   if x.get('role')!='mobile':continue
   day=x['at'][:10]
   if '09:30:00' in x['at'] and day in prev:fund[(x['sid'],prev[day])].append(dict(original_funding_index=fi,raw=x))
   elif '15:10:00' in x['at']:close_size[(x['sid'],day)].append(dict(original_funding_index=fi,raw=x))
 fill_keys=defaultdict(list)
 for x in all_m:fill_keys[(x['sid'],x['decision_at'][:10],x['receipt'])].append(x)
 signal_map={}
 p=base/'opportunities.jsonl.gz';SRC[str(p.resolve())]=sha(p)
 with gzip.open(p,'rt') as f:
  for oi,line in enumerate(f):
   # Skip null CP rows before decoding; exact standard JSON used by the saved book.
   if '"CP1_id": null' in line:continue
   a=json.loads(line)
   if not a.get('CP1_id') or a.get('mobile_Q') is not True:continue
   assert 'mobile' in a['roles']
   sid=a['sid'];day=a['day'];at=clocks[day];g=grade_and_root(sid,day);mem=memory(sid,g['root'],at)
   key=(sid,day,a['CP1_id']);fl=fill_keys.get(key,[]);fu=fund.get((sid,day),[]);reserved=any(x['raw']['result']=='reserved' for x in fu)
   status='ACTUAL_FILL' if fl else 'RESERVED_NO_SAVED_FILL' if reserved else 'ORIGINAL_OPEN_REJECTED' if fu else 'NO_SAVED_OPEN_REQUEST'
   row=dict(window=ref,decision_at=at,decision_day=day,sid=sid,sector=a['sector'],CP1_id=a['CP1_id'],
    original_opportunity_index=oi,original_opportunity=a,grade=g['grade'],G1_ready=g['grade_ready'],
    below2_not_warm=bool(g['grade']<2) if g['grade_ready'] else None,native_cold=g['native_cold'],acute_down=g['acute_down'],
    I_target=g['I_target'],I_buy=g['I_buy'],stock_structure=g['root'],
    prior_any_mobile_sale=mem['prior_any_mobile_sale'],prior_same_root_mobile_sale=mem['prior_same_root_mobile_sale'],
    last_prior_any_sale=mem['last_prior_any_sale'],last_prior_same_root_sale=mem['last_prior_same_root_sale'],
    same_timestamp_any_sale_count=mem['same_timestamp_any_sale_count'],
    main_gate=gate(mem['prior_any_mobile_sale'],g),same_root_gate=gate(mem['prior_same_root_mobile_sale'],g),
    original_barrier_free=not a['barriers'],original_generated_MOBILE_intent=key in intents,
    original_intent=intents.get(key),original_close_sizing_result=close_size.get((sid,day),[]),
    original_OPEN_records=fu,original_funding_status=status,
    actual_fill_layers=[x['layer'] for x in fl],original_filled_contribution=aggregate_layers(fl),
    in_requested_signal_window=first<=day<=last,
    main_newly_blocked_original_intent=key in intents and gate(mem['prior_any_mobile_sale'],g)=='FAIL_G1_LT2',
    same_root_newly_blocked_original_intent=key in intents and gate(mem['prior_same_root_mobile_sale'],g)=='FAIL_G1_LT2')
   signals.append(row);signal_map[key]=row
   if ref=='2022_2024' and sid=='601601.SH' and day=='2024-09-18':taibao.append(row)
 mismatches=[];root_mismatches=[]
 for x in all_m:
  g=grade_and_root(x['sid'],x['decision_at'][:10]);root=md[str(x['layer'])].get('stock_structure')
  if root!=g['root']:root_mismatches.append(x['layer'])
  if g['grade']!=x['original_stock_state']['g_grade'] or g['grade_ready']!=bool(x['original_stock_state']['g_ready']):mismatches.append(x['layer'])
  assert root==g['root'] and not mismatches
  mem=memory(x['sid'],root,x['decision_at']);key=(x['sid'],x['decision_at'][:10],x['receipt']);s=signal_map[key]
  assert s['original_generated_MOBILE_intent']
  out={k:x[k] for k in ['layer','sid','name','industry','sector','role','pool_at_fill','decision_at','opened','closed','qty','cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','remaining_basis','receipt','action']}
  out.update(window=ref,grade=g['grade'],G1_ready=g['grade_ready'],native_cold=g['native_cold'],stock_structure=root,
   prior_any_mobile_sale=mem['prior_any_mobile_sale'],prior_same_root_mobile_sale=mem['prior_same_root_mobile_sale'],
   last_prior_any_sale=mem['last_prior_any_sale'],last_prior_same_root_sale=mem['last_prior_same_root_sale'],
   same_timestamp_any_sale_count=mem['same_timestamp_any_sale_count'],
   main_gate=gate(mem['prior_any_mobile_sale'],g),same_root_gate=gate(mem['prior_same_root_mobile_sale'],g),
   in_requested_fill_window=first<=x['opened'][:10]<=last,
   in_requested_signal_window=first<=x['decision_at'][:10]<=last)
  filled.append(out)
 rf=[x for x in filled if x['window']==ref and x['in_requested_fill_window']]
 rs=[x for x in signals if x['window']==ref and x['in_requested_signal_window']]
 def signal_agg(ss,mode):
  selected=[x for x in ss if x[mode]=='FAIL_G1_LT2'];generated=[x for x in selected if x['original_generated_MOBILE_intent']]
  return dict(qualified_CP_continuing_opportunities=len(ss),G1_lt2_not_warm_opportunities=sum(x['below2_not_warm'] is True for x in ss),
   memory_and_G1_lt2_opportunities=len(selected),originally_barrier_blocked_opportunities=sum(not x['original_barrier_free'] for x in selected),
   barrier_free_opportunities=sum(x['original_barrier_free'] for x in selected),
   newly_blocked_original_generated_intents=len(generated),
   of_newly_blocked_original_funding_status=dict(Counter(x['original_funding_status'] for x in generated)),
   original_OPEN_result_counts=dict(Counter(y['raw']['result'] for x in generated for y in x['original_OPEN_records'])),
   unknown_grade_or_identity=sum(x[mode].startswith('UNKNOWN') for x in ss))
 summaries[ref]=dict(signal_window=[first,last],fill_window=[first,last],
  original_fill_cohort=aggregate_layers(rf),all_G1_lt2_original_fills=aggregate_layers([x for x in rf if x['grade']<2]),
  main_any_prior_sale=dict(signals=signal_agg(rs,'main_gate'),actual_fills=aggregate_layers([x for x in rf if x['main_gate']=='FAIL_G1_LT2'])),
  appendix_same_root=dict(signals=signal_agg(rs,'same_root_gate'),actual_fills=aggregate_layers([x for x in rf if x['same_root_gate']=='FAIL_G1_LT2'])),
  fill_window_signal_outside_window_layers=[x['layer'] for x in rf if not x['in_requested_signal_window']],
  actual_same_session_prior_sell_then_decision_affected_layers=[x['layer'] for x in rf if x['main_gate']=='FAIL_G1_LT2' and x['last_prior_any_sale']['at'][:10]==x['decision_at'][:10]])
 validation[ref]=dict(actual_mobile_fill_count=len(all_m),decision_grade_exact_to_existing_rows=True,root_exact_to_original_metadata=True,
  root_mismatches=root_mismatches,grade_mismatches=mismatches,all_original_MOBILE_fills_have_generated_intent=True,
  memory_history_book_start=min(clocks),memory_history_not_cut_to_reporting_window=True)
 print('WINDOW_COMPLETE',ref,clean(summaries[ref]),flush=True)

semi=[x for x in signals if x['window']=='strong' and x['in_requested_signal_window'] and x['sector']=='URFI881121']
save('ORIGINAL_QUALIFIED_SIGNALS.json',signals)
save('ORIGINAL_MOBILE_FILLS_WITH_MEMORY.json',filled)
save('ORIGINAL_MOBILE_SALE_RECEIPTS.json',sale_sources)
save('SUMMARY.json',summaries);save('TAIBAO_SEP18_SCOPE_CORRECTION.json',taibao)
save('2026H1_SEMICONDUCTOR_QUALIFIED_SIGNALS.json',semi)
save('2026H1_SEMICONDUCTOR_GATE_SUMMARY.json',dict(qualified_signals=len(semi),
 G1_lt2_not_warm_signals=sum(x['below2_not_warm'] is True for x in semi),
 main_newly_blocked_generated_intents=[x for x in semi if x['main_newly_blocked_original_intent']],
 same_root_newly_blocked_generated_intents=[x for x in semi if x['same_root_newly_blocked_original_intent']],
 main_memory_G1_lt2_opportunities=[x for x in semi if x['main_gate']=='FAIL_G1_LT2'],
 actual_fill_layers=[x['layer'] for x in filled if x['window']=='strong' and x['in_requested_fill_window'] and x['sector']=='URFI881121'],
 actual_fill_blocked_layers=[x for x in filled if x['window']=='strong' and x['in_requested_fill_window'] and x['sector']=='URFI881121' and x['main_gate']=='FAIL_G1_LT2']))
save('SOURCE_AND_VALIDATION.json',dict(status='ORIGINAL_PATH_STATIC_MEMORY_SCREEN_NO_ECONOMIC_VALIDATION',
 source_sha256=SRC,script_sha256=sha(__file__),validation=validation,
 identity_reconstruction='Exact original J190-194 E0 root lookup; verified all actual MOBILE metadata roots. No reset at I toggle.',
 left_boundary='Each original account starts fresh; no prior account trades invented. strong memory retains2025H2; no mixing with2022-24 account.',
 new_accounts=0,new_backtests=0,new_strategy_paths=0,strategy_changes=0))
print('SEMICONDUCTOR',len(semi),sum(x['below2_not_warm'] is True for x in semi),sum(x['main_newly_blocked_original_intent'] for x in semi),flush=True)
