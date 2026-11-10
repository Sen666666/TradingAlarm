from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,time
O=Path(__file__).resolve().parent;R=O.parent;U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
c=pd.read_csv(O/'ALL_M3_RESULTS.csv',parse_dates=['day','entry_day','exit_day'],dtype={'window':str});c=c[c.baseline_selected&c.event_type.eq('FALSE_TO_TRUE')].copy()
z=pd.read_csv(R/'breadth_pvr3_priority_v1/rounds/ALL_SHADOW_ROUNDS.csv',low_memory=False);z=z[z.ranking_strategy.eq('ALL_FEASIBLE_DIAGNOSTIC')]
extra=['event_id','sid','entry_risk','floor_raw','first_profitable_close','profitable_close_days','first_CP_fresh','exit_price','exit_reason','all_fees','negative_CP_blocked','industry_first_decline']
c=c.merge(z[extra],on=['event_id','sid'],how='left',validate='one_to_one')
sm={x['symbol']:x for x in json.load(open(U/'STOCK_MANIFEST.json'))}
im=json.load(open(U/'INDUSTRY_MANIFEST.json'));cal=pd.DatetimeIndex(sorted(set().union(*[set(pd.read_parquet(x['refs']['CP1_input']).index) for x in im])));cal=cal[cal<=pd.Timestamp('2026-06-30')]
cases=set()
for w,g in c[c.label.isin(['W','L'])].groupby('window'):
 for _,r in pd.concat([g.nsmallest(3,'core_net'),g.nlargest(2,'core_net')]).drop_duplicates(['event_id','sid']).iterrows():cases.add((r.event_id,r.sid))
for sid,day in [('603938.SH','2022-03-21'),('000921.SZ','2022-11-03'),('300085.SZ','2024-09-12'),('003021.SZ','2024-10-22')]:
 q=c[c.sid.eq(sid)&c.day.eq(day)]
 for _,r in q.iterrows():cases.add((r.event_id,r.sid))
Path(O/'CASE_DEFINITION.json').write_text(json.dumps({'selection':'Post-result descriptive fixed: each window worst3 core_net and best2 plus named structural contrasts; not blind evidence','cases':sorted(cases)},indent=2,ensure_ascii=False))
rows=[];daily=[];started=time.monotonic()
for j,(sid,g) in enumerate(c.groupby('sid',sort=True)):
 m=sm[sid];sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));p=pd.read_parquet(sp).reindex(cal);f=pd.read_parquet(m['refs']['facts']).reindex(cal);cp=pd.read_parquet(m['refs']['CP1']).reindex(cal)
 for _,r in g.iterrows():
  row=r.to_dict();t=cal.get_loc(r.day);e=cal.get_loc(r.entry_day) if pd.notna(r.entry_day) else None;x=cal.get_loc(r.exit_day) if pd.notna(r.exit_day) else None
  if r.label in ['W','L']:
   path=p.iloc[e:x];ret=path.raw_close/r.entry_price-1
   assert path.raw_close.notna().all()
   row.update(hold_days=x-e,held_close_MFE=max(0,ret.max()),held_close_MAE=min(0,ret.min()),never_profitable=pd.isna(r.first_profitable_close),core_loss_to_plan=(-r.core_net/r.entry_risk if r.core_net<0 else np.nan),close_ret_at_exit_signal=p.raw_close.iloc[x-1]/r.entry_price-1)
   row['first5_held_close_MFE']=max(0,ret.iloc[:5].max())
   for h in [1,3,5,10]:row['r'+str(h)+'_if_still_held']=ret.iloc[h-1] if len(ret)>=h else np.nan
   ff=float(f.i_floor.iloc[x-1]/p.adjustment_factor.iloc[x-1]);ff2=float(f.i_floor.iloc[x-2]/p.adjustment_factor.iloc[x-2]);close=float(p.raw_close.iloc[x-1]);sell=float(r.exit_price);q=float(r.entry_q)
   # The original exit-signal row retains floor on I loss. Fallback never silently used.
   row.update(exit_signal_day=cal[x-1],exit_signal_close=close,exit_signal_floor=ff,previous_active_floor=ff2,exit_open=float(p.raw_open.iloc[x]),initial_to_exit_floor_loss=q*(r.entry_price-ff),floor_to_signal_close_loss=q*(ff-close),signal_close_to_exit_fill_loss=q*(close-sell),core_gross_loss=q*(r.entry_price-sell),core_fee_loss=-r.core_net-q*(r.entry_price-sell))
   assert abs(row['initial_to_exit_floor_loss']+row['floor_to_signal_close_loss']+row['signal_close_to_exit_fill_loss']-row['core_gross_loss'])<1e-7
   if (r.event_id,sid) in cases:
    for k in range(max(0,t-10),x+1):
     d=cal[k];zz=p.iloc[k];fr=f.iloc[k];cr=cp.iloc[k]
     daily.append(dict(event_id=r.event_id,sid=sid,name=r['name'],day=d,phase='PRE_SIGNAL' if k<t else ('SIGNAL' if k==t else ('EXIT_OPEN_AFTER_SIGNAL' if k==x else 'HELD')),raw_open=zz.raw_open,raw_high=zz.raw_high,raw_low=zz.raw_low,raw_close=zz.raw_close,raw_volume=zz.raw_volume,amount=zz.amount,I_target=fr.i_target,I_buy=fr.i_buy,G_grade=fr.g_grade,I_floor=fr.i_floor/zz.adjustment_factor,CP_receipt=cr.receipt,CP_candidate=cr.candidate/zz.adjustment_factor,close_vs_entry=zz.raw_close/r.entry_price-1))
  rows.append(row)
 if (j+1)%250==0:print('PATHS',j+1,round(time.monotonic()-started,1),flush=True)
d=pd.DataFrame(rows);d.to_csv(O/'BASELINE_PATH_DIAGNOSTICS.csv',index=False);pd.DataFrame(daily).to_csv(O/'CASES_DAILY.csv',index=False)
cd=d[d.apply(lambda r:(r.event_id,r.sid) in cases,axis=1)];cd.to_csv(O/'CASES_SUMMARY.csv',index=False)
s=[]
for win,g in d.groupby('window'):
 closed=g[g.label.isin(['W','L'])];loss=closed[closed.net_pnl.le(0)];coreloss=closed[closed.core_net.le(0)]
 s.append(dict(window=win,closed=len(closed),W=sum(closed.net_pnl>0),L=len(loss),core_W=sum(closed.core_net>0),core_L=len(coreloss),final_loss_never_profitable=int(loss.never_profitable.sum()),final_loss_prior_profitable=int((~loss.never_profitable.astype(bool)).sum()),core_loss_never_profitable=int(coreloss.never_profitable.sum()),core_loss_MFE_ge10=int(coreloss.held_close_MFE.ge(.1).sum()),core_loss_MFE_ge20=int(coreloss.held_close_MFE.ge(.2).sum()),core_loss_exceed_plan=int(coreloss.core_loss_to_plan.gt(1).sum()),max_loss_to_plan=coreloss.core_loss_to_plan.max(),median_loss_to_plan=coreloss.core_loss_to_plan.median(),gross_core_losses=-coreloss.core_net.sum(),mean_signal_floor_D=closed.D.mean(),top_exit_date=coreloss.exit_day.value_counts().index[0] if len(coreloss) else None,top_exit_date_N=int(coreloss.exit_day.value_counts().max()) if len(coreloss) else 0))
ss=pd.DataFrame(s);ss.to_csv(O/'MECHANISM_SUMMARY.csv',index=False)
grp=d[d.label.isin(['W','L'])].groupby(['window','G_grade']).agg(N=('sid','size'),wins=('net_pnl',lambda s:(s>0).sum()),mean_net=('net_pnl','mean'),mean_core=('core_net','mean'),mean_MFE=('held_close_MFE','mean'),mean_D=('D','mean'));grp.to_csv(O/'G_GRADE_DESCRIPTION.csv')
ex=d[d.label.isin(['W','L'])&d.core_net.lt(0)].groupby(['window','exit_day']).agg(N=('sid','size'),loss=('core_net','sum'),breach_loss=('floor_to_signal_close_loss','sum'),overnight_loss=('signal_close_to_exit_fill_loss','sum'));ex.to_csv(O/'EXIT_DATE_DESCRIPTION.csv')
print('MECHANISM\n',ss.to_string(index=False));print('G_GRADE\n',grp.to_string())
show=['window','day','name','PVR_score','G_grade','D','floor_progress','Q','ret3','ret20','amount_relative21','I_age','I_buy_today','CP1_today','entry_price','entry_risk','core_net','add_net','held_close_MFE','hold_days','never_profitable','core_loss_to_plan','exit_signal_floor','exit_signal_close','exit_open','initial_to_exit_floor_loss','floor_to_signal_close_loss','signal_close_to_exit_fill_loss']
print('CASES\n',cd[show].to_string(index=False))
