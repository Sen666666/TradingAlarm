"""Full-universe additional source facts only; no strategy or admission execution."""
import json,pathlib,hashlib,re,collections
from decimal import Decimal as D
import pandas as pd
F=pathlib.Path(__file__).resolve().parent;R=F.parent;O=R/'mainline_m7_cash_batch_design_v7';O.mkdir(exist_ok=True);V5=R/'mainline_m7_cash_batch_design_v5';B=R/'mainline_m7_long_horizon_sealed_v2/once_20260630';hashes={};drift=[]
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def track(p,expected=None):
 p=str(p)
 if p not in hashes:hashes[p]=sha(p)
 if expected and hashes[p]!=expected:drift.append(p)
 return hashes[p]
def read(p):track(p);return json.loads(pathlib.Path(p).read_text())
inv=read(F/'Q1_UNIVERSE_INVENTORY.json');frozen=read(B/'SOURCE_HASHES.json');mp=next(p for p in frozen if p.endswith('/STOCK_MANIFEST.json'));manifest={m['symbol']:m for m in read(mp)};v5=read(V5/'EXACT_CASH_BATCH_MANIFEST.json');assert len(v5['events'])==19;old_v5_hash=hashes[str(V5/'EXACT_CASH_BATCH_MANIFEST.json')];allrows=[];blocked=[];good=[]
for r in inv['additional_purecash']:
 r=dict(r,action=r['actions'][0]['event'],local_action_ordinal=r['actions'][0]['ordinal'],event_id=r['sid']+'|LOCAL_DISTRIBUTION_'+str(r['actions'][0]['ordinal']).zfill(3),existing_official_rows=r['cached_exact_rows'])
 if not (F/'RAW_ADDITIONAL'/(r['sid']+'.json')).exists() and not r['existing_official_rows']:
  blocked.append(dict(sid=r['sid'],ex_date=r['ex_date'],reasons=['MISSING_OFFICIAL_RESPONSE'],acquisition_status='HTTP403_RETRY_DENIED' if r['sid']=='000728.SZ' else 'NOT_QUERIED_AFTER_SERVICE403_STOP',source_bridge_pass=r['source_bridge_pass']));continue
 sid,ex=r['sid'],r['ex_date'];m=manifest[sid];expected={**m['source_sha256'],**m['output_sha256']};sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));fp=m['refs']['facts'];cp=m['refs']['CP1'];paths=[sp,fp,cp,r['local_action_path']];eh={p:track(p,frozen.get(p,expected.get(p))) for p in paths};z=pd.read_parquet(sp).sort_index();prev=z[z.index<pd.Timestamp(ex)].iloc[-1];cur=z.loc[pd.Timestamp(ex)] if pd.Timestamp(ex) in z.index else None
 rawpath=F/'RAW_ADDITIONAL'/(sid+'.json')
 if not rawpath.exists():rawpath=pathlib.Path(r['existing_official_rows'][0]['path'])
 raw=read(rawpath);eh[str(rawpath)]=hashes[str(rawpath)];hits=[q for q in raw.get('raw',{}).get('records',[]) if q.get('F020D')==ex];fail=[]
 if len(hits)!=1:blocked.append(dict(sid=sid,ex_date=ex,reasons=['NONUNIQUE_OR_MISSING_OFFICIAL_EVENT'],count=len(hits)));continue
 q=hits[0];ds=D(r['action']['cash_per_old_share']);dc=D(str(q['F012N']))/10;fo=D(str(prev.adjustment_factor));fn=D(str(cur.adjustment_factor)) if cur is not None else D(0);pc=D(str(prev.raw_close));res=fo*pc/(pc-ds)/fn-1 if fn and pc>ds else None;origin=lambda row:tuple(str(row.get(k)) for k in ['source_kind','source_path','segment_id']);valid=lambda row:row is not None and all(pd.notna(row.get(k)) and row.get(k) in [True,1] for k in ['observed_bar','price_eligible','volume_eligible']) and all(pd.notna(row.get(k)) and row.get(k) in [False,0] for k in ['source_invalid','synthetic_event_bar']);amount=re.findall(r'10派([0-9.]+)元',q.get('F007V',''))
 checks=dict(unique_source_action=len([a for a in read(r['local_action_path'])['events'] if a['effective_date']==ex])==1,split_one=D(r['action']['split_ratio'])==1,official_pure_cash=all(q.get(k) in [None,0] for k in ['F010N','F011N']) and not any(w in q.get('F007V','') for w in ['送','转增','配股']),official_amount_text=len(amount)==1 and D(amount[0])/10==dc,exact_sid=raw.get('sid')==sid,official_endpoint=raw.get('endpoint')=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139',official_transport=raw.get('transport',{}).get('status_code')==200,dates_known=all(q.get(k) for k in ['F006D','F018D','F020D','F023D']),date_order=all(q.get(k) for k in ['F006D','F018D','F020D','F023D']) and q['F006D']<=q['F018D']<q['F020D']<=q['F023D'],record_is_previous=q.get('F018D')==str(prev.name.date()),previous_valid=bool(valid(prev)),current_valid=bool(valid(cur)),same_lineage=cur is not None and origin(prev)==origin(cur),factor_bridge=res is not None and abs(res)<D('1e-11'),dcash_bounds=D(0)<=dc<=ds)
 fail=[k for k,v in checks.items() if not v]
 coverage=read(r['local_action_path']).get('coverage_evidence',[])
 for c in coverage:
  eh[c['path']]=track(c['path'],c.get('sha256'));rr=read(c['path']);orig=rr.get('source_path')
  if orig and pathlib.Path(orig).exists():eh[orig]=track(orig,rr.get('source_sha256'))
 ev=dict(sid=sid,economic_event_id_candidate=r['event_id'],event_type='PURE_CASH',record_date=q.get('F018D'),ex_date=ex,pay_date=q.get('F023D'),disclosure_date=q.get('F006D'),known_at_precision='DATE_ONLY_NOT_PIT_OPEN',d_source=str(ds),d_cash=str(dc),d_ref=None,factor_old=str(fo),factor_new=str(fn),signal_path=sp,signal_sha256=eh[sp],local_action_path=r['local_action_path'],local_action_sha256=eh[r['local_action_path']],facts_path=fp,facts_sha256=eh[fp],cp1_path=cp,cp1_sha256=eh[cp],cached_response_annotation=dict(target_ex_date=raw.get('target_ex_date'),matches_current_event=raw.get('target_ex_date',ex)==ex,query_is_full_sid_history=raw.get('params',{}).get('scode')==sid[:6],original_response_unchanged=True,annotation_not_an_event_gate=True),primary_evidence=dict(kind='OFFICIAL_CNINFO_RAW',path=str(rawpath),sha256=eh[str(rawpath)],endpoint=raw['endpoint'],disclosure_date=q.get('F006D'),record=q),evidence_hashes=eh,holder_scope='INHERITED_ORDINARY_PUBLIC_CSDC_SHARES_RESEARCH_SCENARIO_NOT_SELF_DISTRIBUTED_HOLDERS',not_PIT=True,source_bridge=dict(previous_observation=str(prev.name.date()),previous_raw_close=str(pc),factor_old=str(fo),factor_new=str(fn),residual=str(res),origin_before=list(origin(prev)),origin_after=list(origin(cur)) if cur is not None else None,origin_hash_scope='Raw signal parquet and facts/CP1 bytes hashed; origin source_path is embedded lineage, not claim that present upstream file reconstructs historical bytes'),fact_predicate_checks=checks,blocked_reasons=fail,reference_bridge_status='SOURCE_COORDINATE_ONLY_D_REF_NULL',research_tax_model='FROZEN_NET80_UNCHANGED',local_action_ordinal=r['local_action_ordinal'])
 allrows.append(ev)
 if fail:blocked.append(dict(sid=sid,ex_date=ex,d_source=str(ds),d_cash=str(dc),cash_minus_source=str(dc-ds),reasons=fail))
 else:good.append(ev)
assert not drift,drift
assert len(allrows)+sum(b['reasons']==['MISSING_OFFICIAL_RESPONSE'] for b in blocked)==74
summary=dict(total_additional=74,official_unique_complete=sum(e['fact_predicate_checks']['dates_known'] for e in allrows),all_source_bridge_pass=sum(e['fact_predicate_checks']['factor_bridge'] for e in allrows),unchanged_loader_eligible=len(good),blocked=len(blocked),blocked_details=blocked,q1_eligible_candidate_count=len(good),all_universe_purecash=94,v6_inherited_q1=20,v6_files_untouched=True,no_history_run=True,no_admission=True)
(O/'Q1_ADDITIONAL_74_FACT_CANDIDATES.json').write_text(json.dumps(dict(summary=summary,events=allrows,source_hashes=hashes),ensure_ascii=False,indent=2)+'\n');(O/'Q1_ADDITIONAL_74_BLOCKERS.json').write_text(json.dumps(blocked,ensure_ascii=False,indent=2)+'\n')
merged=dict(schema='EXACT_2025_Q1_CASH_BATCH_RESEARCH_CANDIDATE',status='SOURCE_CANDIDATE_ONLY_NOT_ADMITTED',events=good,cash_model='UNCHANGED_NET80',q0_factor_only_enabled=False,blocked_additional=blocked,source_inventory_path=str(F/'Q1_UNIVERSE_INVENTORY.json'),source_inventory_sha256=hashes[str(F/'Q1_UNIVERSE_INVENTORY.json')])
(O/'Q1_EXACT_CASH_CANDIDATE_MANIFEST.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2)+'\n');(O/'Q1_ADDITIONAL_74_READOUT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n');track(pathlib.Path(__file__));(O/'Q1_ADDITIONAL_74_SOURCE_HASHES.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n');assert sha(V5/'EXACT_CASH_BATCH_MANIFEST.json')==old_v5_hash
print(json.dumps(summary,ensure_ascii=False,indent=2));print('candidate_manifest_sha256',sha(O/'Q1_EXACT_CASH_CANDIDATE_MANIFEST.json'))
