from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
from collections import defaultdict
import gzip,json,sys,hashlib
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1'); R=O/'run_1200000'
OUT=O.parent/'selection_entry_diagnosis_v1/supported_trajectory_risk_v1'
sys.path.insert(0,str(OUT));from run import score_one,sha,dump
def jl(p): return [json.loads(s) for s in gzip.open(p,'rt')]
a=json.load(gzip.open(R/'pair/PVR.json.gz','rt'))
fund=[r for r in jl(R/'pair/funding.jsonl.gz') if r['account']=='PVR']
daily=[r for r in jl(R/'pair/daily.jsonl.gz') if r['account']=='PVR']; days=[r['at'][:10] for r in daily]
prev=dict(zip(days[1:],days[:-1])); nxt=dict(zip(days[:-1],days[1:])); nav={r['at'][:10]:D(r['nav']) for r in daily}
legal={}
for s in gzip.open(R/'pair/opportunities.jsonl.gz','rt'):
 r=json.loads(s)
 if r['account']=='PVR' and not r['held'] and not r['barriers'] and r['roles']:legal[r['day'],r['sid']]=r
fb=defaultdict(list)
for r in fund:
 d=r['at'][:10]; sd=prev.get(d) if '09:30' in r['at'] else d
 fb[sd,r['sid']].append(r)
res={(r['at'][:10],r['sid']):D(r['gross_budget_cny'])+D(r['fee_reserved_cny']) for r in a['audit'] if r['kind']=='reserve'}
buycost=defaultdict(lambda:D(0))
for t in a['trades']:
 if t['side']=='buy':buycost[t['at'][:10]]+=D(t['gross_cny'])+D(t['fees_cny'])
checks=[r for r in jl(R/'OPEN_CASH_CHECKS.jsonl.gz') if r['account']=='PVR']
c0={r['at'][:10]:D(r['available_after'])+buycost[r['at'][:10]] for r in checks}
spent=defaultdict(lambda:D(0))
for r in fund:
 if '09:30' not in r['at']:continue
 d=r['at'][:10];r['_cash_turn']=c0[d]-spent[d]
 if r['result']=='reserved':spent[d]+=res[d,r['sid']]
ib={(d['at'][:10],i['sid'],i['role']):i for d in a['decisions'] for i in d['intents']}
sys.path.insert(0,str(O/'inputs'));import continuous_inputs as C
rules=json.loads((C.J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json').read_text())
proto=json.loads((C.J.M.BP.C.OLD/'inputs-v2/economic-protocol.json').read_text())
fm=C.J.M.E.FastMarket.__new__(C.J.M.E.FastMarket);fm.rules=rules;fm.protocol=proto;fm.cache_at=None
records={r['series_id']:r for r in json.loads((C.J.M.P/'manifest.json').read_text())['series']}; raw={}
mb=[]
for key,r in legal.items():
 ff=fb.get(key,[]);rr={x['result'] for x in ff}; status='funded' if 'reserved' in rr else 'cash_only' if 'cash_or_original_reserve' in rr else None
 if status is None:continue
 d,sid=key;ex=nxt[d];at=datetime.fromisoformat(ex+'T09:30:00+08:00')
 intents=[ib[key+(role,)] for role in r['roles'] if key+(role,) in ib];i=intents[0]
 fr=next((x for x in ff if x['result']=='reserved'),None)
 cr=next((x for x in ff if x['result']=='cash_or_original_reserve'),fr)
 if sid not in raw:raw[sid]=pd.read_parquet(records[sid]['raw']['path'],columns=['trade_date','open']).set_index('trade_date')['open']
 px=D(str(raw[sid].loc[pd.Timestamp(ex)]))*D('1.0005');q=fm.quantity(sid,at).buy_minimum
 cost=D(q)*px+C.J.LR.fees(q,px,fm.fees(sid,at),'buy',rules.get('security_metadata',{}).get(sid,{}).get('par_value'))
 floor=nav[d]*D('.1');ct=cr['_cash_turn']
 mb.append(dict(day=d,sid=sid,sector=r['sector'],roles='|'.join(r['roles']),status=status,rank=i['priority_rank'],pvr=i['PVR_score'],h1=i['score'],h1_rank=i['original_H1_rank'],epoch=tuple(i['epoch']) if i['epoch'] is not None else None,funded_role=fr['role'] if fr else None,pure_roles=tuple(sorted(x['role'] for x in ff if x['result']=='cash_or_original_reserve')),cash_timing='pre_existing' if cost+floor>c0[ex]+D('1e-8') else 'order_induced',minimum_cost=float(cost),shortfall=float(max(D(0),cost+floor-ct)),cash_start=float(c0[ex]),cash_turn=float(ct),cash_floor=float(floor),donor_reserved=float(res[ex,sid]) if fr else None))
mb=pd.DataFrame(mb);donors=mb[mb.status=='funded'];eligible=mb[(mb.status=='cash_only')&(mb.cash_timing=='order_induced')]
groups={k:g.to_dict('records') for k,g in donors.groupby(['day','sector','roles'])};edges=[]
for r in eligible.to_dict('records'):
 for f in groups.get((r['day'],r['sector'],r['roles']),[]):
  if f['funded_role'] not in r['pure_roles'] or not(pd.notna(f['pvr']) and pd.notna(r['pvr'])) or f['rank']>=r['rank'] or f['donor_reserved']+1e-7<r['shortfall']:continue
  edges.append((r['day'],r['rank']-f['rank'],f['sid'],r['sid'],f,r))
edges.sort(key=lambda x:x[:4]);used=set();pairs=[]
for day,gap,fsid,rsid,f,r in edges:
 if (day,fsid) in used or (day,rsid) in used:continue
 used.update([(day,fsid),(day,rsid)])
 pairs.append(dict(day=day,year=day[:4],sector=f['sector'],role=f['funded_role'],roles=f['roles'],funded_sid=fsid,rejected_sid=rsid,rank_gap=gap,**{f'f_{k}':v for k,v in f.items() if k not in ['day','sector','roles','status','sid']},**{f'r_{k}':v for k,v in r.items() if k not in ['day','sector','roles','status','sid']}))
mp=pd.DataFrame(pairs)
h=hashlib.sha256(json.dumps([(p['day'],p['funded_sid'],p['rejected_sid']) for p in pairs]).encode()).hexdigest()
assert len(mp)==151 and h=='4e1400bce427bba682b1511d7c07ccf1a75f877b6527eff01ba8c45fe5ccf7e8',(len(mp),h)
mp.to_csv(OUT/'EXACT_151_MATCHED_PAIRS_BEFORE_SCORES.csv',index=False)
print('MATCH_HASH',len(mp),mp.day.nunique(),h,flush=True)
# Matching and hash fixed before joining scores or outcome labels.
cal=json.loads((C.J.M.P/'calendars.json').read_text()) if (C.J.M.P/'calendars.json').exists() else None
print('CALENDAR_FILE',str(C.J.M.P),cal.keys() if isinstance(cal,dict) else None,flush=True)
sm={r['symbol']:r for r in json.load(open('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json'))}
hh=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False); dates=pd.DatetimeIndex(hh['dates'])
if cal is not None:
 cd=cal['A'];cd=cd['dates'] if isinstance(cd,dict) and 'dates' in cd else cd
 dates_label=pd.DatetimeIndex(pd.to_datetime(cd)).tz_localize(None).normalize()
else: dates_label=pd.DatetimeIndex(days)
assert dates_label.is_unique
dmap={str(d.date()):j for j,d in enumerate(dates_label)}
features={};facts={};all_keys=set()
for p in pairs:
 for side in ['funded','rejected']:all_keys.add((p[side+'_sid'],p['day'],p['role']))
for sid in sorted({k[0] for k in all_keys}):
 f=pd.read_parquet(sm[sid]['refs']['facts']);facts[sid]=f;features[sid]=score_one(f,dates)
r=[]
for sid,day,role in sorted(all_keys):
 q=features[sid].loc[day];i=ib[day,sid,role];floor=float(i['floor']);close=float(q.close)
 risk=np.log(close/floor) if 0<floor<close else np.nan
 ext=np.log(close)-q.pred_t;reward=20*q.beta-ext;score=reward/risk
 r.append(dict(sid=sid,day=day,role=role,close=close,floor=floor,risk=risk,beta=q.beta,pred_t=q.pred_t,extension=ext,reward20=reward,Q=score,known=bool(np.isfinite(score))))
features_df=pd.DataFrame(r);features_df.to_csv(OUT/'PAIRED_ROLE_SCORES_BEFORE_LABELS.csv',index=False)
for side,prefix in [('funded','f'),('rejected','r')]:
 z=features_df.rename(columns={x:prefix+'_'+x for x in features_df if x not in ['sid','day','role']})
 mp=mp.merge(z,left_on=[side+'_sid','day','role'],right_on=['sid','day','role'],validate='one_to_one').drop(columns='sid')
mp['swap']=mp.f_known&mp.r_known&(mp.r_Q.round(12)>mp.f_Q.round(12))
mp.to_csv(OUT/'PAIRED_SEALED_DECISIONS.csv',index=False)
dump('PAIRED_SEAL_BEFORE_LABELS.json',dict(matching_hash=h,known_pairs=int((mp.f_known&mp.r_known).sum()),swap_pairs=int(mp.swap.sum()),decision_sha256=sha(OUT/'PAIRED_SEALED_DECISIONS.csv'),definition='Exact pre-existing151 budget pairs. Q for actual funded role on BOTH stocks from ORIGINAL SIGNAL pending floor, never filled-layer floor. If either unknown or Q tie keep original. Only pair-level choice, not joint execution.'))
# Labels after independent seal. Same source common-date anchor, open +5bp, no future membership filtering.
labels=[]
for sid,day,role in sorted(all_keys):
 f=facts[sid].reindex(dates_label);t=dmap[day];en=t+1
 raw_full=pd.read_parquet(records[sid]['raw']['path']);raw_full.index=pd.to_datetime(raw_full.trade_date)
 op=raw_full.open.reindex(dates_label).to_numpy(float)*f.factor.to_numpy(float)*1.0005
 cc=f.close.to_numpy(float);r=dict(sid=sid,day=day,role=role)
 for H in [20,60]:
  end=t+H;ok=en<len(cc)and end<len(cc)and np.isfinite(op[en])and op[en]>0 and np.isfinite(cc[en:end+1]).all()and (cc[en:end+1]>0).all()
  r['complete'+str(H)]=bool(ok);r['ret'+str(H)]=cc[end]/op[en]-1 if ok else np.nan
  r['mae'+str(H)]=min(0,cc[en:end+1].min()/op[en]-1)if ok else np.nan
  r['mfe'+str(H)]=max(0,cc[en:end+1].max()/op[en]-1)if ok else np.nan
 labels.append(r)
labels=pd.DataFrame(labels)
for side,prefix in [('funded','f'),('rejected','r')]:
 z=labels.rename(columns={x:prefix+'_'+x for x in labels if x not in ['sid','day','role']})
 mp=mp.merge(z,left_on=[side+'_sid','day','role'],right_on=['sid','day','role'],validate='one_to_one').drop(columns='sid')
mp.to_csv(OUT/'PAIRED_RESULTS_WITH_LABELS.csv',index=False)
result=[]
for year,g in [('ALL',mp)]+list(mp.groupby('year')):
 for H in [20,60]:
  z=g[g['f_complete'+str(H)]&g['r_complete'+str(H)]].copy()
  if not len(z):continue
  z['delta']=np.where(z.swap,z['r_ret'+str(H)]-z['f_ret'+str(H)],0)
  z['risk_delta']=np.where(z.swap,z['r_mae'+str(H)]-z['f_mae'+str(H)],0)
  z['tail_delta']=np.where(z.swap,z['r_mfe'+str(H)]-z['f_mfe'+str(H)],0)
  changed=z[z.swap]
  result.append(dict(year=year,horizon=H,pairs=len(z),swaps=int(z.swap.sum()),dates=z.day.nunique(),pair_mean_delta=z.delta.mean(),date_mean_delta=z.groupby('day').delta.mean().mean(),date_mae_delta=z.groupby('day').risk_delta.mean().mean(),date_mfe_delta=z.groupby('day').tail_delta.mean().mean(),changed_better=int(changed.delta.gt(0).sum()),changed_worse=int(changed.delta.lt(0).sum()),baseline_mean=z['f_ret'+str(H)].mean(),chosen_mean=(z['f_ret'+str(H)]+z.delta).mean()))
results=pd.DataFrame(result);results.to_csv(OUT/'PAIRED_ANNUAL_RESULTS.csv',index=False)
print('RESULTS');print(results.to_string(index=False))
dump('PAIR_RECONSTRUCTION_AUDIT.json',dict(matching_hash=h,match_rows=len(mp),match_dates=mp.day.nunique(),complete20=int((mp.f_complete20&mp.r_complete20).sum()),complete60=int((mp.f_complete60&mp.r_complete60).sum()),label_calendar_source=str(C.J.M.P/'calendars.json')if cal is not None else 'original daily account calendar',no_account_run=True,original_pending_floor=True))
