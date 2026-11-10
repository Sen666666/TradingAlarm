
from pathlib import Path
import json,gzip,hashlib
import pandas as pd,numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
W=U.parent;R=O.parents[1]/'account_comparison_continuous_v1';S=O.parent/'mobile_candidate_response_v1'
def read(p):return json.loads(Path(p).read_text())
sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')}
manifest={r['sid']:r for r in read(W/'2022-normal-reference-20261031/inputs/MANIFEST.json')}
first=pd.read_csv(O.parent/'ALL_FIRST_ENTRIES.csv')
q1=first[(first.account=='PVR')&first.closed_in_entry_year&first.quarter.eq('2022Q1')&first.first_kind.eq('add')]
freq=q1.groupby('sid').agg(rounds=('sid','size'),losers=('round_pnl',lambda x:(x<0).sum()),pnl=('round_pnl','sum'))
freq.sort_values(['losers','pnl'],ascending=[False,True]).to_csv(O/'Q1_MOBILE_ROUND_FREQUENCY.csv')
losers=list(freq.sort_values(['losers','pnl'],ascending=[False,True]).head(3).index)
winner=q1.sort_values('round_pnl',ascending=False).iloc[0].sid
sids=losers+[winner];assert sids==['002385.SZ','600056.SH','601607.SH','600606.SH']
acct=json.load(gzip.open(R/'run_1200000/pair/PVR.json.gz','rt'))
cand=pd.read_parquet(S/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');cand=cand[cand.account=='PVR']
pieces=[];receipt_stats=[]
for sid in sids:
 f=pd.read_parquet(sm[sid]['refs']['facts']);cp=pd.read_parquet(sm[sid]['refs']['CP1']);inp=pd.read_parquet(sm[sid]['refs']['CP1_input'])
 assert f.index.equals(cp.index)and cp.index.equals(inp.index)
 z=f[['close','raw_close','factor','segment_id','e0_target','i_target','i_buy','g_grade']].copy()
 for col in cp:z['cp_'+col]=cp[col]
 z['native_down_event']=inp.e0_down
 for seg,g in f.groupby('segment_id',sort=False):
  c=g.close.where(np.isfinite(g.close)&g.close.gt(0))
  z.loc[g.index,'ema5']=c.ewm(span=5,adjust=False,min_periods=5).mean()
  z.loc[g.index,'ema21']=c.ewm(span=21,adjust=False,min_periods=21).mean()
  z.loc[g.index,'ma21']=c.rolling(21,min_periods=21).mean()
  sd=c.rolling(21,min_periods=21).std(ddof=0)
  z.loc[g.index,'bb_upper']=c.rolling(21,min_periods=21).mean()+2*sd
  z.loc[g.index,'bb_lower']=c.rolling(21,min_periods=21).mean()-2*sd
  rm=cp.loc[g.index,'r']*cp.loc[g.index,'m']
  z.loc[g.index,'net21_weighted']=rm.rolling(21,min_periods=21).sum()
  z.loc[g.index,'eff21_weighted']=rm.rolling(21,min_periods=21).sum()/(cp.loc[g.index,'r'].abs()*cp.loc[g.index,'m']).rolling(21,min_periods=21).sum().replace(0,np.nan)
 z['ema21_change5']=z.groupby('segment_id').ema21.diff(5)
 z['ema5_above_ema21']=z.ema5>z.ema21
 z['close_above_ema21']=z.close>z.ema21
 z['cp_threshold']=np.sqrt(5)*z.cp_scale
 z['price_evidence_ratio']=z.cp_displacement/z.cp_threshold
 z['credit_evidence_ratio']=z.cp_credit/z.cp_threshold
 z['CP_new_anchor_return']=np.exp(z.cp_displacement)-1
 recs=read(manifest[sid]['output_path']);recmap={r['confirmed_day']:r for r in recs}
 z['formation_start']=pd.Series({pd.Timestamp(d):r['formation_start_exclusive']for d,r in recmap.items()})
 z['receipt_id']=pd.Series({pd.Timestamp(d):r['receipt_id']for d,r in recmap.items()})
 sc=pd.read_parquet(Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores')/(sid+'.parquet'))
 z['original_PVR']=sc.score.reindex(z.index)
 z=z.loc['2021-12-01':'2022-04-15'].copy()
 z['sid']=sid;z['day']=z.index.strftime('%Y-%m-%d')
 ck=cand[cand.sid==sid].set_index('day')
 z['legal_empty_mobile']=z.day.isin(ck.index)
 rds=first[(first.account=='PVR')&first.sid.eq(sid)].set_index('entry_day')
 z['actual_first_kind']=z.day.map(rds.first_kind)
 z['actual_round_pnl']=z.day.map(rds.round_pnl)
 z['actual_round_close']=z.day.map(rds.closed_day)
 for d in z.day:
  ts=[t for t in acct['trades']if t['security_id']==sid and t['at'][:10]==d]
  ix=pd.Timestamp(d);z.loc[ix,'buy_gross']=sum(float(t['gross_cny'])for t in ts if t['side']=='buy')
  z.loc[ix,'sell_gross']=sum(float(t['gross_cny'])for t in ts if t['side']=='sell')
  z.loc[ix,'buy_signal_days']='|'.join(t['signal_at'][:10]for t in ts if t['side']=='buy')
  z.loc[ix,'sell_reasons']='|'.join(sorted(set(t['reason']for t in ts if t['side']=='sell')))
 q=z.loc['2022-01-01':'2022-03-31']
 receipt_stats.append(dict(sid=sid,Q1_original_CP_receipts=int(q.cp_receipt.sum()),Q1_legal_empty_mobile=int(q.legal_empty_mobile.sum()),Q1_first_mobile_rounds=int((q.actual_first_kind=='add').sum()),Q1_negative_event_resets=int(q.native_down_event.sum())))
 pieces.append(z.reset_index(drop=True))
daily=pd.concat(pieces,ignore_index=True)
daily.to_csv(O/'FOUR_STOCKS_DAILY.csv',index=False)
signals=daily[daily.cp_receipt|daily.legal_empty_mobile|daily.actual_first_kind.notna()|daily.buy_gross.gt(0)|daily.sell_gross.gt(0)]
signals.to_csv(O/'FOUR_STOCKS_EVENTS.csv',index=False)
pd.DataFrame(receipt_stats).to_csv(O/'FOUR_STOCKS_COUNTS.csv',index=False)
q1.to_csv(O/'ALL_Q1_MOBILE_FIRST_CLOSED_ROUNDS.csv',index=False)
print('COUNTS');print(pd.DataFrame(receipt_stats).to_string(index=False))
print('ACTUAL_FIRST_SIGNAL_FEATURES')
sigs=first[(first.account=='PVR')&first.sid.isin(sids)&first.quarter.eq('2022Q1')][['sid','signal_day','entry_day','first_kind','round_pnl']]
sigs=sigs.merge(daily,left_on=['sid','signal_day'],right_on=['sid','day'],how='left')
cols=['sid','signal_day','entry_day','first_kind','round_pnl','raw_close','original_PVR','cp_phase','formation_start','native_down_event','cp_delta_frontier','price_evidence_ratio','credit_evidence_ratio','net21_weighted','eff21_weighted','close_above_ema21','ema5_above_ema21','ema21_change5']
sigs[cols].to_csv(O/'FIRST_ENTRY_SIGNAL_FEATURES.csv',index=False)
print(sigs[cols].round(6).to_string(index=False))
