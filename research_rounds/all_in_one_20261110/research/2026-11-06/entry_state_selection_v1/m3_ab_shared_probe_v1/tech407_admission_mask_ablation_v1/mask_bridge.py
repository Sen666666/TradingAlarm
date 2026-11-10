"""One admission factor only. Original source, groups, ordering, execution remain read-only."""
from pathlib import Path
import ast,copy,hashlib,inspect,json,sys,textwrap
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'indexed_execution_v1'
sys.path.insert(0,str(BASE))
import engine_indexed_v1 as E
OLD_MANIFEST=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/tech-finite-compound-20261026/data/core-v3/manifest.json')
OLD_HASH='993eb45d11bf536d1b123bfa14af330ea63daa663d36e471356e0e3c7c9f16fb'

def merge_hashes(*maps):
    merged={}
    for mapping in maps:
        for path,digest in mapping.items():
            if path in merged and merged[path]!=digest:
                raise AssertionError(('HASH_KEY_CONFLICT',path,merged[path],digest))
            merged[path]=digest
    return merged

def members():
    assert E.bridge.sha(OLD_MANIFEST)==OLD_HASH
    rows=[x['series_id'] for x in json.loads(OLD_MANIFEST.read_text())['series'] if x['kind']=='stock']
    assert len(rows)==len(set(rows))==407
    return frozenset(rows)

# Derive the exact original selection method. Only queue(g,...) input changes.
# Source self.groups remains full. No original top2 is computed before the mask.
_select_text=textwrap.dedent(inspect.getsource(E.ExecutionBridge._select_close))
_tree=ast.parse(_select_text)
_calls=[n for n in ast.walk(_tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='queue']
assert len(_calls)==1 and ast.unparse(_calls[0].args[0])=='g'
_calls[0].args[0]=ast.parse('self._admission_group(g,day)',mode='eval').body
ast.fix_missing_locations(_tree)
_ns={}
exec(compile(_tree,str(HERE/'mask_bridge.py')+':one_argument_derivation','exec'),E.__dict__,_ns)
_derived_select=_ns['_select_close']
DERIVATION=dict(original_method_sha256=hashlib.sha256(_select_text.encode()).hexdigest(),
    replacements=1,original='queue(g,self.states,ARM)',replacement='queue(self._admission_group(g,day),self.states,ARM)',
    derived_ast=ast.dump(_tree,include_attributes=False))

class AdmissionMaskBridge(E.ExecutionBridge):
    def __init__(self,module,seed_cash=E.D('1200000'),*,admission_members,**kwargs):
        super().__init__(module,seed_cash,**kwargs)
        self.admission_members=frozenset(admission_members)
        self.mask_audit=[];self.open_mask_audit=[]
    def _admission_group(self,g,day):
        # Existing states of any membership remain available to original blockers.
        # Only truly FLAT nonmembers are excluded. No mutation of rows or groups.
        keep=g.sid.isin(self.admission_members)|g.sid.isin(self.states)
        filtered=g.loc[keep]
        sort=lambda frame:frame.sort_values(['PVR_score','sid'],ascending=[False,True],na_position='last',kind='stable')
        before=sort(g);after=sort(filtered)
        self.mask_audit.append(dict(day=day,sector=g.iloc[0]['sector'],
            before_event_ids=before.event_id.tolist(),after_event_ids=after.event_id.tolist(),
            excluded=[dict(event_id=r['event_id'],sid=r['sid'],PVR_score=r['PVR_score'],stock_state_before='FLAT',reason='NONMEMBER_NEW_ADMISSION_ONLY') for r in sort(g.loc[~keep]).to_dict('records')],
            retained_existing_nonmembers=[r['sid'] for r in g.loc[keep].to_dict('records') if r['sid'] not in self.admission_members],
            placement='BEFORE_ORIGINAL_QUEUE_FEASIBILITY_AND_INDUSTRY_TOP2'))
        return filtered
    _select_close=_derived_select
    def _entry_proposal(self,st,day):
        assert st['sid'] in self.admission_members,('NONMEMBER_INIT_AT_OPEN',st['sid'],st['round_id'])
        self.open_mask_audit.append(dict(day=day,event_id=st['event_id'],sid=st['sid'],round_id=st['round_id'],PVR_score=st['PVR_score'],membership=True))
        return super()._entry_proposal(st,day)

def make_bridge(source,arm):
    if arm=='all1709':return E.ExecutionBridge(source,seed_cash=E.D('1200000'))
    if arm=='tech407':return AdmissionMaskBridge(source,seed_cash=E.D('1200000'),admission_members=members())
    raise ValueError(arm)
