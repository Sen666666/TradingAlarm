"""Exactly one signal-CLOSE admission block; no economic change elsewhere."""
import ast
import pandas as pd
from runtime import O,SOURCE,sha,read,select_source
from joint_engine import JointConsumer

GATE_BLOCK="""if not self._entry_permission(pr):
    continue
"""

def selector_tree():
    source,cls=select_source();m=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_close')
    original=ast.dump(m,include_attributes=False);changed=0
    for n in ast.walk(m):
        for field,value in ast.iter_fields(n):
            if isinstance(value,list):
                for i,child in enumerate(value):
                    if isinstance(child,ast.If) and ast.unparse(child.test)=="industry_gate(pr) != 'PASS'":
                        value[i:i]=ast.parse(GATE_BLOCK).body;changed+=1;break
    assert changed==1,'EXACTLY_ONE_ADMISSION_INTERVENTION'
    return m,original

def selector():
    import joint_engine as j
    m,_=selector_tree();env=dict(vars(j))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[m],type_ignores=[])),str(SOURCE/'joint_engine.py')+':entry_admission_only','exec'),env)
    return env['select_close']

class GateUnknown(RuntimeError):pass

class GateMixin:
    select_close=selector()
    def _entry_permission(self,row):
        key=(row['sid'],pd.Timestamp(row['day']))
        for book in self.books.values():
            if book.root_id[0]==row['sid'] and book.responsibility()['owner_locked']:
                raise GateUnknown(('UNKNOWN_FLAT_WITH_UNRESOLVED_PARENT_RESPONSIBILITY',key))
        if key not in self._entry_features:
            self.entry_gate_audit.append(dict(sid=key[0],day=key[1],gate_status='UNKNOWN_MISSING_GATE_KEY'))
            raise GateUnknown(('UNKNOWN_MISSING_GATE_KEY',key))
        f=self._entry_features[key]
        if tuple(row['root_id'])!=tuple(f['root_id']):
            self.entry_gate_audit.append(dict(sid=key[0],day=key[1],gate_status='UNKNOWN_GATE_ROOT_ID_MISMATCH'))
            raise GateUnknown(('UNKNOWN_GATE_ROOT_ID_MISMATCH',key,row['root_id'],f['root_id']))
        if repr(row['receipt_id'])!=f['receipt_identity'] or float(row['adjustment_factor'])!=float(f['signal_factor']) or float(row['raw_close'])!=float(f['signal_raw_close']) or row['root_id'][1]!=f['signal_identity']:
            raise GateUnknown(('UNKNOWN_GATE_SIGNAL_IDENTITY_FACTOR_OR_CLOSE_MISMATCH',key))
        z=dict(sid=key[0],day=key[1],receipt_id=repr(row['receipt_id']),root_id=repr(row['root_id']),gate_status=f['gate_status'],generation=f['generation'],generation_birth=f['generation_birth'],entry_U=f['entry_U'],entry_active=f['entry_active'],clock='SIGNAL_CLOSE',new_initial_only=True)
        self.entry_gate_audit.append(z)
        if str(f['gate_status']).startswith('UNKNOWN'):raise GateUnknown(('UNKNOWN_GATE_FACT',z))
        allow=f['gate_status']=='ALLOW'
        assert allow==bool(f['entry_active']),'GATE_STATE_INCONSISTENT'
        return allow

class GateConsumer(GateMixin,JointConsumer):
    def __init__(self,engine,market,window):
        from release import require_release
        a=require_release(window)
        assert (O/('ENTRY_GATE_RUN_ONCE_'+window+'.json')).exists(),'RUN_ONCE_REQUIRED_BEFORE_CONSUMER'
        super().__init__(engine,market,window)
        self.entry_gate_audit=[];self._last_processed_day=None
        p=O/'market_tape/RECEIPT_GATE_FACTS.parquet'
        assert a['input_sha256'][str(p)]==sha(p)
        f=pd.read_parquet(p);f=f[f.window.eq(self.window)]
        assert not f.duplicated(['sid','day']).any()
        # source identity derives from exactly the frozen candidate table, not tail.
        candidates=JointConsumer._candidate_frame(self)
        assert set(zip(f.sid,f.day))==set(zip(candidates.sid,candidates.day)),'CANDIDATE_GATE_DOMAIN_NOT_EXACT'
        candidate_rows={(r['sid'],pd.Timestamp(r['day'])):r for r in candidates.to_dict('records')}
        roots={key:tuple(r['root_id']) for key,r in candidate_rows.items()}
        self._entry_features={}
        for row in f.to_dict('records'):
            key=(row['sid'],pd.Timestamp(row['day']));root=tuple(row['root_id'])
            assert root==roots[key],'ROOT_SOURCE_METADATA_MISMATCH'
            cr=candidate_rows[key]
            assert row['receipt_identity']==repr(cr['receipt_id']),'RECEIPT_METADATA_MISMATCH'
            assert row['signal_identity']==root[1],'SOURCE_LINEAGE_METADATA_MISMATCH'
            assert row['signal_factor']==cr['adjustment_factor'],'FACTOR_METADATA_MISMATCH'
            assert row['signal_raw_close']==cr['raw_close'],'RAW_CLOSE_METADATA_MISMATCH'
            assert root[-1]==str(pd.Timestamp(row['root_day']).date()),'ROOT_BIRTH_METADATA_MISMATCH'
            self._entry_features[key]=dict(row,root_id=root)
        self.feature_count=len(f)
    def _candidate_frame(self):
        f=super()._candidate_frame()
        assert set(zip(f.sid,f.day))==set(self._entry_features),'LOOP_CANDIDATE_GATE_DOMAIN_NOT_EXACT'
        return f
    def process_day(self,day,prevday,ab_rows,price_rows):
        assert self._last_processed_day is None or day>self._last_processed_day,'SECOND_LOOP_OR_NONMONOTONE_DAY'
        self._last_processed_day=day
        return super().process_day(day,prevday,ab_rows,price_rows)
