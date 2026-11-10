"""One frozen CP effective-balance signal; original cache, no account/sizing."""
from pathlib import Path
import importlib.util
import json, hashlib, csv
import pandas as pd
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HELPER = ROOT / 'balance.py'
FREEZE = ROOT / 'FREEZE.md'
ORIGINAL = HERE / 'ORIGINAL_FULL_PREFIX_CP_FACTS.parquet'
OUT = HERE / 'fixed_balance_run'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [clean(x) for x in v]
    if v is None or v is pd.NA: return None
    if isinstance(v, np.generic): v = v.item()
    if isinstance(v, pd.Timestamp): return str(v.date())
    if isinstance(v, float) and not np.isfinite(v): return None
    return v
def save(name, v): (OUT / name).write_text(json.dumps(clean(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    OUT.mkdir(exist_ok=False)
    sources = {str(p): sha(p) for p in (HELPER, FREEZE, ORIGINAL, Path(__file__), HERE / 'PREPARATION_RECEIPT.json')}
    spec = importlib.util.spec_from_file_location('silver_frozen_balance', HELPER)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    f = pd.read_parquet(ORIGINAL)
    cp = f[[c for c in f if c.startswith('oldCP__')]].rename(columns=lambda c: c[7:])
    q = f[[c for c in f if c.startswith('q__')]].rename(columns=lambda c: c[3:])
    balance = helper.calculate(cp, q)
    cut = '2024-10-16'
    prefix = helper.calculate(cp.loc[:cut], q.loc[:cut])
    assert prefix.equals(balance.loc[:cut])
    selected = f.loc['2024-09-01':'2024-11-30']
    original_annotation_path = HERE / 'ORIGINAL_DAILY_FACTS.json'; sources[str(original_annotation_path)] = sha(original_annotation_path)
    annotations = {r['day']: r for r in json.loads(original_annotation_path.read_text())}
    rows = []
    for t, raw in selected.iterrows():
        day = str(t.date()); old = clean(cp.loc[t].to_dict()); new = clean(balance.loc[t].to_dict()); note = annotations[day]
        rows.append(dict(sid='300085.SZ', day=day, C=raw['q__close'], raw_C=raw['native__raw_close'],
            original_I_target=raw['q__i_target'], original_E0_event=raw['originalE0__event'],
            old_CP=old, fixed_balance=new,
            canonical_original_CP_id=None if note['original_canonical_receipt'] is None else note['original_canonical_receipt']['receipt_id'],
            recorded_original_intents_only=note['recorded_original_intents_only'],
            original_actual_layer_ids=[x['original']['layer'] for x in note['original_actual_buys_from_this_signal']],
            permission_scope='Market effective advance only for potential continuous MATURE_ADD. Not V5 mature/position/ACK/financial grant; original CORE and per-UP probe are outside this filter.'))
    raw_receipts = [r for r in rows if r['old_CP']['receipt']]
    assert len(rows) == 58 and len(raw_receipts) == 16
    save('ALL_58_DAILY.json', rows); save('ALL_16_ORIGINAL_CP_RECEIPTS.json', raw_receipts)
    flat = [dict(day=r['day'], C=r['C'], raw_C=r['raw_C'],
        original_E0_event=r['original_E0_event'], original_I_target=r['original_I_target'],
        original_CP_receipt=r['old_CP']['receipt'], original_CP_candidate=r['old_CP']['candidate'],
        original_reset_reason=r['old_CP']['reset_reason'], original_r=r['old_CP']['r'], original_m=r['old_CP']['m'],
        original_delta_frontier=r['old_CP']['delta_frontier'], original_used_scale=r['old_CP']['scale'],
        **r['fixed_balance'], canonical_original_CP_id=r['canonical_original_CP_id'],
        original_actual_layer_ids=r['original_actual_layer_ids']) for r in rows]
    for name, subset in [('ALL_58_DAILY.csv', flat), ('ALL_16_ORIGINAL_CP_RECEIPTS.csv', [r for r in flat if r['original_CP_receipt']])]:
        with (OUT / name).open('w', newline='') as out:
            w = csv.DictWriter(out, fieldnames=list(flat[0])); w.writeheader()
            w.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in r.items()} for r in subset)
    key_days = {'2024-10-09','2024-10-10','2024-10-11','2024-10-14','2024-10-16','2024-11-01','2024-11-05'}
    save('FIXED_KEY_DAYS.json', [r for r in rows if r['day'] in key_days])
    summary = dict(original_CP_receipts=16, effective_advance_receipts=sum(r['fixed_balance']['effective_advance'] for r in raw_receipts),
        effective_days=[r['day'] for r in raw_receipts if r['fixed_balance']['effective_advance']],
        rejected_original_CP_days=[r['day'] for r in raw_receipts if not r['fixed_balance']['effective_advance']],
        first_original_receipt=raw_receipts[0]['day'],
        first_effective_advance=next((r['day'] for r in raw_receipts if r['fixed_balance']['effective_advance']), None),
        original_actual_layer_signal_annotations=[dict(layer=layer, day=r['day'], effective_advance=r['fixed_balance']['effective_advance']) for r in raw_receipts for layer in r['original_actual_layer_ids']],
        restriction='Static original-signal touch only, no avoided-loss/candidate-return/account claim.')
    save('SUMMARY.json', summary)
    save('PREFIX_CHECK.json', dict(cutoff=cut, full_original_first_day=str(f.index[0].date()),
                                  prefix_original_observations=len(prefix), exact_all_helper_columns=True))
    assert all(sha(p) == expected for p, expected in sources.items())
    save('RUN_RECEIPT.json', dict(status='FROZEN_SINGLE_BALANCE_SIGNAL_COMPLETE', source_sha256=sources,
         helper_LAMBDA=helper.LAMBDA, full_original_observations=len(f), display_observations=len(rows),
         original_CP_recomputed=False, new_E0_events=0, parameters_scanned=0,
         new_accounts=0, new_quantities=0, new_cash_paths=0, new_returns=0))
    save('OUTPUT_SHA256.json', {str(p): sha(p) for p in OUT.iterdir() if p.is_file() and p.name != 'OUTPUT_SHA256.json'})
    print(json.dumps(clean({'summary': summary, 'key_days': [dict(day=r['day'], old_receipt=r['old_CP']['receipt'], r=r['old_CP']['r'], m=r['old_CP']['m'], delta_frontier=r['old_CP']['delta_frontier'], **r['fixed_balance']) for r in rows if r['day'] in key_days]}), ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
