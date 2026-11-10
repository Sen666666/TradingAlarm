"""Fixed risk-reduction benchmark; not an added fusion signal candidate."""
from pathlib import Path
import json,hashlib,datetime
import pandas as pd,numpy as np
R=Path(__file__).resolve().parent;P=R.parent/'strategy-switching-20261024';O=R/'results/v0';receipt=R/'cash-reference-protocol.json'
assert not receipt.exists()
receipt.write_text(json.dumps({'recorded_before_reference_calculation_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'Separate the incremental value of R from simply deploying less capital in E0. This benchmark is essential to interpret the fixed50/50 fusion, and is not a new signal candidate or weight search. Added after the fusion results, explicitly disclosed.','scope':'Gold continuous window only; all three existing execution scenarios','formula':'NAV_ref = 0.5 * NAV_E0 + 0.5 cash; cash interest0, no transfers/rebalance','additional_reference_paths':3,'additional_signal_accounts':0,'fusion_weights_unchanged':True,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2))
rows=[]
for sc in ['base','cost2','delay1']:
 l=pd.read_parquet(P/'results/v0/accounts'/f'continuous_USHJ518880__E0__{sc}/ledger.parquet');v=.5*l.nav+.5;dd=v/np.maximum.accumulate(np.r_[1.,v.to_numpy()])[1:]-1;out=pd.DataFrame({'nav':v,'drawdown':dd,'cash':.5*l.cash+.5,'quantity':.5*l.quantity,'close':l.close});np.testing.assert_allclose(out.nav,out.cash+out.quantity*out.close,atol=1e-12)
 out.to_parquet(O/f'gold-half-E0-cash__{sc}.parquet');rows.append(dict(policy='half_E0_half_cash',scenario=sc,net_return=float(v.iloc[-1]-1),max_drawdown=float(-dd.min()),role='risk_reduction_benchmark_not_fusion_candidate'))
pd.DataFrame(rows).to_csv(O/'cash-reference-summary.csv',index=False);print(pd.DataFrame(rows).to_string(index=False))
