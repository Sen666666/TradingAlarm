"""Definition-only reuse of original FAST role consumer, bound to each window engine.
No new Q, CP, role ordering, sizing, fee, or protection formula.
"""
import ast, hashlib
from pathlib import Path
from decimal import Decimal as D
import pandas as pd
import numpy as np

class NativeRoles:
    def __init__(self,s,cpmap):
        self.s=s;source=Path(__file__).resolve().parent.parent/'fast_entry_equity_2022_v1/lifecycle.py'
        self.source=source;txt=source.read_text();tree=ast.parse(txt)
        self.saved={k:getattr(s,k) for k in ['record','before_held','entry_open','held_open','held_close']}
        self.old_cp_open=getattr(s,'cp_role_held_open',None)
        # Native CP OPEN changes only additive-layer risk. Adds are disabled here.
        # Use exact extracted CP OPEN nevertheless to avoid a latent role substitution.
        src=s.SOURCE.read_text();t=ast.parse(src);node=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='held_open')
        cpopen=ast.get_source_segment(src,node).replace('def held_open(','def cp_role_held_open(',1)
        old="""  pf=facts[sid].get(prevd,{}).get('i_floor',np.nan)
  if not finite(pf):return freeze_unknown(states,sid,st,'ADD_PREVIOUS_FLOOR_UNKNOWN',d)
  pf=D(str(pf))/st['fac']
  exist=max(D(0),D(st['core'])*(px-pf*(1-SLIP))+st['initial_fee']+fee(st['core'],pf*(1-SLIP),fs,'sell',pa))"""
        new="""  pf=st.get('initialfloor')
  if st['core'] and pf is None:return freeze_unknown(states,sid,st,'ADD_CP_INITIAL_FLOOR_UNKNOWN',d)
  exist=max(D(0),D(st['core'])*(px-pf*(1-SLIP))+st['initial_fee']+fee(st['core'],pf*(1-SLIP),fs,'sell',pa)) if st['core'] else D(0)"""
        assert cpopen.count(old)==1;cpopen=cpopen.replace(old,new);exec(compile(cpopen,str(source)+':exact_native_CP_open','exec'),s.__dict__)
        g=dict(s=s,D=D,pd=pd,np=np,json=__import__('json'),ADAPTER_ON=True,role_cache={},role_attempts=[],consumptions=[],core_consumed=set(),cp_consumed=set(),cpmap=cpmap)
        for k,v in self.saved.items():g['original_'+k]=v
        g['original_checkclose']=s.checkclose
        names={'close_role','role_options','prepare','record','consume','before_held','entry_open','held_open','cp_receipt','held_close'};hashes={};patches={}
        for n in tree.body:
            if not isinstance(n,ast.FunctionDef) or n.name not in names:continue
            segment=ast.get_source_segment(txt,n);hashes[n.name]=hashlib.sha256(segment.encode()).hexdigest()
            if n.name=='entry_open' and hasattr(s,'unadmitted_action_at'):
                needle=" if s.pending_bridge(st,d,z,prev):prev=dict(prev,adjustment_factor=z['adjustment_factor'])"
                assert segment.count(needle)==1
                segment=segment.replace(needle," if s.unadmitted_action_at(sid,d):return s.freeze_unknown(states,sid,st,'UNADMITTED_ACTION_AT_ENTRY_UNKNOWN',d)\n"+needle)
                patches[n.name]='Retain the 2024 window unadmitted-action guard before pending bridge.'
            if n.name=='held_close':
                needle=" if states.get(sid,{}).get('state')=='HELD' and st.get('addpending') is not None:"
                assert segment.count(needle)==1
                segment=segment.replace(needle," st['addpending']=None # Local experiment has no additional layer.\n"+needle)
                patches[n.name]='Suppress additional-layer intent before irrelevant add-receipt checks; original initial-role protection unchanged.'
            exec(compile(segment,str(source)+':'+n.name,'exec'),g)
        assert set(hashes)==names
        self.g=g;self.hashes=hashes;self.patches=patches
        for k in self.saved:setattr(s,k,g[k])
        s.hashes[str(source)]=hashlib.sha256(source.read_bytes()).hexdigest()

    def prepare(self,r,arm):
        r=dict(r);r['AB_I_qualified']=False;r['AB_event_id']=None;r['AB_event_type']=None
        return self.g['prepare'](r,arm)

    def initial_epoch(self,st,r):
        st['i_epoch']=r.get('i_epoch');st['cp_id']=None
        st['role_options']=[dict(role='I_CORE',floor=st['i_floor'],sources='ORIGINAL_AB_INITIAL')]
        st['source_mask']='ORIGINAL_AB_INITIAL';st['signal_cp_id']=None

    def recovery(self,st,r,options):
        for key in ['i_epoch','cp_id','source_mask']:st[key]=r.get(key)
        st['signal_cp_id']=r.get('cp_id');st['role_options']=options

    def restore(self):
        for k,v in self.saved.items():setattr(self.s,k,v)
        if self.old_cp_open is None:delattr(self.s,'cp_role_held_open')
        else:self.s.cp_role_held_open=self.old_cp_open
