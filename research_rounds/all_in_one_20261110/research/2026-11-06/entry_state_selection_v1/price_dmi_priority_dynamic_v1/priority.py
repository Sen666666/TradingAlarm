"""Only intervention: reorder mutable PRICE identities within original numeric slots."""
import ast
import numpy as np,pandas as pd
from runtime import O,SOURCE,read,sha,select_source
from joint_engine import JointConsumer
from joint_policy import rank_key,known_pvr,finite

def reorder_slots(ordered,feature):
    """Input is today's dynamically feasible base-ranked queue, not old ranks."""
    out=list(ordered);mutable=[];values={}
    for index,(row,check) in enumerate(ordered):
        if row['owner_lane']=='PRICE':
            # Missing key is a coverage error and halts. Explicit NaN d is UNKNOWN
            # and preserves the exact numeric slot, never a numeric zero.
            d=feature(row['sid'],row['day'])
            values[row['sid']]=d
            if known_pvr(row) and finite(d):mutable.append(index)
    ranked=sorted((ordered[i] for i in mutable),key=lambda rc:(-float(values[rc[0]['sid']]),-float(rc[0]['PVR_score']),rc[0]['sid']))
    for index,item in zip(mutable,ranked):out[index]=item
    old={row['sid']:i+1 for i,(row,c) in enumerate(ordered)}
    audit=[]
    for rank,(row,c) in enumerate(out,1):
        sid=row['sid'];mut=(old[sid]-1) in mutable
        if not mut:assert old[sid]==rank
        audit.append(dict(sid=sid,day=row['day'],sector=row['sector'],owner_lane=row['owner_lane'],original_numeric_rank=old[sid],dmi_numeric_rank=rank,original_selected=old[sid]<=2,dmi_selected=rank<=2,mutable=mut,d=values.get(sid),PVR_known=known_pvr(row),PVR_score=row.get('PVR_score'),rank_changed=old[sid]!=rank))
    assert sorted(old.values())==list(range(1,len(out)+1))
    assert sum(r['owner_lane']=='PRICE' for r,c in ordered[:2])==sum(r['owner_lane']=='PRICE' for r,c in out[:2])
    return out,audit

def selector():
    """AST exact original select_close except its one ordered-assignment RHS."""
    import joint_engine as j
    source,cls=select_source()
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='select_close')
    changed=0
    for node in ast.walk(method):
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='ordered':
            if isinstance(node.value,ast.Call) and ast.unparse(node.value).startswith('sorted([(r, c) for r, c in options'):
                node.value=ast.Call(func=ast.Attribute(value=ast.Name(id='self',ctx=ast.Load()),attr='rank_options',ctx=ast.Load()),args=[node.value],keywords=[])
                changed+=1
    assert changed==1,'EXACTLY_ONE_SORT_INTERVENTION'
    env=dict(vars(j))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(SOURCE/'joint_engine.py')+':price_slot_sort_only','exec'),env)
    return env['select_close']

class DmiConsumer(JointConsumer):
    select_close=selector()
    def __init__(self,engine,market,window):
        from dmi_gates import require_release,claim_once
        approved=require_release(window)
        self._run_lock=claim_once(window,approved)
        self._authorization_sha=approved['authorization_sha256']
        super().__init__(engine,market,window)
        self.dmi_rank_audit=[];self._last_processed_day=None
        p=O/'features/ALL_PRICE_RECEIPT_FEATURES.parquet'
        assert approved['input_sha256'][str(p)]==sha(p)
        f=pd.read_parquet(p,columns=['sid','day','d','window'])
        f=f[f.window.eq(self.window)]
        assert not f.duplicated(['sid','day']).any()
        self._dmi={(r.sid,pd.Timestamp(r.day)):r.d for r in f.itertuples(index=False)}
        self.feature_count=len(self._dmi)
    def feature(self,sid,day):
        key=(sid,pd.Timestamp(day))
        assert key in self._dmi,('MISSING_DYNAMIC_CANDIDATE_FEATURE',key)
        return self._dmi[key]
    def rank_options(self,ordered):
        # Original key order was already constructed at this exact program point.
        out,audit=reorder_slots(ordered,self.feature)
        self.dmi_rank_audit.extend(audit)
        return out
    def process_day(self,day,prevday,ab_rows,price_rows):
        assert self._run_lock.exists(),'RUN_LOCK_REQUIRED'
        assert self._last_processed_day is None or day>self._last_processed_day,'SECOND_LOOP_OR_NONMONOTONE_DAY_FORBIDDEN'
        self._last_processed_day=day
        return super().process_day(day,prevday,ab_rows,price_rows)
