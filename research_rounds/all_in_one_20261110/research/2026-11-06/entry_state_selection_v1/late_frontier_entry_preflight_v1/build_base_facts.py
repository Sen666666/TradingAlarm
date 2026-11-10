"""Reads saved facts only. No imports of any economic engine or project module."""
from pathlib import Path
import json,hashlib,ast,math
from collections import defaultdict
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent.parent; O=Path(__file__).resolve().parent;H={}
def src(p):
 p=Path(p);H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def csv(p,**kw):return pd.read_csv(src(p),**kw)
def par(p,**kw):return pd.read_parquet(src(p),**kw)
def js(p):return json.loads(src(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.strftime('%Y-%m-%d')
 if isinstance(x,float) and not math.isfinite(x):return None
 return x
def dump(n,x):
 with (O/n).open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def write(n,x):x.to_csv(O/n,index=False,mode='x')
def rootkey(sid,identity,day):return json.dumps([sid,identity,str(day)[:10]],ensure_ascii=False,separators=(',',':'))
src(O/'CONTRACT.md');src(__file__)
entry=csv(R/'price_entry_mechanism_comparison_v1/ENTRY_FACTS.csv',low_memory=False)
for k in ['signal_day','root_day']:entry[k]=entry[k].astype(str).str[:10]
start={2022:'2022-01-04',2024:'2024-09-02'}
# Complete market receipts and saved rolling20High only. No generation result is imported.
ovcols=['sid','name','industry','sector','day','window','identity','root_day','born','new_frontier','receipt','receipt_id','phase','confirmed_now','confirmed_at','C','Q','R','U','S_old','S_new','old_e0_target','old_i_target','old_i_buy','old_sector_known','old_sector_observed_today','old_sector_rs_ready_fresh','old_sector_up','old_AB_event_id','old_AB_event_type','old_ab_I_PVR_qualified_permit','old_PVR_score']
ov=par(R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet',columns=ovcols)
ov['day']=pd.to_datetime(ov.day).dt.strftime('%Y-%m-%d');ov['root_day']=pd.to_datetime(ov.root_day).dt.strftime('%Y-%m-%d')
m=ov[ov.window.isin(['2022','2024_924'])].copy();m['year']=m.window.map({'2022':2022,'2024_924':2024})
high=par(R/'price_entry_generation_gate_preflight_v1/RECEIPT_GATE_FACTS.parquet',columns=['sid','day','contemporary_prior20_high','current20_high_break']);high['day']=pd.to_datetime(high.day).dt.strftime('%Y-%m-%d')
m=m.merge(high,on=['sid','day'],validate='one_to_one');assert len(m)==37456
controls=csv(R/'reentry_evidence_identity_audit_v1/SAME_SIGNAL_AB_PRICE_CONTROLS.csv',low_memory=False).rename(columns={'signal_day':'day'})
m=m.merge(controls,on=['year','sid','day'],how='left',validate='one_to_one');assert m.price_request_id.notna().all()
# Parent existence uses actual saved target registration clock, not selected round IDs.
parents=[];allrounds=[];allbuys=[];common={};book_summary={}
for year in [2022,2024]:
 e=R/f'independent_channel_joint_economic_v1/economic_{year}'
 books=js(e/'EXECUTION_BOOKS.json');rounds=csv(e/'joint/ROUNDS.csv',low_memory=False);actions=csv(e/'joint/ACTIONS.csv',low_memory=False)
 rep=js(e/'COMPARISON_REPORT_RECOVERED.json');common[year]=set(rep['summary'][0]['common_covered_sids'])
 rounds['year']=year;allrounds.append(rounds)
 buys=actions[actions.side.eq('buy_core')].merge(rounds[['round_id','owner_lane','exit_day','price_root']],on='round_id',validate='one_to_one');buys['year']=year;allbuys.append(buys)
 for rid,b in books.items():
  p=b.get('parents',{}).get('Role.PROBE')
  if not p:continue
  t=p['target'];rt=t['root_id'];clock=t['registered_known_at'];parents.append(dict(year=year,root_key=rootkey(*rt),probe_round_id=rid,probe_parent_id=t['parent_id'],probe_registered_day=clock['day'],probe_registered_sequence=clock['sequence'],proxy_target_Q=t['target_Q'],proxy_filled_F=p['filled_F'],real_order_ACK_fill='UNKNOWN_NOT_PROVIDED'))
 book_summary[year]=dict(books=len(books),probe_parents=sum('Role.PROBE' in b.get('parents',{}) for b in books.values()))
p=pd.DataFrame(parents);assert not p.duplicated(['year','root_key']).any()
rr=pd.concat(allrounds,ignore_index=True);bb=pd.concat(allbuys,ignore_index=True);by_stock={k:g.sort_values('day') for k,g in bb.groupby(['year','sid'])}
m['root_key']=[rootkey(a,b,c) for a,b,c in zip(m.sid,m.identity,m.root_day)]
m=m.merge(p,on=['year','root_key'],how='left',validate='many_to_one')
m['proxy_parent_before_signal']=np.where(m.probe_registered_day.notna()&m.probe_registered_day.le(m.day),'EXISTING_PROXY_PROBE_PARENT','NO_PROXY_PROBE_PARENT')
m['real_zero_partial_parent_evidence']='UNKNOWN_NOT_PROVIDED'
m['prewindow_root_fact']=[d<start[y] for d,y in zip(m.root_day,m.year)]
m['common']=[s in common[y] for s,y in zip(m.sid,m.year)]
m['ticket_fact']=np.where(m.born,'ROOT_BIRTH',np.where(m.current20_high_break,'CONTINUING_BREAKS_CURRENT20HIGH','CONTINUING_NOT_CURRENT20HIGH'))
m['late_no_proxy_parent']=~m.born&m.proxy_parent_before_signal.eq('NO_PROXY_PROBE_PARENT')
prior=[]
for z in m.itertuples():
 g=by_stock.get((z.year,z.sid));g=g[g.day.astype(str).str[:10].le(z.day)] if g is not None else pd.DataFrame()
 if len(g):
  a=g.iloc[-1];ex=str(a.exit_day)[:10] if pd.notna(a.exit_day) else None
  if ex and ex<=z.day:rel='ROOT_BORN_AFTER_PREVIOUS_EXIT' if z.root_day>ex else 'ROOT_BORN_ON_PREVIOUS_EXIT_DAY' if z.root_day==ex else 'ROOT_ALREADY_EXISTED_AT_PREVIOUS_EXIT'
  else:rel='PREVIOUS_PROXY_BUY_NOT_FULLY_EXITED'
  prior.append(dict(prior_proxy_round_id=a.round_id,prior_proxy_owner=a.owner_lane,prior_proxy_buy_day=str(a.day)[:10],prior_proxy_exit_day=ex,window_participation_fact='PRIOR_PROXY_BUY',root_exit_relation_fact=rel))
 else:prior.append(dict(prior_proxy_round_id=None,prior_proxy_owner=None,prior_proxy_buy_day=None,prior_proxy_exit_day=None,window_participation_fact='NO_PRIOR_WINDOW_PROXY_BUY',root_exit_relation_fact='FIRST_WINDOW_PARTICIPATION'))
m=pd.concat([m.reset_index(drop=True),pd.DataFrame(prior)],axis=1)
q0=entry[entry.status.eq('PRECHECK_Q0_NO_SUBMIT')].copy();q0['root_key']=[rootkey(a,b,c) for a,b,c in zip(q0.sid,q0.identity,q0.root_day)]
q0map=q0.groupby(['year','root_key']).signal_day.min().to_dict();m['prior_q0_same_root_day']=[q0map.get((y,k)) if q0map.get((y,k),'9999')<d else None for y,k,d in zip(m.year,m.root_key,m.day)]
# Industry native market-stage source, never derived from M3.
manifest=js('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
native=[];source_rows=[]
for item in manifest:
 path=item['refs']['state'];s=par(path);assert H[path]==item['output_sha256'][path]
 s['sector']=item['series'];s['day']=pd.to_datetime(s.day).dt.strftime('%Y-%m-%d');s=s.rename(columns={c:'native_sector_'+c for c in s if c not in ['sector','day']});native.append(s)
 source_rows.append(dict(sector=item['series'],state_path=path,state_sha256=H[path],state_rows=len(s),first_day=s.day.min(),last_day=s.day.max(),receipt_json_path=item['refs']['receipts'],CP1_input_path=item['refs']['CP1_input'],CP1_path=item['refs']['CP1']))
native=pd.concat(native,ignore_index=True);assert not native.duplicated(['sector','day']).any()
m=m.merge(native,on=['sector','day'],how='left',validate='many_to_one')
breadth=par(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet',columns=['day','sector','M3_candidate','PVR3_candidate']);breadth.day=pd.to_datetime(breadth.day).dt.strftime('%Y-%m-%d');m=m.merge(breadth,on=['sector','day'],how='left',validate='many_to_one')
added=[c for c in m if c.startswith(('native_sector_','proxy_','probe_','prior_proxy_','real_zero_'))]+['root_key','prewindow_root_fact','late_no_proxy_parent','root_exit_relation_fact','window_participation_fact','prior_q0_same_root_day','ticket_fact']
ent=entry.merge(m[['year','sid','day']+added],left_on=['year','sid','signal_day'],right_on=['year','sid','day'],how='left',validate='one_to_one',suffixes=('','_saved_market'))
assert ent.root_key.notna().all();assert ent.proxy_parent_before_signal.eq('NO_PROXY_PROBE_PARENT').all()
fields=['E0_valid','E0_episode','stage','stage_before','action','authorization_usable','receipt','new_receipt'];fieldcheck=[]
for c in fields:
 a=ent['sector_'+c];b=ent['native_sector_'+c];same=(a.eq(b)|(a.isna()&b.isna()));assert same.all(),(c,ent.loc[~same,['sid','signal_day','sector_'+c,'native_sector_'+c]])
 fieldcheck.append(dict(field=c,entry_rows=len(ent),known=int(b.notna().sum()),identical=int(same.sum())))
assert (ent.actual_buy.eq(ent.probe_round_id.eq(ent.round_id))).all()
# A q0 round may have a later same-root first parent; this is not its own parent.
write('MARKET_RECEIPT_BASE_FACTS.csv',m);write('REGISTERED_ENTRY_BASE_FACTS.csv',ent);write('PROXY_PROBE_PARENTS.csv',p);write('NATIVE_SECTOR_SOURCE_COVERAGE.csv',pd.DataFrame(source_rows));write('NATIVE_FIELD_RECONCILIATION.csv',pd.DataFrame(fieldcheck));write('Q0_NO_PARENT_FACTS.csv',ent[ent.status.eq('PRECHECK_Q0_NO_SUBMIT')])
# Complete disjoint original-label tables. Original PnL is descriptive, not counterfactual.
def agg(g):
 z=g[g.full_closed];return dict(n_registered=len(g),n_proxy_buy=int(g.actual_buy.sum()),n_closed=len(z),n_unknown=int(g.status.str.contains('UNKNOWN').sum()),n_q0=int(g.status.eq('PRECHECK_Q0_NO_SUBMIT').sum()),n_no_buy=int((~g.actual_buy).sum()),old_closed_pnl_descriptive_only=float(z.closed_total_pnl.sum()),old_profit_n=int(z.closed_total_pnl.gt(0).sum()),old_loss_n=int(z.closed_total_pnl.lt(0).sum()))
tables=[];den=[];rawtables=[]
for y in [2022,2024]:
 for scope in ['ALL','COMMON']:
  g=ent[ent.year.eq(y)&(ent.common if scope=='COMMON' else True)];den.append(dict(year=y,scope=scope,**agg(g)))
  for cols in [['ticket_fact'],['ticket_fact','participation'],['ticket_fact','root_exit_relation_fact'],['ticket_fact','prewindow_root_fact'],['ticket_fact','native_sector_stage','native_sector_action','native_sector_new_receipt','native_sector_authorization_usable'],['ticket_fact','M3_entry','native_sector_authorization_usable']]:
   for key,z in g.groupby(cols,dropna=False):
    key=key if isinstance(key,tuple) else (key,);tables.append(dict(year=y,scope=scope,grouping='|'.join(cols),**dict(zip(cols,key)),**agg(z)))
  raw=m[m.year.eq(y)&(m.common if scope=='COMMON' else True)]
  for cols in [['ticket_fact','proxy_parent_before_signal'],['ticket_fact','proxy_parent_before_signal','window_participation_fact'],['ticket_fact','proxy_parent_before_signal','prewindow_root_fact']]:
   for key,z in raw.groupby(cols,dropna=False):rawtables.append(dict(year=y,scope=scope,grouping='|'.join(cols),**dict(zip(cols,key)),n_market_receipts=len(z),n_selected_PRICE=int(z.selected_lane.eq('PRICE').sum())))
write('ORIGINAL_LABEL_DESCRIPTIVE_TABLES.csv',pd.DataFrame(tables));write('RAW_RECEIPT_COUNTS.csv',pd.DataFrame(rawtables));dump('DENOMINATORS.json',den)
# Cases beyond ledger windows are signal-only and do not invent parent state.
casekeys=[('000977.SZ','2022-01-05'),('600100.SH','2022-01-04'),('002174.SZ','2022-11-08'),('605020.SH','2022-07-15'),('002031.SZ','2022-06-13'),('688660.SH','2024-09-25')]+[('002583.SZ','2024-09-'+d) for d in ['20','23','24','25']]+[('600396.SH','2024-10-28'),('002241.SZ','2024-09-30'),('002126.SZ','2024-12-25')]+[('300666.SZ',d) for d in ['2025-12-15','2025-12-17','2026-01-05','2026-01-15','2026-01-30','2026-02-02','2026-02-05']]
supp=csv(R/'price_entry_generation_gate_preflight_v1/supplement_v2/SUPPLEMENTAL_CASES.csv');supj=pd.DataFrame(js(R/'price_entry_generation_gate_preflight_v1/SUPPLEMENT_2025_2026_CASES.json'))
cases=[]
for sid,d in casekeys:
 z=m[m.sid.eq(sid)&m.day.eq(d)]
 if len(z):rec=z.iloc[0].to_dict();rec['case_source_status']='EXACT_ORIGINAL_WINDOW_MARKET_RECEIPT'
 else:
  z=ov[ov.sid.eq(sid)&ov.day.eq(d)]
  if len(z):rec=z.iloc[0].to_dict();rec['case_source_status']='EXACT_SIGNAL_ONLY_NO_ECONOMIC_WINDOW'
  else:
   z=supp[supp.sid.eq(sid)&supp.day.eq(d)];rec=z.iloc[0].to_dict() if len(z) else dict(sid=sid,day=d,name='江丰电子',sector='URFI881121');rec['case_source_status']='SAVED_SIGNAL_SUPPLEMENT' if len(z) else 'UNKNOWN_MISSING_SOURCE'
  ns=native[native.sector.eq(rec.get('sector','URFI881121'))&native.day.eq(d)]
  if len(ns):rec.update(ns.iloc[0].to_dict())
  if rec.get('sector') is None:rec['sector']='URFI881121'
  rec['proxy_parent_before_signal']='UNKNOWN_NO_ECONOMIC_WINDOW';rec['real_zero_partial_parent_evidence']='UNKNOWN_NOT_PROVIDED'
  hh=supj[supj.sid.eq(sid)&supj.day.eq(d)]
  if len(hh):
   for c in ['original_root_day','contemporary_prior20_high','current20_high_break']:rec[c]=hh.iloc[0].get(c)
  rec['root_day']=rec.get('root_day',rec.get('original_root_day'));rec['born']=rec.get('born',rec.get('root_day')==d if rec.get('root_day') else None)
 er=ent[ent.sid.eq(sid)&ent.signal_day.eq(d)]
 if len(er):
  for c in ['round_id','participation','entry_root_relation','status','entry_day','exit_day','actual_buy','full_closed','closed_total_pnl','PROBE_realized','ADD_realized','net80_income','common']:rec[c]=er.iloc[0][c]
 else:rec['original_round_status']='NO_SELECTED_PRICE_ROUND_ON_THIS_DAY'
 cases.append(rec)
write('FIXED_CASE_BASE_FACTS.csv',pd.DataFrame(cases))
# Guard source hashes; no economic importer was ever loaded.
seal=js(R/'independent_channel_joint_economic_v1/FINAL_RUN_SEAL.json')
for name,h in seal['code_sha256'].items():assert hashlib.sha256(src(R/'independent_channel_joint_economic_v1'/name).read_bytes()).hexdigest()==h
assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in H.items())
dump('BASE_SOURCE_HASHES.json',H);dump('BASE_QA.json',dict(market_receipts=len(m),registered_entries=len(ent),proxy_probe_parents=len(p),all_initial_entry_signal_clocks_have_no_existing_proxy_parent=True,real_zero_partial_evidence='UNKNOWN_NOT_PROVIDED',native_fields_exact=fieldcheck,sources_unchanged=True,economic_runs=0,filtered_pnl_runs=0,parameter_searches=0,raw_stock_reloads=0,book_summary=book_summary))
print(json.dumps(clean(den),ensure_ascii=False,indent=2));print('BASE_DONE',len(m),len(ent),len(p))
