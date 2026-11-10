"""M10 research-only positive-CP INITIAL protection. Historical runner intentionally disabled."""
from pathlib import Path
import sys, importlib.util, copy, json, inspect, argparse
sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
ROOT = O.parent
BASE = ROOT / 'mainline_m7_downturn_cash_batch_v6'
BASE_SHA = 'b81f78fc04dec3709191258230c2e2fa7580f8658315c78e9b25bf3fea318c2e'
sp = importlib.util.spec_from_file_location('m10_frozen_m7_cash_v6', BASE / 'engine.py')
m7 = importlib.util.module_from_spec(sp)
sys.modules[sp.name] = m7
sp.loader.exec_module(m7)
read, save, sha, day, pd, Blocked, D, dec = (getattr(m7, k) for k in ('read','save','sha','day','pd','Blocked','D','dec'))
assert sha(BASE / 'engine.py') == BASE_SHA
m3 = m7.v5.v4.v3.m7.m3
SLIP = m3.SLIP
REASON = 'POSITIVE_CP_INITIAL_PROTECTION'

class Data(m7.Data):
    def __init__(self, end='2024-10-31'):
        super().__init__(end)
        for name in ('engine.py','CONTRACT.md','synthetic_protection.py'):
            self.hashes[str(O/name)] = sha(O/name)

class Engine(m7.Engine):
    def layered_pressure(self, a, d):
        rows=[];proceeds=D(0)
        for lot in a['lots']:
            if not lot['q']:
                continue
            floor = lot['floor'] if lot['kind']=='ADD' else a['ifloor']
            if lot.get('capital_role')=='INITIAL' and lot.get('seed_cp'):
                floor=max(floor,dec(lot['seed_cp']['floor']))
            p=floor/a['factor']*(1-SLIP)
            fee=self.d.fee(a['sid'],d,lot['q'],p,'sell')
            value=lot['q']*p-fee;proceeds+=value
            rows.append(dict(lot_id=lot['id'],kind=lot['kind'],capital_role=lot.get('capital_role'),
                qty=lot['q'],signal_floor=str(floor),factor=str(a['factor']),
                stressed_execution_price=str(p),separate_lot_fee=str(fee),net_proceeds=str(value)))
        return dict(convention='SEPARATE_SELL_FEE_PER_LOT_AT_ACTUAL_LAYER_FLOOR_NOT_EXECUTION_FORECAST',
                    cashflow=str(a['cashflow']),dividend=str(a['dividend']),lots=rows,
                    net=str(a['cashflow']+a['dividend']+proceeds))

    def lock_seed(self,a,lot,d,phase):
        if not lot.get('m10_locked'):
            if lot.get('exit') and lot['exit']!=REASON:
                lot['m10_baseline_exit']=lot['exit']
            lot['m10_locked']=dict(day=day(d),phase=phase,reason=REASON,
                                   protection=copy.deepcopy(lot['seed_cp']))
            self.candidates.append(dict(day=day(d),phase=phase,sid=a['sid'],round_id=a['id'],
                lot_id=lot['id'],event='M10_INITIAL_BREACH',decision=REASON,
                evidence=copy.deepcopy(lot['m10_locked'])))
        lot['exit']=lot.get('exit') or REASON

    def close(self,d,prev):
        # Prior stop first, before inherited code can discover this CLOSE's new CP.
        for s,a in sorted(self.active.items()):
            z=self.d.z(s,d)
            if not m3.valid(z) or not m3.finite(z.get('raw_close')) or z['raw_close']<=0 or m3.lineage(z)!=a['origin']:
                raise Blocked(f'{day(d)} {s} CLOSE_INVALID')
            for lot in a['lots']:
                cp=lot.get('seed_cp')
                if lot.get('capital_role')=='INITIAL' and cp and lot['q'] and dec(z['raw_close'])*a['factor']<=dec(cp['floor']):
                    self.lock_seed(a,lot,d,'CLOSE')
        result=super().close(d,prev)
        # Preserve legacy column, explicitly add the actual execution protection.
        for rows in (self.holdings,self.capital_lots):
            for row in rows:
                if row.get('day')!=day(d):continue
                a=self.active.get(row['sid'])
                if not a or row.get('round_id')!=a['id']:continue
                lot=next((l for l in a['lots'] if l['id']==row.get('lot_id')),None)
                if lot is None:continue
                floor=lot['floor'] if lot['kind']=='ADD' else a['ifloor']
                if lot.get('capital_role')=='INITIAL' and lot.get('seed_cp'):
                    floor=max(floor,dec(lot['seed_cp']['floor']))
                row.update(baseline_I_signal=str(a['ifloor']),effective_protection_signal=str(floor),
                    seed_cp_floor=lot.get('seed_cp',{}).get('floor'),
                    seed_cp_id=lot.get('seed_cp',{}).get('cp_id'),
                    m10_locked=copy.deepcopy(lot.get('m10_locked')))
        return result

    def adopt_seed_protection(self,d):
        for s,a in sorted(self.active.items()):
            z=self.d.z(s,d);cp=a.get('cp');q=self.quantity(a)
            valid=bool(m3.valid(z) and m3.finite(z.get('raw_close')) and z['raw_close']>0
                       and m3.lineage(z)==a['origin'])
            net=self.net(a,d,'raw_close') if valid and q else None
            # Current pointer with today's creation identity, never a historical CP search.
            fresh=bool(valid and cp and cp['date']==day(d) and cp['origin']==a['origin']
                and not cp['consumed'] and not cp['invalid'] and dec(cp['floor'])>0
                and dec(z['raw_close'])*a['factor']>dec(cp['floor']))
            cpnet=None
            if fresh and q:
                price=dec(cp['floor'])/a['factor']*(1-SLIP)
                cpnet=a['cashflow']+a['dividend']+q*price-self.d.fee(s,d,q,price,'sell')
            for lot in a['lots']:
                if lot.get('capital_role')!='INITIAL':continue
                before=self.layered_pressure(a,d) if valid else None
                old=copy.deepcopy(lot.get('seed_cp'));reason='ADOPT'
                if old:old.pop('admission_evidence',None)
                if not lot['q'] or not q:reason='ZERO_QUANTITY'
                elif a['exit'] or lot.get('exit') or lot.get('m10_locked'):reason='LOCKED_EXIT'
                elif not valid:reason='INVALID_CLOSE'
                elif not fresh:reason='NO_TODAY_VALID_NEW_CP'
                elif day(d)<lot['bought']:reason='RECEIPT_BEFORE_ACTUAL_BUY'
                elif net is None or not net.is_finite() or net<=0:reason='CLOSE_NET_NOT_POSITIVE'
                elif cpnet is None or not cpnet.is_finite() or cpnet<=0:reason='CP_NET_NOT_POSITIVE'
                elif old and dec(cp['floor'])<=dec(old['floor']):reason='NO_FLOOR_RAISE'
                if reason=='ADOPT':
                    lot['seed_cp']=dict(floor=str(cp['floor']),cp_id=cp['id'],receipt_day=cp['date'],
                        adopted_day=day(d),round_id=a['id'],origin=cp['origin'],
                        net_close=str(net),net_at_CP=str(cpnet),factor=str(a['factor']))
                record=dict(day=day(d),phase='CLOSE',sid=s,round_id=a['id'],lot_id=lot['id'],
                    event='M10_INITIAL_CP_ADMISSION',decision=reason,
                    candidate=copy.deepcopy(cp),candidate_is_today_valid=fresh,
                    net_close=str(net) if net is not None else None,
                    net_at_CP=str(cpnet) if cpnet is not None else None,
                    raw_close=str(z.get('raw_close')),factor=str(a['factor']),
                    old_protection=old,new_protection=copy.deepcopy(lot.get('seed_cp')),
                    layered_pressure_before=before,layered_pressure_after=self.layered_pressure(a,d) if valid else None)
                if reason=='ADOPT':lot['seed_cp']['admission_evidence']=copy.deepcopy(record)
                self.candidates.append(record)

    def plan_transfers(self,d,pending):
        self.adopt_seed_protection(d)
        return super().plan_transfers(d,pending)

    def exit_open(self,d):
        # Original protective inventory and ordering remain intact; only add INITIAL coverage.
        for s,a in sorted(list(self.active.items())):
            z=self.d.z(s,d);px=dec(z['raw_open']);adj=px*a['factor']
            self.invalidate_cp(a,d,'OPEN','raw_open')
            if adj<=a['ifloor']:a['exit']='I_OPEN_PROTECTION'
            base=[];extra=[];reasons={}
            for lot in a['lots']:
                cp=lot.get('seed_cp')
                prior=lot.get('exit')
                is_m10=bool(lot.get('capital_role')=='INITIAL' and cp and day(d)>cp['adopted_day'] and
                    (lot.get('m10_locked') or adj<=dec(cp['floor'])))
                original=bool(a['exit'] or lot.get('m10_baseline_exit') or (prior and not lot.get('m10_locked'))
                    or (lot['kind']=='ADD' and adj<=lot['floor']))
                if is_m10 and not a['exit']:
                    self.lock_seed(a,lot,d,'OPEN')
                if original or is_m10:
                    if d>pd.Timestamp(lot['bought']):
                        (base if original else extra).append(lot)
                        reasons[lot['id']]=a['exit'] or lot.get('m10_baseline_exit') or (prior if original and prior else 'CP_LAYER_EXIT' if original else REASON)
                    else:lot['exit']='T1_LOCKED_EXIT'
            qb=sum(l['q'] for l in base);qe=sum(l['q'] for l in extra);add=0
            if qe:
                rule=self.d.getmeta(s,d)[0];total=self.quantity(a)
                allowed=rule.sell_floor(qb+qe,total)
                # Never reduce baseline exits to make the new component legal.
                if qb<=allowed<=qb+qe and rule.sell_floor(allowed,total)==allowed:add=allowed-qb
            quantities={l['id']:l['q'] for l in base};remaining=add
            for lot in sorted(extra,key=lambda l:l['id']):
                take=min(lot['q'],remaining)
                if take:quantities[lot['id']]=take;remaining-=take
            q=qb+add
            if q:
                reason=a['exit'] or ('CP_LAYER_EXIT' if base else REASON)
                self.order(a,d,'SELL_ALL' if q==self.quantity(a) else 'SELL_LAYERS',q,px*(1-SLIP),reason,
                    lots=list(quantities),lot_quantities=quantities,
                    lot_reasons={lid:reasons[lid] for lid in quantities},
                    initial_protection_evidence={l['id']:copy.deepcopy(l.get('m10_locked'))
                        for l in a['lots'] if l['id'] in quantities and l.get('m10_locked')})
                for lot in a['lots']:lot['q']-=quantities.get(lot['id'],0)
                a['lots']=[l for l in a['lots'] if l['q']];a['plan']=None
            if not self.quantity(a):a['exit_day']=day(d);self.active.pop(s)

    def export(self,path):
        m7.v5.v4.v3.m7.Engine.export(self,path)
        save(Path(path)/'INITIAL_CP_PROTECTION.json',[
            dict(sid=a['sid'],round_id=a['id'],lot_id=l['id'],qty=l['q'],
                 protection=l.get('seed_cp'),locked=l.get('m10_locked'),exit=l.get('exit'))
            for a in self.archive.values() for l in a['lots'] if l.get('capital_role')=='INITIAL'])
        save(Path(path)/'OUTPUT_HASHES.json',{p.name:sha(p) for p in Path(path).iterdir()
             if p.is_file() and p.name!='OUTPUT_HASHES.json'})

    def run(self,checkpoint=True):
        raise RuntimeError('M10 historical execution requires separate independent review and authorization')

source=m7.source
exec(compile(source,'M10_UNCHANGED_ATOMIC_LOOP','exec'),globals())
def self_check():
    allowed={'close','plan_transfers','exit_open','export','run'}
    ids={n:getattr(Engine,n) is getattr(m7.Engine,n) for n in dir(m7.Engine)
         if not n.startswith('__') and callable(getattr(m7.Engine,n)) and n not in allowed}
    assert all(ids.values()) and source==m7.source
    return dict(result='PASS',history_run=False,method_identity=ids,overrides=sorted(allowed),
                engine_sha256=sha(O/'engine.py'),contract_sha256=sha(O/'CONTRACT.md'),
                atomic_loop_byte_identical=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check'],required=True);ap.parse_args()
    save(O/'STATIC_QA.json',self_check())
