"""Read all original held closes and all I pilot requests; no account replay."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,gzip,hashlib
import pandas as pd
import numpy as np
O=Path(__file__).parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={};FF={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
def at(sid,day):
 if sid not in FF:
  p=Path(SM[sid]['refs']['facts']);h=sha(p);assert h==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
  f=pd.read_parquet(p,columns=['close','segment_id','i_target','i_floor','e0_target','e0_floor'])
  # Prior known floor excludes the CURRENT observation and cannot cross source
  # domains. Exit-day retained floors and later pending repeats remain causal.
  f['prior_known_I_floor']=f.groupby('segment_id',sort=False).i_floor.transform(lambda z:z.ffill().shift())
  FF[sid]=f
 f=FF[sid];idx=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert idx>=0
 r=f.iloc[idx];qd=str(f.index[idx].date())
 prior=r.prior_known_I_floor
 # A stale source row's preserved exit floor was already published before
 # today's CLOSE, so it is also a valid prior known reference.
 if qd<day and np.isfinite(r.i_floor):prior=r.i_floor
 line=None if not np.isfinite(prior) else D(str(prior));c=D(str(r.close))
 return r,qd,line,c
SUMMARY={}
for ref,run in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),('strong',B/'pvr_pool_feasibility/runs/2025_26')]:
 book=read(run/'pair/B.json.gz',gz=True);daily=read(run/'pair/daily.jsonl.gz',gz=True,lines=True)
 allpil=[r for r in book['audit'] if r['kind']=='pilot_layer_exit'];ips=[r for r in allpil if r['reason']=='I_structure_exit']
 events={(r['at'],r['sid']):r for r in ips};assert len(events)==len(ips)
 earlier=defaultdict(list)
 for r in allpil:
  for lid in r['layers']:earlier[lid].append((r['at'],r['reason']))
 seen=set();records=[];snap={};counts=Counter();first=[];allfirstIoff={}
 for d in daily:
  dt=d['at'];day=dt[:10]
  for x in d['layers']:
   lid=x['id'];sid=x['sid'];r,qd,line,c=at(sid,day);counts['all_actual_held_layer_closes']+=1
   if bool(r.i_target):continue
   initial=lid not in seen;seen.add(lid);prev=[p for p in earlier[lid] if p[0]<dt]
   broken=line is not None and c<=line;e0off=not bool(r.e0_target)
   soft=bool(line is not None and c>line and not e0off)
   z=dict(at=dt,sid=sid,layer=lid,kind=x['kind'],first_held_Ioff_for_layer=initial,quote_day=qd,causal_close=c,
    prior_known_I_floor=line,prior_floor_broken=broken,E0_target=bool(r.e0_target),I_target=False,
    Ioff_above_prior_floor_and_E0_on=soft,previous_exit_requests=prev,
    pending_after_original_CLOSE=sid in d['pending_sells'],ACT_on=d['on'],original_layer_floor=x['floor'],
    last_core_line=x.get('last_core_line'),unknown_prior_floor=line is None)
   records.append(z);snap[dt,lid]=z
   counts['all_Ioff_held_layer_closes']+=1;counts['Ioff_prior_floor_broken']+=broken;counts['Ioff_E0_off']+=e0off
   counts['Ioff_above_prior_floor_E0_on']+=soft;counts['Ioff_unknown_prior_floor']+=line is None;counts['Ioff_stale_source_rows']+=qd!=day
   if initial:
    first.append(z);allfirstIoff[lid]=dt;counts['first_Ioff_layers']+=1;counts['first_Ioff_prior_floor_broken']+=broken
    counts['first_Ioff_E0_off']+=e0off;counts['first_Ioff_above_prior_floor_E0_on']+=soft;counts['first_Ioff_unknown_prior_floor']+=line is None
 requests=[];missing=[]
 for a in ips:
  members=[]
  for lid in a['layers']:
   z=snap.get((a['at'],lid))
   if z is None:missing.append(dict(at=a['at'],sid=a['sid'],layer=lid));continue
   members.append(z)
  requests.append(dict(at=a['at'],sid=a['sid'],all_saved_target_layers=a['layers'],held_Ioff_targets=members))
 counts['all_I_pilot_request_events']=len(ips);counts['all_I_pilot_target_memberships']=sum(len(x['layers']) for x in ips)
 counts['I_pilot_unmatched_held_target_memberships']=len(missing)
 counts['repeated_I_pilot_layer_memberships']=sum(sum(1 for t,r in earlier[lid] if r=='I_structure_exit')-1 for lid in {lid for a in ips for lid in a['layers']})
 counts['first_Ioff_with_prior_CP_request']=sum(any(r=='CP1_add_protection' for _,r in x['previous_exit_requests']) for x in first)
 counts['all_terminal_I_layers']=sum(x['reason']=='I_structure_exit' for x in book['layers'])
 assert counts['first_Ioff_above_prior_floor_E0_on']==0 and counts['first_Ioff_unknown_prior_floor']==0
 assert counts['first_Ioff_layers']==counts['first_Ioff_prior_floor_broken']
 assert not missing
 # Every later potential softer state already had an earlier original hard
 # I-floor breach; the preserved hard exit cannot be cancelled by grace.
 later_soft=[x for x in records if x['Ioff_above_prior_floor_and_E0_on']]
 assert all(not x['first_held_Ioff_for_layer'] and allfirstIoff[x['layer']]<x['at'] for x in later_soft)
 SUMMARY[ref]=dict(counts=counts,later_soft_rows=len(later_soft),all_later_soft_have_earlier_hard_trigger=True,
  original_path_induction='No first eligible soft-grace deviation exists. With unchanged deterministic admission/execution and no cancellation of original hard exits, candidate follows original until an eligible deviation; every possible first Ioff is a prior-known-floor breach, so preserved-hardrisk grace has no first divergence.',
  scope='Witness includes all native held CLOSEs even ACT-labelled, all I pilot requests including repeated pending/CP-before-I. It does not infer all-account identity merely from final sell reason.',
  actual_account_replay=False,new_accounts=0)
 save(ref+'_ALL_HELD_IOFF_CLOSES.json',records);save(ref+'_ALL_I_PILOT_REQUESTS.json',requests)
save('NO_SOFT_GRACE_WITNESS.json',dict(status='PASS',summary=SUMMARY,new_accounts=0,new_account_steps=0,
 necessary_conditions='Ioff, current CLOSE>strictly prior-known same-domain I floor, E0 shadow still valid, no previously triggered hard exit. Any unknown floor is ineligible.',
 limitation='Logical no-first-deviation witness under frozen hard-risk-preserving plugin semantics; not an executed six-arm equality test. No claim that delaying structural protection is safe or unsafe from this witness alone.'))
SRC[str(Path(__file__).resolve())]=sha(__file__);save('NO_SOFT_GRACE_SOURCE_SHA256.json',SRC)
print(json.dumps(SUMMARY,ensure_ascii=False,default=str))
