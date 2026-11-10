
from pathlib import Path
import pandas as pd,numpy as np,json
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/cp1_signal_mechanism_v1');B=O.parent/'mobile_candidate_response_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
labels=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet').set_index(['sid','day'])
r=pd.read_csv(O/'REJECTED_FIRST_NATURAL_NEW_SIGNAL.csv');old=r.recovery_signal_close_vs_original_open.copy()
for sid,idx in r.groupby('sid').groups.items():
 f=pd.read_parquet(sm[sid]['refs']['facts'])
 for j in idx:
  day=r.at[j,'first_new_joint_market_day'];signal=r.at[j,'signal_day']
  r.at[j,'recovery_signal_close_vs_original_open']=float(f.at[pd.Timestamp(day),'close']/labels.at[(sid,signal),'entry_adjusted_open']-1)if pd.notna(day)else np.nan
r.to_csv(O/'REJECTED_FIRST_NATURAL_NEW_SIGNAL_CORRECTED.csv',index=False)
(O/'RECOVERY_PRICE_COORDINATE_CORRECTION.json').write_text(json.dumps(dict(reason='Initial recovery-only quote comparison used canonical adjusted original entry open against native fact recovery close. Corrected file uses native open from FIXED_NATIVE_PRICE_LABELS. No gate, acceptance, ranking, PnL, or coverage result changed.',affected_rows=int((old.fillna(0)-r.recovery_signal_close_vs_original_open.fillna(0)).abs().gt(1e-10).sum()),authoritative_file='REJECTED_FIRST_NATURAL_NEW_SIGNAL_CORRECTED.csv'),indent=2))
stats=[]
for(a,y),g in r.groupby(['account','year']):
 z=g[g.original_closed_in_entry_year]if y==2022 else g[g.original_closed]
 for win,w in [('winner',z[z.original_pnl>0]),('loser',z[z.original_pnl<0])]:
  stats.append(dict(account=a,year=y,group=win,n=len(w),next_joint_ever=int(w.first_new_joint_market_day.notna().sum()),next_joint_within5=int(w.wait_common_days.le(5).sum()),next_joint_within20=int(w.wait_common_days.le(20).sum()),median_wait=w.wait_common_days.median(),median_recovery_quote_change=w.recovery_signal_close_vs_original_open.median()))
pd.DataFrame(stats).to_csv(O/'REJECTED_FIRST_RECOVERY_SUMMARY.csv',index=False)
j=pd.read_csv(O/'ACTUAL_FIRST_MOBILE_GATE_ATTRIBUTION.csv')
print('PVR RECOVERY');print(pd.DataFrame(stats).query("account=='PVR'").to_string(index=False))
print('2024-25_REJECTED_WINNERS');print(j[(j.account=='PVR')&j.year.isin([2024,2025])&~j.accepted&j.round_pnl.gt(0)].sort_values('round_pnl',ascending=False)[['sid','signal_day','entry_day','closed_day','round_pnl','original_g_grade','original_i_buy','close_MFE20','ret20_forward']].head(8).to_string(index=False))
# Lost roots natural recovery independent of whether original account then held stock.
roots=pd.read_csv(O/'GATE_ROOT_EPISODES.csv');lost=roots[roots.big60&roots.ORIGINAL_PVR_capture&~roots.EMPTY_MOBILE_I_AND_CP_capture]
sel=pd.read_parquet(B/'SEALED_SAME_K_SELECTIONS.parquet');sel=sel[sel.strategy=='ORIGINAL_PVR']
c=pd.read_parquet(O/'EMPTY_MOBILE_SIGNAL_GATE.parquet')
h=np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz');ds=pd.DatetimeIndex(h['dates']);ds=ds[(ds>='2022-01-01')&(ds<='2026-05-15')];cal={str(d.date()):i for i,d in enumerate(ds)}
im=json.loads((U/'INDUSTRY_MANIFEST.json').read_text());st={}
for x in im:
 z=pd.read_parquet(x['refs']['state']).set_index('day');st[x['series']]=z.E0_valid&z.attempt_id.notna()&z.stage.gt(0)
out=[]
for sid,g in lost.groupby('sid'):
 f=pd.read_parquet(sm[sid]['refs']['facts']);cp=pd.read_parquet(sm[sid]['refs']['CP1']);sector=c[c.sid==sid].sector.iloc[0]
 active=pd.Series(st[sector].to_numpy(),index=pd.to_datetime(st[sector].index)).reindex(f.index).fillna(False)
 joint=f.i_buy.eq(True)&cp.receipt.eq(True)&active
 for q in g.itertuples():
  z=sel[(sel.account==q.account)&sel.sid.eq(sid)&sel.epoch.eq(q.epoch)&sel.t.between(cal[q.birth_day],cal[q.birth_day]+5)].sort_values('t')
  assert len(z);first=z.iloc[0];cut=ds[min(cal[q.birth_day]+5,len(ds)-1)]
  possible=f.index[(f.index>pd.Timestamp(first.day))&(f.index<=cut)&joint]
  after=f.index[(f.index>pd.Timestamp(first.day))&(f.index<=pd.Timestamp('2026-05-15'))&joint]
  out.append(dict(account=q.account,year=q.year,sid=sid,epoch=q.epoch,birth_day=q.birth_day,first_original_selected_blocked_day=first.day,new_joint_signal_inside_original_early_window=bool(len(possible)),first_joint_in_early_window=str(possible[0].date())if len(possible)else None,first_later_joint=str(after[0].date())if len(after)else None))
pd.DataFrame(out).to_csv(O/'LOST_ROOT_NATURAL_RECOVERY.csv',index=False)
print('LOST ROOT RECOVERY');print(pd.DataFrame(out).groupby(['account','year']).agg(lost_roots=('sid','size'),natural_joint_in_early_window=('new_joint_signal_inside_original_early_window','sum')).to_string())
