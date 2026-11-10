import json
from pathlib import Path
from collections import Counter
from ths_signal_adjustment import signal_frame
ROOT=Path(__file__).resolve().parent
raw_paths=sorted((ROOT/'data/ths-raw').glob('*.json'))
missing_rights=[p.stem for p in raw_paths if not (ROOT/'data/ths-rights'/p.name).exists()]
rows=[]
for path in sorted((ROOT/'data/ths-rights').glob('*.json')):
 raw=ROOT/'data/ths-raw'/path.name
 if not raw.exists():continue
 try:
  frame=signal_frame(json.loads(raw.read_text()),json.loads(path.read_text()))
  rows.append(dict(symbol=path.stem,status='signal_transform_available',rows=len(frame),event_days=int(frame.factor.diff().fillna(0).ne(0).sum()),synthetic_event_days=int(frame.synthetic_event_bar.sum())))
 except (ValueError,KeyError,TypeError) as exc:rows.append(dict(symbol=path.stem,status='requires_review',reason=str(exc)))
report=dict(start='2013-01-01',reason='Two-year warmup before2015evaluation; corporate actions before price anchor affect only irrelevant absolute scale.',partial_snapshot=bool(missing_rights),raw_symbols=len(raw_paths),missing_rights=missing_rights,records=rows,available=sum(x['status']=='signal_transform_available' for x in rows),review=sum(x['status']=='requires_review' for x in rows),review_reasons=dict(Counter(x['reason'] for x in rows if 'reason' in x)),ledger_ready=False,limitation='Transformation availability is not source completeness or account-backtest certification.')
(ROOT/'results/stock-data-audit/ths-signal-readiness.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False,indent=2))
