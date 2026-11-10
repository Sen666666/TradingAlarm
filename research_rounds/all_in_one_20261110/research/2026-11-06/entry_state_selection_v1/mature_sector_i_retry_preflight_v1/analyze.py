from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np,json,gzip,hashlib,sys,collections
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;T=R/'technology_winrate_scope_audit_v1';C=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');hs={}
def h(p):
 p=Path(p);hs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def js(p):return json.loads(h(p).read_text())
def pq(p,**kw):return pd.read_parquet(h(p),**kw)
def csv(p,**kw):return pd.read_csv(h(p),**kw)
def out(n,x):
 def conv(v):
  if isinstance(v,dict):return {str(k):conv(w) for k,w in v.items()}
  if isinstance(v,(list,tuple)):return [conv(w) for w in v]
  if isinstance(v,(np.integer,)):return int(v)
  if isinstance(v,(np.bool_,)):return bool(v)
  if isinstance(v,(pd.Timestamp,D)):return str(v)
  if isinstance(v,(float,np.floating)) and not np.isfinite(v):return None
  return v
 (O/n).write_text(json.dumps(conv(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
protocol=js(O/'PROTOCOL.json');out('FREEZE.json',dict(protocol_sha256=hs[str(O/'PROTOCOL.json')],code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),history_seen=True,account_runs=0))
old=csv(T/'OLD_TECH_A_2024_FALL_ENTRIES.csv');roster=csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');manifest={x['symbol']:x for x in js(U/'STOCK_MANIFEST.json')}
panel=pq(C/'COMMON_K_COMPARISON.parquet').sort_values(['sector','day']);panel['previous_S']=panel.groupby('sector').M3_candidate.shift();panel=panel.set_index(['sector','day'])
rr=pd.concat([pq(C/'WARM_PREFIX_M_R.parquet'),pq(C/'RIGHT3.parquet')]).sort_index();kk=pd.concat([pq(C/'WARM_PREFIX_M_K.parquet'),pq(C/'KNOWN3.parquet')]).sort_index();ms=rr.astype('int8').where(kk,-1);pm=ms.shift();cal=rr.index;pv=pq(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['sid','day'])
facts={};ix={};cps={};raws={};caps={}
def load(sid,raw=False):
 if sid not in facts:facts[sid]=pq(manifest[sid]['refs']['facts'])
 if raw and sid not in raws:
  p=next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet'));raws[sid]=pq(p);f=raws[sid];caps[sid]=(f.raw_volume[f.raw_volume.gt(0)].rolling(20,min_periods=20).mean()*.01).reindex(f.index).ffill()
def point(sid,day):
 day=pd.Timestamp(day);load(sid);sec=roster.loc[sid,'sector_id'];p=panel.loc[(sec,day)];f=facts[sid].loc[day] if day in facts[sid].index else pd.Series(dtype='object');v=pv.loc[(sid,day)];s=int(p.M3_candidate);ps=int(p.previous_S) if pd.notna(p.previous_S) else -1;m=int(ms.at[day,sid]);prev=int(pm.at[day,sid]) if pd.notna(pm.at[day,sid]) else -1
 iq=f.get('e0_ready')==1 and f.get('g_ready')==True and f.get('i_target')==1 and np.isfinite(f.get('i_floor',np.nan)) and f.get('i_floor',0)>0
 pk=bool(np.isfinite(v.score) and v.state>=0 and v.valid_observation);ib=f.get('i_buy')==True;typ='A' if s==1 and ps==0 and m==1 else 'B' if s==ps==1 and m==1 and prev==0 else ''
 cs=s==ps==m==prev==1 and iq and ib and pk
 return dict(sid=sid,name=roster.loc[sid,'name'],sector=sec,industry=p.sector_name,day=str(day.date()),S=s,previous_S=ps,M=m,previous_M=prev,n=int(p.M3_n),N=int(p.N),K=int(p.K),right_fixed_share=float(p.M3_n/p.N),diffusion=float(p.M3_delta3),entered3=int(p.M3_entered3),left3=int(p.M3_left3),I_qualified=bool(iq),i_target=f.get('i_target'),i_buy=bool(ib),g_grade=f.get('g_grade'),g_fresh_up=f.get('g_fresh_up'),PVR=float(v.score),PVR_known=pk,AB_type=typ,C_raw=bool(cs),raw_close=f.get('raw_close'),raw_I_floor=f.get('i_floor',np.nan)/f.get('factor',np.nan),e0_target=f.get('e0_target'))
accounts={}
for win,sub in [('2024_924','indexed_execution_v1/cohort_2024_924'),('2022','known_halt_contract_v1/cohort_2022_recovery_v2')]:
 b=R/'m3_ab_shared_probe_v1'/sub;accounts[win]={n:js(b/(n+'.json')) for n in ['EXACT_TRADE_JOURNAL','ARCHIVES','AUDIT','DAY_LEDGER','DECISIONS','SOURCE_ROUNDS','LAYER_REPORT']}
def state_at(sid,day):
 ds=str(day)[:10];win='2022' if ds<'2023' else '2024_924';a=accounts[win];q=0
 for z in a['EXACT_TRADE_JOURNAL']:
  if a['ARCHIVES'][z['round_id']]['sid']!=sid or z['day'][:10]>ds:continue
  q+=int(z['q'])*(1 if z['side'].startswith('buy') else -1)
 if q>0:return 'HELD'
 for z in a['SOURCE_ROUNDS']:
  if z['sid']==sid and 'UNKNOWN' in z['status'] and str(z.get('status_day','9999'))[:10]<=ds:return 'UNKNOWN'
 return 'FLAT'
# Primary old decision and original account ACT clock, not an inferred signal.
acc=js(M/'pvr-local-finite-capital-20261029/baseline/accounts-v2/I__S0_base.json');decs={}
with gzip.open(h(M/'pvr-local-finite-capital-20261029/baseline/accounts-v2/decisions.jsonl.gz'),'rt') as f:
 for line in f:
  z=json.loads(line)
  if z['account']=='I__S0_base':decs[z['at'][:10]]=z
allrows=[];traces=[]
for x in old.itertuples():
 d=pd.Timestamp(x.decision_at[:10]);r=point(x.symbol,d);sid=x.symbol
 ix[sid]=pq(M/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet');cps[sid]=pq(manifest[sid]['refs']['CP1']);g=ix[sid].loc[d];cp=cps[sid].loc[d]
 sd=pq(P/'facts'/f'{r["sector"]}.parquet').loc[d];r.update(old_decision_at=x.decision_at,old_entry_at=x.entry_at,old_exit_at=x.exit_at,old_actual_net=x.net_pnl,old_Q_eligible=sid in decs[r['day']]['eligible'],old_order_accepted=sid in decs[r['day']]['accepted'],old_sector_E0_target=int(sd.e0_target),old_sector_E0_ready=int(sd.e0_ready),G_phase=g.phase,G_fresh_reasons=g.up_reasons,fresh_CP=bool(cp.receipt),current_state=state_at(sid,d),missing_reason='SECTOR_NOT_RIGHT' if r['S']!=1 else 'STOCK_M3_NOT_RIGHT' if r['M']!=1 else 'I_INELIGIBLE' if not r['I_qualified'] else 'MATURE_RIGHT_NO_AB_EDGE')
 assert r['old_Q_eligible'] and r['old_order_accepted'];allrows.append(r)
 at=cal.get_loc(d)
 for t in cal[max(0,at-10):at+11]:
  if (r['sector'],t) not in panel.index:continue
  z=point(sid,t);z['current_baseline_state']=state_at(sid,t);z['old_decision_day']=str(d.date());z['fresh_CP']=bool(cps[sid].loc[t,'receipt']) if t in cps[sid].index else None;traces.append(z)
pd.DataFrame(allrows).to_csv(O/'OLD8_EXACT_DECISION_STATE.csv',index=False);pd.DataFrame(traces).to_csv(O/'OLD8_POINT_TIME_TRACE.csv',index=False)
act=[z for z in acc['audit_log'] if z['kind']=='risk_checkpoint' and '2024-09-20'<=z.get('at','')[:10]<='2024-09-30'];out('OLD_ACT_RESUME_CLOCK.json',act);out('OLD8_ORIGINAL_ORDERS.json',[z for z in acc['audit_log'] if z.get('sid') in set(old.symbol) and z.get('at','')[:10] in set(old.decision_at.str[:10]) and z['kind'] in ['reserve','entry_contract']])
# Saved current events, exact ranks and budget causes, no repaired birth dates.
events=[]
for win,a in accounts.items():
 if win!='2024_924':continue
 sr={z['event_id']:z for z in a['SOURCE_ROUNDS']};reason={z['round_id']:z for z in a['AUDIT'] if z['type']=='BUDGET_REJECTED' and z['kind']=='INIT'}
 for z in a['DECISIONS']:
  if z['sid'] not in set(old.symbol):continue
  w=dict(z);r=sr.get(z['event_id'],{});w['original_status']=r.get('status');w['original_entry_day']=r.get('entry_day');w['original_budget_minimum_reasons']=reason.get(z.get('round_id'),{}).get('trials',[{}])[-1].get('reasons');events.append(w)
pd.DataFrame(events).to_csv(O/'OLD8_ALL_ORIGINAL_AB_DECISIONS.csv',index=False)
# Use original isolated stateless market rule functions only, never any account module.
B=M/'rs-h1-execution-20261025';sys.path.insert(0,str(B/'code'));from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=js(B/'inputs-v2/market-rules.json');proxy=js(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];slip=D('.0005')
def fee(q,p,fs,side,par):return sum(fs.incremental(side,D(q)*p,{}, {},1,shares=q,par_value=par).values(),D(0))
def closecheck(r,nd):
 sid=r['sid'];d=pd.Timestamp(r['day']);load(sid,True);raw=raws[sid]
 if d not in raw.index:return dict(close_check='MISSING_CLOSE_UNKNOWN')
 z=raw.loc[d];fl=D(str(r['raw_I_floor']));pr=D(str(z.raw_close));cap=caps[sid].get(d,np.nan)
 valid=all(z.get(c)==True for c in ['observed_bar','price_eligible','volume_eligible']) and z.get('source_invalid')==False and z.get('synthetic_event_bar')==False
 if not valid or not np.isfinite(cap):return dict(close_check='SOURCE_OR_CAPACITY_UNKNOWN')
 if pr<=fl:return dict(close_check='AT_BELOW_FLOOR')
 try:
  ident=market_identity_on(rules,sid,r['day'],proxy);v=version_on(rules['fee_versions'][ident['venue']],r['day'],proxy)['schedule'];fs=FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x) for x in v['components']));qr=QuantityRule(**version_on(rules['quantity_versions'][sid],r['day'],proxy)['rule']);par=D(str(rules['security_metadata'][sid]['par_value']));pr*=1+slip;q=qr.buy_floor(min(int(nd*D('.02')/pr),int(cap)))
  while q>0:
   bf=fee(q,pr,fs,'buy',par);sf=fee(q,fl*(1-slip),fs,'sell',par);risk=max(D(0),D(q)*(pr-fl*(1-slip))+bf+sf)
   if D(q)*pr+bf<=nd*D('.02') and risk<=nd*D('.0025'):return dict(close_check='PASS',close_q=q,close_fee=float(bf),close_plan_risk=float(risk))
   q=qr.buy_floor(q-1)
  return dict(close_check='MINIMUM_LOT_OR_RISK_REJECT')
 except (RuleUnavailable,KeyError,ValueError) as ex:return dict(close_check='DATED_RULE_UNKNOWN',error=str(ex))
fixed=['2022-01-07','2022-01-10','2022-01-11','2022-01-12','2024-09-27','2024-11-19','2024-11-26'];queue=[];summary=[]
for ds in fixed:
 d=pd.Timestamp(ds);win='2022' if ds<'2023' else '2024_924';a=accounts[win];snap=next(x for x in a['AUDIT'] if x['type']=='CLOSE_SNAPSHOT' and x['day'].startswith(ds));nd=D(snap['Nd']) if snap['Nd'] is not None else None
 # Existing actual AB decisions preserve held/unknown state exactly. Only new C rows use saved baseline state.
 ab=[dict(z,channel='AB',shadow_feasible=z.get('close_check')=='PASS' and z['stock_state_before']=='FLAT') for z in a['DECISIONS'] if z['day'].startswith(ds)];cr=[]
 for sid in ms.columns:
  sec=roster.loc[sid,'sector_id'];p=panel.loc[(sec,d)]
  if p.M3_candidate!=1 or p.previous_S!=1 or ms.at[d,sid]!=1 or pm.at[d,sid]!=1:continue
  z=point(sid,d)
  if not z['C_raw']:continue
  z.update(channel='C',stock_state_before=state_at(sid,d));z.update(closecheck(z,nd) if nd is not None else dict(close_check='NAV_UNKNOWN'));z['shadow_feasible']=z['stock_state_before']=='FLAT' and z['close_check']=='PASS';z['PVR_score']=z['PVR'];cr.append(z)
 rows=ab+cr;by=collections.defaultdict(list)
 for z in rows:
  z['shadow_top2']=False
  if z['shadow_feasible']:by[z['sector']].append(z)
 for sec,seq in by.items():
  for rank,z in enumerate(sorted(seq,key=lambda z:(-z['PVR_score'],z['sid'])),1):z['shadow_rank']=rank;z['shadow_top2']=rank<=2
 for z in rows:z['signal_day']=ds;z['shadow_warning']='Original baseline state, request-only. Not a new account, fill or PnL.'
 queue+=rows
 summary.append(dict(day=ds,original_Nd=nd,AB_events=len(ab),AB_original_pending=sum(z.get('selected',False) for z in ab),C_signal_rows=len(cr),C_flat=sum(z['stock_state_before']=='FLAT' for z in cr),C_close_pass_flat=sum(z['shadow_feasible'] for z in cr),C_shadow_top2=sum(z['shadow_top2'] for z in cr),AB_shadow_top2=sum(z['shadow_top2'] for z in ab),old8_C_top2=[z['sid'] for z in cr if z['shadow_top2'] and z['sid'] in set(old.symbol)]))
pd.DataFrame(queue).to_csv(O/'FIXED7_SHADOW_REQUEST_QUEUES.csv',index=False);pd.DataFrame(summary).to_csv(O/'FIXED7_REQUEST_SUMMARY.csv',index=False)
# Unchanged existing 42 controls, followed only after their actual exit when available.
controls=csv(R/'klinger_vf_entry_preflight_v1/FIXED42_ORIGINAL_LABEL_CONTROLS.csv');ctrl=[];reentry=[]
for z in controls.to_dict('records'):
 p=point(z['sid'],z['signal_day']);p.update(original_actual_shared_fill=z['original_actual_shared_fill'],original_core_NET80=z['original_core_NET80'],original_core_return=z['original_core_return']);ctrl.append(p)
 if z['window']!='2022' or not z['original_actual_shared_fill']:continue
 a=accounts['2022'];rid=z['round_id'];ex=next((x for x in a['EXACT_TRADE_JOURNAL'] if x['round_id']==rid and x['side']=='sell_all'),None)
 if ex is None:continue
 ed=pd.Timestamp(ex['day']);at=cal.get_loc(ed)
 for d in cal[at:at+21]:
  p=point(z['sid'],d);p.update(old_exit_day=str(ed.date()),current_state=state_at(z['sid'],d),prior_round_id=rid,prior_actual_core_NET80=z['original_core_NET80'],same_day_new_after_exit_close=d==ed);reentry.append(p)
pd.DataFrame(ctrl).to_csv(O/'FIXED42_UNCHANGED_CONTROLS.csv',index=False);pd.DataFrame(reentry).to_csv(O/'WEAK_ORIGINAL_EXIT_RETRY_TRACE.csv',index=False)
# Verify isolated sizing against all original AB PASS rows on the three strong dates, fixed weak dates.
checks=[]
for ds in fixed:
 win='2022' if ds<'2023' else '2024_924';a=accounts[win];nd=D(next(x['Nd'] for x in a['AUDIT'] if x['type']=='CLOSE_SNAPSHOT' and x['day'].startswith(ds)))
 for z in a['DECISIONS']:
  if not z['day'].startswith(ds) or z.get('close_check')!='PASS':continue
  r=point(z['sid'],ds);v=closecheck(r,nd);assert v['close_check']=='PASS' and v['close_q']==z['close_q'] and abs(v['close_plan_risk']-z['close_plan_risk'])<1e-6,(z,v);checks.append(dict(day=ds,sid=z['sid'],quantity_exact=True,risk_tolerance=1e-6))
pd.DataFrame(checks).to_csv(O/'ORIGINAL_SIZING_PARITY.csv',index=False)
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==hh for p,hh in hs.items());out('SOURCE_HASHES.json',hs);out('QA.json',dict(old8_eligible_and_accepted=8,old8_same_day_AB=0,old8_reasons=pd.Series([x['missing_reason'] for x in allrows]).value_counts().to_dict(),old8_C=sum(x['C_raw'] for x in allrows),old8_shadow_top2={x['day']:x['old8_C_top2'] for x in summary},fixed_controls=len(ctrl),weak_exit_trace_rows=len(reentry),original_size_parity_rows=len(checks),source_unchanged=True,account_replays=0,new_fills=0,new_profits=0))
print(pd.DataFrame(allrows)[['sid','day','S','M','I_qualified','i_buy','C_raw','fresh_CP','missing_reason']].to_string(index=False));print(pd.DataFrame(summary).to_string(index=False));print('QA',len(checks))
