"""Independent contemporaneous sector/CP1 diagnosis. No account replay or fitting."""
from pathlib import Path
import json,hashlib,math
import numpy as np,pandas as pd
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
B=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
O=Path(__file__).resolve().parent
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
MP=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
CASES=[('600606.SH','2022-03-22'),('002385.SZ','2022-03-04'),('688582.SH','2024-07-29'),('300182.SZ','2022-01-04'),('600056.SH','2022-03-03'),('601607.SH','2022-03-24'),('300666.SZ','2026-01-05'),('603061.SH','2026-01-05'),('300666.SZ','2026-01-15'),('603061.SH','2026-01-15')]
KEYDATES=sorted(set(d for s,d in CASES)|{'2024-09-24'})
FREEZE={'status':'mechanism hypothesis frozen before new case feature inspection; development history, not OOS','score':'LDP=exp(tanh(Zrel20))*((1+B20_peer_t)/(1+B20_peer_tminus5))*exp(tanh(log(share5_peer/median_prior21_share_peer)))','Zrel20':'sum last20 residual daily log returns / (std residual prior20 excluding today * sqrt20); residual=stock log return - equal-weight mean peer log return; no annualization; zero denominator unknown','diffusion':'B20 and tminus5 on intersection of valid peer members at both dates; peers exclude candidate; denominator window exactly prior20 mean including that close; higher-level market no hard gate','amount':'daily peer sector CNY amount / total available fixed1709 CNY amount excluding candidate; share5=mean t-4..t; reference=median t-25..t-5, nonoverlapping prior21; exp(tanh(log ratio)) bounded (e^-1,e)','clock':'after close t only; rank existing legal empty MOBILE CP1 candidates descending LDP, then original PVR descending, sid; next independent common trading open. Unknown score retains original PVR slot; no changed eligibility, number of slots, budget, exits, or CP1 computation','limits':'fixed future-selected1709 stock pool and non-PIT industry roster; amount share is trading-activity share, NOT net capital inflow; changing availability counts disclosed; relative-return peer index uses available mean daily return; 20 residual observations required','cases':CASES,'keydates':KEYDATES,'account_runs':0,'grid_searches':0}
(O/'FORMULA_FREEZE.json').write_text(json.dumps(FREEZE,ensure_ascii=False,indent=2))
meta=json.loads(MP.read_text());manifest={r['symbol']:r for r in json.loads(U.read_text())}
h=np.load(P/'h1.npz');dates=pd.DatetimeIndex(h['dates']);symbols=list(h['symbols']);ids=[s for s in symbols if not s.startswith('URFI')]
assert len(ids)==1709
C=pd.DataFrame(h['close'],index=dates,columns=symbols).loc['2021-09-01':'2026-02-27'].copy();G=pd.DataFrame(h['segment'],index=dates,columns=symbols).reindex(C.index)
C=C.where(np.isfinite(C)&C.gt(0));ma=C.rolling(20,min_periods=20).mean().where(G.eq(G.shift(19)));K=C.notna()&ma.notna();above=C.gt(ma);R=np.log(C).diff().where(G.eq(G.shift()))
A={};V={};audit=[]
for n,s in enumerate(ids):
 f=pd.read_parquet(P/'bars'/f'{s}.parquet',columns=['trade_date','amount','volume','amount_unit','price_eligible','volume_eligible','observed_bar']);f=f.set_index('trade_date').reindex(C.index)
 good=f.price_eligible.fillna(False).astype(bool)&f.volume_eligible.fillna(False).astype(bool)&f.observed_bar.fillna(False).astype(bool)&f.amount_unit.eq('CNY')
 A[s]=f.amount.where(good&f.amount.gt(0));V[s]=f.volume.where(good&f.volume.gt(0));audit.append({'sid':s,'available':int(A[s].notna().sum())})
 if n%400==0:print('AMOUNT',n,flush=True)
A=pd.DataFrame(A);V=pd.DataFrame(V);VR=V/V.shift().rolling(21,min_periods=21).median();TOTAL=A.sum(axis=1,min_count=1)
sectors={s:[i for i in ids if meta[i]['sector_id']==s] for s in sorted({meta[i]['sector_id'] for i in ids})}
market=pd.DataFrame({'market_B20':(above[ids]&K[ids]).sum(axis=1)/K[ids].sum(axis=1),'market_known':K[ids].sum(axis=1),'amount_known':A.notna().sum(axis=1)})
paired=K[ids]&K[ids].shift(5,fill_value=False);market['market_dB5']=((above[ids].astype(int)-above[ids].shift(5,fill_value=False).astype(int))*paired).sum(axis=1)/paired.sum(axis=1)
cache={}
def features(sid):
 if sid in cache:return cache[sid]
 sec=meta[sid]['sector_id'];peers=[x for x in sectors[sec] if x!=sid];k=K[peers];a=above[peers];pair=k&k.shift(5,fill_value=False);npair=pair.sum(axis=1)
 b=(a&k).sum(axis=1)/k.sum(axis=1);bpair=(a&pair).sum(axis=1)/npair;bprev=(a.shift(5,fill_value=False)&pair).sum(axis=1)/npair
 peer_r=R[peers].mean(axis=1);res=R[sid]-peer_r;z=res.rolling(20,min_periods=20).sum()/(res.shift().rolling(20,min_periods=20).std(ddof=0).replace(0,np.nan)*np.sqrt(20));rel=res.cumsum();relhigh=rel-rel.shift().rolling(20,min_periods=20).max();offrel=np.log(C[sid]/C[sec]);offhigh=offrel-offrel.shift().rolling(20,min_periods=20).max()
 share=A[peers].sum(axis=1,min_count=1)/(TOTAL-A[sid]);sh5=share.rolling(5,min_periods=5).mean();shref=share.shift(5).rolling(21,min_periods=21).median();flow=sh5/shref;D=(1+bpair)/(1+bprev);L=np.exp(np.tanh(z));F=np.exp(np.tanh(np.log(flow)));score=L*D*F
 f=pd.DataFrame({'sid':sid,'sector':sec,'name':meta[sid]['name'],'industry':meta[sid]['industry'],'close':C[sid],'peer_n':k.sum(axis=1),'peer_pair_n':npair,'B20_peer':b,'dB5_peer':bpair-bprev,'up1_peer':R[peers].gt(0).sum(axis=1)/R[peers].notna().sum(axis=1),'positive5_peer':(C[peers]/C[peers].shift(5)-1).gt(0).sum(axis=1)/(C[peers]/C[peers].shift(5)-1).notna().sum(axis=1),'peer_ret5':np.expm1(peer_r.rolling(5,min_periods=5).sum()),'stock_ret5':C[sid]/C[sid].shift(5)-1,'stock_ret20':C[sid]/C[sid].shift(20)-1,'residual20':res.rolling(20,min_periods=20).sum(),'Zrel20':z,'rel_high20_log':relhigh,'official_rel_high20_log':offhigh,'sector_peer_amount_share':share,'sector_peer_share5':sh5,'sector_peer_share_prior21':shref,'amountshare_ratio':flow,'peer_amount_n':A[peers].notna().sum(axis=1),'target_amount_share_sector':A[sid]/A[sectors[sec]].sum(axis=1,min_count=1),'target_amount_ratio21':A[sid]/A[sid].shift().rolling(21,min_periods=21).median(),'peer_median_volume_ratio21':VR[peers].median(axis=1),'peer_up_amount_share':A[peers].where(R[peers].gt(0),0).sum(axis=1)/A[peers].sum(axis=1,min_count=1),'L':L,'D':D,'F':F,'LDP':score}).join(market)
 cache[sid]=f;return f
summ=[];daily=[]
for sid,d in CASES:
 f=features(sid).copy();cp=pd.read_parquet(manifest[sid]['refs']['CP1']);facts=pd.read_parquet(manifest[sid]['refs']['facts']);f['cp_receipt']=cp.receipt.reindex(f.index);f['cp_reset_reason']=cp.reset_reason.reindex(f.index);f['cp_credit']=cp.credit.reindex(f.index);f['cp_displacement']=cp.displacement.reindex(f.index);f['cp_scale']=cp.scale.reindex(f.index);f['i_buy']=facts.i_buy.reindex(f.index);f['i_target']=facts.i_target.reindex(f.index);f['raw_close']=facts.raw_close.reindex(f.index)
 f['case_signal_day']=d;summ.append(f.loc[[d]]);at=f.index.get_loc(d);daily.append(f.iloc[max(0,at-10):at+11])
summary=pd.concat(summ).reset_index(names='day');daily=pd.concat(daily).reset_index(names='day');summary.to_csv(O/'FIXED_SIGNAL_SUMMARY.csv',index=False);daily.to_csv(O/'FIXED_DAILY.csv',index=False)
# Date-level sector rows, excluding no particular candidate, not for stock ranking.
ss=[]
for sec,mem in sectors.items():
 k=K[mem];a=above[mem];pair=k&k.shift(5,fill_value=False);b=(a&k).sum(axis=1)/k.sum(axis=1);delta=((a.astype(int)-a.shift(5,fill_value=False).astype(int))*pair).sum(axis=1)/pair.sum(axis=1);sh=A[mem].sum(axis=1,min_count=1)/TOTAL;r=R[mem].mean(axis=1)
 z=pd.DataFrame({'sector':sec,'industry':meta[mem[0]]['industry'],'members':len(mem),'known':k.sum(axis=1),'B20':b,'dB5':delta,'up1':R[mem].gt(0).sum(axis=1)/R[mem].notna().sum(axis=1),'ret5':np.expm1(r.rolling(5,min_periods=5).sum()),'amount_share':sh,'amount_share5':sh.rolling(5,min_periods=5).mean(),'amount_share_ratio':sh.rolling(5,min_periods=5).mean()/sh.shift(5).rolling(21,min_periods=21).median(),'volume_ratio21_median':VR[mem].median(axis=1)}).join(market)
 z=z.loc[(z.index.isin(KEYDATES))|((z.index>='2024-09-16')&(z.index<='2024-10-09'))|((z.index>='2025-12-22')&(z.index<='2026-01-23'))].copy();ss.append(z)
pd.concat(ss).reset_index(names='day').to_csv(O/'SECTORS_DAILY.csv',index=False)
# Frozen original candidate mother, same-day ranking only, no return based tuning.
cand=pd.read_parquet(B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');cand=cand[(cand.account=='PVR')&cand.day.isin(KEYDATES)].copy();rows=[]
for rr in cand.itertuples():
 v=features(rr.sid).loc[rr.day].to_dict();v.update(rr._asdict());rows.append(v)
x=pd.DataFrame(rows);out=[]
for d,g in x.groupby('day',sort=True):
 g=g.sort_values(['original_PVR','sid'],ascending=[False,True]).copy();g['PVR_same_mother_rank']=range(1,len(g)+1);known=np.isfinite(g.LDP);slots=g.loc[known,'PVR_same_mother_rank'].tolist();order=g.loc[known].sort_values(['LDP','original_PVR','sid'],ascending=[False,False,True]).index;g['LDP_same_mother_rank']=g.PVR_same_mother_rank;g.loc[order,'LDP_same_mother_rank']=slots;out.append(g)
x=pd.concat(out);x.to_csv(O/'FIXED_DATE_CANDIDATE_RANKS.csv',index=False)
# Exact prefix checks: formulas rolled causally; reconstruct target core features with truncated matrices.
checks=[]
for sid,d in CASES:
 t=C.index.get_loc(d);f=features(sid);peers=[a for a in sectors[meta[sid]['sector_id']] if a!=sid];re=(R[sid].iloc[:t+1]-R[peers].iloc[:t+1].mean(axis=1));z=re.rolling(20,min_periods=20).sum()/(re.shift().rolling(20,min_periods=20).std(ddof=0)*np.sqrt(20));same=bool(np.isclose(z.iloc[-1],f.loc[d,'Zrel20'],equal_nan=True));checks.append({'sid':sid,'day':d,'Zrel20_prefix_exact':same})
assert all(c['Zrel20_prefix_exact'] for c in checks)
(O/'CHECKS.json').write_text(json.dumps({'stocks':len(ids),'cases':len(CASES),'candidate_rows':len(x),'prefix_checks':checks,'account_runs':0,'original_indicator_replays':0},indent=2))
paths=[P/'h1.npz',MP,U,B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',Path(__file__)];(O/'SOURCE_HASHES.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2))
cols=['sid','day','cp_receipt','i_buy','B20_peer','dB5_peer','peer_ret5','stock_ret5','Zrel20','rel_high20_log','amountshare_ratio','target_amount_share_sector','peer_median_volume_ratio21','LDP','market_B20','market_dB5']
print(summary[cols].round(5).to_string(index=False));print('OUTPUT',O,flush=True)
