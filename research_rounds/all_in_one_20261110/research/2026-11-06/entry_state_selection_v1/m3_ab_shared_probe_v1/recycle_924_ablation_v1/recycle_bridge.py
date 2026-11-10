"""One CLOSE exit gate, derived from the frozen shared engine. Import is data-free."""
from pathlib import Path
from decimal import Decimal as D
import ast, hashlib, inspect, sys, textwrap

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'indexed_execution_v1'
sys.path.insert(0, str(BASE))
import engine_indexed_v1 as E

REASON = 'PROBE_LOSS_SECTOR_FALSE'

def eligible(*, state, pool, sector_m3, net, exitpending):
    """-1/None/NaN are not FALSE. Exact Decimal zero belongs to the exit side."""
    return (state == 'HELD' and pool == 'probe' and sector_m3 == 0
            and not exitpending and isinstance(net, D) and net.is_finite() and net <= 0)

_text = textwrap.dedent(inspect.getsource(E.ExecutionBridge.close_phase))
_tree = ast.parse(_text)
_sites = [(parent, i) for parent in ast.walk(_tree)
          if hasattr(parent, 'body') and isinstance(parent.body, list)
          for i, node in enumerate(parent.body)
          if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
          and ast.unparse(node.value.func) == 'self.s.held_close']
assert len(_sites) == 1
_parent, _index = _sites[0]
_parent.body.insert(_index + 1, ast.parse('self._recycle_close(st, day)').body[0])
ast.fix_missing_locations(_tree)
_ns = {}
exec(compile(_tree, str(HERE / 'recycle_bridge.py') + ':single_hook', 'exec'), E.__dict__, _ns)
DERIVATION = dict(original_close_sha256=hashlib.sha256(_text.encode()).hexdigest(),
                  change='One call after original held_close, before original _capture_cp',
                  insertion_count=1, derived_ast=ast.dump(_tree, include_attributes=False))

class RecycleBridge(E.ExecutionBridge):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recycle_audit = []

    def _recycle_close(self, st, day):
        assert self.phase == 'CLOSE'
        rid, sid = st['round_id'], st['sid']
        state = self.states.get(sid, {}).get('state')
        pool = self.pools.get(rid)
        m3 = self.s.sector[st['sector']].get(day, -1)
        if state != 'HELD' or pool != 'probe' or m3 != 0 or st.get('exitpending'):
            return
        z = self.s.raw[sid].get(day, {})
        # Original held_close has already checked CLOSE data and I/CP state.
        net = self.s.mark(st, D(str(z['raw_close'])) * (1 - self.s.SLIP), day)
        trigger = eligible(state=state, pool=pool, sector_m3=m3, net=net,
                           exitpending=st.get('exitpending'))
        before = (self.cash(), self.receivable(), st['core'], st['add'],
                  self.pools[rid], tuple((x.layer_id, x.qty) for x in self.layers))
        if trigger:
            st['exitpending'] = REASON
            # No current freshCP can qualify at M3=0/net<=0. Clear a stale intention.
            st['addpending'] = None
        assert before == (self.cash(), self.receivable(), st['core'], st['add'],
                          self.pools[rid], tuple((x.layer_id, x.qty) for x in self.layers))
        self.recycle_audit.append(dict(day=day, round_id=rid, sid=sid,
            sector=st['sector'], pool=pool, COMMON_K_M3_candidate=m3,
            trigger_close_net=net, trigger=trigger, reason=REASON if trigger else 'NET_POSITIVE',
            actual_execution='NONE_AT_CLOSE', next_step='ORIGINAL_NEXT_COMMON_OPEN_EXIT',
            raw_close=z['raw_close']))

    close_phase = _ns['close_phase']

def make_bridge(source, arm, **kwargs):
    if arm == 'B0':
        return E.ExecutionBridge(source, seed_cash=D('1200000'), **kwargs)
    if arm == 'R1':
        return RecycleBridge(source, seed_cash=D('1200000'), **kwargs)
    raise ValueError(arm)
