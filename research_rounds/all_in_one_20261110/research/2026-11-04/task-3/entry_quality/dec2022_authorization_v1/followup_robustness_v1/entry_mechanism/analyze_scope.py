"""Read-only fixed-JOINT permission-state scope; no account/model imports."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,datetime
getcontext().prec=70
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
COMP=ROOT/'account_comparison/results_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
SOURCES={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected,(str(p),'hash mismatch')
 SOURCES[str(p)]=h
 return json.loads(p.read_text())
def write(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def amount(rows,field='net'):
 vals=[D(r[field]) for r in rows]
 return dict(layers=len(rows),stocks=len({r['sid'] for r in rows}),negative=str(sum((v for v in vals if v<0),D(0))),positive=str(sum((v for v in vals if v>0),D(0))),net=str(sum(vals,D(0))))
def summary(rows,field='net'):
 hit=[r for r in rows if r['candidate_blocked_on_JOINT_history']]
 a=amount(rows,field);h=amount(hit,field)
 return dict(all=a,hit=h,unknown=sum(bool(r['unknown']) for r in rows),negative_coverage_pct=str(100*D(h['negative'])/D(a['negative'])) if D(a['negative']) else None,positive_coverage_pct=str(100*D(h['positive'])/D(a['positive'])) if D(a['positive']) else None,hit_by_actual_action=dict(Counter(r['actual_entry_action'] for r in hit)),not_policy_profit=True)

protocol=read(OUT/'PROTOCOL.json')
annual=[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json']
annual_records=[read(p) for p in annual]
strong_manifest=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
strong_ref={r['symbol']:r for r in strong_manifest}
name_map={}
for window in ['2022_2024','strong']:
 p=ROOT.parent/'entry_exit_scale/decision_features'/f'{window}_ROWS.json'
 for r in read(p):name_map[r['sid']]=r.get('name',r['sid'])
all_rows={};all_summary={};all_case=[];chains={};tails_out={};validation={}
for window in ['2022_2024','strong']:
 layers=read(COMP/f'JOINT_{window}_LAYERS.json')
 baseline=read(COMP/f'BASELINE_{window}_LAYERS.json')
 sids={r['sid'] for r in layers};receipt_by_id={};receipt_by_sid=defaultdict(list)
 if window=='2022_2024':
  for records in annual_records:
   for ref in records:
    if ref['sid'] not in sids or ref.get('industry'):continue
    for r in read(ref['output_path'],ref['output_sha256']):
     assert r['receipt_id'] not in receipt_by_id
     receipt_by_id[r['receipt_id']]=r;receipt_by_sid[ref['sid']].append(r)
 else:
  for sid in sids:
   ref=strong_ref[sid];p=Path(ref['refs']['receipts'])
   for r in read(p,ref['output_sha256'][str(p)]):
    receipt_by_id[r['receipt_id']]=r;receipt_by_sid[sid].append(r)
 log=ROOT/'runs/JOINT'/window/'pair/mobile-authorization-policy.jsonl.gz'
 SOURCES[str(log)]=sha(log);triggers=[]
 with gzip.open(log,'rt') as f:
  for line in f:
   r=json.loads(line)
   if r.get('phase')=='held_mobile_after_native_hard_exits' and r.get('added_mobile_exit_layer_ids'):
    assert r['decision']['denies_mobile'] and r['native_ACT_on'] and r['native_I_target']
    triggers.append(r)
 # One request/CLOSE per stock; layer count does not multiply barriers.
 assert len({(r['sid'],r['at']) for r in triggers})==len(triggers)
 events=defaultdict(list)
 for t in triggers:events[t['sid']].append((t['at'][:10],0,t))
 for sid,rs in receipt_by_sid.items():
  for r in rs:events[sid].append((r['confirmed_day'],1,r))
 for r in layers:events[r['sid']].append((r['decision_at'][:10],2,r))
 rows=[];releases=[];trigger_hist=defaultdict(list)
 for sid,evs in events.items():
  barrier=None;last_trigger=None;last_release=None
  for day,kind,r in sorted(evs,key=lambda e:(e[0],e[1],str(e[2].get('layer_in_this_book','')))):
   if kind==0:
    barrier=r;last_trigger=r;last_release=None;trigger_hist[sid].append(r)
   elif kind==1 and barrier is not None:
    start=r.get('formation_start_exclusive');unknown=r.get('trace_unknown')
    if start is not None and not unknown and start>=barrier['at'][:10]:
     last_release=dict(withdrawal_at=barrier['at'],release_receipt=r['receipt_id'],confirmed_day=day,formation_start_exclusive=start,actually_funded_not_required=True)
     releases.append(dict(sid=sid,**last_release));barrier=None
   elif kind==2:
    unknown=[];cp=None
    if r['role']=='mobile':
     cp=receipt_by_id.get(r['receipt'])
     if cp is None:unknown.append('missing_original_receipt')
     elif cp.get('trace_unknown'):unknown.extend(cp['trace_unknown'])
     if cp is not None:
      assert cp['confirmed_day']==day and cp['canonical_series']==sid
      assert cp['formation_start_exclusive']<day
      assert cp['formation_end_inclusive']==day
    blocked=bool(r['role']=='mobile' and barrier is not None and not unknown)
    q=dict(r,name=name_map.get(sid,sid),candidate_blocked_on_JOINT_history=blocked,unknown=unknown,
           last_H2_request=last_trigger,active_proof_barrier=barrier,last_market_proof_release=last_release,
           original_receipt=cp,tag_is_fixed_JOINT_history_not_candidate_state=True)
    rows.append(q)
 rows.sort(key=lambda r:(r['decision_at'],r['sid'],r['layer_in_this_book']))
 if window=='2022_2024':
  dec=read(COMP/'JOINT_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');decdict={r['key']:r for r in dec}
  for r in rows:
   r['Dec_wealth']=decdict.get(r['key'],{}).get('Dec_components',{}).get('wealth','0')
   r['Dec_cohort']=decdict.get(r['key'],{}).get('cohort','outside_Dec')
  groups={'all_entries':rows,'all_mobile':[r for r in rows if r['role']=='mobile'],'opened2022_2023':[r for r in rows if r['opened'][:4] in ['2022','2023']],
          'Dec_new135':[r for r in rows if r['Dec_cohort'].startswith('Dec_new')], 'Dec_new_mobile':[r for r in rows if r['Dec_cohort'].startswith('Dec_new') and r['role']=='mobile']}
 else:groups={'all_entries':rows,'all_mobile':[r for r in rows if r['role']=='mobile']}
 for label,group in list(groups.items()):
  metric='Dec_wealth' if label.startswith('Dec_') else 'net'
  all_summary[window+'|'+label]=summary(group,metric)
  for action in ['first','add','reentry']:
   all_summary[window+'|'+label+'|'+action]=summary([r for r in group if r['actual_entry_action']==action],metric)
 # Full fixed original controls: exact entry and all entries in original stocks are separate.
 ft=read(COMP/f'JOINT_{window}_FIXED83_94_TAILS.json');bykey={r['key']:r for r in rows};trows=[]
 for t in ft['rows']:
  q=bykey.get(t['entry_key']);orig=t['original_fixed_member'];sid=orig['sid']
  trows.append(dict(original_fixed_member=orig,entry_key=t['entry_key'],original_status=t['status'],
   JOINT_exact_entry_present=q is not None,exact_entry_candidate_blocked=q['candidate_blocked_on_JOINT_history'] if q else None,
   exact_JOINT_entry_net=q['net'] if q else None,all_JOINT_same_stock_entry_keys=[r['key'] for r in rows if r['sid']==sid],
   blocked_same_stock_entry_keys=[r['key'] for r in rows if r['sid']==sid and r['candidate_blocked_on_JOINT_history']],
   absent_exact_entry_is_not_no_stock_holding=True))
 stockset={r['original_fixed_member']['sid'] for r in trows}
 exact=[bykey[t['entry_key']] for t in ft['rows'] if t['entry_key'] in bykey]
 tails_out[window]=dict(original_members=len(trows),JOINT_exact_entry_scope=summary(exact),
  all_JOINT_entries_in_fixed_original_stocks=summary([r for r in rows if r['sid'] in stockset]),rows=trows)
 # Outcome-ranked explanatory samples fixed in protocol, no outcome enters state.
 sample_groups={'full':rows}
 if window=='2022_2024':sample_groups['Dec_new135']=groups['Dec_new135']
 selected={}
 for group,rr in sample_groups.items():
  field='Dec_wealth' if group.startswith('Dec') else 'net'
  for action in ['first','add','reentry']:
   aa=[r for r in rr if r['actual_entry_action']==action]
   for sense,n in [('negative',3),('positive',2)]:
    ss=sorted([r for r in aa if (D(r[field])<0 if sense=='negative' else D(r[field])>0)],key=lambda r:D(r[field]),reverse=sense=='positive')[:n]
    for r in ss:selected.setdefault(r['key'],dict(row=r,selection=[]))['selection'].append(f'{window}:{group}:{action}:{sense}:top{n}')
 for r in rows:
  if r['sid'] in {'002969.SZ','688146.SH','603618.SH','601869.SH'}:
   selected.setdefault(r['key'],dict(row=r,selection=[]))['selection'].append('known_repair_or_strong_start_counterexample_control')
 for v in selected.values():
  r=v['row'];all_case.append(v)
  ck=window+'|'+r['sid']
  chains[ck]=dict(window=window,sid=r['sid'],name=r['name'],JOINT_stock_all_entries=[x for x in rows if x['sid']==r['sid']],
   BASELINE_stock_all_entries=[x for x in baseline if x['sid']==r['sid']],JOINT_real_H2_requests=trigger_hist[r['sid']],
   JOINT_all_original_market_receipts=sorted(receipt_by_sid[r['sid']],key=lambda x:x['confirmed_day']),
   same_key_and_all_stock_must_not_be_mixed=True)
 validation[window]=dict(all_layers=len(rows),mobile_layers=sum(r['role']=='mobile' for r in rows),source_receipts=len(receipt_by_id),H2_unique_requests=len(triggers),
  market_proof_releases=len(releases),missing_or_unknown_mobile_receipts=sum(bool(r['unknown']) for r in rows if r['role']=='mobile'),
  blocked_first_actual=sum(r['candidate_blocked_on_JOINT_history'] and r['actual_entry_action']=='first' for r in rows),new_financial_paths=0)
 write(f'{window}_ALL_LAYER_SCOPE.json',rows);write(f'{window}_MARKET_PROOF_RELEASES.json',releases);all_rows[window]=rows
write('SUMMARY.json',all_summary);write('SYSTEMATIC_CASES.json',all_case);write('COMPLETE_SELECTED_STOCK_CHAINS.json',chains);write('FIXED_ORIGINAL_TAIL_CONTROLS.json',tails_out);write('VALIDATION.json',validation)
write('SOURCE_MANIFEST.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=SOURCES,deliverables={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='SOURCE_MANIFEST.json'},new_accounts=0,new_models=0))
print(json.dumps(dict(validation=validation,main={k:v for k,v in all_summary.items() if k.count('|')==1}),ensure_ascii=False))
