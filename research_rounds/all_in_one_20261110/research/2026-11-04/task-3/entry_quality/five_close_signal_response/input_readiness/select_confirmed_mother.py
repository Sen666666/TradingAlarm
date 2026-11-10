"""Select the parent's confirmed one I-root signal mother, no outcome labels."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
import json,gzip,hashlib

O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');M=B/'risk_constraints/ma63_information_diagnostic_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(n,z):
 with (O/n).open('x') as f:json.dump(z,f,ensure_ascii=False,indent=2,allow_nan=False)
def stream(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def write_rows(name,rows):
 with (O/name).open('x') as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')

def main():
 protocol=dict(confirmed_at=datetime.now().astimezone().isoformat(),authorization='parent explicit confirmation received before first-root selection',mother='core_Q true OR (mobile_Q true AND CP1_id nonempty)',root='sid + original source_segment + real false-to-true I_target episode start',dedup='first qualified market signal only per unique root, no account-dependent fields',left_censor='root_start < first continuous opportunity-log day excluded from primary and reported separately; its first observed signal is not certified historical first',scan='entire existing2022-24 and2025Jul-2026Jun continuous opportunity logs, no new models/accounts',evaluation={'2022_weak':['2022-01-01','2022-12-31'],'2024_sep_recovery':['2024-09-02','2024-11-29'],'strong2025_26':['2025-07-01','2026-06-30']},warmup='all certified primary first signals outside evaluation windows retained for historical fixed-age input preparation; not relabelled as evaluation',not_used=['roles','held','barriers','ACTon','financial_pool','actual_fills','future_prices','5day labels'],E0='original E0 root retained as separate source attribute, never used as alternative mother')
 save('CONFIRMED_UNIQUE_MOTHER.json',protocol)
 primary=[];left=[];unknown=[];stats={};sources={};daily=[]
 def evaluation(ref,day):
  if ref=='strong':return 'strong2025_26'
  if '2022-01-01'<=day<='2022-12-31':return '2022_weak'
  if '2024-09-02'<=day<='2024-11-29':return '2024_sep_recovery'
  return 'warmup_only'
 for ref in ['2022_2024','strong']:
  p=O/(ref+'_UNION_SOURCE_EVENTS_NO_FIRST_SELECTION.jsonl.gz');sources[str(p)]=sha(p)
  first={};union_count=0;source_types=Counter();unknowns=[]
  for z in stream(p):
   union_count+=1;source_types[z['union_signal_kind']]+=1
   if z['lineage_status']!='exact_cached_I_root' or not z.get('original_I_root'):
    unknowns.append(z);continue
   assert z['core_Q'] is True or (z['mobile_Q'] is True and z['CP1_id'])
   assert z['original_I_target'] is True
   root=z['original_I_root'];key=(z['day'],z['sid'])
   if root not in first or key<(first[root]['day'],first[root]['sid']):first[root]=z
  pp=[];ll=[]
  for root,z in first.items():
   z=dict(z);z['signal_id']=f'{ref}|{root}|firstQ|{z["day"]}';z['evaluation_window']=evaluation(ref,z['day']);z['fixed_age_labels_computed']=False
   if z['left_censored_root']:
    z['first_status']='first_observed_only_historical_first_unknown';ll.append(z)
   else:
    assert z['original_I_root_start']>=z['first_continuous_opportunity_day'];z['first_status']='first_qualified_signal_in_complete_original_I_root';pp.append(z)
  # Actual fills are annotations only, joined after the mother is irreversibly selected.
  fp=M/(ref+'_ENTRIES.json');sources[str(fp)]=sha(fp);fills=defaultdict(list)
  for x in read(fp):fills[(x['sid'],x['decision_at'][:10])].append(dict(layer=x['layer'],role=x['role'],receipt=x['receipt'],actual_fill_at=x['opened'],financial_pool=x['pool_at_fill']))
  for z in pp+ll:z['actual_fill_annotation_not_selection']=fills[z['sid'],z['day']]
  for z in unknowns:z['evaluation_window']=evaluation(ref,z['day'])
  pp.sort(key=lambda x:(x['day'],x['sid'],x['original_I_root']));ll.sort(key=lambda x:(x['day'],x['sid'],x['original_I_root']))
  primary.extend(pp);left.extend(ll);unknown.extend(unknowns)
  def countwindow(rows):return dict(Counter(x['evaluation_window'] for x in rows))
  stats[ref]=dict(all_union_source_events=union_count,union_source_types=dict(source_types),unique_I_roots_with_at_least_one_qualified_event=len(first),
    primary_complete_root_first_signals=len(pp),left_censored_root_first_observed_signals=len(ll),lineage_unknown_events=len(unknowns),
    discarded_same_root_qualified_followup_events=union_count-len(first)-len(unknowns),primary_by_evaluation_window=countwindow(pp),left_censored_by_evaluation_window=countwindow(ll),
    primary_first_signal_type_counts=dict(Counter(x['union_signal_kind'] for x in pp)),left_censored_first_observed_signal_type_counts=dict(Counter(x['union_signal_kind'] for x in ll)),
    primary_root_first_with_actual_same_decision_fill_annotation=sum(bool(x['actual_fill_annotation_not_selection']) for x in pp),
    primary_root_first_without_actual_same_decision_fill=sum(not bool(x['actual_fill_annotation_not_selection']) for x in pp))
  byday=defaultdict(list)
  for z in pp:byday[z['day']].append(z)
  for c in read(O/(ref+'_DAILY_INPUT_COVERAGE.json')):
   day=c['day'];signals=byday[day];daily.append(dict(window=ref,day=day,evaluation_window=evaluation(ref,day),fixed_roster=c['fixed_roster'],observed_stock_rows=c['observed_stock_rows'],original_union_signal_events=c['union_signal_count'],original_core_Q_unknown_stock_days=c['core_Q_counts'].get('None',0),original_mobile_Q_unknown_stock_days=c['mobile_Q_counts'].get('None',0),primary_unique_root_first_signals=len(signals),primary_unique_root_first_signal_ids=[x['signal_id'] for x in signals],left_censored_first_observed_signals=sum(x['day']==day for x in ll)))
  print(ref,stats[ref],flush=True)
 assert len({x['signal_id'] for x in primary})==len(primary)
 assert len({(x['window'],x['original_I_root']) for x in primary})==len(primary)
 assert not any(x['left_censored_root'] for x in primary)
 write_rows('SIGNALS.jsonl',primary);write_rows('LEFT_CENSORED_FIRST_OBSERVED.jsonl',left);write_rows('UNKNOWN_LINEAGE_EVENTS.jsonl',unknown)
 save('DAILY_SIGNAL_INPUT_COHORTS.json',daily);save('SIGNAL_MOTHER_COUNTS.json',stats)
 save('SIGNAL_SELECTION_VALIDATION.json',dict(sources=sources,script_sha256=sha(__file__),parent_protocol=str(O/'CONFIRMED_UNIQUE_MOTHER.json'),parent_protocol_sha256=sha(O/'CONFIRMED_UNIQUE_MOTHER.json'),unique_signal_ids=True,one_first_per_complete_original_I_root=True,left_censored_excluded_only_from_primary_and_retained_separately=True,actual_fill_annotations_added_after_selection=True,new_5close_labels=0,new_accounts=0,new_models=0))

if __name__=='__main__':main()
