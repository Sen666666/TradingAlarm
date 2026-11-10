from pathlib import Path
import datetime,hashlib,json
from signals import czsc,BUY_SETS,SPECS
from engine import SCENARIOS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
paths=[HERE/x for x in ['PROTOCOL.md','prepare.py','signals.py','engine.py','run.py','freeze.py','inputs/AU0-all.parquet','inputs/AU0-main.parquet','preparation.json']]
paths+=[ROOT/'research_rounds/gold-chart-fit-20261024/raw/sina-AU0.response']
record=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),user_authorization='Gold Chan buy-rule interval backtest with prehistory warmup; existing algorithms unchanged',period=['2025-01-02','2026-10-13'],czsc_version=czsc.__version__,native_path=czsc._native.__file__,native_sha256=hashlib.sha256(Path(czsc._native.__file__).read_bytes()).hexdigest(),min_bi_len=6,max_bi_num=100,buy_sets=BUY_SETS,signals=SPECS,scenarios=SCENARIOS,accounts=39,hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
with (HERE/'freeze.json').open('x') as fp:json.dump(record,fp,ensure_ascii=False,indent=2);fp.write('\n')
print('frozen',record['accounts'],'accounts; CZSC',czsc.__version__)
