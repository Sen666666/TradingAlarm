"""Read-only fixed case identity and one-day queue audit. No account replay."""
from pathlib import Path
import sys,json,hashlib,math,ast
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 p=Path(p);S[str(p)]=sha(p)
 if expected:assert S[str(p)]==expected,str(p)
 return p
def read(p):return json.loads(source(p).read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
W={'2022':B/'known_halt_contract_v1/cohort_2022_recovery_v2','2024_924':B/'indexed_execution_v1/cohort_2024_924'}
DAYS={'2022':['2022-01-05','2022-01-06','2022-01-07'],'2024_924':['2024-09-02','2024-09-24','2024-09-25','2024-09-26','2024-09-27','2024-09-30']}
datasets={};case_map={};qrows=[];daily=[]
def addcase(d,tag):
 if d['event_id'] not in case_map:case_map[d['event_id']]=dict(d,case_tags=[])
 case_map[d['event_id']]['case_tags'].append(tag)
for w,base in W.items():
 ds=read(base/'DECISIONS.json');au=read(base/'AUDIT.json');acts=read(base/'ACTIONS.json')
 dm={x['round_id']:x for x in ds if x.get('round_id')};am={x['round_id']:x for x in acts if x['side']=='buy_core'}
 reservations={x['round_id']:x for x in au if x['type'] in ['RESERVED','BUDGET_REJECTED'] and x['kind']=='INIT'}
 datasets[w]=(ds,au,acts,dm,am,reservations)
 for day in DAYS[w]:
  dd=[x for x in ds if x['day'].startswith(day)]
  pend=sorted([x for x in dd if x['decision']=='SELECTED_PENDING'],key=lambda x:(-x['PVR_score'],x['sid']))
  if not pend:daily.append(dict(window=w,signal_day=day,pending=0,original_fills=0));continue
  rr=[reservations.get(x['round_id']) for x in pend];od=next((x['day'][:10] for x in rr if x),None)
  for rank,d in enumerate(pend,1):
   r=reservations.get(d['round_id']);a=am.get(d['round_id'])
   qrows.append(dict(window=w,signal_day=day,open_day=od,event_id=d['event_id'],sid=d['sid'],name=d['name'],sector=d['sector'],PVR_score=d['PVR_score'],global_priority=rank,close_q=d['close_q'],original_proposed_q=r.get('before_shared_q') if r else None,original_reserved_q=r.get('shared_q') if r else None,original_fill_q=a['q'] if a else 0,last_reasons=r['trials'][-1]['reasons'] if r and r['trials'] else []))
  daily.append(dict(window=w,signal_day=day,open_day=od,events=len(dd),close_pass=sum(x.get('close_check')=='PASS' for x in dd),pending=len(pend),original_fills=sum(x['round_id'] in am for x in pend),rejected=sum(x and x['type']=='BUDGET_REJECTED' for x in rr),minimum_probe_risk=sum(bool(x and x['trials'] and 'probe_risk' in x['trials'][-1]['reasons']) for x in rr)))
  for d in sorted(pend,key=lambda x:x['sid'])[:2]:addcase(d,'fixed_day_first_two_sid_pending')
  for d in pend:
   if d['round_id'] in am:addcase(d,'all_original_actual_first_buys_on_fixed_days')
 # first three actually repeated stock buys, chronological then sid, regardless outcome
 seen=set();repeat=[]
 for a in sorted(am.values(),key=lambda x:(x['signal_day'],x['sid'])):
  if a['sid'] in seen:repeat.append(a)
  seen.add(a['sid'])
 for a in repeat[:3]:addcase(dm[a['round_id']],'first_three_actual_repeat_buys_not_selected_by_outcome')
 for sid,day in ([('300085.SZ','2024-09-12'),('300570.SZ','2024-09-25'),('000833.SZ','2024-09-26')] if w=='2024_924' else []):
  dd=next(x for x in ds if x['sid']==sid and x['day'].startswith(day));addcase(dd,'previously_fixed_right_tail_identity_only_no_old_label')
cases=sorted(case_map.values(),key=lambda x:(x['day'],x['sid']))
pd.DataFrame(cases).to_csv(O/'FIXED_CASE_IDENTITIES.csv',index=False)
pd.DataFrame(qrows).to_csv(O/'FIXED_DAILY_ORIGINAL_QUEUES.csv',index=False)
pd.DataFrame(daily).to_csv(O/'FIXED_DAILY_FUNNEL.csv',index=False)
save('CASE_SELECTION_SEAL.json',dict(case_rows=len(cases),source_hashes=S.copy(),no_new_features_yet=True,no_new_order_or_outcome=True))
mm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
FORM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py')
env={'np':np,'pd':pd};exec(compile(source(FORM).read_text(),str(FORM),'exec'),env);score=env['score']
sys.path[:0]=[str(M/'pv-strength-b5-20261025/code'),str(M/'b5-g1-20261025/code'),str(M/'pv-participation-response-20261020/code')]
from policy import e0_policy
from policies_g1 import project
from data_utils import eligible_prices
for p in [M/'pv-strength-b5-20261025/code/policy.py',M/'b5-g1-20261025/code/policies_g1.py',M/'pv-participation-response-20261020/code/data_utils.py']:source(p)
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
with np.load(source(H),allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
def native(b,ev,st,x):
 valid=eligible_prices(b);assert valid.index.equals(x.index)
 for c in ['open','high','low','close','volume','segment_id']:np.testing.assert_equal(x[c].to_numpy(),valid[c].to_numpy())
 e=x[['segment_id','open','high','low','close','volume']].copy()
 e['valid_price_observation']=True;e['price_observation']=e.groupby('segment_id',sort=False).cumcount()
 e['event']=ev.event;e['confirmed_pivot_price']=ev.confirmed_pivot_price;e['ready']=st.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
 v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0));e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
 for c in ['volume_ratio','high_effort','declined']:e[c]=st[c]
 e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
 base,_=e0_policy(e);g=x[['grade','strength_ready','fresh_up','acute_down']].rename(columns={'strength_ready':'ready'})
 return project(e,base,g,'G1_I'),base
features=[];terms=[];qa=[]
for sid in sorted({x['sid'] for x in cases}):
 cs=[x for x in cases if x['sid']==sid];m=mm[sid];cut=max(x['day'][:10] for x in cs)
 paths={k:next(p for p in m['source_sha256'] if p.endswith('/'+k+'.parquet')) for k in ['signal','events','states']}
 px=next(p for p in m['source_sha256'] if '/ix-a-share-entry-' in p)
 b=pd.read_parquet(source(paths['signal'],m['source_sha256'][paths['signal']])).loc[:cut]
 ev=pd.read_parquet(source(paths['events'],m['source_sha256'][paths['events']])).loc[:cut]
 st=pd.read_parquet(source(paths['states'],m['source_sha256'][paths['states']])).loc[:cut]
 x=pd.read_parquet(source(px,m['source_sha256'][px])).loc[:cut]
 f=pd.read_parquet(source(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])).loc[:cut]
 cp=pd.read_parquet(source(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])).loc[:cut]
 n,base=native(b,ev,st,x)
 for a,c in [('target','i_target'),('floor','i_floor'),('buy_event','i_buy')]:
  np.testing.assert_allclose(n[a].to_numpy(float),f[c].to_numpy(float),rtol=0,atol=0,equal_nan=True)
 pv=score(b);valid=pv.e.notna();weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 for d in cs:
  t=pd.Timestamp(d['day']);row={k:d.get(k) for k in ['event_id','window','sid','name','sector','PVR_score','decision','round_id']};row.update(signal_day=t,case_tags='|'.join(d['case_tags']))
  nf=n.loc[:t];active=nf.iloc[-1];entries=nf.index[nf.entered.eq(1)]
  if not len(entries) or active.target!=1:
   row['identity_status']='UNKNOWN_NO_CURRENT_ORIGINAL_ENTERED';features.append(row);continue
  birth=entries[-1];assert nf.loc[birth:,'target'].eq(1).all()
  exits=nf.loc[:birth].index[nf.loc[:birth,'exited'].eq(1)];previous_exit=exits[-1] if len(exits) else None
  priorentries=entries[entries<birth];previous_birth=priorentries[-1] if len(priorentries) else None
  earlier=nf.index[nf.index<birth];assert len(earlier) and nf.loc[earlier[-1],'target']==0
  assert np.isclose(pv.at[t,'score'],d['PVR_score'],atol=1e-10,rtol=0)
  # Original terms are observation-based; missing common days are separately disclosed.
  loc=b.index.get_loc(t);idx=b.index[loc-20:loc+1];p=pv.reindex(idx);assert len(p)==21 and p.e.notna().all()
  en=(weights*p.e.to_numpy()).sum();assert abs(en-pv.at[t,'E'])<1e-12
  rootpos=b.index.get_loc(birth);sum_pre=sum_cur=sum_previous=sum_inactive=0.;pos_pre=pos_total=0.;negative_pre=0.;fullnew=0
  for j,(dt,ww,ee) in enumerate(zip(idx,weights,p.e.to_numpy())):
   bi=b.index.get_loc(dt);v=float(ww*ee);pre=dt<birth
   category='CURRENT_I'
   if pre:category='PREVIOUS_I' if previous_birth is not None and previous_birth<=dt<(previous_exit if previous_exit is not None else birth) else 'I_INACTIVE_TRANSITION' if previous_exit is not None and previous_exit<=dt<birth else 'OLDER_OR_UNKNOWN_I'
   if pre:sum_pre+=v;pos_pre+=max(0,v);negative_pre+=min(0,v)
   else:sum_cur+=v
   if category=='PREVIOUS_I':sum_previous+=v
   if category=='I_INACTIVE_TRANSITION':sum_inactive+=v
   pos_total+=max(0,v);fullnew+=bi-64>=rootpos
   terms.append(dict(event_id=d['event_id'],term_day=dt,weight=ww,r=pv.at[dt,'r'],scale=pv.at[dt,'scale'],amount_reference=pv.at[dt,'amount_ref'],u=pv.at[dt,'u'],b=pv.at[dt,'b'],e=ee,weighted_e=v,term_native_I_category=category,return_input_start=b.index[bi-1],scale_price_support_start=b.index[bi-64],amount_support_start=b.index[bi-21],full_raw_support_at_or_after_original_I_entered=bi-64>=rootpos))
  common=cal[(cal>=birth)&(cal<=t)];missing=common.difference(nf.index)
  known_ev=ev.loc[:t];piv=known_ev[known_ev.event.ne(0)&known_ev.event.notna()].iloc[-1]
  row.update(identity_status='ORIGINAL_PROJECT_ENTERED_REGENERATED_EXACT',original_I_entered=birth,original_previous_I_entered=previous_birth,original_previous_I_exited=previous_exit,I_age_observations=nf.index.get_loc(t)-nf.index.get_loc(birth),I_episode_common_gap_count=len(missing),native_event_confirmation_day=known_ev[known_ev.event.ne(0)&known_ev.event.notna()].index[-1],native_confirmed_pivot_day=piv.confirmed_pivot_date,price_at_signal=float(f.at[t,'close']),I_floor=float(f.at[t,'i_floor']),CP_receipt=bool(cp.at[t,'receipt']),i_buy=bool(f.at[t,'i_buy']),E=float(en),E_pre_current_I=sum_pre,E_current_I=sum_cur,E_previous_I=sum_previous,E_inactive_transition=sum_inactive,positive_e_share_before_current_I=pos_pre/pos_total if pos_total else None,negative_e_before_current_I=negative_pre,terms_before_current_I=sum(idx<birth),terms_entire_raw_support_after_current_I=fullnew,earliest_PVR_raw_price_support=b.index[loc-84])
  if t==pd.Timestamp(cs[0]['day']):
   npv=score(b.loc[:t]);pd.testing.assert_frame_equal(npv,pv.loc[:t],check_exact=True)
   nn,nb=native(b.loc[:t],ev.loc[:t],st.loc[:t],x.loc[:t]);pd.testing.assert_frame_equal(nn,n.loc[:t],check_exact=True)
  features.append(row)
 qa.append(dict(sid=sid,native_I_rows=len(n),native_I_target_floor_buy_exact=True,PVR_fixed_case_scores_exact=True,first_case_physical_prefix_exact=True))
pd.DataFrame(features).sort_values(['signal_day','sid']).to_csv(O/'FIXED_SIGNAL_CREDIT_FEATURES_PRELABEL.csv',index=False)
pd.DataFrame(terms).to_csv(O/'PVR_21_TERM_PROVENANCE.csv',index=False)
save('FEATURE_SEAL.json',dict(feature_sha256=sha(O/'FIXED_SIGNAL_CREDIT_FEATURES_PRELABEL.csv'),terms_sha256=sha(O/'PVR_21_TERM_PROVENANCE.csv'),no_score_changes=True,no_new_fills=True,no_new_economics=True))
# Link only actual original shared-account labels; rejected candidates stay unlabelled.
ll=[]
for w,base in W.items():
 ls={x['round_id']:x for x in read(base/'LAYER_REPORT.json') if x['layer']=='core'}
 ds,au,acts,dm,am,res=datasets[w]
 for row in features:
  if row['window']!=w:continue
  rid=row.get('round_id');a=am.get(rid);l=ls.get(rid) if a else None
  ll.append(dict(row,original_actual_shared_fill=bool(a),original_buy_day=a['day'] if a else None,original_buy_q=a['q'] if a else None,original_core_status=l.get('layer_status') if l else None,original_core_NET80=l.get('NET80') if l else None,original_core_return=l.get('return_on_layer_buy_cash') if l else None))
pd.DataFrame(ll).to_csv(O/'FIXED_CASES_WITH_ORIGINAL_SHARED_LABELS.csv',index=False)
assert all(sha(p)==v for p,v in S.items())
save('SOURCE_SHA256.json',S);save('QA.json',dict(cases=len(cases),terms=len(terms),stocks=len(qa),native_exact_rows=sum(q['native_I_rows'] for q in qa),checks=qa,source_sha256_unchanged=True,account_replays=0,parameter_searches=0,model_fits=0,changed_scores=0,new_fills=0))
print(pd.DataFrame(daily).to_string(index=False))
print(pd.DataFrame(ll)[['signal_day','sid','name','I_age_observations','terms_before_current_I','E_pre_current_I','E_current_I','positive_e_share_before_current_I','original_actual_shared_fill','original_core_return']].to_string(index=False))
