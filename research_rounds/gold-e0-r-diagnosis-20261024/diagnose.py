from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';DATA=R.parent/'market-regimes-exit-20261024/inputs/USHJ518880.parquet'
sys.path.insert(0,str(P));from legacy import context
(R/'evidence').mkdir(exist_ok=True)
d=pd.read_parquet(DATA);e,b,f=context(d);old=pd.read_parquet(R.parent/'three-layer-prototype-20261024/inputs/USHJ518880.parquet')
z=d.loc['2021-01-01':'2026-10-16'];assert len(z)==1400
for c in ['open','high','low','close','volume']:np.testing.assert_array_equal(d[c],old['raw_'+c])
np.testing.assert_array_equal(old.adjustment_factor,np.ones(len(old)));assert old.valid.all() and old.geometry_valid.all()
pd.testing.assert_frame_equal(b,pd.read_parquet(P/'contexts/USHJ518880/shadow-E0.parquet'),check_exact=True)
e.to_parquet(R/'evidence/events.parquet');f.to_parquet(R/'evidence/features.parquet')
t0=pd.read_csv(P/'results/v0/accounts/continuous_USHJ518880__E0__base/trades.csv');tr=pd.read_csv(P/'results/v0/accounts/continuous_USHJ518880__R__base/trades.csv')
assert t0.entry_date.tolist()==tr.entry_date.tolist();np.testing.assert_array_equal(t0.entry_price,tr.entry_price);assert tr.exit_reason.eq('atr2').all()
x=pd.DataFrame({'entry':t0.entry_date,'E0_exit':t0.exit_date,'R_exit':tr.exit_date,'E0_return':t0.net_return,'R_return':tr.net_return,'E0_pnl':t0.net_pnl,'R_pnl':tr.net_pnl,'log_gap':np.log1p(t0.net_return)-np.log1p(tr.net_return),'E0_terminal':t0.terminal})
waits=[]
for i,row in x.iterrows():
 rdt=pd.Timestamp(row.R_exit);edt=pd.Timestamp(row.E0_exit);entry=pd.Timestamp(row.entry);nextentry=pd.Timestamp(x.entry.iloc[i+1]) if i+1<len(x) else z.index[-1]
 x.loc[i,'E0_observations']=len(z.loc[entry:edt]);x.loc[i,'R_observations']=len(z.loc[entry:rdt]);x.loc[i,'waiting_to_next_entry_calendar_days']=(nextentry-rdt).days
 sig=pd.Timestamp(tr.exit_signal.iloc[i]);sR=pd.read_parquet(P/'prepared/continuous_USHJ518880/R.parquet');v=f.loc[sig]
 x.loc[i,'signal_atr_pct']=100*v.atr;x.loc[i,'signal_q']=v.q;x.loc[i,'signal_close']=d.loc[sig,'close'];x.loc[i,'R_exit_line']=sR.loc[sig,'exit_line'];x.loc[i,'E0_floor']=b.loc[sig,'floor']
 ev=e.loc[sig:edt];ups=ev[ev.event.eq(1)]
 for dt,evrow in ups.iterrows():waits.append(dict(original_entry=str(entry.date()),recognized=str(dt.date()),close=float(d.loc[dt,'close']),q=float(f.loc[dt,'q']),pivot=float(evrow.confirmed_pivot_price),pivot_date=evrow.confirmed_pivot_date,prior_floor=float(b.floor.shift().loc[dt]),updated_floor=float(b.floor.loc[dt]),R_target=int(sR.target.loc[dt]),E0_new_entry=int(b.entered.loc[dt])))
x['log_gap_share']=x.log_gap/x.log_gap.sum();x.to_csv(R/'evidence/paired-cycles.csv',index=False);pd.DataFrame(waits).to_csv(R/'evidence/ignored-up-events.csv',index=False)
# Counterfactual here means signal evidence, not a new trading strategy or account.
for entry in ['2022-07-27','2023-10-16','2024-08-20']:
 print('WAITING EVENTS',entry);print(pd.DataFrame(waits).query('original_entry==@entry').head(10).to_string(index=False))
print(x.round(5).to_string(index=False))
meta=dict(symbol='USHJ518880',first=str(z.index[0].date()),last=str(z.index[-1].date()),observations=len(z),input_sha256=hashlib.sha256(DATA.read_bytes()).hexdigest(),raw_equal_adjusted_all_fields=True,adjustment_factors_all_one=True,identical_entry_dates_prices=14,R_all_14_atr_exits=True,log_wealth_ratio=float(x.log_gap.sum()),dominant_cycle_share=float(x.loc[x.entry.eq('2024-08-20'),'log_gap_share'].iloc[0]),top3_log_gap_share=float(x.log_gap.nlargest(3).sum()/x.log_gap.sum()),original_accounts_not_rerun=True,new_signal_accounts=0)
(R/'input-checks.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(json.dumps(meta,ensure_ascii=False))
