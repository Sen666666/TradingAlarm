"""Six existing A-share histories: technical bridge comparison, no accounts."""
from pathlib import Path
import json
import sys
import pandas as pd
import numpy as np
import current_pool_bridge as b

root = Path(__file__).resolve().parents[1]
source = root / 'audit-a/fusion-smoke-6-v1/security-manifest.json'
out = root / 'audit-execution/bridge-validation/real-a-smoke-01'
out.mkdir(parents=True, exist_ok=False)
(out/'actions').mkdir()
inputs = json.loads(source.read_text())
series, lines, comparisons = [], [], []
sys.path.insert(0, str(b.ROOT/'TradingAlarm/research'))
from ths_signal_adjustment import signal_frame

for row in inputs:
    sid = row['symbol']
    rights = json.loads(Path(row['rights_path']).read_text())
    unresolved = [x for x in rights['unparsed'] if row['first'].replace('-','') <= str(x['row']['1']) <= row['last'].replace('-','')]
    events = []
    for e in rights['events']:
        if row['first'] < e['effective_date'] <= row['last']:
            events.append(dict(effective_date=e['effective_date'],
                cash_per_old_share=str(e['gross_cash_per_old_share']),
                split_ratio=str(1+b.decimal(e['bonus_shares_per_old_share'])+b.decimal(e['capitalization_shares_per_old_share'])),
                source_id=row['rights_sha256']))
    action = dict(series_id=sid, currency='CNY', status='reviewed_terms',
        coverage_evidence={'description':'All received THS terms within exact signal source window parsed; not a complete corporate-action or payment ledger certificate',
                           'rights_path':row['rights_path'], 'sha256':row['rights_sha256'],
                           'start':row['first'], 'end':row['last']},
        complete_actions_certified=False, ledger_ready=False,
        events=events, unresolved=unresolved,
        ignored_before_origin=[x for x in rights['unparsed'] if str(x['row']['1']) < row['first'].replace('-','')])
    ap = out/'actions'/f'{sid}.json'
    ap.write_text(json.dumps(action, ensure_ascii=False, indent=2)+'\n')
    record = dict(series_id=sid, kind='stock', status='ready', currency='CNY',
        source_start=row['first'], volume_unit='shares', price_adjustment='raw',
        close_available_time='15:05:00', raw={'path':row['bars_path'],'sha256':row['bars_sha256']},
        adjustment={'method':'theoretical_ex_price','actions':{'path':str(ap),'sha256':b.sha256(ap)}})
    series.append(record)
    lines.append(dict(security_id=sid, market='A', issuer_id=None, sector_id=None,
                      company_cap_cny=None, current_stock=True))
    raw = b.read_raw(Path(row['bars_path']),record)
    prepared = b.prepare_signal(raw,record,events)
    old_bars = raw.reset_index().to_dict('records')
    old = signal_frame({'symbol':row['ths_symbol'],'bars':old_bars},
        {'symbol':row['ths_symbol'],'records':rights['records']}, start=row['first'])
    maximum = max(float(((prepared[c]-old['signal_'+c]).abs()/old['signal_'+c].abs()).max()) for c in b.OHLC)
    prefix_checks = []
    for cut in (len(raw)//3, len(raw)*2//3):
        prefix=b.prepare_signal(raw.iloc[:cut],record,events)
        pd.testing.assert_frame_equal(prefix, prepared.loc[:raw.index[cut-1]],check_exact=True,check_freq=False)
        prefix_checks.append(cut)
    comparisons.append(dict(series_id=sid,rows=len(raw),events=len(events),unresolved_in_window=len(unresolved),
        max_relative_price_difference_from_existing_float_helper=maximum,
        exact_source_prefix_checks=prefix_checks,
        note='Source precision uses Decimal action-only recurrence; no model or execution claim'))
selection=dict(snapshot_id='REAL-A-6-TECHNICAL-ONLY',observed_at='2026-10-22T23:34:00+08:00',
    source_id='Current master referenced by fused raw manifest '+b.sha256(source),lines=lines)
sp=out/'selection.json'; sp.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
manifest=dict(schema_version=1,scope_date='2026-10-22',research_basis=b.RESEARCH_BASIS,
    upstream_sha256={name:b.sha256(path) for name,path in b.UPSTREAM.items()},
    selection={'path':str(sp),'sha256':b.sha256(sp)},series=series,sector_series={},
    purpose='Technical sample only: source origin, adjustment, masks, fixed state production; no selection/cap/industry facts invented')
mp=out/'input-manifest.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
summary=b.write_bundle(b.load_bundle(mp,technical_sample=True),out/'prepared')
(out/'comparison.json').write_text(json.dumps(dict(accounts_run=0,technical_sample=True,series=comparisons,
    blocked=[x for x in summary['series'] if x['blocked_reason']]),ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'out':str(out),'series':len(series),'blocked':sum(bool(x['blocked_reason']) for x in summary['series']), 'accounts_run':0}))
