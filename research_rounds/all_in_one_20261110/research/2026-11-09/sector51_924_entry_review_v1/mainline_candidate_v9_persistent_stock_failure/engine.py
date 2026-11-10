"""M9 research-only lot retirement. Historical runner intentionally disabled."""
from pathlib import Path
import sys, importlib.util, copy, json, inspect, argparse
sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
ROOT = O.parent
BASE = ROOT / 'mainline_m7_downturn_cash_batch_v6'
BASE_SHA = 'b81f78fc04dec3709191258230c2e2fa7580f8658315c78e9b25bf3fea318c2e'
sp = importlib.util.spec_from_file_location('m9_frozen_m7_cash_v6', BASE / 'engine.py')
m7 = importlib.util.module_from_spec(sp)
sys.modules[sp.name] = m7
sp.loader.exec_module(m7)
read, save, sha, day, pd, Blocked, D, dec = (getattr(m7, k) for k in ('read','save','sha','day','pd','Blocked','D','dec'))
assert sha(BASE / 'engine.py') == BASE_SHA
m3 = m7.v5.v4.v3.m7.m3
SLIP = m3.SLIP
REASON = 'PERSISTENT_STOCK_NONPROFIT_EXPANSION_RETIREMENT'

class Data(m7.Data):
    def __init__(self, end='2024-10-31'):
        super().__init__(end)
        for name in ('engine.py', 'CONTRACT.md', 'synthetic_retirement.py'):
            self.hashes[str(O / name)] = sha(O / name)

class Engine(m7.Engine):
    def retirement_observation(self, s, a, d):
        record = dict(day=day(d), round_id=a['id'], sector_state=None, M=None,
                      stock_state=None, close_net=None, observed_close=False,
                      known=False, qualifies=False)
        def state(value):
            return int(value) if m3.finite(value) and value in (0, 1) else None
        try:
            record['sector_state'] = state(self.d.sectors[self.d.sid_sector[s]].at[d, 'state'])
            record['M'] = state(self.d.m(s, d).M)
            record['stock_state'] = state(self.d.stock.at[d, s])
            z = self.d.z(s, d)
            record['observed_close'] = bool(m3.truth(z.get('observed_bar'))
                and m3.valid(z) and m3.finite(z.get('raw_close'))
                and z['raw_close'] > 0 and m3.lineage(z) == a['origin'])
            if record['observed_close']:
                net = self.net(a, d, 'raw_close')
                if net.is_finite():
                    record['close_net'] = str(net)
            record['known'] = bool(record['observed_close']
                and record['close_net'] is not None
                and all(record[k] is not None for k in ('sector_state', 'M', 'stock_state')))
            record['qualifies'] = bool(record['known']
                and all(record[k] == 0 for k in ('sector_state', 'M', 'stock_state'))
                and dec(record['close_net']) <= 0)
        except (KeyError, IndexError, AttributeError):
            # Absent evidence never reconstructs or borrows a nearby bar.
            pass
        return record

    def mark_retirements(self, d):
        loc = self.d.cal.get_indexer([d])[0]
        previous_day = day(self.d.cal[loc-1]) if loc > 0 else None
        for s, a in sorted(self.active.items()):
            current = self.retirement_observation(s, a, d)
            if loc < 0:
                current.update(known=False, qualifies=False)
            prior = copy.deepcopy(a.get('m9_close_observation'))
            consecutive = bool(previous_day is not None and prior
                and prior['day'] == previous_day and prior['round_id'] == a['id'])
            confirmed = bool(consecutive and prior['qualifies'] and current['qualifies'])
            a['m9_close_observation'] = copy.deepcopy(current)
            evidence = dict(current=current, prior=prior, consecutive=consecutive,
                            confirmed=confirmed)
            self.candidates.append(dict(day=day(d), phase='CLOSE', sid=s, round_id=a['id'],
                event='M9_CLOSE_EVIDENCE', decision='CONFIRMED' if confirmed else 'RETAIN',
                **copy.deepcopy(evidence)))
            if not confirmed:
                continue
            for lot in a['lots']:
                if lot.get('capital_role') != 'EXPANSION' or a['exit'] or lot.get('exit'):
                    continue
                if 'retirement_signal_day' not in lot:
                    lot['retirement_signal_day'] = day(d)
                    lot['retirement_evidence'] = copy.deepcopy(evidence)
                    self.candidates.append(dict(day=day(d), phase='CLOSE', sid=s,
                        round_id=a['id'], lot_id=lot['id'], event='EXPANSION_RETIREMENT',
                        decision=REASON, capital_role='EXPANSION', kind=lot['kind'],
                        sector_state=0, M=0, stock_state=0, qty=lot['q'],
                        retirement_evidence=copy.deepcopy(evidence)))

    def plan_transfers(self, d, pending):
        self.mark_retirements(d)
        return super().plan_transfers(d, pending)

    def exit_open(self, d):
        # Preserve I/CP execution, attribution and grouping exactly. Never clear a protection.
        super().exit_open(d)
        for s, a in sorted(list(self.active.items())):
            eligible = [l for l in sorted(a['lots'], key=lambda l: l['id'])
                        if l.get('retirement_signal_day') and l.get('capital_role') == 'EXPANSION'
                        and not a['exit'] and not l.get('exit')
                        and d > pd.Timestamp(l['retirement_signal_day'])
                        and d > pd.Timestamp(l['bought'])]
            total = sum(l['q'] for l in eligible)
            if not total:
                continue
            q = self.d.getmeta(s, d)[0].sell_floor(total, self.quantity(a))
            if not q:
                continue
            remaining = q
            quantities = {}
            for lot in eligible:
                take = min(lot['q'], remaining)
                if take:
                    quantities[lot['id']] = take
                    remaining -= take
            assert remaining == 0
            signals = {l['id']: l['retirement_signal_day'] for l in eligible if l['id'] in quantities}
            p = dec(self.d.z(s, d)['raw_open']) * (1 - SLIP)
            self.order(a, d, 'SELL_ALL' if q == self.quantity(a) else 'SELL_LAYERS',
                       q, p, REASON, signal_day=min(signals.values()),
                       lots=list(quantities), lot_quantities=quantities,
                       retirement_signal_days=signals, capital_role='EXPANSION',
                       retirement_evidence={l['id']:copy.deepcopy(l['retirement_evidence'])
                                            for l in eligible if l['id'] in quantities})
            for lot in eligible:
                lot['q'] -= quantities.get(lot['id'], 0)
            a['lots'] = [l for l in a['lots'] if l['q']]
            a['plan'] = None
            if not self.quantity(a):
                a['exit_day'] = day(d)
                self.active.pop(s)

    def pending_retirements(self):
        return [dict(sid=s, sector51=self.d.sid_sector[s], round_id=a['id'],
                     lot_id=l['id'], kind=l['kind'], capital_role=l['capital_role'],
                     signal_day=l['retirement_signal_day'], reason=REASON,
                     remaining_qty=l['q'], bought=l['bought'],
                     protective_exit=a['exit'] or l.get('exit'),
                     retirement_evidence=copy.deepcopy(l['retirement_evidence']))
                for s, a in sorted(self.active.items()) for l in a['lots']
                if 'retirement_signal_day' in l]

    def export(self, path):
        # Strategy ablation is not a fact-only extension: no M7 prefix-equality assertions.
        m7.v5.v4.v3.m7.Engine.export(self, path)
        save(Path(path)/'PENDING_RETIREMENTS.json', self.pending_retirements())
        save(Path(path)/'ROUND_EXIT_EVIDENCE.json', {r:a.get('m9_close_observation')
                                                   for r,a in self.archive.items()})
        save(Path(path)/'OUTPUT_HASHES.json', {p.name:sha(p) for p in Path(path).iterdir()
                                             if p.is_file() and p.name!='OUTPUT_HASHES.json'})

    def run(self, checkpoint=True):
        raise RuntimeError('M9 historical execution requires separate independent review and authorization')

# Exact baseline atomic algorithm, rebound only to local class and output directory.
source = m7.source
exec(compile(source, 'M9_UNCHANGED_ATOMIC_LOOP', 'exec'), globals())

def self_check():
    allowed = {'plan_transfers', 'exit_open', 'export', 'run'}
    identities = {name: getattr(Engine, name) is getattr(m7.Engine, name)
                  for name in dir(m7.Engine) if not name.startswith('__')
                  and callable(getattr(m7.Engine, name)) and name not in allowed}
    assert all(identities.values())
    assert source == m7.source
    close = m7.v5.v4.v3.m7.m6.close_source
    assert close.index("l['exit']='CP_CLOSE_PROTECTION'") < close.index('self.plan_transfers(d,pending)')
    assert 'self.mark_retirements(d)' in inspect.getsource(Engine.plan_transfers)
    return dict(result='PASS', history_run=False, baseline_sha256=BASE_SHA,
                unchanged_method_identity=identities, overrides=sorted(allowed),
                atomic_loop_byte_identical=True, close_hook_after_protective_decisions=True,
                engine_sha256=sha(O/'engine.py'), contract_sha256=sha(O/'CONTRACT.md'))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['check'], required=True)
    ap.parse_args()
    save(O/'STATIC_QA.json', self_check())
