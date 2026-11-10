"""Source text/AST + two existing event-row examples. No signal/model import."""
from pathlib import Path
import json,hashlib,ast
import pandas as pd
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent;W=O.parents[1]
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
paths={
 'stock_signal':W/'selection_qualification_closeout_v1/eligibility_source/stock_signal.py',
 'numeric':RR/'pv-participation-response-20261020/code/numeric.py',
 'policy':RR/'pv-strength-b5-20261025/code/policy.py',
 'policy_arithmetic':RR/'pv-strength-b5-20261025/code/arithmetic.py',
 'G1_I':RR/'b5-g1-20261025/code/policies_g1.py',
 'observation_mask':RR/'pv-participation-response-20261020/code/data_utils.py',
 'participation':RR/'pv-participation-response-20261020/code/participation.py',
 'native_cache':Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py'),
 'producer':W/'full_local_signal_20240924_v1/signals/run_signals.py',
 'latest_run_freeze':W/'full_local_signal_two_dates_v1/2026-01-15/signals/FREEZE.json',
 'latest_saved19':W/'full_local_signal_two_dates_v1/2026-01-15/signals/ALL_SIGNALS.parquet',
 'example_events':RR/'a-share-selection-e0-20261024/prepared-v2/000072/events.parquet',
 'example_manifest':RR/'a-share-selection-e0-20261024/prepared-v2/manifest.json'}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
freeze=json.loads(paths['latest_run_freeze'].read_text())
for p,h in freeze['original_algorithm_code_sha256'].items():assert sha(p)==h
manifest=json.loads(paths['example_manifest'].read_text());record=next(x for x in manifest['series'] if x['series_id']=='000620.SZ')
assert record['files']['events']['sha256']==sha(paths['example_events'])
for k,p in paths.items():
 if p.suffix=='.py':ast.parse(p.read_text())
cols=['event','leg_direction','confirmed_pivot_price','confirmed_pivot_date','pivot_age','developing_extreme_price','developing_extreme_date','segment_id']
f=pd.read_parquet(paths['example_events'],columns=cols).loc['2022-01-01':'2022-01-31'];f=f[f.event.ne(0)].head(2)
examples=[]
for dt,r in f.iterrows():
 row={k:(int(v)if k=='segment_id'else float(v)if isinstance(v,(float,int))else str(v))for k,v in r.items()}
 row['confirmation_observation_day']=str(dt.date());row['confirmed_pivot_date_meaning']='occurrence day, not known day';examples.append(row)
assert [x['confirmation_observation_day']for x in examples]==['2022-01-06','2022-01-17']
assert [x['confirmed_pivot_date']for x in examples]==['2021-12-31','2022-01-14']
saved=pq.read_schema(paths['latest_saved19']).names
pivot_fields=['confirmed_pivot_price','confirmed_pivot_date','pivot_age','confirmation','developing_extreme_price','developing_extreme_date','sigma','volume_baseline','activity','confirmed_at','known_at']
assert not set(pivot_fields)&set(saved)
# The current adapter explicitly returns original19 but discards the transient events columns.
s=paths['stock_signal'].read_text();assert "events=event_frame_numeric(f.close,f.volume,joint=True,event_exit=False)" in s
assert "out['numeric_event']=events.event" in s and "out['numeric_leg_direction']=events.leg_direction" in s
sources={str(p):{'sha256':sha(p),'bytes':p.stat().st_size}for p in paths.values()}
(O/'SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
ranges={'stock_signal':[(8,15),(25,40),(46,55)],'numeric':[(23,35),(53,55),(67,79),(80,96),(97,128),(129,135)],'policy':[(14,14),(86,114)],'G1_I':[(6,34)],'native_cache':[(16,34)],'producer':[(163,185)]}
chunks=['# Source excerpts (read only; line numbers from current bound bytes)\n']
for key,rr in ranges.items():
 p=paths[key];lines=p.read_text().splitlines()
 for a,b in rr:
  chunks.append(f'## {key}: {p}:{a}\n\n```python\n'+'\n'.join(f'{i:4d} {lines[i-1]}'for i in range(a,b+1))+'\n```\n')
(O/'SOURCE_EXCERPTS.md').write_text('\n'.join(chunks))
result={
 'status':'PASS_BOUNDED_SOURCE_EVIDENCE_WITH_SAVED19_PIVOT_INFORMATION_GAP',
 'remaining_source_review_blocks':[],
 'scope':'Read actual bound stock_signal/numeric/e0_policy/G1_I source only; two old same-source saved examples; no reconstruction or new model.',
 'all11_latest_run_source_hashes_exact':True,
 'event_semantics':{'up_event':'+1 confirms previous developing close trough, then current new leg becomes +1','down_event':'-1 confirms previous developing close peak, then current new leg becomes -1','occurrence_day_field':'confirmed_pivot_date = d.index[ext].date()','confirmation_day':'current output row/index d.index[t] on which confirmation reaches threshold','confirmation_field':'numeric confirmation strength ratio, not timestamp','actual_publication_or_receive_timestamp_saved':False,'extreme_definition':'eligible close extrema, not daily HIGH/LOW and not hindsight final maxima','same_bar_event_count_max':1,'equal_close_policy':'numeric.compare gamma4 tie retains earlier extreme and date','event_rows_backfilled_to_occurrence_day':False},
 'event_inputs':{'sigma':'prior63 local log returns RMS, excludes current; uses frozen sigma[ext]','baseline':'previous21 median volume; confirmation uses baseline[ext]','activity':'mean positive-volume observations ext+1..t divided by baseline[ext], sqrt clipped .5..2','threshold':'(-direction)*log(Ct/Cext)*activity/(sqrt5*sigma[ext]) >=1 under compare','invalid':'numeric only finite positive close+volume; reindex omitted rows gets event0, not proof of valid no-event'},
 'same_day_priority':['Numeric checks active previous floor before extrema/event; +event cannot reenter on same row marked exited.','E0 policy likewise checks old floor, then processes +event; down does not itself invalidate E0 under event_exit=False.','G1_I checks E0 shadow or close<=old I floor before ratchet and entry; exited row cannot reenter. G1_I is entry-only strength gate, not G1_X cold exit.'],
 'latest_saved19_pivot_fields_absent':pivot_fields,
 'latest_saved_schema':saved,
 'saved19_recoverability':{'single_date19':'Not invertible: event direction/leg/close and ratcheted E0/I floors do not save previous peak price, occurrence day or confirmation lag.','sparse_fixed_dates':'Cannot get intervening confirmed pivots from three target-date snapshots or infer them from final floor.','complete_history_possible_only_with_more_inputs':'A fully observed matching valid close/event chronology and exact mask/segment/tie/init could be used in an additional reconstruction; that is not direct retrieval and was not done.','old_prepared_events':'Some original1709 saved event tables retain pivot price/date/age and confirmation-row index; source/factor/segment must match. They are not canonical5517 substitutions.','minimum_saved_provenance_for_current_stage':'decision/confirmation observation day, event, confirmed pivot close/occurrence day, current developing extreme if needed, source+segment+mask+prefix_end/code SHA; actual known_at remains unknown without publication evidence.'},
 'existing_original_examples_not_new_canonical':examples,
 'causal_usage':'Filter confirmation-row day<=decision day; never join/backfill confirmed_pivot_date as known-at. No future extrema or future confirmed event may label earlier candidate state.',
 'new_signal_model_calls':0,'new_accounts':0,'new_reconstructions':0,
 'source_index_sha256':sha(O/'SOURCE_SHA256.json'),'source_excerpt_sha256':sha(O/'SOURCE_EXCERPTS.md')}
(O/'SOURCE_PIVOT_CLOCK_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':result['status'],'audit_sha256':sha(O/'SOURCE_PIVOT_CLOCK_AUDIT.json'),'examples':examples},ensure_ascii=False))
