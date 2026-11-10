"""Independent all-held first-Ioff witness, without any account execution."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,gzip,hashlib
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;E=P/'execution_review';B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');C=Counter();S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
manifest=read(E/'NO_SOFT_GRACE_SOURCE_SHA256.json')
for p,h in manifest.items():assert sha(p)==h;C['producer_source_SHA']+=1
sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};cache={}
def frame(sid):
 if sid not in cache:
  p=sm[sid]['refs']['facts'];assert sha(p)==sm[sid]['output_sha256'][p];S[p]=sha(p);f=pd.read_parquet(p,columns=['close','segment_id','i_target','i_floor','e0_target']);prior=[];lastseg=None;lastfloor=None
  for segment,line in zip(f.segment_id,f.i_floor):
   if lastseg is None or pd.isna(segment) or pd.isna(lastseg) or segment!=lastseg:lastfloor=None
   prior.append(lastfloor);lastseg=segment
   if pd.notna(line) and np.isfinite(line):lastfloor=D(str(line))
  cache[sid]=(f,prior)
 return cache[sid]
w=read(E/'NO_SOFT_GRACE_WITNESS.json');summary={};first_examples=[]
for ref,root in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 daily=read(root/'daily.jsonl.gz');book=read(root/'B.json.gz');reported=read(E/(ref+'_ALL_HELD_IOFF_CLOSES.json'));rm={(r['at'],r['layer']):r for r in reported};assert len(rm)==len(reported);pil=[r for r in book['audit'] if r['kind']=='pilot_layer_exit'];ips=[r for r in pil if r['reason']=='I_structure_exit'];history=defaultdict(list)
 for r in pil:
  for lid in r['layers']:history[lid].append((r['at'],r['reason']))
 seen=set();counts=Counter();found=set();firstbroken=0;first_ownbroken=0;later=[]
 for day in daily:
  at=day['at'];date=at[:10]
  for layer in day['layers']:
   sid=layer['sid'];lid=layer['id'];f,prior=frame(sid);j=f.index.searchsorted(pd.Timestamp(date),side='right')-1;assert j>=0;r=f.iloc[j];qd=str(f.index[j].date());assert not pd.isna(r.i_target) and not pd.isna(r.e0_target);C['all_held_causal_quote']+=1;counts['all_actual_held_layer_closes']+=1
   if bool(r.i_target):continue
   key=(at,lid);assert key in rm;found.add(key);z=rm[key];initial=lid not in seen;seen.add(lid);line=prior[j]
   if qd<date and pd.notna(r.i_floor) and np.isfinite(r.i_floor):line=D(str(r.i_floor))
   close=D(str(r['close']));broken=line is not None and close<=line;e0off=not bool(r.e0_target);soft=line is not None and close>line and not e0off;earlier=[x for x in history[lid] if x[0]<at]
   assert (z['at'],z['sid'],z['layer'],z['kind'],z['quote_day'],z['first_held_Ioff_for_layer'])==(at,sid,lid,layer['kind'],qd,initial)
   assert D(z['causal_close'])==close and ((z['prior_known_I_floor'] is None and line is None) or D(z['prior_known_I_floor'])==line)
   assert (z['prior_floor_broken'],z['E0_target'],z['I_target'],z['Ioff_above_prior_floor_and_E0_on'],z['pending_after_original_CLOSE'],z['ACT_on'],z['unknown_prior_floor'])==(broken,not e0off,False,soft,sid in day['pending_sells'],day['on'],line is None)
   assert z['previous_exit_requests']==[list(x) for x in earlier] and z['original_layer_floor']==layer['floor'] and z['last_core_line']==layer.get('last_core_line');C['all_Ioff_record']+=1
   counts['all_Ioff_held_layer_closes']+=1;counts['Ioff_prior_floor_broken']+=broken;counts['Ioff_E0_off']+=e0off;counts['Ioff_above_prior_floor_E0_on']+=soft;counts['Ioff_unknown_prior_floor']+=line is None;counts['Ioff_stale_source_rows']+=qd!=date
   if initial:
    counts['first_Ioff_layers']+=1;counts['first_Ioff_prior_floor_broken']+=broken;counts['first_Ioff_E0_off']+=e0off;counts['first_Ioff_above_prior_floor_E0_on']+=soft;counts['first_Ioff_unknown_prior_floor']+=line is None;counts['first_Ioff_with_prior_CP_request']+=any(reason=='CP1_add_protection' for t,reason in earlier)
    assert broken and line is not None;firstbroken+=1
    own=D(layer['last_core_line'] if layer['kind']=='core' else layer['floor']);assert close<=own,(ref,lid,close,own);first_ownbroken+=1
    if len(first_examples)<6:first_examples.append(dict(ref=ref,layer=lid,sid=sid,at=at,kind=layer['kind'],close=str(close),prior_stock_floor=str(line),original_own_risk_floor=str(own)))
   elif not broken:later.append(z)
 assert found==set(rm)
 reqrows=read(E/(ref+'_ALL_I_PILOT_REQUESTS.json'));assert len(reqrows)==len(ips)
 for raw,z in zip(ips,reqrows):assert (raw['at'],raw['sid'],raw['layers'])==(z['at'],z['sid'],z['all_saved_target_layers']);assert z['held_Ioff_targets']==[rm[(raw['at'],lid)] for lid in raw['layers']];C['all_I_pilot_event']+=1
 counts['all_I_pilot_request_events']=len(ips);counts['all_I_pilot_target_memberships']=sum(len(x['layers']) for x in ips);counts['I_pilot_unmatched_held_target_memberships']=0;counts['repeated_I_pilot_layer_memberships']=sum(sum(reason=='I_structure_exit' for t,reason in history[lid])-1 for lid in {lid for x in ips for lid in x['layers']});counts['all_terminal_I_layers']=sum(x['reason']=='I_structure_exit' for x in book['layers'])
 assert dict(counts)==w['summary'][ref]['counts'],(ref,counts,w['summary'][ref]['counts']);assert firstbroken==first_ownbroken==len(seen)
 for z in later:assert not z['first_held_Ioff_for_layer'] and any(t<z['at'] and reason=='I_structure_exit' for t,reason in history[z['layer']])
 summary[ref]=dict(counts=counts,first_stock_and_own_risk_broken=firstbroken,later_not_prior_stock_floor_broken=len(later),later_rows=later)
out=dict(status='PASS_NO_FIRST_ELIGIBLE_DEVIATION_WITNESS',summary=summary,checks=dict(C),source_sha256=S,producer_source_sha256=manifest,first_boundary_examples=first_examples,limits=['No six-grace-arm economic replay performed or implied. This is an induction witness only under frozen unchanged admission/execution and preserved original hard risk/pending exit semantics.','Every first held-layer Ioff breaches both strictly prior stock I floor and its original own current native risk reference (core last_core_line or mobile old floor); E0off is separately recorded, not needed to manufacture zero floor-safe coverage.','Later softening while pending cannot cancel an earlier hard exit. Strong has one later above-prior-floor row, still E0off and earlier hard request.','Native held quotes include explicitly counted stale marks; unknown floor would be ineligible, no unknown observed.'],new_accounts=0)
(O/'NO_SOFT_GRACE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['source_sha256','producer_source_sha256','first_boundary_examples']},ensure_ascii=False,indent=2,default=str))
