"""Read original layer/CP sell/daily records. No new market or account state."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal
import json, gzip, hashlib
import pandas as pd

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
WORK = BASE.parent
PAIR = WORK / 'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
CAMPAIGNS = WORK / 'structural_failure_v1/accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json'
CHAINS = WORK / 'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json'
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
SOURCES = {}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    SOURCES[str(p)] = sha(p)
    with (gzip.open(p, 'rt') if p.suffix == '.gz' else p.open()) as f: return json.load(f)
def save(n, x): (HERE / n).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str) + '\n')
def ref(section, i): return {'path': str(PAIR / 'B.json.gz'), 'index': f'{section}[{i}]', 'index_base': 0}
def pick(layer):
    return {k: layer.get(k) for k in ('id', 'sid', 'kind', 'qty', 'opened', 'signal_at', 'floor', 'last_core_line', 'pool', 'role', 'stock_structure')}


def main():
    book = read(PAIR / 'B.json.gz'); campaigns = read(CAMPAIGNS); chains = read(CHAINS)
    metas = {r['symbol']: r for r in read(SM)}
    layers = {x['id']: x for x in book['layers']}; by_sid = defaultdict(list)
    for layer in layers.values(): by_sid[layer['sid']].append(layer)
    camp_by_layer = {lid: c for c in campaigns for lid in c['layer_ids']}
    receipts = [(i, t) for i, t in enumerate(book['trades']) if t['side'] == 'sell' and any(p['reason'] == 'CP1_add_protection' for p in t.get('parts', []))]
    parts = [(i, t, p) for i, t in receipts for p in t['parts'] if p['reason'] == 'CP1_add_protection']
    candidates = []
    for ti, trade, part in parts:
        older = layers[part['layer']]
        if older['closed'] != trade['at']: continue
        survivors = [n for n in by_sid[trade['security_id']] if n['kind'] == 'add' and older['opened'] < n['opened']
                     and n['opened'][:10] < trade['at'][:10] and (n['closed'] is None or n['closed'] > trade['at'])]
        if survivors: candidates.append((ti, trade, older, survivors))
    candidates.sort(key=lambda c: Decimal(camp_by_layer[c[2]['id']]['endpoint_net']), reverse=True)
    assert [(c[2]['sid'], c[2]['id']) for c in candidates] == [('600926.SH', 1998), ('688088.SH', 1156)]
    daily = []; p = PAIR / 'daily.jsonl.gz'; SOURCES[str(p)] = sha(p)
    with gzip.open(p, 'rt') as f:
        for i, line in enumerate(f):
            record = json.loads(line)
            if record.get('account') == 'B': daily.append((i, record))
    output = []
    for ti, trade, older, survivors in candidates:
        sid = older['sid']; survivor = survivors[0]
        ai, request = max((i, x) for i, x in enumerate(book['audit']) if x.get('sid') == sid
                          and x.get('kind') == 'pilot_layer_exit' and older['id'] in x['layers'] and x['at'] < trade['at'])
        trigger = request['at'][:10]; fill_day = trade['at'][:10]
        pos = next(i for i, (_, d) in enumerate(daily) if d['at'][:10] == trigger)
        previous_line_index, previous = daily[pos - 1]; trigger_line_index, current = daily[pos]
        fill_line_index, after = next((i, d) for i, d in daily if d['at'][:10] == fill_day)
        before_layers = {x['id']: x for x in previous['layers'] if x['sid'] == sid}
        trigger_layers = {x['id']: x for x in current['layers'] if x['sid'] == sid}
        after_layers = {x['id']: x for x in after['layers'] if x['sid'] == sid}
        fact_path = Path(metas[sid]['refs']['facts']); SOURCES[str(fact_path)] = sha(fact_path)
        assert SOURCES[str(fact_path)] == metas[sid]['output_sha256'][str(fact_path)]
        facts = pd.read_parquet(fact_path)
        event_path = Path(next(p for p in metas[sid]['source_sha256'] if p.endswith('/events.parquet')))
        cp_path = Path(metas[sid]['refs']['CP1'])
        for source_path, expected in [(event_path, metas[sid]['source_sha256'][str(event_path)]),
                                      (cp_path, metas[sid]['output_sha256'][str(cp_path)])]:
            SOURCES[str(source_path)] = sha(source_path)
            assert SOURCES[str(source_path)] == expected
        events = pd.read_parquet(event_path); original_cp = pd.read_parquet(cp_path)
        def market_at(day):
            f = facts.loc[day]; e = events.loc[day]; cp = original_cp.loc[day]
            return dict(original_E0_event=None if pd.isna(e['event']) else int(e['event']),
                        native_I_target=int(f['i_target']), native_I_floor=str(f['i_floor']),
                        adjusted_C=str(f['close']), raw_C=str(f['raw_close']),
                        original_CP_receipt=bool(cp['receipt']),
                        original_CP_candidate=None if pd.isna(cp['candidate']) else str(cp['candidate']),
                        V3_mature='UNKNOWN_NOT_MAPPED_NO_NEW_V3_RUN')
        fact = facts.loc[trigger]; forward = facts.loc[trigger:survivor['closed'][:10]]
        original_requests = [(i, a) for i, a in enumerate(book['audit']) if a.get('sid') == sid
                            and a.get('kind') in ('pilot_layer_exit', 'exit_request') and survivor['opened'] <= a.get('at', '') <= trade['at']]
        targeted_later = [a for _, a in original_requests if a['kind'] == 'pilot_layer_exit' and survivor['id'] in a['layers']]
        assert not targeted_later and survivor['id'] in after_layers and older['id'] not in after_layers
        assert sid not in after['pending_sells']
        assert Decimal(str(fact['close'])) <= Decimal(before_layers[older['id']]['floor'])
        assert Decimal(str(fact['close'])) > Decimal(before_layers[survivor['id']]['floor'])
        assert fact['i_target'] == 1 and forward.i_target.eq(1).all()
        roots = {trigger_layers[x['id']]['stock_structure'] for x in [older, survivor]}
        assert len(roots) == 1
        snaps = []
        for line_index, d in daily:
            day = d['at'][:10]
            if not previous['at'][:10] <= day <= survivor['closed'][:10]: continue
            f = facts.loc[day]
            live = [pick(x) for x in d['layers'] if x['sid'] == sid]
            snap = {'day': day, 'original_CLOSE_at': d['at'], 'daily_line_index': line_index,
                    'original_live_layers': live, 'own_pending_sell': sid in d['pending_sells'],
                    'ACT_on_original': d['on'], 'native_facts': {k: str(f[k]) for k in ('close', 'raw_close', 'factor', 'i_target', 'i_floor', 'i_buy', 'e0_target', 'g_grade')}}
            snap['original_E0_and_CP'] = market_at(day)
            snaps.append(snap)
        buy_records = [{'source': ref('trades', i), 'original': {k: t[k] for k in ('layer', 'kind', 'shares', 'at', 'signal_at', 'floor', 'price', 'reason')}}
                       for i, t in enumerate(book['trades']) if t['side'] == 'buy' and t['layer'] in (older['id'], survivor['id'])]
        c = camp_by_layer[older['id']]
        output.append({'sid': sid, 'name': c['name'], 'classification': 'ORIGINAL_LAYER_SURVIVAL_ANALOG_NOT_A_WINNER_OR_V5_PROBE',
          'original_campaign_id': c['campaign_id'], 'original_campaign_endpoint_net': c['endpoint_net'],
          'older_layer': older['id'], 'later_ADD_layer': survivor['id'],
          'original_buy_records': buy_records, 'trigger_CLOSE': request['at'],
          'trigger_C_adjusted': str(fact['close']), 'trigger_raw_C': str(fact['raw_close']),
          'trigger_original_market_facts': market_at(trigger),
          'sale_day_CLOSE_original_market_facts': market_at(fill_day),
          'older_previously_known_floor': before_layers[older['id']]['floor'],
          'later_previously_known_floor': before_layers[survivor['id']]['floor'],
          'previous_CLOSE': previous['at'], 'previous_daily_line_index': previous_line_index,
          'original_trigger_layers': [pick(trigger_layers[x['id']]) for x in [older, survivor]],
          'exit_request_source': ref('audit', ai), 'exit_request_original': request,
          'all_stock_exit_requests_since_later_entry_until_older_fill': [{'source': ref('audit', i), 'original': a} for i, a in original_requests],
          'older_actual_proxy_sell_source': ref('trades', ti), 'older_actual_proxy_sell': trade,
          'after_older_fill_CLOSE': after['at'], 'after_fill_original_later_layer': pick(after_layers[survivor['id']]),
          'after_fill_daily_line_index': fill_line_index, 'after_fill_own_pending_sell': False,
          'later_no_own_exit_request_before_older_fill': True,
          'I_target_remains_true_through_later_actual_end': True,
          'original_same_entry_root': next(iter(roots)),
          'V3_structure_id': 'NOT_MAPPED_NO_NEW_V3_RUN; original old-E0 stock_structure is not a V3 generation ID.',
          'root_scope': 'Saved layer entry labels equal and native I never OFF in inspected forward interval. No independent current-root timestamp snapshot or V3 identity is inferred.',
          'trigger_G1_grade': str(fact['g_grade']), 'daily_original_forward_rows': snaps,
          'source_native_facts': str(fact_path),
          'restriction': 'Original role/pool are not V5 probe identity; price protection survival is not healthy trend evidence or a return guarantee.'})
    save('TWO_ORIGINAL_LAYER_SURVIVAL_ANALOGS.json', output)
    save('COVERAGE_AND_SEARCH_RECEIPT.json', {'status': 'ORIGINAL_FACTS_ONLY_COMPLETE',
       'original_account': str(PAIR / 'B.json.gz'), 'campaigns': len(campaigns), 'existing_detailed_chains_checked': len(chains),
       'original_layers': len(layers), 'CP_sell_receipts': len(receipts), 'CP_sell_parts': len(parts),
       'fully_closed_CP_older_layer_ids': len({p['layer'] for _, t, p in parts if layers[p['layer']]['closed'] == t['at']}),
       'candidate_events': len(candidates), 'positive_endpoint_campaign_candidates': sum(Decimal(camp_by_layer[c[2]['id']]['endpoint_net']) > 0 for c in candidates),
       'candidate_definition': 'An original CP1_add_protection sell part completes older layer; a later-opened ADD was entered before sell day and remains open after this sell. Then check original old floor, per-layer exit requests, after-fill own pending cleared, I continuity.',
       'partial_pending_not_called_inheritance': True, 'new_models': 0, 'new_V3_traces': 0, 'new_accounts': 0, 'new_quantities': 0,
       'source_sha256': SOURCES, 'script_sha256': sha(__file__)})
    print(json.dumps({'campaigns': len(campaigns), 'CP_sell_receipts': len(receipts), 'CP_sell_parts': len(parts),
                     'candidate_events': len(candidates), 'winner_candidates': 0,
                     'examples': [{k: r[k] for k in ('sid', 'older_layer', 'later_ADD_layer', 'trigger_CLOSE', 'trigger_C_adjusted', 'older_previously_known_floor', 'later_previously_known_floor', 'after_older_fill_CLOSE')} for r in output]}, ensure_ascii=False))


if __name__ == '__main__': main()
