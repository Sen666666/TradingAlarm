from pathlib import Path
import datetime,hashlib,json
from models import configurations
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
paths=[HERE/'models.py',HERE/'run.py',HERE/'PROTOCOL.md',HERE/'freeze.py',HERE.parent/'gold-temperature-inference-20261024/calibrate.py',HERE.parent/'gold-temperature-inference-20261024/refined-targets.json',HERE.parent/'gold-temperature-inference-20261024/measured-daily.csv',HERE.parent/'gold-chart-fit-20261024/data/sina-AU0.csv',HERE.parent/'three-layer-prototype-20261024/results/v0/daily/AU0.parquet']
paths+=sorted((HERE.parent/'gold-chart-fit-20261024/results/v0/daily').glob('*.parquet'))
record=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),purpose='User-authorized bounded offline price/volume formula identification; no account/WeChat access',configurations=configurations(),hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
with (HERE/'freeze.json').open('x') as f:json.dump(record,f,ensure_ascii=False,indent=2);f.write('\n')
print('frozen',len(record['configurations']),'configurations',len(paths),'code/input files')
