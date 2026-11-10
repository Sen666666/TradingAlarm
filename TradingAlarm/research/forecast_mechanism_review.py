"""Reconcile forecast error decomposition; no fitted model or trading rule."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
out=ROOT/'results/forecast-mechanism-review';out.mkdir(exist_ok=True)
source=ROOT/'results/segmented-forecast-audit/forecasts.parquet';f=pd.read_parquet(source)
np.testing.assert_allclose(f.squared_error,(f.prediction-f.actual)**2,rtol=1e-12,atol=1e-14)
np.testing.assert_allclose(f.rw_error,f.actual**2,rtol=1e-12,atol=1e-14)
rows=[]
for (group,year,model,h),g in f.groupby(['group','year','model','horizon']):
 p=g.prediction.to_numpy();a=g.actual.to_numpy();energy=float(np.mean(p*p));alignment=float(np.mean(p*a));rw=float(np.mean(a*a));mse=float(np.mean((p-a)**2))
 assert abs(mse-rw-energy+2*alignment)<1e-12
 rows.append(dict(group=group,year=int(year),model=model,horizon=int(h),n=len(g),mse_ratio=mse/rw,prediction_energy=energy,twice_alignment=2*alignment,alignment_positive=alignment>0,signed_actual_mean=float(np.mean(np.sign(p)*a)),direction_accuracy=float(np.mean(np.sign(p)==np.sign(a)))))
s=pd.DataFrame(rows);s.to_csv(out/'annual-decomposition.csv',index=False)
files=['results/trajectory-break-diagnostic/decision.json','results/anchored-forecast-diagnostic/decision.json','results/segmented-forecast-audit/decision.json','results/strength-segmented/decision.json']
report={'status':'evidence_review_complete_no_strategy_adopted','forecast_rows_verified':len(f),'annual_cells':len(s),'mse_worse_cells':int(s.mse_ratio.gt(1).sum()),'positive_alignment_cells':int(s.alignment_positive.sum()),'source_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files},'forecast_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'interpretation':['MSE excess equals prediction energy minus twice prediction/actual alignment. This identity separates overlarge extrapolation from useful directional alignment.','Positive in-sample alignment is not a calibrated forecast, independent evidence, or attainable trading profit. No oracle shrink coefficient is fitted or adopted.','Earlier one-day negative surprise failed to distinguish temporary pullback and sustained decline; do not restart the same mechanism with another threshold.','Forecast MSE is not a sufficient acceptance/rejection gate for the requested asymmetric trend utility. Acceptance still requires net ordinary trade economics, right-tail participation, drawdown and cost/delay transfer.'],
 'next':'Return to shared-capital sector allocation: compare existing frozen trend scores under the same entry opportunities and capital budget, with sector gate and initial equal sizing fixed; audit candidate coverage first. Do not add another forecast factor or relabel tested history as holdout.'}
(out/'review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
p=ROOT/'progress.json';d=json.loads(p.read_text());d['latest_forecast_mechanism_review']={'status':'completed','review':'results/forecast-mechanism-review/review.json','next':report['next']};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
print({k:report[k] for k in ['forecast_rows_verified','annual_cells','mse_worse_cells','positive_alignment_cells']})
print(s.groupby(['model','horizon']).agg(cells=('n','size'),positive_alignment=('alignment_positive','sum')).to_string())
