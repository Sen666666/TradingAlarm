"""Exercise the entire publication pipeline using retained THS responses. No network/backtest."""
import json
import shutil
import sys
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk.data import MarketData,ROOT,BASE
import desk.refresh as refresh


def main():
    tmp=Path(tempfile.mkdtemp(prefix='tradingalarm-update-replay-'));runtime=tmp/'runtime';runtime.mkdir();old=MarketData(runtime)
    reference=ROOT/'research_rounds/rs-h1-execution-20261025';original=json.loads((reference/'inputs-v2/input-manifest.json').read_text())
    prefix=tmp/'prefix';prefix.mkdir();original['series']=[r for r in original['series'] if r['series_id'] in old.columns];refresh.atomic(prefix/'manifest.json',original)
    old.published={'path':str(prefix)};old.h1_path=reference/'h1/matrix.npz';old.as_of='2026-10-22';old.recovery=old.recovery.loc[:old.as_of]
    old.facts={s:f.loc[:old.as_of].copy() for s,f in old.facts.items()}
    fixtures={p.stem:p for source in ['tail-v3','reference-tail'] for p in (BASE/source).glob('batch-*/checkpoints/*.json')}
    original_module=refresh.module
    def fixture_module(name,path):
        m=original_module(name,path)
        if name=='desk_history_batch':
            class RecordedCollector(m.Collector):
                def run(self):
                    for item in self.plan['items']:
                        source=fixtures[item['symbol']];cp=json.loads(source.read_text());folder=source.parents[1]
                        target=self.out/'history'/f"{item['symbol']}.json";target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(folder/'history'/target.name,target)
                        target=self.out/'checkpoints'/source.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
                        if item['rights']:
                            right=Path(cp['rights']['attempt']);dst=self.out/right;dst.mkdir(parents=True,exist_ok=True)
                            shutil.copy2(folder/right/'decoded.json',dst/'decoded.json')
            m.Collector=RecordedCollector
        return m
    refresh.module=fixture_module
    run=tmp/'replay';run.mkdir()
    receipt=refresh._update(old,'2026-10-26',run,lambda m:print(m,flush=True))
    new=Path(receipt['path'])
    for sid in old.facts:
        a=pd.read_parquet(new/'facts'/f'{sid}.parquet');b=pd.read_parquet(old.facts_dir/f'{sid}.parquet')
        for col in ['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_ready','factor','raw_close']:
            np.testing.assert_allclose(a[col].astype(float),b[col].astype(float),rtol=0,atol=0,equal_nan=True,err_msg=sid+'/'+col)
    with np.load(new/'h1.npz') as a,np.load(BASE/'prepared-v2/h1.npz') as b:
        np.testing.assert_array_equal(a['dates'],b['dates']);np.testing.assert_array_equal(a['score'],b['score'])
    m=MarketData(runtime);assert m.as_of=='2026-10-26' and m.integrity['passed']
    result=dict(passed=True,network_requests=0,new_backtests=0,series=len(old.columns),facts=len(old.facts),h1_full_rank_matrix_exact=True,publication_loaded=True,temporary_directory=str(tmp))
    (ROOT/'TradingAlarm/update-replay-verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)

if __name__=='__main__':main()
