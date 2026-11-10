from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import json,csv,hashlib,statistics
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=ROOT/'mainline_seed_entry_diagnostic_v1';R=ROOT/'mainline_m7_cash_batch_design_v6/once_20260630';X=ROOT/'mainline_m7_extended_capture_diagnostic_v1'
def rd(p):return json.loads(p.read_text())
def save(n,x):
 (O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/(n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
hashes={};s=rd(R/'SECTOR_DAILY.json');sd={(x['day'],x['sector51']):x for x in s};days=sorted(set(x['day'] for x in s));prev={d:days[i-1] if i else None for i,d in enumerate(days)}
filled=rd(O/'FILLED_SEED_CLASSIFICATION.json');requests=rd(O/'REQUEST_CLASSIFICATION.json')
def mature_gate(day,sec,phase):
 if phase!='MATURE':return 'PASS_NOT_MATURE'
 old=sd.get((prev[day],sec),{}).get('M',-1);now=sd[(day,sec)]['M']
 return 'PASS' if now==old==1 else 'UNKNOWN' if -1 in [old,now] else 'BLOCK_NOT_TWO_ADJACENT_M_CLOSES'
for r in filled:r['M2D']=mature_gate(r['plan_day'],r['sector51'],r['phase'])
for r in requests:r['M2D']=mature_gate(r['day'],r['sector51'],r['allocation_phase'])
def sm(a):
 return dict(n=len(a),net=sum((D(x['net']) for x in a),D(0)),gross_losses=-sum((min(D(0),D(x['net'])) for x in a),D(0)),gross_gains=sum((max(D(0),D(x['net'])) for x in a),D(0)),closed=sum(not x['final_qty'] for x in a),open=sum(bool(x['final_qty']) for x in a),seed_cost=sum((D(x['seed_cost']) for x in a),D(0)))
m2sum=[]
for name,rs in [('all',filled),('new_since_1106',[x for x in filled if x['seed_day']>'2024-11-06']),('startup_actual_open_0923_0930',[x for x in filled if '2024-09-23'<=x['seed_day']<='2024-09-30'])]:
 for status in ['ALL','BLOCK','PASS','UNKNOWN']:
  a=[r for r in rs if status=='ALL' or r['M2D'].startswith(status)];m2sum.append(dict(period=name,status=status,**sm(a)))
startup=[]
for d in ['2024-09-23','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30']:
 for phase in ['EVENT','RESIDUAL','MATURE']:
  a=[r for r in filled if r['seed_day']==d and r['phase']==phase];b=[r for r in a if r['M2D'].startswith('BLOCK')]
  startup.append(dict(actual_open=d,phase=phase,all_n=len(a),blocked_n=len(b),blocked_cost=sum((D(x['seed_cost']) for x in b),D(0)),blocked_names=[x['name'] for x in b],plan_closes=sorted(set(x['plan_day'] for x in a))))
m={x['symbol']:x for x in rd(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
seq=rd(X/'ENTRY_TIME_SEQUENCE_ROWS.json')
ret=[x for x in seq if x['allocation_phase']=='MATURE' and x['retained_after_previous_OPEN_rejection']]
frames={}
for sid in sorted(set(x['sid'] for x in ret)):
 mm=m[sid];frames[sid]={}
 for kind,p in [('raw',next(p for p in mm['source_sha256'] if p.endswith('/signal.parquet'))),('facts',mm['refs']['facts']),('cp',mm['refs']['CP1'])]:
  h=hashlib.sha256(Path(p).read_bytes()).hexdigest();assert h=={**mm['source_sha256'],**mm['output_sha256']}[p];hashes[p]=h;frames[sid][kind]=pd.read_parquet(p).loc[:'2025-01-20']
details=[]
for r in ret:
 z=frames[r['sid']]['raw'];f=frames[r['sid']]['facts'];cp=frames[r['sid']]['cp'];s=pd.Timestamp(r['signal_day']);p=pd.Timestamp(r['plan_day']);en=pd.Timestamp(r['entry_day']);a=z.loc[s];b=z.loc[p]
 span=z.loc[s:p];ok=bool(span.observed_bar.all() and span.price_eligible.all() and span.volume_eligible.all() and not span.source_invalid.any() and not span.synthetic_event_bar.any() and len(span[['source_kind','source_path','segment_id']].drop_duplicates())==1)
 C0=float(a.raw_close*a.adjustment_factor);Ct=float(b.raw_close*b.adjustment_factor);I0=float(f.at[s,'i_floor']);It=float(f.loc[s:p,'i_floor'].max())
 assert ok and C0>I0 and Ct>It
 cspan=cp.loc[s:p];after=cspan[cspan.index>s];receipts=after[(after.receipt==True)&after.candidate.notna()&after.candidate.gt(0)]
 lastdate=str(receipts.index[-1].date()) if len(receipts) else None;lastfloor=float(receipts.iloc[-1].candidate) if len(receipts) else None
 cpvalid=None
 if lastdate:
  post=z.loc[lastdate:r['plan_day']];cpp=float(lastfloor);cpvalid=bool(((post.raw_close*post.adjustment_factor)>cpp).all() and ((post.loc[post.index>pd.Timestamp(lastdate),'raw_open']*post.loc[post.index>pd.Timestamp(lastdate),'adjustment_factor'])>cpp).all())
 first_rej=min(x['day'] for x in r['prior_OPEN_rejections']);firstrow=next(x for x in r['prior_OPEN_rejections'] if x['day']==first_rej)
 expected=z.index[z.index>s][0];expectedd=str(expected.date());op0=float(z.at[expected,'raw_open']*z.at[expected,'adjustment_factor']);op1=float(z.at[en,'raw_open']*z.at[en,'adjustment_factor'])
 details.append(dict(**r,first_rejected_OPEN=first_rej,first_rejected_phase=firstrow['allocation_phase'],first_rejected_reason=firstrow['decision'],first_rejected_caps=firstrow['violated_caps'],original_next_OPEN=expectedd,first_reject_is_original_next_OPEN=first_rej==expectedd,
  original_signal_adjusted_close=C0,fill_plan_adjusted_close=Ct,fill_plan_close_vs_signal_pct=100*(Ct/C0-1),original_I_floor=I0,current_ratcheted_I_floor=It,I_floor_raised=It>I0*(1+1e-10),I_floor_raise_pct=100*(It/I0-1),original_I_gap_pct=100*(C0-I0)/C0,current_I_gap_pct=100*(Ct-It)/Ct,I_gap_change_pp=100*((Ct-It)/Ct-(C0-I0)/C0),new_CP_receipts=len(receipts),CP_receipt_days=[str(x.date()) for x in receipts.index],last_CP_date=lastdate,last_CP_floor=lastfloor,last_CP_survived_known_OPEN_CLOSE_until_plan=cpvalid,CP_state_all_known=bool(after.receipt.notna().all()),actual_open_vs_original_next_open_pct=100*(op1/op0-1),information_confirmation_before_first_seed=False,source_lineage_valid=True))
def quant(a):
 a=sorted(float(x) for x in a);return dict(min=a[0],median=statistics.median(a),p90=float(pd.Series(a).quantile(.9)),max=a[-1])
def group(a):
 return dict(n=len(a),signal_to_entry_hist=dict(Counter(x['signal_to_entry_intervals'] for x in a)),signal_to_entry=quant(x['signal_to_entry_intervals'] for x in a),first_reject_to_fill=quant(days.index(x['entry_day'])-days.index(x['first_rejected_OPEN']) for x in a),first_reject_at_original_next_open=sum(x['first_reject_is_original_next_OPEN'] for x in a),first_reject_phases=dict(Counter(x['first_rejected_phase'] for x in a)),price_close_change_pct=quant(x['fill_plan_close_vs_signal_pct'] for x in a),price_close_higher=sum(x['fill_plan_close_vs_signal_pct']>1e-10 for x in a),I_floor_raised=sum(x['I_floor_raised'] for x in a),I_gap_change_pp=quant(x['I_gap_change_pp'] for x in a),I_gap_narrowed=sum(x['I_gap_change_pp']<-1e-10 for x in a),new_CP_receipt_count=sum(x['new_CP_receipts']>0 for x in a),last_CP_survived_count=sum(x['last_CP_survived_known_OPEN_CLOSE_until_plan'] is True for x in a),CP_unknown_count=sum(not x['CP_state_all_known'] for x in a),no_I_raise_and_no_new_CP=sum(not x['I_floor_raised'] and not x['new_CP_receipts'] for x in a),actual_open_vs_original_next_open_pct=quant(x['actual_open_vs_original_next_open_pct'] for x in a))
summary=group(details);summary['notes']=['412 baseline retained MATURE fills after 2024-11-06 only. Current frozen signal and original identity are preserved. No observed price or CP change is a new admission rule.','A new CP receipt before first SEED is market evidence, not information_confirmed. Baseline requires a new CP dated on/after actual seed to validate ADD.','All timing is exchange-session index; observed price deltas are not opportunity cost or executable savings.','No threshold optimization, no filtered portfolio or strategy replay.']
save('M2D_FILLED_CLASSIFICATION',filled);save('M2D_REQUEST_CLASSIFICATION',requests);save('M2D_SUMMARY',m2sum);save('M2D_STARTUP_ACTUAL_OPEN',startup)
save('RETAINED_PRICE_CP_DETAILS',details);save('RETAINED_PRICE_CP_SUMMARY',summary);save('RETAINED_SOURCE_HASHES',hashes)
print(json.dumps(dict(maturity=m2sum,retained=summary),ensure_ascii=False,default=str))
