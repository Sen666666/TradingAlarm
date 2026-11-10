"""Thin exact clocks and cross-book original87/122 + fixed-tail continuation audit."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
import json,gzip,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent/'trend_exit_controls_v1';C=P/'account_comparison/results_v1';Z=D(0);checks=Counter();SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def near(a,b,k):assert abs(D(str(a))-D(str(b)))<D('.000001'),(k,a,b);checks[k]+=1
def iso(x):return pd.Timestamp(x).isoformat()
prior=O/'H2_COMPARISON_MATRIX_DEC_TAIL_AUDIT.json';proof=read(prior);assert proof['status']=='PASS_ALL_32_PERIODS_DEC_WEALTH_CAPITAL_AND_FIXED_TAILS'
for p,h in proof['source_sha256'].items():assert sha(p)==h
RUN={}
for arm in ['BASELINE','R_ONLY','P_ONLY','JOINT']:
 for win in ['2022_2024','strong']:
  root=R if arm=='BASELINE' else P;out=root/'runs'/arm/win;b=read(out/'pair/B.json.gz');rows=read(C/f'{arm}_{win}_LAYERS.json');native={x['id']:x for x in b['layers']};req={a['event_id']:a for a in b['audit'] if a['kind']=='exit_request'};fills={a['receipt']['receipt_id']:a for a in b['audit'] if a['kind']=='fill'};parts=defaultdict(list)
  for t in b['trades']:
   if t['side']=='sell':
    rq=req[fills[t['receipt_id']]['order_id']]
    for p in t['parts']:parts[p['layer']].append(dict(at=t['at'],reason=p['reason'],net_cash=p['net_cash'],shares=p['shares'],order_created_at=rq['at']))
  for x in rows:
   i=x['layer_in_this_book'];n=native[i];assert x['closed']==(None if not n['closed'] else iso(n['closed']));assert x['qty']==n['qty'] and x['initial_qty']==n['initial_qty'];assert x['actual_sale_parts']==parts[i];checks['all_reported_actual_part_clocks_and_remaining_qty']+=1
  bykey={x['key']:x for x in rows};RUN[arm,win]=dict(rows=rows,bykey=bykey)
  tf=read(C/f'{arm}_{win}_FIXED83_94_TAILS.json');cc=Counter()
  for t in tf['rows']:
   a=t['candidate_exact_entry_match'];b=t['baseline_current_exact_match'];k=t['entry_key'];early=bool(b is not None and a is not None and a['closed'] is not None and a['closed']<(b['closed'] or ('2024-12-31T15:10:00+08:00' if win=='2022_2024' else '2026-06-30T15:10:00+08:00')));after=[]
   if early:
    end=b['closed'] or ('2024-12-31T15:10:00+08:00' if win=='2022_2024' else '2026-06-30T15:10:00+08:00');after=[x for x in rows if x['sid']==a['sid'] and x['key']!=k and x['opened']<end and (x['closed'] is None or x['closed']>a['closed'])]
   assert t['matched_entry_exited_earlier']==early;assert t['candidate_other_holding_after_exact_layer_exit_before_baseline_end_keys']==[x['key'] for x in after];assert t['candidate_new_entries_after_exact_layer_exit_before_baseline_end_keys']==[x['key'] for x in after if x['opened']>=a['closed']];assert t['candidate_no_further_holding_after_early_exit']==((not after) if early else None)
   cc['none']+=t['candidate_no_actual_holding_during_original_tail_interval'];cc['baseline_none']+=t['candidate_no_actual_holding_during_original_tail_interval'] and b is not None;cc['early_no_more']+=early and not after;checks['tail_early_exit_and_later_actual_holdings']+=1
  su=tf['summary'];assert su['completely_no_holding_in_original_tail_interval']==cc['none'] and su['baseline_matched_cohort_completely_no_holding_in_original_tail_interval']==cc['baseline_none'] and su['matched_tail_earlier_exit_then_no_further_holding']==cc['early_no_more']
base=read(C/'BASELINE_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');fixedsets={'ORIGINAL87':[x for x in base if x['cohort']=='old_inventory_Nov30'],'ORIGINAL122':[x for x in base if x['cohort'].startswith('Dec_new_')]};assert [len(v) for v in fixedsets.values()]==[87,122];summaries=read(C/'ORIGINAL87_122_CORRESPONDENCE_SUMMARY.json')
for arm in ['BASELINE','R_ONLY','P_ONLY','JOINT']:
 own=read(C/f'{arm}_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');ownby={x['key']:x for x in own};run=RUN[arm,'2022_2024'];denials={}
 if arm!='BASELINE':
  for x in read(P/'runs'/arm/'2022_2024/pair/mobile-authorization-policy.jsonl.gz',True):
   if x['phase']=='new_mobile_role_before_pending' and not x['allowed']:denials[iso(x['at']),x['sid'],x['CP1_id']]=x
 for label,originals in fixedsets.items():
  z=read(C/f'{arm}_{label}_FULL_KEY_CORRESPONDENCE.json');assert len(z['rows'])==len(originals);co=Counter();money=Z
  for x,b in zip(z['rows'],originals):
   k=b['key'];assert x['original_full_entry_key']==k and x['original_layer']==b;candidate=run['bykey'].get(k);assert x['candidate_exact_entry']==candidate;parts=json.loads(k);denied=denials.get((parts[3],parts[0],parts[2]));assert x['direct_guard_rejection_at_original_decision']==denied
   ownrow=ownby.get(k);sameheld=ownrow is not None and ownrow['cohort']=='old_inventory_Nov30';assert x['candidate_same_key_held_Nov30']==sameheld;assert x['candidate_own_Dec_cohort']==(ownrow['cohort'] if ownrow else None)
   expected=ownrow['Dec_components'] if ownrow else {q:'0' for q in ['real','unreal','AR','wealth']} if candidate else None
   if expected is None:assert x['candidate_Dec_components'] is None
   else:
    for q,v in expected.items():near(x['candidate_Dec_components'][q],v,'fixed_Dec_component_'+q)
    money+=D(expected['wealth'])
   other=[a['key'] for a in run['rows'] if a['sid']==b['sid'] and a['key']!=k];assert x['candidate_other_same_stock_entries']==other;overlap=any(a['sid']==b['sid'] and a['opened']<'2022-12-30T15:10:00+08:00' and (a['closed'] is None or a['closed']>'2022-11-30T15:10:00+08:00') for a in run['rows']);assert x['candidate_has_any_Dec_stock_holding']==overlap
   co['matches']+=candidate is not None;co['denied']+=denied is not None;co['held']+=sameheld;co['core']+=b['role']=='core';co['coreheld']+=b['role']=='core' and sameheld;co['none']+=not overlap;checks['original87_122_fixed_rows']+=1
  su=z['summary'];assert su==summaries[arm+'|'+label];assert su['original_members']==len(originals) and su['candidate_exact_entry_matches']==co['matches'] and su['direct_denied_at_original_decision']==co['denied'] and su['candidate_same_key_held_Nov30']==co['held'] and su['original_CORE_members']==co['core'] and su['candidate_original_CORE_keys_held_Nov30']==co['coreheld'] and su['no_actual_Dec_holding_same_stock']==co['none'];near(su['original_Dec_wealth'],sum((D(b['Dec_components']['wealth']) for b in originals),Z),'fixed_original_Dec_wealth');near(su['candidate_same_key_Dec_contribution'],money,'fixed_candidate_Dec_wealth')
result=dict(status='PASS_ALL_ACTUAL_CLOCKS_FIXED_DEC_COHORTS_AND_TAIL_CONTINUATIONS',checks=dict(checks),source_sha256=SRC,script_sha256=sha(__file__),new_accounts=0,limits=['Reuses hash-verified32-period/Dec capital audit. All15431 report layer clocks/remaining quantities and actualsellparts cross rawbooks.','Fixed original87/122 membership and836 cross-book rows checked. Same-key contribution is not same-hold causal exit savings.','All708 original tail rows checked for early exit, other holdings/reentries and no-holding summary. No post-result tail selection.'])
(O/'H2_FIXED_COHORT_AND_CLOCK_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],checks=dict(checks)),ensure_ascii=False,indent=2))
