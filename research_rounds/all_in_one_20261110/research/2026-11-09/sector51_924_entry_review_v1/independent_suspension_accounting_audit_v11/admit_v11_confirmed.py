from pathlib import Path
from decimal import Decimal as D
import json,hashlib,ast,importlib.util,sys
import pandas as pd
sys.dont_write_bytecode=True
A=Path(__file__).resolve().parent;O=A.parent;C=O/'joint51_candidate_v11_suspension_accounting';B=O/'joint51_candidate_v10_suspension_accounting';rd=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();checks=[];errors=[]
def ck(k,a,b,ctx=None):
 checks.append(k)
 if a!=b:errors.append(dict(check=k,actual=str(a),expected=str(b),context=ctx))
def asts(p):
 out={}
 for n in ast.parse(Path(p).read_text()).body:
  if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
  if isinstance(n,ast.ClassDef):
   for f in n.body:
    if isinstance(f,ast.FunctionDef):out[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
 return out
old=asts(B/'engine.py');new=asts(C/'engine.py');changed=sorted(k for k in old if old[k]!=new.get(k));ck('only_registry_and_checkpoint_changed',changed,['Data.__init__','Data.suspension','Engine.run']);ck('no_added_removed_economic_functions',set(old),set(new))
names=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END','SUSPENSION_EVENTS','PREFLIGHT_CHECKS'];prefix={}
for n in names:
 x=B/'full_20241031_once'/(n+'.json');y=C/'replay_20241028'/(n+'.json');ck('34_day_11_family_byte_exact',x.read_bytes(),y.read_bytes(),n);prefix[n]=dict(rows=len(rd(y)),sha256=sha(y))
pols=rd(C/'SUSPENSION_POLICY.json')['policies'];pmap={p['sid']:p for p in pols};ck('exact_two_distinct_policies',len(pols),len(pmap));ck('exact_policy_sids',set(pmap),{'300277.SZ','002064.SZ'});ck('old_policy_object_unchanged',pmap['300277.SZ'],rd(B/'SUSPENSION_POLICY.json'));p=pmap['002064.SZ'];dates=['2024-10-29','2024-10-30','2024-10-31'];ck('new_policy_dates_only',p['covered_dates'],dates);ck('known_from','2024-10-29',p['known_from_date']);ck('new_mark_day',p['mark_source_day'],'2024-10-28');ck('new_mark',p['raw_mark'],'8.11');ck('new_factor',p['factor'],'2.277636261313823');ck('fact_hash',sha(p['fact_envelope_path']),'6a33945b5190bfe0a7e6d0eb4bb4a1e346db0edde57a52ce54de7ac32fa4303c')
for pol in pols:
 for stem in ['source','official_notice','official_text','fact_envelope']:ck('policy_source_hash',sha(pol[stem+'_path']),pol[stem+'_sha256'],[pol['sid'],stem])
 ck('no_future_resume_field',any(k in pol for k in ['resume_date','future_resume_date','retrospectively_confirmed_resume_date']),False,pol['sid']);ck('no_future_decision_flag',pol['future_notices_or_resume_date_used_for_decisions'],False,pol['sid'])
fact=rd(p['fact_envelope_path'])
for path,h in fact.get('evidence_hashes',{}).items():ck('new_official_fact_evidence_hash',sha(path),h,path)
txt=''.join(Path(p['official_text_path']).read_text().split());ck('official_start_date_in_text','自2024年10月29日开市时起开始停牌。' in txt,True)
z=pd.read_parquet(p['source_path']);anchor=z.loc[pd.Timestamp('2024-10-28')];ck('raw_anchor_price',D(str(anchor.raw_close)),D('8.11'));ck('raw_anchor_factor',D(str(anchor.adjustment_factor)),D(p['factor']));ck('no_missing_bars_inserted',all(pd.Timestamp(d) not in z.index for d in dates),True)
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');k=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet',columns=['002064.SZ']);pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv[pv.sid.eq('002064.SZ')].set_index('day').state
for dt in pd.to_datetime(dates):ck('new_missing_days_remain_UNKNOWN',bool(k.at[dt,'002064.SZ']) and pd.notna(pv.get(dt)) and pv.get(dt)>=0,False,str(dt.date()))
ck('34_day_holding_811',sum(D(h['market_value']) for h in rd(B/'full_20241031_once/HOLDINGS.json') if h['sid']=='002064.SZ' and h['day']=='2024-10-28'),D(811));ck('combined_stale_2013',D(100)*(D(pmap['300277.SZ']['raw_mark'])+D(p['raw_mark'])),D(2013))
spec=importlib.util.spec_from_file_location('audit_v11_engine',C/'engine.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);fake=object.__new__(m.Data);fake.suspension_policies=json.loads(json.dumps(pols))
for sid,ds,expected in [('300277.SZ','2024-10-28',True),('002064.SZ','2024-10-28',False),('002064.SZ','2024-10-29',True),('002064.SZ','2024-11-01',False),('000001.SZ','2024-10-29',False)]:ck('registry_sid_and_date_exact',fake.suspension(sid,pd.Timestamp(ds)) is not None,expected,[sid,ds])
for pol in fake.suspension_policies:pol['future_resume_date']='2099-01-01'
ck('future_injected_date_ignored',fake.suspension('002064.SZ',pd.Timestamp('2024-11-01')),None)
for path,h in rd(C/'FREEZE.json')['hashes'].items():ck('all_8651_frozen_hashes',sha(path),h,path)
ck('author_37_tests_pass',rd(C/'SYNTHETIC_QA.json')['result'],'PASS');ck('author_test_count',len(rd(C/'SYNTHETIC_QA.json')['checks']),37)
report=dict(status='PASS_ADMISSION_AND_34_DAY_PREFIX' if not errors else 'FAIL',check_count=len(checks),errors=errors,changed_methods=changed,prefix=prefix,engine_sha256=sha(C/'engine.py'),freeze_sha256=sha(C/'FREEZE.json'),new_policy=p,test_wording_note='Initial audit asserted the shorter phrase 开市起停牌; official source instead states 自2024年10月29日开市时起开始停牌。 The exact original text was manually checked, and this corrected check matches it. No fact, policy or strategy was changed; original diagnostic is retained.',scope='Only the second official suspension is added. Engine accounting, fees, orders, queue, CP, I, rollback and valuation methods are AST-identical to independently audited v10. This auditor did not run history; late three days require output audit.')
pout=A/'ADMISSION_AND_PREFIX_CONFIRMED.json';assert not pout.exists();pout.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['prefix','new_policy']},ensure_ascii=False,indent=2))
