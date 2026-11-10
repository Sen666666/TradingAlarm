"""Freeze exact signal ACT/industry permission and compile, never project."""
from pathlib import Path
from collections import Counter
import gzip,hashlib,json,sys,time
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];PR=ROOT/'reentry_v1/funding_agent/private_projection'
sys.path.insert(0,str(OUT));from conditional_release_api import FrozenPermission,compile_conditional,load_complete_batches,P
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(OUT/n).write_text(json.dumps(P.serial(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def main():
 t=time.monotonic();batches=load_complete_batches();signal_days=sorted({str(i['clock'].decision_at.date())for _,xs,_ in batches.values()for i in xs});assert len(signal_days)==13
 source={str(Path(__file__)):sha(__file__),str(OUT/'conditional_release_api.py'):sha(OUT/'conditional_release_api.py'),str(OUT/'CONDITIONAL_RELEASE_CARD.txt'):sha(OUT/'CONDITIONAL_RELEASE_CARD.txt')}
 root=P.O/'runs/2025_26/pair';bookpath=root/'B.json.gz';source[str(bookpath)]=sha(bookpath)
 with gzip.open(bookpath,'rt')as f:book=json.load(f)
 decisions={d['at'][:10]:d for d in book['decisions']if d['at'][:10]in signal_days};assert len(decisions)==13
 upath=ROOT/'cash_release_v1/LEDGER_RECONSTRUCTION_AUDIT.json';u=read(upath);assert u['passed']and u['known_extra_U_zero_under_original_book']is True;source[str(upath)]=sha(upath)
 mpath=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json');manifest=read(mpath);assert len(manifest)==90;source[str(mpath)]=sha(mpath)
 dates={d:dict(ACT_on=decisions[d]['on'],ACT_source_at=decisions[d]['at'],sectors={})for d in signal_days};assert all(type(x['ACT_on'])is bool for x in dates.values())
 for item in manifest:
  p=Path(item['refs']['state']);h=sha(p);assert h==item['output_sha256'][str(p)];source[str(p)]=h
  f=pd.read_parquet(p,columns=['day','stage','stage_name','attempt_id','financial_state_owned']);f=f[f.day.astype(str).str[:10].isin(signal_days)]
  assert len(f)==13 and set(f.day.astype(str).str[:10])==set(signal_days)
  for row in f.itertuples(index=False):
   d=str(row.day)[:10];assert row.stage_name in['observe','probe','confirmed','expanded']and int(row.stage)==['observe','probe','confirmed','expanded'].index(row.stage_name)
   assert row.financial_state_owned is False or row.financial_state_owned==False
   dates[d]['sectors'][item['series']]=dict(stage_name=row.stage_name,stage_code=int(row.stage),attempt_id=None if pd.isna(row.attempt_id)else row.attempt_id,
    exact_source_day=d,source_path=str(p),financial_state_not_used_for_release=True)
 assert all(len(x['sectors'])==90 for x in dates.values())
 eventpath=root/'industry.jsonl.gz';source[str(eventpath)]=sha(eventpath);checks=0
 with gzip.open(eventpath,'rt')as f:
  for r in map(json.loads,f):
   if r['day']in dates:assert dates[r['day']]['sectors'][r['sector']]['stage_name']==r['market_stage'];checks+=1
 permission=dict(contract='ACT_on AND frozen signal industry confirmed/expanded; permission only releases cash buffer',known_extra_U_cny='0',dates=dates,
  stage_source='exact signal-day raw CP1 state, not financial level or sparse event fill',missing_or_unknown='STOP',buy_eligibility_not_changed=True)
 save('FROZEN_SIGNAL_PERMISSION.json',permission);gate=FrozenPermission(OUT/'FROZEN_SIGNAL_PERMISSION.json');rows=[]
 for day,(s,xs,at)in batches.items():
  a=P.AccountView(s)
  for i in xs:rows.append(dict(opening=day,key=P.B.bid(i),sid=i['sid'],role=i['role'],CP1_id=i.get('CP1_id'),**gate.describe(a,i,at)))
 save('ALL4172_FROZEN_RELEASE_ELIGIBILITY.json',rows);compiled=[];diff=[]
 for allocation in['native_singlepass','confirmed_min_first']:
  for mode in['reference_cash10','ACT_mature_U0']:
   bundle=compile_conditional(allocation,mode,gate);compiled.append(dict(allocation=allocation,mode=mode,sources=bundle['generated_sources'],source_diffs=bundle['source_diffs'],projection_calls=0));diff.append(allocation+' '+mode+'\n'+json.dumps(bundle['source_diffs'],ensure_ascii=False,indent=2))
 save('CONDITIONAL_COMPILED_SOURCES.json',compiled);(OUT/'CONDITIONAL_INTERFACE_SOURCE.diff').write_text('\n\n'.join(diff))
 schema=['opening','key','sid','role','CP1_id','rank','sector','signal_day','ACT_on','frozen_signal_industry_stage','cash_release_eligible','U_cny','old_order','new_order','quantity_delta','gross_delta','fee_delta','old_result','new_result','required_buffer_old','required_buffer_new']
 save('CONDITIONAL_OUTPUT_SCHEMA.json',dict(fields=schema,full_candidates=4172,rows_per_comparison=4172,main='A1-A0 native greedy conditional cash vs native greedy cash10',secondary='B1-B0 min-first conditional cash vs min-first cash10',interaction_separate=True,price_labels_not_computed=True))
 source[str(OUT/'FROZEN_SIGNAL_PERMISSION.json')]=sha(OUT/'FROZEN_SIGNAL_PERMISSION.json');source.update(P.source_hashes())
 for path in [PR/'OFF_IDENTITY.json',PR/'ON_COMPLETION.json',PR/'ON_ARTIFACT_SHA256.json']+[PR/('PREVIEWS_'+d+'.json')for d in batches]:source[str(path)]=sha(path)
 save('CONDITIONAL_SOURCE_SHA256.json',source);assert all(sha(p)==h for p,h in source.items())
 result=dict(prepared=True,signal_dates=13,sectors=90,permission_rows=1170,exact_event_market_stage_checks=checks,intents=4172,
  candidate_stage_counts=dict(Counter(r['frozen_signal_industry_stage']for r in rows)),eligible_intents=sum(r['cash_release_eligible']for r in rows),
  eligible_by_role=dict(Counter(r['role']for r in rows if r['cash_release_eligible'])),compiled_bindings=4,projection_calls=0,new_accounts=0,new_restores=0,seconds=time.monotonic()-t,
  conditional_card_ready_for_independent_review=True,old_hash_sources_not_modified=True)
 save('CONDITIONAL_PREPARATION.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
