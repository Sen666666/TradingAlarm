import json,hashlib
from pathlib import Path
import pandas as pd
import numpy as np
from calibrate_pair_order import calibration
from calibrated_order_signal import reset_signal
out=Path('results/strength-calibrated-order');f=pd.read_parquet(out/'training-score-pairs.parquet');saved=json.loads((out/'calibration.json').read_text())
assert f.index.max()<pd.Timestamp('2022-01-01')
r=calibration(f.pair.reset_index(drop=True),f.order.reset_index(drop=True))
for k in r:assert r[k]==saved[k]
ix=pd.bdate_range('2020-01-01',periods=800);rng=np.random.default_rng(3);c=pd.Series(np.exp(rng.normal(0,.025,800).cumsum()),index=ix);v=pd.Series(rng.uniform(1,100,800),index=ix)
for model in ['reset_pairwise_volume','reset_pair_order_volume','calibrated_pair_order_volume']:
    a=reset_signal(c,v,model);b=reset_signal(c.iloc[:650],v.iloc[:650],model)
    pd.testing.assert_series_equal(a.iloc[:650],b)
    assert a.loc[:'2021-12-31'].eq(0).all()
    np.testing.assert_array_equal(a,reset_signal(c*100,v*10,model))
result=dict(training_rows=len(f),training_symbols=f.symbol.nunique(),last_training_date=str(f.index.max().date()),threshold_exact_reproduced=True,three_model_prefix_and_unit_checks=True,flat_pre2022=True,training_sha256=hashlib.sha256((out/'training-score-pairs.parquet').read_bytes()).hexdigest(),calibration_sha256=hashlib.sha256((out/'calibration.json').read_bytes()).hexdigest())
(out/'calibration-validation.json').write_text(json.dumps(result,indent=2));print(result)
