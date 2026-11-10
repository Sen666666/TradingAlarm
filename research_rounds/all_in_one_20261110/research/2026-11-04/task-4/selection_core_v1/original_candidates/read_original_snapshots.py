"""Read original frozen opportunity/rank/score snapshots; no native imports or scores calculated."""
from pathlib import Path
import json,gzip,collections,hashlib,time
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');U=B/'universe-cp1-inputs-20261031'
DATES=['2024-09-23','2024-09-24','2024-09-27','2024-09-30','2024-10-08','2024-10-11','2022-01-20','2022-01-24','2022-03-15','2022-04-27','2022-10-31','2026-01-05','2026-01-15','2026-02-03','2026-04-08','2026-05-20','2026-06-29'];EARLY=['2024-09-24','2026-01-15','2022-01-24']
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
PM={'long':Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json'),'strong':B/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json'}
SHA={};start=time.monotonic()
def read(p):
 p=Path(p);bb=p.read_bytes();SHA[str(p)]=hashlib.sha256(bb).hexdigest();return json.loads(bb)
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,(float,)) and not np.isfinite(x):return None
 if isinstance(x,pd.Timestamp):return str(x.date())
 return x
def dump(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
SM={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};IM={x['series']:x for x in read(U/'INDUSTRY_MANIFEST.json')};meta=read(M);pms={k:read(v) for k,v in PM.items()}
h=np.load(H);hd=pd.DatetimeIndex(h['dates']);hs=h['symbols'].astype(str);hv=h['score'];di={str(t.date()):i for i,t in enumerate(hd)};si={s:i for i,s in enumerate(hs)};SHA[str(H)]=hashlib.sha256(H.read_bytes()).hexdigest()
nextdays={d:str(hd[di[d]+1].date()) for d in DATES};allread=set(DATES)|set(nextdays.values())
collected={k:[] for k in ['opportunities','rank-policy','funding','industry']}
for window,sub in [('long','long_OFF'),('strong','strong_OFF')]:
 for name in collected:
  p=Path('new_price_trend_v1/funding/runs')/sub/'pair'/(name+'.jsonl.gz');SHA[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest()
  with gzip.open(p,'rt') as f:
   for line in f:
    key='"at": "' if name=='funding' else '"day": "';q=line.find(key)
    if q<0:continue
    day=line[q+len(key):q+len(key)+10]
    if day not in (allread if name=='funding' else set(DATES)):continue
    r=json.loads(line);r['source_window']=window;r['source_file']=str(p.resolve());collected[name].append(r)
 for name,rows in collected.items():
  if name=='opportunities':print('EXTRACTED',window,name,len(rows),'seconds',round(time.monotonic()-start,2),flush=True)
for name,rows in collected.items():
 with (O/('ORIGINAL_'+name.upper().replace('-','_')+'.jsonl')).open('w') as f:
  for r in rows:f.write(json.dumps(clean(r),ensure_ascii=False,allow_nan=False)+'\n')
ops={(r['day'],r['sid']):r for r in collected['opportunities'] if r.get('account')=='B'};rp={(r['day'],r['sid']):r for r in collected['rank-policy'] if r.get('account')=='B'}
fund=collections.defaultdict(list)
for r in collected['funding']:
 if r.get('account','B')=='B':fund[(r['at'][:10],r['sid'])].append(r)
bridge=pd.read_csv('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022/audit-snapshot/a-industry-index-bridge.csv');names=dict(zip(bridge.index_symbol,bridge.industry_name))
industries=[]
for d in DATES:
 ids=sorted(IM,key=lambda s:(-hv[di[d],si[s]] if np.isfinite(hv[di[d],si[s]]) else np.inf,s))
 for n,sid in enumerate(ids):industries.append({'date':d,'sector':sid,'industry_static':names.get(sid),'H1_cache_score':float(hv[di[d],si[sid]]),'cache_numeric_order_0based':n,'score_known':bool(np.isfinite(hv[di[d],si[sid]])),'source':str(H),'static_mapping_PIT_verified':False})
pd.DataFrame(industries).to_csv(O/'INDUSTRY_H1_ALL90.csv',index=False);pd.DataFrame([r for r in industries if r['cache_numeric_order_0based']<20]).to_csv(O/'INDUSTRY_H1_TOP20.csv',index=False)
rows=[]
for d in EARLY:
 for r0 in sorted([r for (dd,_),r in ops.items() if dd==d],key=lambda r:r['rank'])[:20]:
  r=dict(r0);sid=r['sid'];r.update(name=meta[sid]['name'],H1_cache_score=float(hv[di[d],si[sid]]));rows.append(r)
dump('EARLY_THREE_H1_ALL_PACKET_TOP20.json',rows)
focus=[s for s,m in meta.items() if any(n in m['name'] for n in ['海能达','银之杰','江丰','珂玛','金海通','盈新'])]
foc=[]
for sid in focus:
 f=pd.read_parquet(SM[sid]['refs']['facts']);cp=pd.read_parquet(SM[sid]['refs']['CP1'])
 scores={w:pd.read_parquet(p.parent/'scores'/(sid+'.parquet')) for w,p in PM.items()}
 for d in EARLY:
  t=pd.Timestamp(d);w='strong' if d.startswith('2026') else 'long';r={'date':d,'sid':sid,'name':meta[sid]['name'],'sector_static':meta[sid]['sector_id'],'industry_static':meta[sid]['industry'],'opportunity_original':ops.get((d,sid)),'rank_policy_original':rp.get((d,sid)),'signal_day_funding_original':fund.get((d,sid),[]),'next_OPEN_day':nextdays[d],'next_OPEN_day_funding_original':fund.get((nextdays[d],sid),[]),'H1_cache_score':hv[di[d],si[sid]],'PVR_cache_score':scores[w].at[t,'score'] if t in scores[w].index else None,'facts_original':f.loc[t].to_dict() if t in f.index else None,'CP_original':cp.loc[t].to_dict() if t in cp.index else None};foc.append(r)
dump('EARLY_THREE_FOCAL_ORIGINAL_RECORDS.json',foc)
pending=sorted([r for r in collected['rank-policy'] if r['day'] in EARLY and r.get('account')=='B'],key=lambda r:(r['day'],r['final_slot']))
dump('EARLY_THREE_ACTUAL_PENDING_PVR_TOP20.json',[r for r in pending if r['final_slot']<20])
dump('FROZEN_DATES.json',{'root_frozen_dates':DATES,'first_delivery_dates':EARLY,'no_dates_selected_by_outcomes':True,'next_original_calendar_sessions':nextdays})
dump('EARLY_SOURCE_SHA256.json',SHA)
counts={d:{'opportunities':sum(dd==d for dd,s in ops),'original_source_qualified':sum(bool(dd==d and (r.get('core_Q') is True or (r.get('CP1_id') and r.get('mobile_Q') is True))) for (dd,s),r in ops.items()),'pre_size_roles_no_barriers':sum(dd==d and bool(r.get('roles')) and not r.get('barriers') for (dd,s),r in ops.items()),'actual_pending_unique_stock':sum(dd==d for dd,s in rp)} for d in EARLY}
print('EARLY_COUNTS',json.dumps(counts),flush=True)
for r in foc:
 if (r['date']=='2024-09-24' and any(n in r['name'] for n in ['海能','银之'])) or (r['date']=='2026-01-15' and any(n in r['name'] for n in ['江丰','珂玛','金海通'])) or (r['date']=='2022-01-24' and '盈新' in r['name']):
  op=r['opportunity_original'];rr=r['rank_policy_original'];print('FOCUS',r['date'],r['sid'],r['name'],'H1score',r['H1_cache_score'],'PVR',r['PVR_cache_score'],'op',json.dumps(op,ensure_ascii=False),'pending',json.dumps(rr,ensure_ascii=False),'fund',json.dumps(r['signal_day_funding_original']+r['next_OPEN_day_funding_original'],ensure_ascii=False),flush=True)
print('EARLY_COMPLETE_SECONDS',time.monotonic()-start,flush=True)
