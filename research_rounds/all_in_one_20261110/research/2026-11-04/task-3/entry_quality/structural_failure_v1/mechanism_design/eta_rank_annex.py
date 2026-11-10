"""Append-only diagnostics: true eta ordering vs native H1 tie/NA behavior."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import gzip,hashlib,json,math,time
import numpy as np
import pandas as pd
getcontext().prec=65
O=Path(__file__).resolve().parent;E=O.parents[1];T=E/'trend_exit_controls_v1';SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):p=Path(p);SRC[str(p)]=sha(p);return p
def read(p):return json.loads(bind(p).read_text())
def rows(p):
 with gzip.open(bind(p),'rt') as f:
  for x in f:yield json.loads(x)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.write('\n')
def agg(a):
 return dict(layers=len(a),stocks=len({x['sid'] for x in a}),cost=sum((D(x['cost']) for x in a),D(0)),net=sum((D(x['net']) for x in a),D(0)),positive=sum((max(D(0),D(x['net'])) for x in a),D(0)),negative=sum((min(D(0),D(x['net'])) for x in a),D(0)))
def kind(a,b):
 x,y=a['eta'],b['eta']
 if x is None or y is None:return 'pair_touches_UNKNOWN_fixed_H1_slot'
 return 'round12_tie_H1_order' if round(x,12)==round(y,12) else 'true_unequal_eta_order'
def main():
 begin=time.monotonic();manifest=read(O/'SCORES_MANIFEST.json');before={str(p):sha(p) for p in [O/'prepare_eta.py',O/'PROTOCOL.json',O/'SCORES_MANIFEST.json',O/'RANKING_PRE_LABEL_FREEZE.json']}
 array={};dates=None
 for m in manifest['entries']:
  p=O/'scores'/(m['symbol']+'.parquet');assert sha(p)==m['output_sha256'];SRC[str(p)]=sha(p);f=pd.read_parquet(p)
  dd=[str(t.date()) for t in f.index]
  if dates is None:dates=dd
  else:assert dates==dd
  array[m['symbol']]=f[['score','original_E','absolute_energy','original_score']].to_numpy(float)
 datepos={d:i for i,d in enumerate(dates)};all_summary={};tails={};opps={};competitions={};affected={};rowclasses={}
 for win in ('2022_2024','strong'):
  mm=list(rows(O/(win+'_PENDING_RANK_MOVES.jsonl.gz')));byday=defaultdict(list);mmap={}
  for x in mm:byday[x['day']].append(x);mmap[x['day'],x['sid']]=x
  count=Counter();classes={};dayrows=[]
  for day,z in sorted(byday.items()):
   z.sort(key=lambda x:x['old_PVR_slot']);n=len(z);eta=np.array([np.nan if x['eta'] is None else round(x['eta'],12) for x in z]);new=np.array([x['new_eta_slot'] for x in z]);changed=np.array([x['eta_minus_PVR_slot']!=0 for x in z])
   inv=np.triu(new[:,None]>new[None,:],k=1);ready=np.isfinite(eta);known=ready[:,None]&ready[None,:];tie=known&(eta[:,None]==eta[None,:]);masks={'true_unequal_eta_order':inv&known&~tie,'round12_tie_H1_order':inv&tie,'pair_touches_UNKNOWN_fixed_H1_slot':inv&~known}
   assert sum(int(v.sum()) for v in masks.values())==int(inv.sum())
   local={k:int(v.sum()) for k,v in masks.items()};flags={k:(v.sum(axis=0)+v.sum(axis=1))>0 for k,v in masks.items()}
   for i,x in enumerate(z):
    kk=[k for k in masks if flags[k][i]]
    if changed[i]:assert kk,(win,day,x['sid'])
    label='UNCHANGED_SLOT' if not changed[i] else '+'.join(kk)
    count['row_class:'+label]+=1;classes[day,x['sid']]=label
   ct=Counter(float(q) for q in eta if math.isfinite(q));tie_sizes=[q for q in ct.values() if q>1]
   count['batches']+=1;count['pending_stock_days']+=n;count['all_inverted_pairs']+=int(inv.sum());count['tie_rows']+=sum(tie_sizes);count['days_with_eta_ties']+=bool(tie_sizes);count['max_eta_tie_group']=max(count['max_eta_tie_group'],max(tie_sizes,default=0))
   for k,v in local.items():count['pair_kind:'+k]+=v
   for x in z:
    if x['eta'] is None:count['eta_UNKNOWN']+=1
    else:
     count['eta_exact_plus1']+=x['eta']==1;count['eta_round12_plus1']+=round(x['eta'],12)==1;count['eta_round12_minus1']+=round(x['eta'],12)==-1
   dayrows.append(dict(day=day,stocks=n,pair_inversions=int(inv.sum()),pair_kinds=local,eta_tie_rows=sum(tie_sizes),largest_eta_tie=max(tie_sizes,default=0)))
  all_summary[win]=dict(count);rowclasses[win]=classes;save(win+'_TIE_AND_PAIR_DAILY.json',dayrows)
  # Full original opportunity domain, not just orders or filled names.
  co=defaultdict(Counter)
  for r in rows(T/'runs/BASELINE'/win/'pair/opportunities.jsonl.gz'):
   e,E0,A0,old=array[r['sid']][datepos[r['day']]];scopes=['all_original_opportunity_rows']
   if r['roles']:scopes+=['native_role_rows']
   if r['roles'] and not r['barriers']:scopes+=['native_role_and_barrier_free_rows']
   for role in r['roles']:scopes+=['role_'+role]
   for scope in scopes:
    co[scope]['rows']+=1;co[scope]['old_PVR_ready']+=math.isfinite(old);co[scope]['eta_ready']+=math.isfinite(e)
    co[scope]['zero_denominator_old_E_ready']+=math.isfinite(E0) and A0==0
    if math.isfinite(e):
     co[scope]['eta_exact_plus1']+=e==1;co[scope]['eta_round12_plus1']+=round(e,12)==1;co[scope]['eta_round12_minus1']+=round(e,12)==-1
  opps[win]={k:dict(v) for k,v in co.items()}
  pair=Counter();background=Counter();touched=set();examples=[]
  for b in rows(O/(win+'_RESOURCE_COMPETITION_BACKGROUNDS.jsonl.gz')):
   assert '09:30:00' in b['original_rejected_funding']['at'],b['original_rejected_funding']
   c=b['candidate_rank'];ks=set()
   for f in b['original_earlier_reserved_now_later']:
    k=kind(c,f);pair[k]+=1;ks.add(k);touched.add((b['decision_day'],f['sid']))
    if len(examples)<12:examples.append(dict(decision_day=b['decision_day'],pair_kind=k,rejected_sid=c['sid'],reserved_sid=f['sid'],rejected_old_eta=[c['old_PVR_slot'],c['new_eta_slot'],c['eta']],reserved_old_eta=[f['old_PVR_slot'],f['new_eta_slot'],f['eta']],original_reject_reason=b['original_rejected_funding']['result']))
   label='+'.join(sorted(ks));background[label]+=1
  competitions[win]=dict(pair_counts=dict(pair),background_row_classes=dict(background),original_reserved_stock_days_crossed_by_rejected=len(touched),examples=examples,meaning='Order inversions are necessary competition backgrounds. FixedH1 tie/NA behavior is identified, not a causal profit decomposition. Different sector/role/minimum/cash guards may prevent replacement.')
  actual=read(O/(win+'_ACTUAL_ENTRY_RANK_DIAGNOSTIC.json'));actualmap={x['layer']:x for x in actual}
  aa=[x for x in actual if (x['decision_at'][:10],x['sid']) in touched]
  affected[win]=dict(all_original_actual_entries_touched=agg(aa),first=agg([x for x in aa if x['action']=='first_actual_participation']),own_tail30=agg([x for x in aa if D(x['net'])/D(x['cost'])>=D('.3')]),all_actual_by_class={k:agg([x for x in actual if classes[x['decision_at'][:10],x['sid']]==k]) for k in sorted({classes[x['decision_at'][:10],x['sid']] for x in actual})})
  controls=read(E/'structural_failure_v1/state_semantics'/(win+'_FIXED_TAIL_CONTROLS.json'));rr=[];matched=[]
  for c in controls:
   cc=[]
   for q in c['matched_No60_rows']:
    x=actualmap[q['layer']];assert x['sid']==q['sid'] and D(x['cost'])==D(q['cost']) and D(x['net'])==D(q['net'])
    z=dict(q,eta_rank_diagnostic=x['eta_rank_diagnostic'],rank_pair_row_class=classes[x['decision_at'][:10],x['sid']],original_funding_competition_touched=(x['decision_at'][:10],x['sid']) in touched);cc.append(z);matched.append(z)
   rr.append(dict(original=c['original'],unmatched=c['unmatched'],matched_No60_rows=cc))
  save(win+'_FIXED83_94_ETA_CONTROL_ROWS.json',rr)
  tails[win]=dict(original_members=len(rr),matched_original_members=sum(bool(c['matched_No60_rows']) for c in rr),matched_actual_layers=len(matched),movement={k:agg([x for x in matched if ('earlier' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']<0 else 'later' if x['eta_rank_diagnostic']['eta_minus_PVR_slot']>0 else 'same')==k]) for k in ('earlier','same','later')},original_reserved_crossed_by_resource_reject=agg([x for x in matched if x['original_funding_competition_touched']]))
 save('RANK_TIE_NONTIE_NA_ANNEX.json',dict(summary=all_summary,meaning='Pure pair-order inversion accounting; unequal eta, rounded eta ties resolved byH1, or pairs touchingUNKNOWN fixed H1 slots. Changed-row flags can be mixed; no unique economic attribution.'))
 save('OPPORTUNITY_TIE_ZERO_ANNEX.json',opps);save('COMPETITION_TIE_NONTIE_ANNEX.json',competitions);save('ACTUAL_COMPETITION_TOUCH_ANNEX.json',affected);save('FIXED83_94_ETA_SUMMARY.json',tails)
 assert all(sha(p)==h for p,h in before.items()),'Frozen feature/protocol was modified'
 save('ANNEX_SOURCE_BINDING.json',dict(sources=SRC,frozen_before_hashes=before,script_sha256=sha(__file__),seconds=time.monotonic()-begin,new_accounts=0,new_models=0))
 print('ETA_ANNEX_COMPLETE',round(time.monotonic()-begin,2),flush=True)
if __name__=='__main__':main()
