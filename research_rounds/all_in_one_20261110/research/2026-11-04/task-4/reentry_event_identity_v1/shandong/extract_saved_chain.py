"""Saved 601019 chain only: read parquet/JSON/book, never model/features/account."""
from pathlib import Path
from collections import defaultdict
import json,gzip,hashlib,math,csv
import pandas as pd

O=Path(__file__).resolve().parent;ROOT=O.parents[1];SID='601019.SH';START='2023-03-28';END='2023-05-09';SHA={}
def bind(p):
 p=Path(p);SHA[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
 if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return[clean(v)for v in x]
 if x is pd.NA or x is pd.NaT:return 'SOURCE_NULL'
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return 'SOURCE_NULL'
 if isinstance(x,pd.Timestamp):return str(x)
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def gz(p):
 with gzip.open(bind(p),'rt')as f:return json.load(f)
def rowat(frame,day):return frame.loc[pd.Timestamp(day)].to_dict()if pd.Timestamp(day)in frame.index else {'status':'NOT_SAVED'}

bind(__file__);seed=read(ROOT/'native_algorithm_read_v1/v_reversal_counterexample/SHANDONG_601019_EXACT_SAVED_WINDOW.json')
sm=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');rec=next(r for r in sm if r['symbol']==SID)
f=pd.read_parquet(bind(rec['refs']['facts']));cp=pd.read_parquet(bind(rec['refs']['CP1']))
ep=next(p for p in rec['source_sha256']if p.endswith('/events.parquet'));gp=next(p for p in rec['source_sha256']if '/ix-a-share-entry-'in p);sp=next(p for p in rec['source_sha256']if p.endswith('/signal.parquet'))
events=pd.read_parquet(bind(ep));g=pd.read_parquet(bind(gp));signal=pd.read_parquet(bind(sp))
for p,h in {**rec['source_sha256'],**rec['output_sha256']}.items():
 if str(Path(p).resolve())in SHA:assert SHA[str(Path(p).resolve())]==h
ym=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/recovery-2023-readiness-20261101/inputs/MANIFEST.json');yr=next(r for r in ym if r['sid']==SID);receipts=read(yr['output_path']);assert SHA[str(Path(yr['output_path']).resolve())]==yr['output_sha256'];rd={r['confirmed_day']:r for r in receipts}
pair=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';book=gz(pair/'B.json.gz')
trades=[t for t in book['trades']if t['security_id']==SID and '2023-03-20'<=t['at'][:10]<=END]
audit=[r for r in book['audit']if START<=r.get('at','')[:10]<=END and(r.get('sid')==SID or r.get('kind')=='risk_checkpoint')]
daily={};fund=defaultdict(list);ops=defaultdict(list)
for file,target in [('daily.jsonl.gz',daily),('funding.jsonl.gz',fund),('opportunities.jsonl.gz',ops)]:
 with gzip.open(bind(pair/file),'rt')as h:
  for line in h:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if day>END:break
   if file=='daily.jsonl.gz':
    if '2023-03-20'<=day:target[day]=r
   elif START<=day and r.get('sid')==SID:target[day].append(r)

def true_run(day,col):
 j=f.index.get_loc(pd.Timestamp(day));i=j
 while i>0 and f.iloc[i-1][col]==1 and f.iloc[i-1].segment_id==f.iloc[j].segment_id:i-=1
 return dict(start=str(f.index[i].date()),last_prior_day=str(f.index[i-1].date())if i else None,prior_value=clean(f.iloc[i-1][col])if i else'NOT_SAVED',source_segment=clean(f.iloc[j].segment_id),derivation='Lookup contiguous already-saved target=1 observations, not re-running a model.')
e0run=true_run(START,'e0_target');irun=true_run(START,'i_target');e0start=e0run['start'];assert e0run==true_run(END,'e0_target')and irun==true_run(END,'i_target')

def context_event(dt,row,day):
 pd0=row.confirmed_pivot_date;fact=rowat(f,str(pd0));return dict(confirmed_at=str(dt.date()),direction=row.event,pivot_at=str(pd0),pivot_adjusted=row.confirmed_pivot_price,pivot_raw_at_pivot_date=fact.get('raw_close','NOT_SAVED'),pivot_raw_in_today_units=row.confirmed_pivot_price/f.loc[day,'factor'],source='Original saved events confirmation row; historical pivot date is not its availability date.')

rows=[];flat=[]
for dt,z in f.loc[START:END].iterrows():
 day=str(dt.date());prev=max(d for d in daily if d<day);d=daily[day];pday=daily[prev];ex=rowat(events,day);gg=rowat(g,day);cc=rowat(cp,day)
 for a,b in [('g_grade','grade'),('g_fresh_up','fresh_up'),('g_ready','strength_ready')]:assert z[a]==gg[b],(day,a)
 evprior=events.loc[(events.index>=pd.Timestamp(e0start))&(events.index<dt)];evknown=events.loc[(events.index>=pd.Timestamp(e0start))&(events.index<=dt)]
 peaks=evprior.loc[evprior.event.eq(-1)];troughs=evknown.loc[evknown.event.eq(1)]
 lastpeak=context_event(peaks.index[-1],peaks.iloc[-1],day)if len(peaks)else'NOT_SAVED'
 highpeak=context_event(peaks.confirmed_pivot_price.idxmax(),peaks.loc[peaks.confirmed_pivot_price.idxmax()],day)if len(peaks)else'NOT_SAVED'
 lasttrough=context_event(troughs.index[-1],troughs.iloc[-1],day)if len(troughs)else'NOT_SAVED'
 pf=f.loc[(f.index>=pd.Timestamp(e0start))&(f.index<dt)];prior_max_day=pf.close.idxmax();core_pf=f.loc[(f.index>=pd.Timestamp('2023-03-21'))&(f.index<dt)];coremaxday=core_pf.close.idxmax()
 live=[x for x in d['layers']if x['sid']==SID];oldlive=[x for x in pday['layers']if x['sid']==SID]
 canonical=rd.get(day)
 if cc['receipt']:assert canonical is not None
 risk=next((r for r in audit if r.get('kind')=='risk_checkpoint'and r['at'][:10]==day),None)
 rr=dict(day=day,at=d['at'],actual_facts=z.to_dict(),original_signal=rowat(signal,day),original_event={k:ex.get(k,'NOT_SAVED')for k in['confirmation','leg_direction','event','pivot_age','confirmed_pivot_price','confirmed_pivot_date','developing_extreme_price','developing_extreme_date']},
  original_G1_only={k:gg.get(k,'NOT_SAVED')for k in['grade','proposal','phase','z5','z21','fresh_up','up_reasons','acute_up','acute_down','strength_ready','promotion_blocked']},original_CP=cc,canonical_CP_receipt=canonical if canonical else'NO_RECEIPT_THIS_DAY',
  actual_E0_entered='NOT_SAVED',actual_I_entered='NOT_SAVED',actual_I_exit_reason='NOT_SAVED',same_saved_E0_true_run=e0run,same_saved_I_true_run=irun,ACT_checkpoint=risk,
  last_confirmed_peak_known_before_today=lastpeak,highest_confirmed_peak_known_before_today_same_E0=highpeak,last_confirmed_trough_known_by_today_CLOSE=lasttrough,
  prior_observed_max_CLOSE_same_E0=dict(day=str(prior_max_day.date()),close_adjusted=pf.loc[prior_max_day,'close'],raw_at_that_day=pf.loc[prior_max_day,'raw_close'],current_unit_raw=pf.loc[prior_max_day,'close']/z.factor,derivation='Pure max lookup of saved CLOSEs strictly before today; not a confirmed turning-point label or new trading rule.'),
  prior_observed_max_CLOSE_since_original_CORE_entry=dict(day=str(coremaxday.date()),close_adjusted=core_pf.loc[coremaxday,'close'],current_unit_raw=core_pf.loc[coremaxday,'close']/z.factor),
  original_previous_CLOSE_stock_layers=oldlive,original_current_CLOSE_stock_layers=live,actual_qty_at_CLOSE=d['positions'].get(SID,0),original_trades=[t for t in trades if t['at'][:10]==day],original_proposals=[r for r in audit if r.get('kind')=='pilot_layer_exit'and r['at'][:10]==day],original_opportunities=ops[day],original_funding=fund[day])
 rows.append(rr)
 flat.append(dict(day=day,raw_close=z.raw_close,close_adjusted=z.close,factor=z.factor,E0=z.e0_target,I=z.i_target,I_floor_adjusted=z.i_floor,i_buy=z.i_buy,G1=z.g_grade,G1_fresh=z.g_fresh_up,CP_receipt=cc['receipt'],CP_candidate_adjusted=cc['candidate'],event=ex['event'],pivot_at=ex['confirmed_pivot_date'],pivot_adjusted=ex['confirmed_pivot_price'],running_extreme_at=ex['developing_extreme_date'],running_extreme_adjusted=ex['developing_extreme_price'],prior_peak_confirmed_at=lastpeak.get('confirmed_at')if isinstance(lastpeak,dict)else'NOT_SAVED',prior_peak_pivot_at=lastpeak.get('pivot_at')if isinstance(lastpeak,dict)else'NOT_SAVED',prior_peak_raw_in_today_units=lastpeak.get('pivot_raw_in_today_units')if isinstance(lastpeak,dict)else'NOT_SAVED',prior_max_CLOSE_since_CORE_raw=core_pf.loc[coremaxday,'close']/z.factor,qty_at_CLOSE=d['positions'].get(SID,0),live_layer_ids=','.join(str(x['id'])for x in live),funding_results=';'.join(r['at'][11:16]+':'+r['result']for r in fund[day])))

save('ALL_SAVED_DAILY_CHAIN.json',rows)
with (O/'DAILY_CHAIN.csv').open('w',newline='')as h:
 w=csv.DictWriter(h,fieldnames=list(flat[0]));w.writeheader();w.writerows(clean(flat))
all_e0_ids=sorted({r['original_E0_episode_id']for r in receipts if START<=r['confirmed_day']<=END})
ids=dict(stock_saved_E0_true_run=e0run,stock_saved_I_true_run=irun,canonical_stock_original_E0_episode_ids=all_e0_ids,original_layer_epoch_values=sorted({str(x['epoch'])for r in rows for x in r['original_current_CLOSE_stock_layers']}),saved_stock_structure_values=sorted({x.get('stock_structure','NOT_SAVED')for r in rows for x in r['original_current_CLOSE_stock_layers']}),ACT_episode_values=sorted({r['ACT_checkpoint']['episode']for r in rows if r['ACT_checkpoint']}),industry_budget_episode_values=sorted({x.get('episode','NOT_SAVED')for r in rows for x in r['original_current_CLOSE_stock_layers']}),warning='Stock E0 identity, saved I/source runner counter, account ACT episode and industry budget episode are separate. Same[0,5] alone does not prove same E0.',known_source_I_vs_legacy_IX='Only selected G1 fields crosschecked; legacy ix_target/entered/exit_reason never used as currentI.')
save('EVENT_IDENTITIES.json',ids);save('ORIGINAL_STOCK_TRADES_AND_PROPOSALS.json',dict(trades=trades,proposals=[r for r in audit if r.get('kind')=='pilot_layer_exit'],focus_closed_layer_snapshots=[x for x in book['layers']if x['id']in[1161,1183,1230,1267,1283]],metadata={k:v for k,v in book['metadata'].items()if int(k)in[1148,1161,1183,1230,1267,1283]}))
save('SOURCE_SHA256.json',SHA);save('SCOPE.json',dict(status='SAVED_JSON_PARQUET_BOOK_EXTRACTION_ONLY',dates=[START,END],daily_rows=len(rows),new_model_or_features_or_calculate_calls=0,new_account_or_strategy_or_backtest=0,missing_fields_filled=0,derived_context='Only target-run boundaries, and strictly past lookup/max of saved closes or already-confirmed original event pivots; no new signal or future profit labels.'))
for r in flat:
 if r['day']in['2023-04-06','2023-04-10','2023-04-11','2023-04-12','2023-04-13','2023-04-14','2023-05-08','2023-05-09']:print(r)
print('IDENTITIES',json.dumps(clean(ids),ensure_ascii=False))
