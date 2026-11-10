from pathlib import Path
from decimal import Decimal as D
import json,hashlib,ast
import pandas as pd
A=Path(__file__).resolve().parent;O=A.parent;C=O/'joint51_candidate_v10_suspension_accounting';B=O/'joint51_candidate_v9_facts';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=[];errors=[]
def ck(label,a,b,ctx=None):
 checks.append(label)
 if a!=b:errors.append(dict(check=label,actual=str(a),expected=str(b),context=ctx))
names=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END'];prefix={}
for n in names:
 old=B/'full_20241031_once'/(n+'.json');new=C/'replay_20241025'/(n+'.json');ck('prefix_byte_exact',old.read_bytes(),new.read_bytes(),n);prefix[n]=dict(rows=len(read(old)),sha256=sha(new))
ck('prefix_last_date',read(C/'replay_20241025/DAY_LEDGER.json')[-1]['day'],'2024-10-25');ck('prefix_no_suspension_log',read(C/'replay_20241025/SUSPENSION_EVENTS.json'),[]);ck('prefix_no_preflight_log',read(C/'replay_20241025/PREFLIGHT_CHECKS.json'),[])
pol=read(C/'SUSPENSION_POLICY.json');fact=read(pol['fact_envelope_path']);ck('fact_pinned_hash',sha(pol['fact_envelope_path']),'445535ff22e63c0d33dfba7e97abc7c4c5b1284a02ee6d047c58f101a2a2305a');ck('covered_security',pol['sid'],'300277.SZ');dates=['2024-10-28','2024-10-29','2024-10-30','2024-10-31'];ck('bounded_covered_dates',pol['covered_dates'],dates);ck('operational_policy_no_resume_date',any(k in pol for k in ['resume_date','future_resume_date','retrospectively_confirmed_resume_date']),False);ck('operational_future_notices_flag',pol['future_notices_or_resume_date_used_for_decisions'],False)
for key in ['source','official_notice','official_text','fact_envelope']:ck('policy_evidence_hash',sha(pol[key+'_path']),pol[key+'_sha256'],key)
txt=Path(pol['official_text_path']).read_text();compact=''.join(txt.split());ck('official_initial_notice_suspension_start','自2024年10月28日（星期一）开市起停牌' in compact,True);ck('merger_is_proposal',fact['transaction_is_proposal_not_effective_share_conversion'],True)
z=pd.read_parquet(pol['source_path']);anchor=z.loc[pd.Timestamp('2024-10-25')];ck('anchor_raw_close',D(str(anchor.raw_close)),D('12.02'));ck('anchor_factor',D(str(anchor.adjustment_factor)),D(pol['factor']));ck('no_raw_rows_inserted',all(pd.Timestamp(d) not in z.index for d in dates),True);ck('anchor_mark_total',D(100)*D(pol['raw_mark']),D('1202'))
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');k=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet',columns=['300277.SZ']);pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv[pv.sid.eq('300277.SZ')].set_index('day').state;states=[]
for ds in dates:
 dt=pd.Timestamp(ds);pvv=pv.get(dt,float('nan'));known=bool(k.at[dt,'300277.SZ']) and pd.notna(pvv) and pvv>=0;ck('original_common_known_remains_UNKNOWN',known,False,ds);states.append(dict(day=ds,known3=bool(k.at[dt,'300277.SZ']),pvr_state=float(pvv) if pd.notna(pvv) else None,common_known=bool(known),stock_state='UNKNOWN'))
def methods(p):
 out={}
 for n in ast.parse(Path(p).read_text()).body:
  if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
  if isinstance(n,ast.ClassDef):
   for f in n.body:
    if isinstance(f,ast.FunctionDef):out[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
 return out
old=methods(B/'engine.py');new=methods(C/'engine.py');changed=sorted(k for k in old if k in new and old[k]!=new[k]);added=sorted(set(new)-set(old));allowed=['Data.__init__','Engine.__init__','Engine.qvalue','Engine.net','Engine.economic_preflight','Engine.order','Engine.exit_open','Engine.alloc_open','Engine.close','Engine.run','Engine.export'];ck('only_reviewed_boundary_methods_changed',changed,sorted(allowed));ck('no_original_method_removed',set(old)-set(new),set())
for p,h in read(C/'FREEZE.json')['hashes'].items():ck('frozen_hash',sha(p),h,p)
qa=read(A/'INDEPENDENT_ADMISSION_TESTS.json');ck('independent_test_engine_hash_matches_frozen',qa['engine_sha256'],sha(C/'engine.py'));ck('independent_tests_pass',qa['status'],'PASS');ck('implementation_35_tests_pass',read(C/'SYNTHETIC_QA.json')['result'],'PASS')
report=dict(status='PASS_ADMISSION_AND_33_DAY_PREFIX' if not errors else 'FAIL',check_count=len(checks),errors=errors,reviewed_engine_sha256=sha(C/'engine.py'),reviewed_policy_sha256=sha(C/'SUSPENSION_POLICY.json'),reviewed_contract_sha256=sha(C/'FROZEN_CONTRACT.md'),prefix=prefix,changed_methods=changed,added_methods=added,original_missing_stock_states=states,static_review='Only valuation qvalue/mark is allowed to carry the 12.02 anchor. net and order fail for suspended assets; exits and alloc reject execution; CLOSE skips I/CP/price changes and may preserve a sector-only trial exit; active/pending preflight retains action/event/anchor guards; separate liquidation reporting excludes the nontradable asset. No future resume date controls the four-day policy.',scope='Independent admission and historical old-prefix reads. This auditor has not run the historical account. Four-day extension remains subject to actual-output accounting audit.')
p=A/'ADMISSION_AND_PREFIX.json';assert not p.exists();p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['prefix','original_missing_stock_states']},ensure_ascii=False,indent=2))
