"""Read-only local market-evidence diagnostic. No engine/Data/history import or portfolio replay."""
from pathlib import Path
import json,csv,hashlib,math,statistics
from collections import Counter
import pandas as pd
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
O=R/'mainline_daily_industry_startup_opportunity_v1'
B=R/'mainline_m7_cash_batch_design_v6/once_20260630'
P=R/'mainline_seed_entry_diagnostic_v1'
hashes={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,expected=None):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,('INPUT_DRIFT',str(p))
 hashes[str(p)]=h
 return json.loads(p.read_text())
def frame(p,expected=None,**kw):
 p=Path(p);h=sha(p)
 if expected is not None:assert h==expected,('INPUT_DRIFT',str(p))
 hashes[str(p)]=h
 return pd.read_parquet(p,**kw)
def write(name,x):
 (O/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
 if isinstance(x,list) and x:
  with (O/(name+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except:return False
def btri(x):return int(x) if isinstance(x,(bool,np.bool_)) else -1
def ntri(x):
 if isinstance(x,(bool,np.bool_)):return int(x)
 return int(x) if finite(x) and x in (0,1) else -1
def AND(*a):return 0 if 0 in a else -1 if -1 in a else 1
def majority(k,u,N):
 return -1 if not N else 1 if 2*k>N else 0 if 2*(k+u)<=N else -1
def median_bounds(vals,N):
 # Unknown price-return support is [-1,+inf); using +/-infinity is conservative.
 vals=[float(x) for x in vals if finite(x)];u=N-len(vals)
 if not N:return dict(observed_median=None,median_exact=None,median_lower=None,median_upper=None,median_positive=-1)
 low=float(np.median(vals+[-np.inf]*u));high=float(np.median(vals+[np.inf]*u))
 return dict(observed_median=float(np.median(vals)) if vals else None,median_exact=float(np.median(vals)) if not u else None,
  median_lower=low if math.isfinite(low) else None,median_upper=high if math.isfinite(high) else None,
  median_lower_unbounded=not math.isfinite(low),median_upper_unbounded=not math.isfinite(high),
  median_positive=1 if low>0 else 0 if high<=0 else -1)
def metric(states,N,prefix):
 k=sum(x==1 for x in states);u=sum(x==-1 for x in states)
 return {prefix+'_n':k,prefix+'_known':N-u,prefix+'_unknown':u,prefix+'_lower':k/N if N else None,prefix+'_upper':(k+u)/N if N else None,prefix+'_majority':majority(k,u,N)}
source=read(B/'SOURCE_HASHES.json');seal=read(B/'OUTPUT_HASHES.json')
for n in ['SECTOR_DAILY.json','REFERENCE_DAILY.json','EVENT_REGISTRY.json','ORDERS.json','EVENT_REQUEST_PLANS.json','EVENT_LOG.json']:
 p=B/n
 # seals can use names or absolute paths.
 h=seal.get(n,seal.get(str(p)))
 assert h is not None,('MISSING_SEAL',n)
 assert sha(p)==h,('BASELINE_DRIFT',n)
sectors=read(B/'SECTOR_DAILY.json');reference=read(B/'REFERENCE_DAILY.json');events=read(B/'EVENT_REGISTRY.json')
orders=read(B/'ORDERS.json');plans=read(B/'EVENT_REQUEST_PLANS.json');eventlog=read(B/'EVENT_LOG.json')
filled=read(P/'FILLED_SEED_CLASSIFICATION.json')
sd={(x['day'],x['sector51']):x for x in sectors};rf={(x['day'],x['sector51']):x for x in reference}
days=sorted({x['day'] for x in sectors});di={d:i for i,d in enumerate(days)}
def previous(d):return days[di[d]-1] if di[d] else None
def nxt(d):return days[di[d]+1] if di[d]+1<len(days) else None
e_audit=[]
for z in sectors:
 d,sec=z['day'],z['sector51'];old=sd.get((previous(d),sec));rr=rf[(d,sec)]
 raw=max(float(z['rs5']),0)*z['n']/z['N'] if all(finite(z[k]) for k in ['rs5','n','N']) and z['N']>0 else None
 assert (raw is None and not finite(z['E'])) or math.isclose(raw,z['E'],rel_tol=1e-12,abs_tol=1e-12)
 ep=float(old['E']) if old and finite(old['E']) else None
 delta=raw-ep if raw is not None and ep is not None else None
 gated=raw if z['M']==1 else 0. if z['M']==0 else None
 gp=ep if old and old['M']==1 else 0. if old and old['M']==0 else None
 gd=gated-gp if gated is not None and gp is not None else None
 if rr['W'] is not None and old:
  assert math.isclose(float(rr['previous_E']),ep,rel_tol=1e-12,abs_tol=1e-12)
  assert math.isclose(float(rr['W']),raw+max(delta,0),rel_tol=1e-12,abs_tol=1e-12)
 e_audit.append(dict(day=d,sector51=sec,M=z['M'],previous_M=old['M'] if old else None,rs5=z['rs5'],n=z['n'],N=z['N'],raw_e=raw,exported_E=z['E'],previous_raw_e=ep,raw_delta=delta,actual_W=float(rr['W']) if finite(rr['W']) else None,
  hypothetical_M_gated_E=gated,hypothetical_M_gated_delta=gd,first_M_after_known_false=bool(old and old['M']==0 and z['M']==1),
  hypothetical_extra_innovation=max(gd,0)-max(delta,0) if gd is not None and delta is not None else None))
windows=[('STARTUP_ALL_MARKET', '中药', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '互联网电商', '2024-09-25', '2024-09-25'), ('STARTUP_ALL_MARKET', '交通运输与物流', '2024-09-23', '2024-09-23'), ('STARTUP_ALL_MARKET', '光伏风电设备', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '光学电子', '2024-09-25', '2024-09-25'), ('STARTUP_ALL_MARKET', '农牧养殖', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '动力电池', '2024-09-26', '2024-09-27'), ('STARTUP_ALL_MARKET', '化学制药', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '化工材料', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '医疗器械', '2024-09-26', '2024-09-27'), ('STARTUP_ALL_MARKET', '医药商业', '2024-09-25', '2024-09-25'), ('STARTUP_ALL_MARKET', '半导体', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '商贸零售', '2024-09-23', '2024-09-24'), ('STARTUP_ALL_MARKET', '基建工程', '2024-09-23', '2024-09-25'), ('STARTUP_ALL_MARKET', '基础耗材与包装', '2024-09-25', '2024-09-25'), ('STARTUP_ALL_MARKET', '家电家居', '2024-09-20', '2024-09-20'), ('STARTUP_ALL_MARKET', '工程咨询与专业服务', '2024-09-23', '2024-09-23'), ('STARTUP_ALL_MARKET', '房地产开发', '2024-09-23', '2024-09-23'), ('STARTUP_ALL_MARKET', '旅游酒店', '2024-09-26', '2024-09-27'), ('STARTUP_ALL_MARKET', '服装纺织', '2024-09-25', '2024-09-25'), ('STARTUP_ALL_MARKET', '汽车整车', '2024-09-20', '2024-09-23'), ('STARTUP_ALL_MARKET', '汽车零部件', '2024-09-20', '2024-09-20'), ('STARTUP_ALL_MARKET', '油气能源', '2024-09-24', '2024-09-24'), ('STARTUP_ALL_MARKET', '游戏传媒', '2024-09-23', '2024-09-27'), ('STARTUP_ALL_MARKET', '煤炭', '2024-09-20', '2024-09-25'), ('STARTUP_ALL_MARKET', '环保设备与服务', '2024-09-23', '2024-09-23'), ('STARTUP_ALL_MARKET', '珠宝饰品', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '生物制品', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '电气电网设备', '2024-09-26', '2024-09-26'), ('STARTUP_ALL_MARKET', '白酒', '2024-09-23', '2024-09-26'), ('STARTUP_ALL_MARKET', '美容护理', '2024-09-26', '2024-09-27'), ('STARTUP_ALL_MARKET', '计算机设备', '2024-09-23', '2024-09-24'), ('STARTUP_ALL_MARKET', '证券保险', '2024-09-20', '2024-09-23'), ('STARTUP_ALL_MARKET', '软件与IT服务', '2024-09-23', '2024-09-24'), ('STARTUP_ALL_MARKET', '通信设备', '2024-09-23', '2024-09-23'), ('STARTUP_ALL_MARKET', '通信运营服务', '2024-09-23', '2024-09-25'), ('STARTUP_ALL_MARKET', '金属钢铁', '2024-09-23', '2024-09-24'), ('STARTUP_ALL_MARKET', '银行', '2024-09-23', '2024-09-26'), ('STARTUP_ALL_MARKET', '食品饮料', '2024-09-23', '2024-09-26'), ('STARTUP_ALL_MARKET', '饲料动保', '2024-09-26', '2024-09-26')]
targetsecs={x[1] for x in windows}
cp=R/'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv'
assert sha(cp)==source[str(cp)];hashes[str(cp)]=sha(cp)
classification=pd.read_csv(cp,keep_default_na=False);classification=classification[classification.eligible.eq(True)]
ids=sorted(classification[classification.sector51.isin(targetsecs)].symbol)
names=classification.set_index('symbol').name.to_dict();sidsector=classification.set_index('symbol').sector51.to_dict()
manifestpath=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
manifest={x['symbol']:x for x in read(manifestpath,source[str(manifestpath)])}
Q=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
kp=Q/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet';rp=kp.with_name('RIGHT3.parquet')
pp=Q/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet'
known=frame(kp,source[str(kp)],columns=ids);right=frame(rp,source[str(rp)],columns=ids)
ps=frame(pp,source[str(pp)],columns=['sid','day','state'])
ps=ps[ps.sid.isin(ids)].pivot(index='day',columns='sid',values='state').reindex(index=known.index,columns=ids)
known=known&ps.ge(0);right=right&known
cal=known.index[(known.index>='2024-09-18')&(known.index<='2024-09-30')]
raws={};facts={};cps={};prices={};valids={};lineages={};cpstates={};frontierstates={};issuereasons=Counter()
rawcols=['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor','close','observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar','source_kind','source_path','segment_id']
for sid in ids:
 m=manifest[sid];hs={**m['source_sha256'],**m['output_sha256']}
 p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
 raw=frame(p,hs[p],columns=rawcols).reindex(cal);fact=frame(m['refs']['facts'],hs[m['refs']['facts']],columns=['i_target','i_floor','segment_id']).reindex(cal)
 c=frame(m['refs']['CP1'],hs[m['refs']['CP1']],columns=['ready','receipt','candidate','delta_frontier','reset_reason','phase','frontier']).reindex(cal)
 vals=[];px=[];lins=[];receipts=[];frontiers=[]
 for t,row in raw.iterrows():
  lin=tuple(str(row[k]) for k in ['source_kind','source_path','segment_id']) if all(pd.notna(row[k]) and str(row[k]).strip().lower() not in ('','unknown','none','null','nan','na') for k in ['source_kind','source_path','segment_id']) else None
  valid=all(btri(row[k])==1 for k in ['observed_bar','price_eligible','volume_eligible']) and all(btri(row[k])==0 for k in ['source_invalid','synthetic_event_bar']) and all(finite(row[k]) and row[k]>0 for k in ['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']) and lin is not None
  pr=float(row.raw_close*row.adjustment_factor) if valid else None
  valid=valid and finite(row.close) and math.isclose(pr,float(row.close),rel_tol=1e-10,abs_tol=1e-10)
  vals.append(valid);px.append(pr if valid else np.nan);lins.append(lin)
  cr=c.loc[t];rt=btri(cr.receipt)
  if rt==0:receipt=0
  elif rt==1 and valid and finite(cr.candidate) and cr.candidate>0 and pr>cr.candidate and finite(cr.delta_frontier) and cr.delta_frontier>0:receipt=1
  else:receipt=-1
  receipts.append(receipt)
  fs=-1 if not valid or btri(cr.ready)!=1 or not finite(cr.delta_frontier) else int(cr.delta_frontier>0)
  frontiers.append(fs)
  if not valid:issuereasons['invalid_quote_stock_day']+=1
  if rt==-1:issuereasons['unknown_receipt_stock_day']+=1
 raws[sid]=raw;facts[sid]=fact;cps[sid]=c;prices[sid]=pd.Series(px,index=cal);valids[sid]=pd.Series(vals,index=cal);lineages[sid]=pd.Series(lins,index=cal);cpstates[sid]=pd.Series(receipts,index=cal);frontierstates[sid]=pd.Series(frontiers,index=cal)
def st(sid,t):
 return -1 if t not in known.index or btri(known.at[t,sid])!=1 else btri(right.at[t,sid])
def connected(sid,a,b):
 sp=valids[sid].loc[a:b]
 return bool(len(sp) and sp.all() and lineages[sid].loc[a:b].nunique(dropna=False)==1)
def birthq(sid,t):
 r=raws[sid].loc[t];f=facts[sid].loc[t]
 it=ntri(f.i_target);stock=st(sid,t);priceok=1 if valids[sid].loc[t] else -1
 floorok=-1 if not finite(f.i_floor) or f.i_floor<=0 else int(valids[sid].loc[t] and prices[sid].loc[t]>f.i_floor)
 return AND(stock,it,priceok,floorok)
cohorts={};members=[]
def event_for(sec,d):
 es=[e for e in events.values() if e['sector51']==sec and e['birth_day']<=d]
 return max(es,key=lambda e:e['birth_day']) if es else None
for label,sec,start,end in windows:
 for d in days:
  if not start<=d<=end:continue
  ev=event_for(sec,d)
  if not ev:continue
  eid=ev['event_id']
  if eid in cohorts:continue
  birth=pd.Timestamp(ev['birth_day']);ss=sorted(s for s in ids if sidsector[s]==sec)
  assert len(ss)==sd[(d,sec)]['N']
  quals={s:birthq(s,birth) for s in ss};cohorts[eid]=dict(all=ss,observed=[s for s in ss if valids[s].loc[birth]],qualified=[s for s in ss if quals[s]==1],birth=ev['birth_day'],sector51=sec)
  for s in ss:members.append(dict(event_id=eid,sector51=sec,birth_day=ev['birth_day'],sid=s,name=names[s],in_ALL_FIXED=True,in_BIRTH_PRICE_KNOWN=bool(valids[s].loc[birth]),in_BIRTH_QUALIFIED=quals[s]==1,birth_qualification=quals[s],birth_stock_state=st(s,birth),birth_I_state=ntri(facts[s].loc[birth].i_target),birth_quote_known=bool(valids[s].loc[birth]),birth_adjusted_close=float(prices[s].loc[birth]) if valids[s].loc[birth] else None))
memberdaily=[];daily=[]
for label,sec,start,end in windows:
 for d in days:
  if not start<=d<=end:continue
  ev=event_for(sec,d);eid=ev['event_id'];co=cohorts[eid];birth=pd.Timestamp(co['birth']);t=pd.Timestamp(d);pr=pd.Timestamp(previous(d));z=sd[(d,sec)];er=next(x for x in e_audit if x['day']==d and x['sector51']==sec)
  atom={}
  for sid in co['all']:
   ok=connected(sid,birth,t);pair=connected(sid,pr,t);p=float(prices[sid].loc[t]) if valids[sid].loc[t] else None
   ret=float(p/prices[sid].loc[birth]-1) if ok else None
   dr=float(p/prices[sid].loc[pr]-1) if pair else None
   positive=-1 if ret is None else int(ret>0)
   advance=-1 if dr is None else int(dr>0);decline=-1 if dr is None else int(dr<0)
   profitable_advance=AND(positive,advance)
   hist=prices[sid].loc[birth:t];before=hist.loc[hist.index<t]
   newhigh=-1 if not ok else 0 if not len(before) else int(p>float(before.max()))
   drawdown=float(p/hist.max()-1) if ok else None
   receipt=int(cpstates[sid].loc[t]);frontier=int(frontierstates[sid].loc[t])
   # Cross-sectional widening of profitable members, retaining each denominator member.
   prev_ok=connected(sid,birth,pr) if pr>=birth else False
   prevret=float(prices[sid].loc[pr]/prices[sid].loc[birth]-1) if prev_ok else None
   crossed=-1 if ret is None or prevret is None else int(prevret<=0 and ret>0)
   lost=-1 if ret is None or prevret is None else int(prevret>0 and ret<=0)
   a=dict(sequence=label,sector51=sec,event_id=eid,birth_day=co['birth'],close_day=d,sid=sid,name=names[sid],in_BIRTH_QUALIFIED=sid in co['qualified'],event_return=ret,daily_return=dr,positive=positive,advance=advance,decline=decline,profitable_advance=profitable_advance,new_event_high=newhigh,event_peak_drawdown=drawdown,CP_receipt=receipt,CP_frontier_advance=frontier,new_positive=crossed,lost_positive=lost,event_path_known=ok,pair_path_known=pair)
   atom[sid]=a;memberdaily.append(a)
  for typ,ss in [('ALL_FIXED',co['all']),('BIRTH_PRICE_KNOWN',co['observed']),('BIRTH_QUALIFIED',co['qualified'])]:
   N=len(ss);aa=[atom[s] for s in ss]
   entry=[x for x in filled if x['plan_day']==d and x['sector51']==sec]
   req=[x for x in plans if x['day']==d and x['sector51']==sec and x['kind']=='SEED']
   rr=dict(sequence=label,cohort=typ,sector51=sec,close_day=d,next_OPEN=nxt(d),event_id=eid,birth_day=co['birth'],N_fixed=N,birth_qualification_unknown=sum(m['birth_qualification']==-1 for m in members if m['event_id']==eid),state=z['state'],M=z['M'],S=z['S'],F=z['F'],n=z['n'],N_sector=z['N'],U_sector=z['U'],E=z['E'],raw_delta_E=er['raw_delta'],actual_W=er['actual_W'],hypothetical_gated_delta_E=er['hypothetical_M_gated_delta'],event_active=z['state']==1,
     event_return_known=sum(x['event_return'] is not None for x in aa),daily_return_known=sum(x['daily_return'] is not None for x in aa),
     next_OPEN_actual_EVENT=sum(x['phase']=='EVENT' for x in entry),next_OPEN_actual_MATURE=sum(x['phase']=='MATURE' for x in entry),next_OPEN_actual_RESIDUAL=sum(x['phase']=='RESIDUAL' for x in entry),
     next_OPEN_MATURE_names=[x['name'] for x in entry if x['phase']=='MATURE'],next_OPEN_MATURE_sids=[x['sid'] for x in entry if x['phase']=='MATURE'],
     mature_seed_requests=sum(x['allocation_phase']=='MATURE' for x in req),event_seed_requests=sum(x['allocation_phase']=='EVENT' for x in req))
   for nm in ['positive','advance','decline','profitable_advance','new_event_high','CP_receipt','CP_frontier_advance','new_positive','lost_positive']:
    rr.update(metric([x[nm] for x in aa],N,nm))
   for field in ['event_return','daily_return','event_peak_drawdown']:
    rr.update({field+'_'+k:v for k,v in median_bounds([x[field] for x in aa],N).items()})
   rr['G']=rr['profitable_advance_majority']
   daily.append(rr)
# One diagnostic rule, chosen for market semantics, not fitted by PnL or threshold sweep.
# New MATURE SEED only: strict majority of the fixed birth-price-known cohort both above birth and up today.
# A supplied earlier gate is left intact; this is an added condition if ever implemented.
lookup={(x['close_day'],x['sector51']):x for x in daily if x['cohort']=='BIRTH_PRICE_KNOWN'}
classify=[]
for x in filled:
 key=(x['plan_day'],x['sector51'])
 if key not in lookup:continue
 row=lookup[key]
 classify.append({k:x[k] for k in ['round_id','sid','name','sector51','plan_day','seed_day','signal_day','phase','seed_cost','add_count','exit_day','exit_reason']}|dict(sequence=row['sequence'],event_id=row['event_id'],G=row['G'],decision='UNMODIFIED_'+x['phase'] if x['phase']!='MATURE' else 'PASS' if row['G']==1 else 'MARKET_PROGRESS_WAIT' if row['G']==0 else 'UNKNOWN_WAIT'))
# no PnL sum is used or emitted for the hypothetical gate
first=[x for x in e_audit if x['first_M_after_known_false']]
qa=dict(end=days[-1],baseline_sector_rows=len(sectors),raw_e_equals_exported_E_all_rows=True,
 actual_W_matches_ungated_previous_E=True,E_positive_while_M_zero=sum(x['M']==0 and x['raw_e'] is not None and x['raw_e']>0 for x in e_audit),
 first_M_after_false=len(first),first_M_previous_E_positive=sum(x['previous_raw_e'] is not None and x['previous_raw_e']>0 for x in first),
 scope_sectors=len(targetsecs),scope_stocks=len(ids),fixed_events=len(cohorts),member_rows=len(members),daily_rows=len(daily),member_daily_rows=len(memberdaily),
 issue_counts=dict(issuereasons),all_local_only=True,no_engine_import=True,no_history_run=True,no_account_replay=True,no_threshold_sweep=True,
 baseline_output_hashes_verified=[n for n in ['SECTOR_DAILY.json','REFERENCE_DAILY.json','EVENT_REGISTRY.json','ORDERS.json','EVENT_REQUEST_PLANS.json','EVENT_LOG.json']],
 classification_PIT=False,price_history_and_model_inputs_inherit_frozen_non_PIT_limits=True)
for name,x in [('E_GATE_AUDIT',e_audit),('E_FIRST_M_ROWS',first),('EVENT_MEMBERS',members),('MEMBER_DAILY',memberdaily),('DAILY_EVIDENCE',daily),('FIXED_WINDOW_ENTRY_CLASSIFICATION',classify),('QA',qa),('SOURCE_HASHES',hashes)]:write(name,x)
print(json.dumps(qa,ensure_ascii=False))
for r in daily:
 if r['cohort']=='BIRTH_PRICE_KNOWN':print(r['sequence'],r['close_day'],r['birth_day'],'s/m',r['state'],r['M'],'N',r['N_fixed'],'positive',r['positive_n'],'adv/dec',r['advance_n'],r['decline_n'],'both/G',r['profitable_advance_n'],r['G'],'medianR',round(100*r['event_return_observed_median'],2) if r['event_return_observed_median'] is not None else None,'high/CP/front',r['new_event_high_n'],r['CP_receipt_n'],r['CP_frontier_advance_n'],'E/delta',round(r['E'],3),round(r['raw_delta_E'],3),'event/mature',r['next_OPEN_actual_EVENT'],r['next_OPEN_actual_MATURE'])
