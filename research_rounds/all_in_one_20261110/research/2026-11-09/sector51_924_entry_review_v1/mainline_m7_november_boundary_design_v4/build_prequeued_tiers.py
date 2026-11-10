"""Independent source arithmetic and evidence inventory. No event admission."""
import json,pathlib,hashlib,re,collections
from decimal import Decimal as D
import pandas as pd
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1');O=R/'mainline_m7_november_boundary_design_v4';E=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
load=lambda p:json.loads(pathlib.Path(p).read_text());sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
I=load(O/'PREQUEUED_TARGET_FACT_INVENTORY.json');rows=[r for r in I['boundaries'] if not r['in_baseline_admission']];targets={r['sid'] for r in rows};hashes={};issues=[]
def read(p,expected=None):
 p=pathlib.Path(p);h=sha(p);hashes[str(p)]=h
 if expected and h!=expected:issues.append(dict(path=str(p),reason='HASH_MISMATCH'))
 return load(p)
read(O/'PREQUEUED_TARGET_FACT_INVENTORY.json');hashes[str(O/'build_prequeued_tiers.py')]=sha(O/'build_prequeued_tiers.py')
# Stored official API responses, no new retrieval or automatic adjudication.
rawpaths=set(R.glob('**/raw/*.json'))|set(E.glob('cash*/raw/*.json'));rawby=collections.defaultdict(list)
for p in sorted(rawpaths):
 if p.stem not in targets:continue
 obj=read(p)
 if not isinstance(obj,dict) or 'cninfo' not in obj.get('endpoint',''):continue
 for rec in obj.get('raw',{}).get('records',[]):
  dt=rec.get('F020D')
  if isinstance(dt,str) and '2024-11-06'<dt<='2026-06-30':rawby[(obj.get('sid',p.stem),dt)].append(dict(path=str(p),endpoint=obj['endpoint'],retrieved_at=obj.get('retrieved_at_utc'),record=rec))
# Verify existing field mapping source, retain it as evidence, not a new model.
for p in [E/'cash_dividend_2024_coverage_v1/normalize_facts.py',E/'cash_dividend_2024_coverage_v1/adjudicate_and_scope.py']:
 hashes[str(p)]=sha(p)
cache={};out=[]
for r in rows:
 sid,dt=r['sid'],r['date'];acts=r['actions'];pure=len(acts)==1 and D(acts[0]['cash_per_old_share'])>0 and D(acts[0]['split_ratio'])==1 and acts[0].get('classification')=='ordinary_cash_and_pro_rata_bonus'
 if sid not in cache:
  ap=pathlib.Path(r['action_path']);a=read(ap,I['source_hashes'].get(str(ap)));coverage=[]
  for c in a.get('coverage_evidence',[]):coverage.append(read(c['path'],c.get('sha256')))
  sp=r['signal_path'];hashes[sp]=sha(sp)
  if hashes[sp]!=I['source_hashes'][sp]:issues.append(dict(path=sp,reason='HASH_MISMATCH'))
  z=pd.read_parquet(sp).sort_index();cache[sid]=(a,coverage,z)
 a,coverage,z=cache[sid];prev=z[z.index<pd.Timestamp(dt)].iloc[-1];cur=z.loc[pd.Timestamp(dt)] if pd.Timestamp(dt) in z.index else None
 lineage_fields=['source_kind','source_path','segment_id'];same=cur is not None and all(str(prev.get(k))==str(cur.get(k)) for k in lineage_fields)
 f0=D(str(prev.adjustment_factor));f1=D(str(cur.adjustment_factor)) if cur is not None else None;pc=D(str(prev.raw_close));cash=D(acts[0]['cash_per_old_share']) if pure else None
 resid=f0*pc/(pc-cash)/f1-1 if pure and f1 and pc>cash else None
 source_matches=[];term_parse=False
 if pure:
  e=acts[0];match=re.fullmatch(r'(\d{4}-\d{2}-\d{2})\(每十股\s+红利([0-9.]+)元\)\$',e.get('raw_text',''));term_parse=bool(match and match[1]==dt and D(match[2])/10==cash)
  for c in coverage:
   for rec in c.get('records',[]):
    if str(rec.get('1'))==dt.replace('-','') and rec.get('471')==e['raw_text'] and c.get('source_sha256')==e.get('source_id'):source_matches.append(dict(path=c.get('source_path'),source_sha256=c.get('source_sha256'),record=rec))
 # Check original decoded-source immutable content when present.
 for sm in source_matches:
  p=pathlib.Path(sm['path'])
  if p.exists():
   h=sha(p);hashes[str(p)]=h;sm['original_hash_verified']=h==sm['source_sha256']
  else:sm['original_hash_verified']=False
 passed=bool(pure and term_parse and source_matches and all(m['original_hash_verified'] for m in source_matches) and same and resid is not None and abs(resid)<D('1e-11'))
 official=rawby[(sid,dt)];exact_official=[]
 if pure:
  for q in official:
   rec=q['record'];amt=rec.get('F012N');bonus=rec.get('F010N');cap=rec.get('F011N')
   if amt is not None and D(str(amt))/10==cash and (bonus is None or D(str(bonus))==0) and (cap is None or D(str(cap))==0):exact_official.append(q)
 date_sets={field:sorted({q['record'][key] for q in exact_official if q['record'].get(key)}) for field,key in [('announcement_date','F006D'),('record_date','F018D'),('pay_date','F023D')]}
 # Exact-event local notice proposal (already documented and hash frozen).
 notice=None
 if (sid,dt)==('300760.SZ','2024-11-07'):
  p=R/'november_300760_cash_evidence_v1/EVENT_FACT_PROPOSAL.json';notice=read(p)
  for field in date_sets:
   if notice.get(field):date_sets[field]=sorted(set(date_sets[field])|{notice[field]})
 known_dates={k:v[0] if len(v)==1 else None for k,v in date_sets.items()};conflicts={k:v for k,v in date_sets.items() if len(v)>1}
 out.append(dict(sid=sid,date=dt,category='LOCAL_PURE_CASH_SOURCE_BRIDGE_VERIFIED' if passed else 'COMPLEX_STRUCTURAL_OR_UNRESOLVED_FACT',explicit_local_action=bool(acts),action_type=r['action_types'],pure_cash=bool(pure),raw_text_date_amount_exact=term_parse,source_record_matches=source_matches,same_lineage=same,previous_observation=str(prev.name.date()),previous_raw_close=str(pc),factor_before=str(f0),factor_after=str(f1),source_cash_per_share=str(cash) if pure else None,source_bridge_residual=str(resid) if resid is not None else None,source_bridge_pass=passed,official_api_exact_amount_matches=exact_official,official_api_same_date_other_records=official,known_dates=known_dates,date_conflicts=conflicts,local_action_missing_dates={k:not any(e.get(k) for e in acts) for k in ['record_date','paid_at','announcement_date']},official_notice_proposal=str(R/'november_300760_cash_evidence_v1/EVENT_FACT_PROPOSAL.json') if notice else None,not_admitted=True,not_PIT=True))
summary=dict(total_unadmitted=len(out),tier1_explicit_local_action=sum(r['explicit_local_action'] for r in out),tier2_pure_cash_source_bridge_verified=sum(r['source_bridge_pass'] for r in out),tier3_complex_or_unresolved=sum(not r['source_bridge_pass'] for r in out),tiers_overlap='Tier 1 covers all explicit actions; Tier 2 and Tier 3 partition Tier 1. They are not three disjoint buckets.',pure_cash_count=sum(r['pure_cash'] for r in out),pure_cash_bridge_failures=[{'sid':r['sid'],'date':r['date'],'residual':r['source_bridge_residual']} for r in out if r['pure_cash'] and not r['source_bridge_pass']],structural_types=dict(collections.Counter(r['action_type'] for r in out if not r['pure_cash'])),local_action_missing_date_counts={k:sum(r['local_action_missing_dates'][k] for r in out) for k in ['record_date','paid_at','announcement_date']},pure_cash_with_official_api_exact_amount=sum(bool(r['official_api_exact_amount_matches']) for r in out if r['pure_cash']),pure_cash_known_dates={k:sum(r['known_dates'][k] is not None for r in out if r['pure_cash']) for k in ['record_date','pay_date','announcement_date']},pure_cash_missing_dates_after_existing_evidence={k:sum(r['known_dates'][k] is None for r in out if r['pure_cash']) for k in ['record_date','pay_date','announcement_date']},pure_cash_all_three_dates_known=sum(all(r['known_dates'].values()) and not r['date_conflicts'] for r in out if r['pure_cash']),hash_issues=issues,official_raw_files_considered=len(rawpaths),source_hash_count=len(hashes),examples=[r for r in out if (r['sid'],r['date']) in [('601696.SH','2024-11-08'),('600157.SH','2024-11-15'),('300760.SZ','2024-11-07'),('002532.SZ','2024-11-21'),('601229.SH','2024-11-28')]],limits=['Independent recomputation is not independent economic source corroboration: action terms and factors may originate from the same adjusted data pipeline.','Official API raw fields are evidence candidates, not reviewed admission or notice-level certification. No manually fetched PDF is presumed necessary for every event.','Disclosure date is calendar date only, not historical known-at timestamp. Collection dates in 2026 do not prove PIT availability in 2024/2025.','Source factor bridge does not certify exchange reference decrement, payment, record-day entitlement or tax.','No source change, automatic admission, strategy change or historical run.'])
assert not issues,issues
novdec=[r for r in out if r['date']<='2024-12-31']
summary['november_december_2024']=dict(total=len(novdec),pure_cash=sum(r['pure_cash'] for r in novdec),pure_cash_bridge_verified=sum(r['source_bridge_pass'] for r in novdec),complete_dates=sum(r['pure_cash'] and all(r['known_dates'].values()) and not r['date_conflicts'] for r in novdec),pure_cash_incomplete_dates=sum(r['pure_cash'] and not all(r['known_dates'].values()) for r in novdec),structural=sum(not r['pure_cash'] for r in novdec),events=[{k:r[k] for k in ['sid','date','action_type','source_cash_per_share','source_bridge_pass','known_dates']} for r in novdec])
schema=dict(status='PROPOSED_SCHEMA_ONLY_NOT_ADMISSION',identity=['sid','event_id','event_type','component_ids_if_any','effective_date'],immutable_sources=['action_path_sha256','rights_source_path_sha256','original_decoded_path_sha256','signal_path_sha256','official_api_or_notice_path_sha256','source_field_mapping_version_sha256','reviewer_and_review_artifact_hash','frozen_target_snapshot_hash'],dates=['disclosure_date_with_source','disclosure_known_at_or_explicit_not_PIT','record_date_with_source','effective_date_with_source','pay_date_with_source','new_share_sellability_date_when_applicable'],separate_values=['d_source_as_local_series_adjustment','d_cash_as_gross_holder_cash','d_ref_as_official_exchange_reference_decrement_or_unknown','factor_before','factor_after','prior_observed_raw_close','source_lineage'],checks=['Unique exact sid/date/component identity. Never silently combine same-date records.','Reparse source text date and per-share units exactly; verify original hashes.','Require same lineage and source bridge abs(f_old*P/(P-d_source)/f_new-1)<1e-11 for pure cash.','Reference bridge checked separately with d_ref and its own declared tolerance and evidence; never label d_source proof as official d_ref proof.','Disclosure/effective/record/pay dates must be explicit; previous observation is not inferred record date, and ex-date is not inferred pay date.','Unheld existing candidates may need coordinate continuity without receiving any cash.','Zero quantity at ex-date alone does not prove no entitlement: a prior record-date holder may already have sold. Never use the frozen November 6 state to predict later actual quantities.',
'Candidate-chain coordinate-only continuation requires explicit separate reviewed capability plus verified zero actual record-date entitlement, no existing receivable, and no cash posting; if record date is unknown, only provable never-held-before-event history can establish zero entitlement. Otherwise atomic stop. This is a proposal, not new enabled behavior.',
'Unknown pay date blocks any entitled cash path. No guessed payment date, invented receivable-only accounting, NET80 change, or historical cash benefit to new buyers.',
'Cash accrues only on actual recorded entitled holdings at the documented record date, respecting actual lots and rules. Pay only at documented pay date; no new buyer receives historical dividend.','Frozen net80 convention remains labeled research convention, never recast as official universal tax.','Splits, directed issuances, multi-component conflicts, missing facts, hash drift, lineage discontinuity or absent quotes trigger atomic stop before any same-day accounting/order commit.','All entries require explicit reviewed bounded admission manifest; strict runtime validates manifest and hashes without guessing.'],separate_capability_flags=['coordinate_continuity_verified','official_reference_verified','record_entitlement_verified','payment_verified','new_share_sellability_verified','historical_known_at_verified'],batch_workflow=['Inventory source-ready pure cash and reconcile existing official API/date facts in bulk.','Obtain targeted evidence only for unknown/conflicting dates or amounts and structural events.','Independent review and signed frozen fact manifest before any separately authorized execution.'])
schema['minimum_november_december_batch']=summary['november_december_2024']
schema['scope_note']='Explicit local action existence is not equivalent to merely allowlisting an economically complete event. All original action files lack record/pay/disclosure dates; only independently verified capability-specific facts can be reviewed for admission.'
payload=dict(summary=summary,rows=out,proposed_batch_fact_admission_schema=schema,source_hashes=hashes)
(O/'PREQUEUED_FACT_TIERS.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');(O/'PREQUEUED_FACT_TIERS_READOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='examples'},ensure_ascii=False,indent=2));print('EXAMPLES',[(r['sid'],r['date'],r['source_cash_per_share'],r['previous_raw_close'],r['source_bridge_residual'],r['source_bridge_pass'],r['known_dates']) for r in summary['examples']])
