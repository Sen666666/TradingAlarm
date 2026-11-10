"""Post-output summaries, not optimization targets or strategy thresholds."""
import numpy as np,pandas as pd
from data import HERE,read,write,now,NAMES

def main():
 out=HERE/'analysis';out.mkdir(exist_ok=False);rows=[];points={
 'AU0':['2023-01-03','2023-03-31','2023-08-31','2025-09-01','2025-10-22','2026-01-30','2026-02-02','2026-02-09','2026-04-01','2026-06-30'],
 '518880':['2025-04-22','2025-05-15','2025-08-29','2025-09-01'],
 '512480':['2022-04-26','2022-08-05','2022-09-16','2022-10-11','2026-06-29','2026-07-02','2026-07-14','2026-07-15'],
 '001309.SZ':['2026-06-29','2026-07-01','2026-07-02','2026-07-07','2026-07-15','2026-07-16','2026-07-17','2026-07-21','2026-07-22'],
 '688981.SH':['2024-09-23','2024-09-24','2024-09-30','2024-10-08','2024-10-09'],
 '600519.SH':['2024-09-23','2024-09-24','2024-09-30','2024-10-08','2024-10-09'],
 '600036.SH':['2024-01-02','2024-05-31']};stats=[];preview={}
 for sid in NAMES:
  f=pd.read_parquet(HERE/'results'/(sid+'.parquet'));v=f.loc['2021-01-01':].copy();g=v.dropna(subset=['strength']);delta=v.strength.diff();cond=np.isfinite(v.strength)&np.isfinite(v.total_21_strength)
  stats.append(dict(asset=sid,name=NAMES[sid],scored=len(g),positive=int(g.strength.gt(0).sum()),negative=int(g.strength.lt(0).sum()),saturated_abs95=int(g.strength.abs().ge(95).sum()),sign_changes=int((np.sign(g.strength).diff().abs()>0).sum()),s_vs_total_sign_disagreements=int((np.sign(v.loc[cond,'strength'])!=np.sign(v.loc[cond,'total_21_strength'])).sum()),e0_active_negative_s=int((v.e0_target.eq(1)&v.strength.lt(0)).sum())))
  for date in points[sid]:
   sub=f.loc[:date];x=sub.iloc[-1];i=f.index.get_loc(sub.index[-1]);c0=float(f.close.iloc[i-1]);r5=float(x.close/f.close.iloc[max(i-5,0)]-1)
   rows.append(dict(asset=sid,name=NAMES[sid],requested=date,date=str(sub.index[-1].date()),close=float(x.close),day_return=float(x.close/c0-1),five_observation_return=r5,strength=float(x.strength),price_only=float(x.price_only_strength),e0_active=bool(x.e0_target),e0_floor=float(x.e0_floor) if np.isfinite(x.e0_floor) else None,drift_21_pct=float(x.drift_21_pct),temporary_sigma=float(x.temporary_sigma),total_21_strength=float(x.total_21_strength),model_total_21_pct=float(100*np.expm1(x.total_21_log_forecast))))
  z=v[['close','strength','price_only_strength','e0_target','e0_floor','drift_21_pct','temporary_sigma','total_21_strength','normal_weight','persistent_weight','transient_weight']].copy();z.insert(0,'date',z.index.strftime('%Y-%m-%d'));preview[sid]=__import__('json').loads(z.to_json(orient='records'))
 write(out/'selected-facts.json',rows);pd.DataFrame(rows).to_csv(out/'selected-facts.csv',index=False,encoding='utf-8-sig');write(out/'full-sample-stats.json',stats);write(out/'viewer-data.json',preview)
 write(out/'summary.json',dict(recorded_at=now(),no_accounts=True,synthetic_checks_before_real_visual_review=True,real_cache_generated_before_synthetic_execution_disclosed=True,main_vs_total_disagreement_days=sum(x['s_vs_total_sign_disagreements'] for x in stats),thresholds_95_and0_descriptive_only=True,trade_signals_inferred=False))
 print({'point_rows':len(rows),'statistics':stats},flush=True)
if __name__=='__main__':main()
