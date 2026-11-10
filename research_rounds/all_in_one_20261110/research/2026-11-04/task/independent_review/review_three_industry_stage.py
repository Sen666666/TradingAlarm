"""Read saved Stage/trace identities, never run CP1/Stage or import legacy modules."""
from pathlib import Path
import hashlib,json,math
import numpy as np,pandas as pd
O=Path('/Users/bytedance/Documents/Codex/2026-11-04/task/independent_review');P=O.parent/'risk_constraints/industry_stage_interface_v1';V=P/'dependency_fix_v2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def ident(*v):return hashlib.sha256(json.dumps(v,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
f=load(V/'SOURCE_FREEZE.json');done=load(V/'COMPLETED.json');failure=load(P/'FAILED.json');assert done['passed']and len(f['authorized_series'])==3
for p,h in f['all_input_sha256'].items():assert sha(p)==h
assert f['parent_freeze_sha256']==sha(P/'SOURCE_FREEZE.json')and f['parent_failure_sha256']==sha(P/'FAILED.json')
assert done['source_freeze_sha256']==sha(V/'SOURCE_FREEZE.json')and done['seconds']+failure['seconds']<30
reports=[];realids=set();neutralids=set()
for sid in f['authorized_series']:
 rr=f['series'][sid];rs=pd.read_parquet(V/(sid+'_REAL/Stage.parquet'));old=pd.read_parquet(rr['old_state']);pd.testing.assert_frame_equal(rs,old,check_exact=True,check_dtype=False,check_freq=False)
 q=pd.read_parquet(rr['neutral']['q']);cp=pd.read_parquet(rr['neutral']['CP1']);facts=pd.read_parquet(rr['neutral']['facts']);ns=pd.read_parquet(V/(sid+'_NEUTRAL/Stage.parquet'));ids=load(V/(sid+'_NEUTRAL/IDENTITY.json'));can=ids['canonical_series'];scale=ids['scale_id']
 assert can=='PREDICTIVE_VOLUME_NEUTRAL:'+f['neutral_method_identity']+':'+sid and scale=='CP1-predictive-volume-neutral:'+f['neutral_method_identity']
 assert not ids['financial_state_owned'] and not ns.financial_state_owned.any();assert list(ns.day)==[str(d.date())for d in q.index];assert ns.E0_valid.tolist()==facts.e0_target.astype(bool).tolist()
 # Derive Stage's own market-episode IDs solely from saved neutral boolean runs.
 ep=(q.e0_valid&~q.e0_valid.shift(fill_value=False)).cumsum();starts={k:str(g.index[0].date())for k,g in q.groupby(ep,sort=False)}
 expected=[ident('E0',can,str(x.segment_id),starts[ep.loc[d]])if x.e0_valid else None for d,x in q.iterrows()]
 assert [(None if pd.isna(x)else x)for x in ns.E0_episode]==expected
 # Trace uses a distinct original-E0 identity, also rebuilt from neutral runs.
 trace_ep={};previous=None;segment=None;cur=None
 for d,x in q.iterrows():
  seg=str(int(x.segment_id));obs=ident('price-observation',can,seg,str(d.date()))
  if seg!=segment:segment=seg;previous=None;cur=None
  target=bool(x.e0_valid)
  if not target:cur=None
  elif previous is False:cur=ident('original-E0-episode',can,seg,obs)
  elif previous is None:cur=None
  previous=target;trace_ep[str(d.date())]=cur
 receipts=load(V/(sid+'_NEUTRAL/TRACE_RECEIPTS.json'));assert len(receipts)==int(cp.receipt.sum())
 for r in receipts:
  day=r['confirmed_day'];d=pd.Timestamp(day);seg=str(r['source_segment']);obs=ident('price-observation',can,seg,day);anchor=ident('price-observation',can,seg,r['formation_start_exclusive'])
  assert r['original_E0_episode_id']==trace_ep[day]
  assert r['receipt_id']==ident('market-CP1-receipt',can,scale,seg,trace_ep[day],anchor,obs)
  assert r['original_credit']==float(cp.loc[d,'credit'])and r['original_candidate']==float(cp.loc[d,'candidate'])
  mask=(cp.index>pd.Timestamp(r['formation_start_exclusive']))&(cp.index<=d)&cp.delta_frontier.gt(0);adv=cp.loc[mask,'delta_frontier']
  triples=[(ident('price-observation',can,seg,str(k.date())),float(v),1.)for k,v in adv.items()]
  assert [x[0]for x in triples]==r['new_advance_price_event_ids']
  assert r['evidence_signature']==ident(can,seg,anchor,obs,triples)
  neutralids.add(r['receipt_id'])
 for r in load(V/(sid+'_REAL/TRACE_RECEIPTS.json')):realids.add(r['receipt_id'])
 reports.append(dict(sid=sid,real_fullwarm_state_rows_exact=len(old),neutral_own_episode_rows_checked=len(ns),neutral_receipt_ids_effective_m1_signatures_checked=len(receipts),saved_old_compact_receipt_reference_count=len(load(rr['old_receipts']))))
assert not realids&neutralids
prefix=load(V/'NEUTRAL_PHYSICAL_PREFIXES.json');assert {x['sid']for x in prefix}==set(f['authorized_series'])and all(x['cutoff']=='2024-09-23'for x in prefix)
x=dict(status='PASS_WITH_SCOPE_THREE_PURE_INDUSTRY_STAGE_AND_TRACE_INTERFACES_ONLY',input_SHA_checks=len(f['all_input_sha256']),series=reports,
 total_owner_seconds=done['seconds']+failure['seconds'],source_review='Original ident/norm/trace/Stage/run AST verbatim; environment has only requiredpureglobals and frozenCP1ge. Dependency-only v2 injects original stdlibcollections; source originalfailure retained. No COM/common/Account/Runner imports or copiedstatemachine.',
 neutral_identity_review='Ownneutral E0boolean episodes and trace receipt IDs rebuilt; allsavedneutral receipt evidence_signatures explicitly use peradvance effective m1, neverobserved CP1.m. Real/neutral namespaces disjoint.',
 physical_scope='Owner executed3NEUTRAL Sep23physical Stage/trace/increment prefixes; reviewer checked frozen comparator/source and fullreceipt, not rerunmodel/discardedprefixobjects.',
 limitations=['Only three preselected industries, not90industryfullbatch.','Old fullwarm Stage includesreceiptidentities independentlycompared; separate compactreceipt JSON oldreference only10/24/19savedauditdates, no fullwarmoldcompactclaim.','Pure market stage has no financiallevel/capacity/orders/ACTon or account performance.'],reviewer_new_model_or_account_runs=0,
 inputs={str(p):sha(p)for p in [P/'SOURCE_FREEZE.json',P/'FAILED.json',V/'SOURCE_FREEZE.json',V/'COMPLETED.json',V/'NEUTRAL_PHYSICAL_PREFIXES.json',V/'pure_stage_wrapper.py',V/'run_three_industry_once.py',Path(__file__)]})
(O/'VOLUME_THREE_INDUSTRY_STAGE_AUDIT.json').write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=x['status'],series=reports,seconds=x['total_owner_seconds'])))
