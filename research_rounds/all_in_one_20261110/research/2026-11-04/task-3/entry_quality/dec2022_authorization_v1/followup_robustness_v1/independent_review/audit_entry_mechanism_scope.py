"""Independent prefix-search audit of formation-since-withdrawal scope.

Does not import the mechanism author's code or any runner/account.  Classifier
uses only role, sid, decision clock, withdrawal clocks and canonical receipts.
Outcomes are attached after all classifications have been frozen.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
from datetime import datetime,time,timezone,timedelta
import bisect,gzip,hashlib,json
getcontext().prec=70
HERE=Path(__file__).resolve().parent;F=HERE.parent;P=F/'entry_mechanism';H=F.parent;C=H/'account_comparison/results_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
SRC={};Z=D(0);TOL=D('0.000001');TZ=timezone(timedelta(hours=8))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False,expected=None):
 p=Path(p);h=sha(p);SRC[str(p.resolve())]=h
 if expected is not None:assert h==expected,('input hash',str(p))
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def clock(s):return datetime.fromisoformat(s)
def close_clock(day):return datetime.combine(datetime.fromisoformat(day).date(),time(15,10),TZ)
def eq(a,b,label):assert abs(D(str(a))-D(str(b)))<TOL,(label,str(a),str(b))
def sums(rows,metric='net'):
 vals=[D(str(x[metric])) for x in rows]
 return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),negative=sum((v for v in vals if v<0),Z),positive=sum((v for v in vals if v>0),Z),net=sum(vals,Z))

def classify(role,sid,decision_at,withdrawals,receipts):
 """Pure causal prefix query; financial outcomes are not arguments."""
 now=clock(decision_at);prior=[w for w in withdrawals.get(sid,[]) if clock(w['at'])<=now]
 if not prior:return dict(blocked=False,last=None,release=None)
 latest=max(prior,key=lambda w:clock(w['at']));barrier=clock(latest['at']);proven=[]
 for r in receipts.get(sid,[]):
  confirm=close_clock(r['confirmed_day']);anchor=r.get('formation_start_exclusive')
  if barrier<=confirm<=now and anchor is not None and not r.get('trace_unknown') and close_clock(anchor)>=barrier:proven.append(r)
 release=min(proven,key=lambda r:r['confirmed_day']) if proven else None
 return dict(blocked=role=='mobile' and release is None,last=latest,release=release)

def compare_summary(rows,expected,metric):
 hit=[r for r in rows if r['_independent_blocked']];allamount=sums(rows,metric);hitamount=sums(hit,metric)
 for label,value in [('all',allamount),('hit',hitamount)]:
  for k,v in value.items():eq(v,expected[label][k],'summary '+label+' '+k)
 assert expected['unknown']==0
 assert dict(Counter(r['actual_entry_action'] for r in hit))==expected['hit_by_actual_action']
 for sign in ['negative','positive']:
  denominator=allamount[sign];numerator=hitamount[sign];val=None if not denominator else 100*numerator/denominator
  if val is None:assert expected[sign+'_coverage_pct'] is None
  else:eq(val,expected[sign+'_coverage_pct'],'coverage '+sign)

if __name__=='__main__':
 output=HERE/'ENTRY_MECHANISM_SCOPE_AUDIT.json';assert not output.exists(),'Preserve prior independent audit'
 result=dict(status='RUNNING',independent_implementation='Latest-withdrawal + causal canonical-receipt prefix search, not author event-state implementation',new_accounts=0,new_account_events=0)
 try:
  source=read(P/'SOURCE_MANIFEST.json');bad=[]
  for p,h in source['sources'].items():
   if sha(p)!=h:bad.append(p)
  for name,h in source['deliverables'].items():
   if sha(P/name)!=h:bad.append(str(P/name))
  assert not bad,('Source/deliverable hash mismatch',bad)
  protocol=read(P/'PROTOCOL.json');summary=read(P/'SUMMARY.json');validation=read(P/'VALIDATION.json');tails=read(P/'FIXED_ORIGINAL_TAIL_CONTROLS.json');cases=read(P/'SYSTEMATIC_CASES.json');chains=read(P/'COMPLETE_SELECTED_STOCK_CHAINS.json')
  annual=[read(W/'2022-normal-reference-20261031/inputs/MANIFEST.json'),read(W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json'),read(B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')]
  strongrefs={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};reports={};all_blocked=[];selected_independent={};chain_expected={};group_checks=0
  for win in ['2022_2024','strong']:
   layers=read(C/f'JOINT_{win}_LAYERS.json');base=read(C/f'BASELINE_{win}_LAYERS.json');authored={x['key']:x for x in read(P/f'{win}_ALL_LAYER_SCOPE.json')};byid={x['layer_in_this_book']:x for x in layers};sids={r['sid'] for r in layers};receipts=defaultdict(list);byreceipt={}
   refs=[r for records in annual for r in records if not r.get('industry') and r['sid'] in sids] if win=='2022_2024' else [strongrefs[sid] for sid in sorted(sids)]
   for ref in refs:
    path=Path(ref['output_path']) if win=='2022_2024' else Path(ref['refs']['receipts']);expected=ref['output_sha256'] if win=='2022_2024' else ref['output_sha256'][str(path)]
    for r in read(path,expected=expected):
     sid=r['canonical_series'];assert sid in sids;assert r['receipt_id'] not in byreceipt
     assert r['formation_start_exclusive']<r['confirmed_day']==r['formation_end_inclusive']
     assert r['scale_frozen_at']==r['formation_start_exclusive']
     byreceipt[r['receipt_id']]=r;receipts[sid].append(r)
   for rr in receipts.values():rr.sort(key=lambda r:r['confirmed_day'])
   policy=read(H/'runs/JOINT'/win/'pair/mobile-authorization-policy.jsonl.gz',gz=True,lines=True);book=read(H/'runs/JOINT'/win/'pair/B.json.gz',gz=True)
   requests={(x['sid'],clock(x['at'])) for x in book['audit'] if x['kind']=='exit_request'};withdrawals=defaultdict(list);targets=[]
   for event in policy:
    if event.get('phase')!='held_mobile_after_native_hard_exits' or not event.get('added_mobile_exit_layer_ids'):continue
    assert event['arm']=='JOINT' and event['account']=='B' and event['native_ACT_on'] and event['native_I_target'] and not event['core_exit_ids_added']
    q=event['context'];assert q['ready_R'] and q['ready_P'] and q['RS20']<=0 and q['close']<q['EMA20'];assert q['source_max_day']==event['at'][:10]
    assert event['decision']['denies_mobile'];assert clock(event['at']).timetz()==time(15,10,tzinfo=TZ)
    added=event['added_mobile_exit_layer_ids'];assert not set(added)&set(event['prior_pending_layer_ids']);assert set(added)<=set(event['live_mobile_layer_ids'])
    assert all(byid[lid]['role']=='mobile' and byid[lid]['sid']==event['sid'] for lid in added)
    assert (event['sid'],clock(event['at'])) in requests,'No native actual exit request at logged withdrawal'
    withdrawals[event['sid']].append(event);targets.extend(added)
   for rr in withdrawals.values():rr.sort(key=lambda r:clock(r['at']));assert len({x['at'] for x in rr})==len(rr)
   # Independent interval-first reconstruction of every proof release.
   releases=[]
   for sid,ww in withdrawals.items():
    for i,event in enumerate(ww):
     end=clock(ww[i+1]['at']) if i+1<len(ww) else datetime.max.replace(tzinfo=TZ)
     eligible=[r for r in receipts[sid] if clock(event['at'])<=close_clock(r['confirmed_day'])<end and not r.get('trace_unknown') and close_clock(r['formation_start_exclusive'])>=clock(event['at'])]
     if eligible:
      r=min(eligible,key=lambda r:r['confirmed_day']);releases.append(dict(sid=sid,withdrawal_at=event['at'],release_receipt=r['receipt_id'],confirmed_day=r['confirmed_day'],formation_start_exclusive=r['formation_start_exclusive'],actually_funded_not_required=True))
   expected_releases=read(P/f'{win}_MARKET_PROOF_RELEASES.json');assert sorted(releases,key=lambda r:(r['sid'],r['withdrawal_at']))==sorted(expected_releases,key=lambda r:(r['sid'],r['withdrawal_at']))
   decrows={x['key']:x for x in read(C/'JOINT_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json')} if win=='2022_2024' else {}
   rows=[];unknown=0
   for original in layers:
    r=dict(original);tag=classify(r['role'],r['sid'],r['decision_at'],withdrawals,receipts);published=authored[r['key']];r['_independent_blocked']=tag['blocked'];r['Dec_wealth']=decrows.get(r['key'],{}).get('Dec_components',{}).get('wealth','0');r['Dec_cohort']=decrows.get(r['key'],{}).get('cohort','outside_Dec')
    assert r['_independent_blocked']==published['candidate_blocked_on_JOINT_history'];assert tag['last']==published['last_H2_request']
    assert (tag['last'] if tag['last'] is not None and tag['release'] is None else None)==published['active_proof_barrier']
    if r['role']=='mobile':
     cp=byreceipt.get(r['receipt']);assert cp is not None and cp['canonical_series']==r['sid'] and cp['confirmed_day']==r['decision_at'][:10]
     unknown+=bool(cp.get('trace_unknown'));assert cp==published['original_receipt']
    if tag['blocked']:all_blocked.append(dict(window=win,sid=r['sid'],role=r['role'],action=r['actual_entry_action'],key=r['key'],decision_at=r['decision_at'],request_at=tag['last']['at'],receipt=r['receipt'],formation_start_exclusive=byreceipt[r['receipt']]['formation_start_exclusive'],net=r['net']))
    rows.append(r)
   groups={'all_entries':rows,'all_mobile':[r for r in rows if r['role']=='mobile']}
   if win=='2022_2024':groups.update(opened2022_2023=[r for r in rows if r['opened'][:4] in ['2022','2023']],Dec_new135=[r for r in rows if r['Dec_cohort'].startswith('Dec_new')],Dec_new_mobile=[r for r in rows if r['Dec_cohort'].startswith('Dec_new') and r['role']=='mobile'])
   for group,rr in groups.items():
    metric='Dec_wealth' if group.startswith('Dec_') else 'net';compare_summary(rr,summary[win+'|'+group],metric);group_checks+=1
    for action in ['first','add','reentry']:compare_summary([x for x in rr if x['actual_entry_action']==action],summary[win+'|'+group+'|'+action],metric);group_checks+=1
   fixed=read(C/f'JOINT_{win}_FIXED83_94_TAILS.json');bykey={x['key']:x for x in rows};baseby={x['key']:x for x in base};ts=tails[win];assert len(ts['rows'])==len(fixed['rows'])=={'2022_2024':83,'strong':94}[win]
   assert {x['entry_key'] for x in ts['rows']}=={x['entry_key'] for x in fixed['rows']}
   originalkeys={x['entry_key'] for x in fixed['rows']};stocks={x['original_fixed_member']['sid'] for x in fixed['rows']};exact=[r for r in rows if r['key'] in originalkeys];allstocks=[r for r in rows if r['sid'] in stocks]
   compare_summary(exact,ts['JOINT_exact_entry_scope'],'net');compare_summary(allstocks,ts['all_JOINT_entries_in_fixed_original_stocks'],'net');group_checks+=2
   for t in ts['rows']:
    q=bykey.get(t['entry_key']);assert bool(q)==t['JOINT_exact_entry_present'];assert t['blocked_same_stock_entry_keys']==[r['key'] for r in authored.values() if r['sid']==t['original_fixed_member']['sid'] and r['candidate_blocked_on_JOINT_history']]
   for group,rr in [('full',rows)]+([('Dec_new135',groups['Dec_new135'])] if win=='2022_2024' else []):
    metric='Dec_wealth' if group.startswith('Dec') else 'net'
    for action in ['first','add','reentry']:
     aa=[r for r in rr if r['actual_entry_action']==action]
     for sense,n in [('negative',3),('positive',2)]:
      selected=sorted([r for r in aa if (D(r[metric])<0 if sense=='negative' else D(r[metric])>0)],key=lambda r:D(r[metric]),reverse=sense=='positive')[:n]
      for r in selected:selected_independent.setdefault(r['key'],[]).append(f'{win}:{group}:{action}:{sense}:top{n}');chain_expected[win+'|'+r['sid']]=(win,r['sid'])
   for r in rows:
    if r['sid'] in {'002969.SZ','688146.SH','603618.SH','601869.SH'}:selected_independent.setdefault(r['key'],[]).append('known_repair_or_strong_start_counterexample_control');chain_expected[win+'|'+r['sid']]=(win,r['sid'])
   for ck,(window,sid) in [(k,v) for k,v in chain_expected.items() if v[0]==win]:
    ch=chains[ck];assert {x['key'] for x in ch['JOINT_stock_all_entries']}=={x['key'] for x in layers if x['sid']==sid};assert {x['key'] for x in ch['BASELINE_stock_all_entries']}=={x['key'] for x in base if x['sid']==sid}
    assert ch['JOINT_real_H2_requests']==withdrawals[sid];assert ch['JOINT_all_original_market_receipts']==receipts[sid]
   v=validation[win];assert v['all_layers']==len(rows) and v['mobile_layers']==sum(r['role']=='mobile' for r in rows) and v['source_receipts']==len(byreceipt) and v['H2_unique_requests']==sum(map(len,withdrawals.values())) and v['market_proof_releases']==len(releases) and v['missing_or_unknown_mobile_receipts']==unknown==0
   reports[win]=dict(layers=len(rows),mobile_layers=v['mobile_layers'],canonical_receipts=len(byreceipt),unique_actual_withdrawal_clocks=v['H2_unique_requests'],new_mobile_exit_layer_targets=len(targets),market_proof_releases=len(releases),all_layer_flags_exact=True,
    hits=sums([r for r in rows if r['_independent_blocked']]),hit_actions=dict(Counter(r['actual_entry_action'] for r in rows if r['_independent_blocked'])),unknown_actual_mobile=unknown,
    original_tail_members=len(originalkeys),candidate_exact_original_tail_keys=len(exact),baseline_current_exact_original_tail_keys=len(originalkeys&baseby.keys()),baseline_and_candidate_exact_original_tail_intersection=len(originalkeys&baseby.keys()&bykey.keys()),all_original_tail_stock_entries=len(allstocks))
  assert {x['row']['key']:x['selection'] for x in cases}==selected_independent,'All systematic positive/negative/counterexample cases must remain'
  assert set(chains)==set(chain_expected)
  dec9=[x for x in cases if any('Dec_new135:' in s and ':negative:top3' in s for s in x['selection'])];assert len(dec9)==9 and len({x['row']['key'] for x in dec9})==9
  assert len(all_blocked)==3 and all(x['action']=='reentry' for x in all_blocked)
  result.update(status='PASS_STATIC_SCOPE_STOP_NO_CAUSAL_SCOPE',reports=reports,source_manifest_input_hashes_verified=len(source['sources']),source_manifest_deliverable_hashes_verified=len(source['deliverables']),summary_groups_verified=group_checks,all_three_blocked=all_blocked,
   systematic_cases=len(cases),complete_stock_chains=len(chains),all_Dec_negative_top3_per_action_cases=9,all_positive_controls_and_four_counterexample_stock_histories_retained=True,
   causal_input_fields=['original role','sid','decision_at','actual added-target withdrawal CLOSE','canonical receipt confirmed_day','formation_start_exclusive','trace_unknown'],
   outcome_fields_used_for_classifier=[],unknown_source_releases_allowed=False,equality_anchor_withdrawal_valid_because_interval_start_is_exclusive=True,
   restrictions=['Only fixed JOINT path scope, not a candidate full-account result. Earlier changed capital/selection feedback is unmeasured; zero Dec135 hits does not prove every possible candidate Dec path identical.',
    'Receipts read from frozen original exports and checked against source manifests; this thin audit does not cold-recompute CP formation from price-event hashes.',
    'The three flags cover only 348.7066605321 loss versus 1914.51425345135 positive actual endpoint contribution; neither is causal avoided loss or economic profit.',
    'Candidate exact original83/94 keys (46/54) include original keys absent in current baseline. Current-baseline45/67 intersects candidate at33/50; never substitute these denominators.',
    'Outcome-ranked samples are explanatory only and are attached after state flags; they do not enter authorization, release, receipts or the independent classifier.'])
 except BaseException as e:result.update(status='FAIL_PRESERVE_EVIDENCE',error=repr(e));raise
 finally:
  SRC[str(Path(__file__).resolve())]=sha(__file__);result['independent_source_sha256']=SRC
  output.open('x').write(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
 print(result['status'],json.dumps(result.get('reports'),default=str))
