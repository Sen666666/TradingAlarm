"""Join original daily score/qualification tables at root-frozen dates. No scores/eligibility/account recomputation."""
from pathlib import Path
import json,collections,hashlib,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=B/'universe-cp1-inputs-20261031';start=time.monotonic()
D=json.loads((O/'FROZEN_DATES.json').read_text());DATES=D['root_frozen_dates'];EARLY=D['first_delivery_dates'];NEXT=D['next_original_calendar_sessions'];SHA=json.loads((O/'EARLY_SOURCE_SHA256.json').read_text())
def load(p):
 p=Path(p);b=p.read_bytes();SHA[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def lines(n):return [json.loads(x) for x in (O/('ORIGINAL_'+n+'.jsonl')).read_text().splitlines()]
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 if isinstance(x,pd.Timestamp):return str(x.date())
 return x
def dump(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
SM=load(U/'STOCK_MANIFEST.json');IM=load(U/'INDUSTRY_MANIFEST.json');meta=load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');ops={(r['day'],r['sid']):r for r in lines('OPPORTUNITIES') if r.get('account')=='B'};rp={(r['day'],r['sid']):r for r in lines('RANK_POLICY') if r.get('account')=='B'}
PM={'long':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'),'strong':B/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json'};pms={k:{r['symbol']:r for r in load(p)['entries']} for k,p in PM.items()}
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');h=np.load(H);hd=pd.DatetimeIndex(h['dates']);hs=h['symbols'].astype(str);hv=h['score'];di={str(t.date()):i for i,t in enumerate(hd)};si={s:i for i,s in enumerate(hs)}
fund=collections.defaultdict(list)
for r in lines('FUNDING'):
 if r.get('account','B')=='B':fund[(r['at'][:10],r['sid'])].append(r)
rows=[];errors=[];proof=[]
for n,x in enumerate(SM,1):
 sid=x['symbol'];f=pd.read_parquet(x['refs']['facts']);cp=pd.read_parquet(x['refs']['CP1'],columns=['ready','receipt','candidate','anchor','frontier','scale','reset_reason']);scores={}
 for w,p in PM.items():
  sp=p.parent/'scores'/(sid+'.parquet');actual=hashlib.sha256(sp.read_bytes()).hexdigest();SHA[str(sp)]=actual
  if actual!=pms[w][sid]['output_sha256']:errors.append({'sid':sid,'error':'PVR_score_hash_diff','window':w})
  scores[w]=pd.read_parquet(sp)
 for d in DATES:
  t=pd.Timestamp(d);op=ops.get((d,sid));r=rp.get((d,sid));which='strong' if d.startswith('2026') else 'long';sf=scores[which]
  r0={'date':d,'sid':sid,'name_static':meta[sid]['name'],'sector_static':meta[sid]['sector_id'],'industry_static':meta[sid]['industry'],'pool_scope':'2026-10-22_static_1709','pool_and_membership_PIT_verified':False,'original_opportunity_saved':op is not None,'original_H1_rank0':op.get('rank') if op else None,'H1_cache_score':hv[di[d],si[sid]],'H1_score_known':bool(np.isfinite(hv[di[d],si[sid]])),'PVR_cache_score':sf.at[t,'score'] if t in sf.index else None,'PVR_cache_ref':str(PM[which].parent/'scores'/(sid+'.parquet')),'facts_ref':x['refs']['facts'],'CP_ref':x['refs']['CP1'],'H1_ref':str(H),'fact_exact_date_present':t in f.index,'CP_exact_date_present':t in cp.index,'original_core_Q':op.get('core_Q') if op else None,'original_mobile_Q':op.get('mobile_Q') if op else None,'original_CP1_id':op.get('CP1_id') if op else None,'original_held':op.get('held') if op else None,'original_roles_json':json.dumps(op.get('roles'),ensure_ascii=False) if op else None,'original_barriers_json':json.dumps(op.get('barriers'),ensure_ascii=False) if op else None,'source_Q_core_or_CP_mobile':bool(op and (op.get('core_Q') is True or (op.get('CP1_id') and op.get('mobile_Q') is True))),'original_account_pre_size_roles_no_barriers':bool(op and op.get('roles') and not op.get('barriers')),'actual_native_pending':r is not None,'actual_native_pending_slot0':r.get('final_slot') if r else None,'actual_native_original_slot0':r.get('original_slot') if r else None,'actual_priority_rank_H1_slot_key':r.get('priority_rank') if r else None,'actual_pending_roles_json':json.dumps(r.get('roles'),ensure_ascii=False) if r else None,'CLOSE_size_rejections_json':json.dumps([a for a in fund.get((d,sid),[]) if a['at'][11:16]=='15:10'],ensure_ascii=False),'next_original_OPEN_date':NEXT[d],'next_OPEN_funding_verbatim_json':json.dumps([a for a in fund.get((NEXT[d],sid),[]) if a['at'][11:16]=='09:30'],ensure_ascii=False)}
  pos=f.index.searchsorted(t,side='right')-1
  if pos>=0:
   r0['facts_row_asof_source_date']=str(f.index[pos].date())
   for k,v in f.iloc[pos].to_dict().items():r0['fact_'+k]=v
  else:r0['facts_row_asof_source_date']=None
  if t in cp.index:
   for k,v in cp.loc[t].to_dict().items():r0['CP_'+k]=v
   if bool(cp.at[t,'receipt'])!=bool(op and op.get('CP1_id')):errors.append({'sid':sid,'date':d,'error':'original_CP_flag_vs_saved_opportunity_canonical_ID_presence_diff'})
  if r:
   v=r.get('PVR');v2=r0['PVR_cache_score'];eq=(v is None and (v2 is None or pd.isna(v2))) or (v is not None and v2 is not None and v==v2)
   proof.append({'sid':sid,'date':d,'actual_pending_PVR_equals_cache':bool(eq)})
   if not eq:errors.append({'sid':sid,'date':d,'error':'original_pending_PVR_vs_cache_diff'})
  rows.append(clean(r0))
 if n%400==0:print('JOINED',n,'rows',len(rows),'seconds',round(time.monotonic()-start,2),flush=True)
F=pd.DataFrame(rows);F['PVR_known']=np.isfinite(pd.to_numeric(F.PVR_cache_score,errors='coerce'))
Hproof=[]
for d in DATES:
 g=F[F.date==d];expected=sorted(g.sid,key=lambda s:(-hv[di[d],si[s]] if np.isfinite(hv[di[d],si[s]]) else 1.,s));actual=sorted([r for (dd,_),r in ops.items() if dd==d],key=lambda r:r['rank']);actual=[r['sid'] for r in actual]
 Hproof.append({'date':d,'packet_opportunity_count':len(actual),'H1_cache_stock_count':len(g),'original_order_matches_cached_H1_desc_sid_ties':expected==actual})
 if expected!=actual:errors.append({'date':d,'error':'H1_original_order_vs_cache_sort_diff','mismatched_positions':sum(a!=b for a,b in zip(expected,actual))})
 # Inventory numeric order only: not a replay of native pending slot substitution.
 valid=g[g.PVR_known].copy();valid['rounded_sort_score']=valid.PVR_cache_score.round(12);order=valid.sort_values(['rounded_sort_score','original_H1_rank0','sid'],ascending=[False,True,True]).index
 F.loc[order,'inventory_PVR_numeric_order0']=np.arange(len(order))
 for flag,col in [('source_Q_core_or_CP_mobile','source_Q_PVR_numeric_order0'),('original_account_pre_size_roles_no_barriers','pre_size_account_PVR_numeric_order0')]:
  sub=g[g[flag]&g.PVR_known].copy();sub['rounded_sort_score']=sub.PVR_cache_score.round(12);o=sub.sort_values(['rounded_sort_score','original_H1_rank0','sid'],ascending=[False,True,True]).index;F.loc[o,col]=np.arange(len(o))
F=F.sort_values(['date','original_H1_rank0','sid']);F.to_csv(O/'ALL_STATIC_STOCKS_FACTS_H1_PVR.csv',index=False);F.to_parquet(O/'ALL_STATIC_STOCKS_FACTS_H1_PVR.parquet',index=False)
views=[]
for name,mask,sortcol in [('H1_ALL_PACKET',F.original_opportunity_saved,'original_H1_rank0'),('PVR_ALL_STATIC_NUMERIC_INVENTORY',F.PVR_known,'inventory_PVR_numeric_order0'),('H1_SOURCE_Q_CANDIDATES',F.source_Q_core_or_CP_mobile,'original_H1_rank0'),('PVR_SOURCE_Q_CANDIDATES_NUMERIC_VIEW',F.source_Q_core_or_CP_mobile&F.PVR_known,'source_Q_PVR_numeric_order0'),('H1_ORIGINAL_ACCOUNT_PRE_SIZE_CANDIDATES',F.original_account_pre_size_roles_no_barriers,'original_H1_rank0'),('PVR_ORIGINAL_ACCOUNT_PRE_SIZE_NUMERIC_VIEW',F.original_account_pre_size_roles_no_barriers&F.PVR_known,'pre_size_account_PVR_numeric_order0'),('ACTUAL_NATIVE_PENDING_PVR',F.actual_native_pending,'actual_native_pending_slot0')]:
 sub=F[mask].sort_values(['date',sortcol,'sid']);sub.to_csv(O/(name+'_ALL.csv'),index=False)
 top=sub.groupby('date',sort=False).head(20).copy();top['view']=name;top['view_sort_column']=sortcol;top.to_csv(O/(name+'_TOP20.csv'),index=False);views.append(top)
pd.concat(views,ignore_index=True).to_csv(O/'ALL_SEVEN_VIEWS_TOP20.csv',index=False)
F[F.date.isin(EARLY)&F.name_static.str.contains('海能达|银之杰|江丰|珂玛|金海通|盈新')].to_csv(O/'EARLY_THREE_FOCAL_JOINED.csv',index=False)
industry=pd.read_csv(O/'INDUSTRY_H1_ALL90.csv');ir=[]
for x in IM:
 p=Path(x['refs']['state']);f=pd.read_parquet(p).set_index('day');q=pd.read_parquet(x['refs']['CP1_input'])
 for d in DATES:
  r={'date':d,'sector':x['series'],'state_exact_present':d in f.index,'CP_input_exact_present':pd.Timestamp(d) in q.index,'state_ref':str(p),'CP_input_ref':x['refs']['CP1_input']}
  if d in f.index:
   for k,v in f.loc[d].to_dict().items():r['industry_state_'+k]=v
  if pd.Timestamp(d) in q.index:
   for k,v in q.loc[pd.Timestamp(d)].to_dict().items():r['industry_CP_input_'+k]=v
  ir.append(clean(r))
I=industry.merge(pd.DataFrame(ir),on=['date','sector'],validate='one_to_one');I.to_csv(O/'INDUSTRY_H1_E0_CP_STATE_ALL90.csv',index=False)
summary=[]
for d,g in F.groupby('date',sort=True):
 summary.append({'date':d,'static_stocks':len(g),'H1_known':int(g.H1_score_known.sum()),'PVR_known':int(g.PVR_known.sum()),'facts_exact_day':int(g.fact_exact_date_present.sum()),'facts_asof_available':int(g.facts_row_asof_source_date.notna().sum()),'CP_exact_day':int(g.CP_exact_date_present.sum()),'CP_receipts':int(g.CP_receipt.eq(True).sum()),'canonical_ID_missing_among_original_CP':int((g.CP_receipt.eq(True)&g.original_CP1_id.isna()).sum()),'core_Q_true':int(g.original_core_Q.eq(True).sum()),'mobile_Q_true':int(g.original_mobile_Q.eq(True).sum()),'source_Q_core_or_CP_mobile':int(g.source_Q_core_or_CP_mobile.sum()),'account_pre_size_roles_no_barriers':int(g.original_account_pre_size_roles_no_barriers.sum()),'actual_pending_unique_stocks':int(g.actual_native_pending.sum()),'held_stocks':int(g.original_held.eq(True).sum())})
pd.DataFrame(summary).to_csv(O/'COUNTS_BY_FROZEN_DATE.csv',index=False)
dump('ORIGINAL_H1_AND_PVR_CACHE_EXACTNESS.json',{'H1_order_all_dates_exact':all(x['original_order_matches_cached_H1_desc_sid_ties'] for x in Hproof),'H1_order_checks':Hproof,'actual_pending_PVR_cells':len(proof),'actual_pending_PVR_all_exact':all(x['actual_pending_PVR_equals_cache'] for x in proof),'PVR_checks':proof});dump('SOURCE_SHA256.json',SHA);dump('AUDIT_ERRORS.json',errors)
print('COUNTS',pd.DataFrame(summary).to_json(orient='records'),flush=True);print('COMPLETE',len(F),'rows','errors',len(errors),'H1exact',all(x['original_order_matches_cached_H1_desc_sid_ties'] for x in Hproof),'PVRexact',all(x['actual_pending_PVR_equals_cache'] for x in proof),'seconds',time.monotonic()-start,flush=True)
