"""Independent read-only chains/cache/stage audit; no strategy/model replay."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
from bisect import bisect_right
import json,gzip,hashlib,math
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;S=O.parent;E=S.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC={};C=Counter()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with(gzip.open(p,'rt')if gz else p.open())as f:return [json.loads(x)for x in f]if lines else json.load(f)
def frame(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return pd.read_parquet(p)
def eq(a,b,key):
 if a is None or b is None:assert a is None and b is None,key
 elif isinstance(a,(bool,np.bool_))or isinstance(b,(bool,np.bool_)):assert bool(a)==bool(b),(key,a,b)
 elif isinstance(a,(bool,int,float,np.number,D))and isinstance(b,(bool,int,float,np.number,D)):
  if pd.isna(a)or pd.isna(b):assert pd.isna(a)and pd.isna(b),key
  else:assert abs(D(str(a))-D(str(b)))<=D('.000001'),(key,a,b)
 else:assert str(a)==str(b),(key,a,b)
 C[key.split(':')[0]]+=1
def scalar(x):return None if pd.isna(x)else x.item()if hasattr(x,'item')else x
def agg(xs):
 n=lambda x:D(x['net']);return dict(layers=len(xs),net=str(sum(map(n,xs),D(0))))

def main():
 out=O/'TEN_CHAIN_AUDIT.json';assert not out.exists()
 chains=read(S/'chains/COMPLETE_ORIGINAL_CHAINS.json');thin=read(S/'chains/THIN_VERIFICATION.json');sel=read(S/'chains/SELECTION_FREEZE.json');readout=S/'chains/READOUT.md';SRC[str(readout.resolve())]=sha(readout)
 allc=read(S/'accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json');order=sorted(allc,key=lambda c:(D(c['endpoint_net']),c['campaign_id']))
 expected=[c['campaign_id']for c in order[:5]]
 expected += [min(allc,key=lambda c:D(c['stage_wealth']['P03_Dec2022']['wealth']))['campaign_id'],min([c for c in allc if c['opened'][:7]=='2022-12'],key=lambda c:D(c['endpoint_net']))['campaign_id'],min([c for c in allc if c['opened'][:10]<='2024-10-08'],key=lambda c:D(c['stage_wealth']['P10_after2024Oct8']['wealth']))['campaign_id'],min([c for c in allc if c['ACT_exit_part_count']],key=lambda c:D(c['endpoint_net']))['campaign_id'],max(allc,key=lambda c:D(c['endpoint_net']))['campaign_id']]
 assert [x['campaign']['campaign_id']for x in chains[:10]]==expected and len(set(expected))==10
 assert[(x['campaign']['sid'],x['campaign']['opened'][:10])for x in chains[10:]]==[('601595.SH','2023-03-13'),('002583.SZ','2024-10-15'),('002317.SZ','2022-10-14')]
 assert [x['campaign']for x in chains[:10]]==[x['campaign']for x in sel['primary']]
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 pair=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair';book=read(pair/'B.json.gz',True);daily=read(pair/'daily.jsonl.gz',True,True);days=[r['at'][:10]for r in daily];ds={r['at'][:10]:r for r in daily};snaps=[{x['id']:x for x in d['layers']}for d in daily]
 layers={x['id']:x for x in book['layers']};buy={x['layer']:x for x in book['trades']if x['side']=='buy'};consumed=set(book['budget']['consumed']);fills={r['receipt']['receipt_id']:r for r in book['audit']if r.get('kind')=='fill'};requests={r['event_id']:r for r in book['audit']if r.get('kind')=='exit_request'}
 facts={};ixs={};cps={};evs={};industries={};canon={}
 for sid in {x['campaign']['sid']for x in chains}:
  m=sm[sid];facts[sid]=frame(m['refs']['facts']);ixs[sid]=frame(RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet');cps[sid]=frame(m['refs']['CP1']);ep=next(p for p in m['source_sha256']if p.endswith('/events.parquet'));evs[sid]=frame(ep)
 for mp in [W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]:
  for r in read(mp):
   if r['sid']not in facts:continue
   assert sha(r['output_path'])==r['output_sha256']
   for q in read(r['output_path']):canon[r['sid'],q['confirmed_day']]=q
 for sector in {x['campaign']['sector']for x in chains}:
  g=frame(im[sector]['refs']['state']);g['day']=g.day.astype(str).str[:10];industries[sector]=g.set_index('day')
 def state(lid,i):
  if i<0 or buy[lid]['at'][:10]>days[i]:return(D(0),)*4
  if lid in snaps[i]:
   x=snaps[i][lid];sid=x['sid'];f=facts[sid];k=f.index.searchsorted(pd.Timestamp(days[i]),side='right')-1;mark=D(str(f.iloc[k].raw_close))*D(x['qty']);cash=D(x['cash']);ar=D(x['dividend']);return cash+mark+ar,D(0),cash+mark,ar
  x=layers[lid];assert x['closed']and x['closed'][:10]<=days[i];cash=D(x['cash']);ar=D(x['dividend']);return cash+ar,cash,D(0),ar
 phases=[('P01_2022H1','2022-01-01','2022-06-30'),('P02_2022JulNov','2022-07-01','2022-11-30'),('P03_Dec2022','2022-12-01','2022-12-31'),('P04_2023JanApr','2023-01-01','2023-04-30'),('P05_2023MayJul','2023-05-01','2023-07-31'),('P06_2023Aug_2024Jan','2023-08-01','2024-01-31'),('P07_2024FebMay','2024-02-01','2024-05-31'),('P08_2024Jun_Sep23','2024-06-01','2024-09-23'),('P09_2024Sep24_Oct8','2024-09-24','2024-10-08'),('P10_after2024Oct8','2024-10-09','2024-12-31')]
 mobile=0;observations=0;receipts=[]
 for x in chains:
  c=x['campaign'];sid=c['sid'];ids=set(c['layer_ids']);assert ids=={e['layer']for e in x['entries']}
  # Independently verify a maximal stock holding interval, including all layers.
  overlaps={lid for lid,z in layers.items()if z['sid']==sid and z['opened']<c['closed'].replace('T',' ')and(z['closed']is None or z['closed']>c['opened'].replace('T',' '))}
  assert overlaps==ids
  eq(sum((D(layers[l]['cash'])+D(layers[l]['dividend'])for l in ids),D(0)),D(c['endpoint_net']),'campaign_net:'+sid)
  eq(sum((D(buy[l]['gross_cny'])+D(buy[l]['fees_cny'])for l in ids),D(0)),D(c['actual_buycash']),'campaign_buycash:'+sid)
  for label,start,end in phases:
   lo=bisect_right(days,start)-1
   if lo>=0 and days[lo]==start:lo-=1
   hi=bisect_right(days,end)-1;before=[state(l,lo)for l in ids];after=[state(l,hi)for l in ids]
   for j,key in enumerate(['wealth','real','unreal','AR']):eq(sum((a[j]-b[j]for a,b in zip(after,before)),D(0)),D(c['stage_wealth'][label][key]),'phase_'+key+':'+sid)
  for e in x['entries']:
   lid=e['layer'];assert e['actual_buy']==buy[lid];a=e['original_signal_and_authorization'];d=a['decision_at'][:10];q=facts[sid].loc[d];p=cps[sid].loc[d];g=ixs[sid].loc[d];proof=e['original_CP_and_scale_proof'];assert bool(q.i_target)
   assert bool(a['I_buy_now'])==bool(q.i_buy);assert a['G1_up_reasons']==str(g.up_reasons or '').split('|')
   eq(proof['original_frozen_intent_floor_causal'],str(max(float(q.i_floor),float(p.candidate))if a['role']=='mobile'else q.i_floor),'initial_floor:'+str(lid))
   assert days[bisect_right(days,d)]==buy[lid]['at'][:10]
   if a['role']=='mobile':
    mobile+=1;t=proof['CP1_canonical_trace'];c0=canon[sid,d];assert t=={k:c0[k]for k in t};assert t['receipt_id']==a['receipt']and a['receipt']in consumed and t['new_advance_price_event_ids']and not t['trace_unknown'];assert p.receipt and p.delta_frontier>0;receipts.append((sid,a['receipt']))
    for key,v in proof['CP1_cached'].items():eq(v,scalar(p[key]),'CP_cache:'+str(lid)+':'+key)
   for part in e['actual_layer_accounting']['actual_sale_parts']:
    matches=[t for t in book['trades']if t['side']=='sell'and t['at']==part['at']and any(p['layer']==lid and p['net_cash']==part['net_cash']for p in t['parts'])];assert len(matches)==1;tr=matches[0];req=requests[fills[tr['receipt_id']]['order_id']];assert req['at']==part['order_created_at']and req['at']<part['at'];C['request_fill_clock']+=1
  prev={}
  for o in x['observations']:
   observations+=1;d=o['day'];dd=ds[d];f=facts[sid];j=f.index.searchsorted(pd.Timestamp(d),side='right')-1;q=f.iloc[j];assert o['fact_source_day']==str(f.index[j].date())
   for k,v in o['stock'].items():eq(v,scalar(q[k]),'observation_stock:'+k)
   assert o['prior_observed_original_protection']==prev
   for h in o['actual_live_layers']:
    z=h['snapshot'];assert z==next(t for t in dd['layers']if t['id']==z['id']);eq(h['basis'],D(buy[z['id']]['gross_cny'])+D(buy[z['id']]['fees_cny']),'held_basis:'+str(z['id']));eq(h['mark'],D(str(q.raw_close))*D(z['qty']),'held_mark:'+str(z['id']))
   prev={str(h['snapshot']['id']):dict(floor=h['snapshot']['floor'],last_core_line=h['snapshot'].get('last_core_line'),snapshot_day=d)for h in o['actual_live_layers']}
   if o['native_event']is not None:
    ev=evs[sid].loc[d]
    for k,v in o['native_event'].items():eq(v,scalar(ev[k]),'native_event:'+k)
 assert mobile==46 and len(receipts)==len(set(receipts))and observations==262 and sum(len(x['entries'])for x in chains)==52
 # All original entry cache groups: independent parquet joins and aggregation.
 summaries=read(S/'state_semantics/RESULTS.json');derived={};state_source=read(S/'state_semantics/SOURCES.json');source_hashes=dict(read(S/'chains/SOURCE_MANIFEST.json')['source_sha256']);source_hashes.update(state_source['sources'])
 for ref in ['2022_2024','strong']:
  rows=read(S/'state_semantics'/(ref+'_ROWS.json'));new=[]
  for e in rows:
   sid=e['sid'];d=e['decision_at'][:10];sector=e['sector']
   if sid not in facts:facts[sid]=frame(sm[sid]['refs']['facts']);ixs[sid]=frame(RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet');cps[sid]=frame(sm[sid]['refs']['CP1'])
   if sector not in industries:g=frame(im[sector]['refs']['state']);g['day']=g.day.astype(str).str[:10];industries[sector]=g.set_index('day')
   q=facts[sid].loc[d];g=ixs[sid].loc[d];cp=cps[sid].loc[d];ind=industries[sector].loc[d]
   for k,v in e['original_stock_state'].items():eq(v,scalar(q[k]),'all_state_stock:'+k)
   assert e['I_buy_now']==bool(q.i_buy)and e['CP_receipt_now']==bool(cp.receipt)and e['industry_new_receipt_now']==bool(ind.receipt)
   assert e['G1_up_reasons']==str(g.up_reasons or '').split('|');eq(e['CP_used_scale'],scalar(cp.scale),'all_state_CPscale:'+sid)
   z=dict(e);z['I_CP_same_confirmation_CLOSE']=bool(q.i_buy)and bool(cp.receipt);z['industry_new_receipt_now']=bool(ind.receipt);z['I_buy_now']=bool(q.i_buy);new.append(z)
  derived[ref]=new
 for name,rr in [('2022_2024',derived['2022_2024']),('2022_2023',[e for e in derived['2022_2024']if e['opened'][:4]<'2024']),('post_Oct8_303',[e for e in derived['2022_2024']if e['opened'][:10]>'2024-10-08']),('strong',derived['strong'])]:
  sets={'all':rr,'mobile':[e for e in rr if e['role']=='mobile'],'same_CLOSE_I_CP':[e for e in rr if e['I_CP_same_confirmation_CLOSE']],'mobile_no_I_buy_now':[e for e in rr if e['role']=='mobile'and not e['I_buy_now']],'mobile_no_new_industry_receipt_now':[e for e in rr if e['role']=='mobile'and not e['industry_new_receipt_now']]}
  for label,ss in sets.items():eq(len(ss),summaries[name][label]['layers'],'state_group_layers:'+name+label);eq(sum((D(e['net'])for e in ss),D(0)),D(summaries[name][label]['net']),'state_group_net:'+name+label)
 for p,h in source_hashes.items():assert sha(p)==h,('source_changed',p)
 thinbound=S/'chains/LOCAL_BOUND_THIN_REVIEW.json';SRC[str(thinbound.resolve())]=sha(thinbound)
 SRC[str(Path(__file__).resolve())]=sha(__file__)
 result=dict(status='PASS_INDEPENDENT_TEN_CHAIN_AND_ORIGINAL_CACHE_GROUP_THIN_AUDIT',fixed_primary_campaigns=10,attached_positive_controls=3,actual_entry_decisions=52,CLOSE_observations=262,mobile_canonical_receipts_positive_unique_consumed=46,phase_wealth_bridges=130,all_original_state_rows=3436,reported_source_bindings_verified=len(source_hashes),checks=dict(C),source_sha256=SRC,local_bounds_independence='This auditor authored executable_bounds and does not independently audit own A/B. Separate chain-author thin receipt is linked only.',local_bound_thin_review=str(thinbound.resolve()),new_full_accounts=0,new_financial_events=0,limits=['Selection is descriptive outcome-based forensic sampling, not random evidence or a tradable selection rule.','Cap/scale full financial fields remain bound to their separate original financial audits.','Same confirmation CLOSE does not establish statistical independence or identical algorithms; no-new industry receipt does not negate retained authorization.'])
 with out.open('x')as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({k:result[k]for k in ['status','actual_entry_decisions','CLOSE_observations','mobile_canonical_receipts_positive_unique_consumed','all_original_state_rows','reported_source_bindings_verified']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
