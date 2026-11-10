"""One fixed ranking comparison; no future outcomes read before selection seal."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;V=R/'breadth_trade_contract_v1'
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
start=time.monotonic()
assert not (O/'SELECTION_SEAL.json').exists()
source_paths=[Path(__file__),O/'simulate.py',V/'causal_queue_full_v2/ALL_CANDIDATES_CLOSE_CHECKS.csv',V/'ALL_EVENTS.csv',V/'causal_queue_full_v2/SEALED_CLOSE_SELECTED.csv',V/'evaluate_full_queue_v2_clockfixed.py',R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',H,U/'STOCK_MANIFEST.json']
hashes={str(p):sha(p) for p in source_paths}
protocol=dict(created_utc=str(pd.Timestamp.now(tz='UTC')),one_selection_and_one_evaluation_only=True,not_unseen_or_OOS=True,prior_history_seen='Amount20 baseline and related historical results already seen; exploratory finite comparison, no promotion by selecting highest historical result.',windows=[['2022','2022-01-01','2022-12-31',None],['2024_924','2024-09-01','2024-12-31',None],['2026H1_SEMI','2026-01-01','2026-06-30','URFI881121']],arms={'PVR_DESC':'Original PVR scalar at exact t descending then sid, no H1 tie factor','H1_DESC':'Original H1 scalar at exact t descending then sid, no PVR tie factor','AMOUNT20_DESC':'Original CP1_input.amount.where(amount>0).rolling(20,min_periods=20).mean(), includes t, descending then sid; NOT same-day amount, not user-specified or proved best'},common_domain='All original28558 retained. All three arms use finite exact-t PVR and H1, known PVR state and valid observation, and amount20 known. No ffill. Unknown rank not considered weak. Common-domain eligibility refinement is separately disclosed; original5490 baseline remains reference.',amount_source='Canonical signal.amount exactly matches CP1_input.amount for all used rows. Amount20 uses latest20 rows including t, all positive, observed, price/volume eligible, nonsynthetic and non-source-invalid; source_kind/source_path/segment_id same. Not20 positive-value skipping. No factor-constancy requirement on real unadjusted turnover lookback; forward factor changes remainUNKNOWN.',selection='For each event and ranking scan whole common-known queue, use same prior sealed close I/price/lot/2% nominal/.25% plan risk/prior20capacity feasibility, first2PASS; freeze before forward prices. Next-open failure never backfills. No ranking threshold, blending, grid, outcome selection.',execution='Same original clockfixed full-v2:1.2m reference NAV,2% initial nominal,one max2% profitable freshCP add,cumulative4%,.25% plan risk,next common open +/-5bp,dated lot/fees,T+1,original I exit and CP add protection. Not user risk promises. Plan loss not hard stop loss. Same capacity proxy.',unknown='Strict original source/factor/dividend/missing price pathUNKNOWN,June30OPEN,no forced liquidation. Historical exchange orderability alwaysUNKNOWN.',reporting='Every window/industry-definition/event-type/ranking separate; closed/open/unknown/rejected,net win rate,mean win/loss,>=30%closed descriptive tail and additions. No aggregate portfolio return; same stocks repeat and overlap. Original actual cash/resources separate necessary-condition screen only,never admission,after2026-05-15UNKNOWN.',telemetry_fixes='Closed fees_to_date=all_fees; opening-action state refreshed before invalid-closeUNKNOWN. Conditional_liquidation fields remain dated historical mark,not closed realizedPnl.',quick_channel='Preserved separately; full quick-channel/shared capital account not run.',no_accounts=True)
save('PROTOCOL.json',protocol)
c=pd.read_csv(V/'causal_queue_full_v2/ALL_CANDIDATES_CLOSE_CHECKS.csv',parse_dates=['day'],low_memory=False)
assert len(c)==28558 and not c.duplicated(['event_id','sid']).any()
c=c.rename(columns={'selected_close_frozen':'original_selected_close_frozen','queue_rank':'original_queue_rank','rank':'original_rank'})
pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')[['sid','day','score','state','valid_observation']]
pv['day']=pd.to_datetime(pv.day);pv=pv.rename(columns={'score':'PVR_score','state':'PVR_state','valid_observation':'PVR_valid_observation'})
c=c.merge(pv,on=['sid','day'],how='left',validate='many_to_one',sort=False)
h=np.load(H,allow_pickle=False);di=pd.DatetimeIndex(h['dates']).get_indexer(c.day);si=pd.Index(h['symbols']).get_indexer(c.sid)
assert (di>=0).all() and (si>=0).all()
c['H1_score']=h['score'][di,si];c['H1_horizon']=h['h'][di,si];c['H1_reference_n']=h['nref'][di,si]
c['amount20_source_known']=False;c['amount20_source_reason']='NOT_CHECKED';c['amount20_source_count']=np.nan;c['amount20_valid_count']=np.nan;c['amount20_recomputed']=np.nan
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
for sid,g in c.groupby('sid',sort=False):
 m=sm[sid];sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));qp=Path(m['refs']['CP1_input'])
 hashes[str(sp)]=sha(sp);hashes[str(qp)]=sha(qp);p=pd.read_parquet(sp);q=pd.read_parquet(qp)
 liq=q.amount.where(q.amount.gt(0)).rolling(20,min_periods=20).mean()
 for ix,row in g.iterrows():
  d=row.day;pos=q.index.get_loc(d);ix20=q.index[max(0,pos-19):pos+1];x=p.reindex(ix20);expected=liq.get(d,np.nan);actual=row.rank_amount20
  assert (pd.isna(expected) and pd.isna(actual)) or np.isclose(expected,actual,rtol=1e-12,atol=1e-7),(sid,d,'amount20 mismatch',expected,actual)
  np.testing.assert_allclose(q.loc[ix20,'amount'].to_numpy(),x.amount.to_numpy(),rtol=0,atol=0,equal_nan=True)
  ok=x.observed_bar.fillna(False).astype(bool)&x.price_eligible.fillna(False).astype(bool)&x.volume_eligible.fillna(False).astype(bool)&~x.source_invalid.fillna(True).astype(bool)&~x.synthetic_event_bar.fillna(True).astype(bool)&x.amount.gt(0)&np.isfinite(x.amount)
  sc=len(x[['source_kind','source_path','segment_id']].drop_duplicates())
  known=len(x)==20 and bool(ok.all()) and sc==1 and bool(x[['source_kind','source_path','segment_id']].notna().all().all())
  c.loc[ix,['amount20_source_known','amount20_source_count','amount20_valid_count','amount20_recomputed']]=[known,sc,int(ok.sum()),expected]
  c.loc[ix,'amount20_source_reason']='KNOWN' if known else ('UNKNOWN_SHORT_OR_INVALID_AMOUNT20' if len(x)<20 or not ok.all() else 'UNKNOWN_AMOUNT20_SOURCE_CHANGE')
c['ranking_common_known']=np.isfinite(c.PVR_score)&c.PVR_state.ge(0)&c.PVR_valid_observation.fillna(False)&np.isfinite(c.H1_score)&np.isfinite(c.rank_amount20)&c.amount20_source_known
c['ranking_unknown_reason']=c.apply(lambda r:'|'.join(x for yes,x in [(not(np.isfinite(r.PVR_score) and r.PVR_state>=0 and bool(r.PVR_valid_observation)),'PVR_UNKNOWN'),(not np.isfinite(r.H1_score),'H1_UNKNOWN'),(not bool(r.amount20_source_known),str(r.amount20_source_reason))] if yes),axis=1)
c.to_csv(O/'ALL_CANDIDATES_COMMON_DOMAIN.csv',index=False);c[~c.ranking_common_known].to_csv(O/'UNKNOWN_RANK_CANDIDATES.csv',index=False)
allqueues=[]
for strategy,col in [('PVR_DESC','PVR_score'),('H1_DESC','H1_score'),('AMOUNT20_DESC','rank_amount20')]:
 z=c.copy();z['ranking_strategy']=strategy;z['rank']=np.nan;z['selected_close_frozen']=False
 for event,g in z.groupby('event_id',sort=False):
  v=g[g.ranking_common_known].sort_values([col,'sid'],ascending=[False,True],kind='stable');z.loc[v.index,'rank']=range(1,len(v)+1)
  passed=v[v.status.eq('PRICE_SIZE_PROXY_PASS_AT_CLOSE')];z.loc[passed.head(2).index,'selected_close_frozen']=True
 allqueues.append(z)
queue=pd.concat(allqueues,ignore_index=True);queue.to_csv(O/'ALL_RANKED_CLOSE_QUEUES.csv',index=False)
sel=queue[queue.selected_close_frozen].copy();sel.to_csv(O/'SEALED_CLOSE_SELECTED.csv',index=False)
summary=queue.groupby(['window','arm','event_type','ranking_strategy']).agg(candidate_rows=('sid','size'),ranking_common_known=('ranking_common_known','sum'),selected_at_close=('selected_close_frozen','sum')).reset_index();summary.to_csv(O/'COVERAGE.csv',index=False)
old=set(map(tuple,c[c.original_selected_close_frozen][['event_id','sid']].to_numpy()));new=set(map(tuple,sel[sel.ranking_strategy.eq('AMOUNT20_DESC')][['event_id','sid']].to_numpy()))
changes=c[c.apply(lambda r:(r.event_id,r.sid) in old^new,axis=1)].copy();changes['change']=changes.apply(lambda r:'REMOVED_BY_COMMON_DOMAIN' if (r.event_id,r.sid) in old else 'REPLACEMENT_AT_CLOSE_COMMON_DOMAIN',axis=1);changes.to_csv(O/'ORIGINAL_BASELINE_SELECTION_CHANGES.csv',index=False)
assert all(sha(p)==v for p,v in hashes.items())
save('SELECTION_SEAL.json',dict(created_utc=str(pd.Timestamp.now(tz='UTC')),hashes={str(O/n):sha(O/n) for n in ['PROTOCOL.json','ALL_CANDIDATES_COMMON_DOMAIN.csv','UNKNOWN_RANK_CANDIDATES.csv','ALL_RANKED_CLOSE_QUEUES.csv','SEALED_CLOSE_SELECTED.csv','COVERAGE.csv','ORIGINAL_BASELINE_SELECTION_CHANGES.csv']},source_hashes=hashes,all_candidates=len(c),common_known=int(c.ranking_common_known.sum()),unknown_rank_candidates=int((~c.ranking_common_known).sum()),selected=len(sel),baseline_original=len(old),baseline_common_domain=len(new),baseline_removed=len(old-new),baseline_added=len(new-old),seconds=time.monotonic()-start,no_future_labels_loaded_before_seal=True))
print(summary.to_string(index=False));print('SEAL',len(sel),'UNKNOWN',int((~c.ranking_common_known).sum()),'BASELINE',len(old),len(new),len(old-new),len(new-old),flush=True)
