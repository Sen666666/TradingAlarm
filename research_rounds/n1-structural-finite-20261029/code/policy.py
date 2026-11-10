"""Only non-mobile held-price protection changes; stage trigger stays intact."""
from decimal import Decimal as D

def structural_advance(layer,day,close,e_floor,fine,cp,original,new_candidates):
    if layer['kind']=='mobile':return original(layer,day,close,e_floor,fine,cp)
    old=layer['floor']
    layer['floor']=e_floor
    if layer['kind']=='core':
        layer['phase']='CORE_TREND'
        return 'raise' if e_floor>old else 'structural_support_reset' if e_floor<old else None
    assert layer['kind']=='trial'
    cands=new_candidates(layer,day,fine,cp)
    if any(p>layer['entry_cost'] for _,p in cands):
        layer.update(kind='core',bridge_floor=e_floor,promoted_at=day,phase='CORE_TREND',promotion_sources=[n for n,p in cands if p>layer['entry_cost']])
        return 'promote'
    return 'raise' if e_floor>old else 'structural_support_reset' if e_floor<old else None
