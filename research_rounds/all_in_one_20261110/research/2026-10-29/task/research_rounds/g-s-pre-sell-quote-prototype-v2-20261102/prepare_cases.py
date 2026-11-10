"""Read existing JSON records only. No restore, account event or fill window."""
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import asdict
from decimal import Decimal as D
import json,gzip,copy,hashlib
import quote_package as P

O=Path(__file__).resolve().parent;RR=O.parent
def read(p):
    p=Path(p)
    if p.exists():return json.loads(p.read_text())
    return json.loads(gzip.open(str(p)+'.gz','rt').read())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,default=str,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def build(b):
    path=Path(b['source_snapshot']);saved=read(path);a=saved['account'];parent=copy.deepcopy(saved['active'])
    at=P.instant(('2025-08-25' if b['case']=='Aug25_C20' else '2022-01-13')+'T09:30:00+08:00')
    orig=next(r['projection'] for r in reversed(saved['results']) if r['certificate']['certificate_id']==parent['certificate_id'])
    pp=P.N.CPolicy.__new__(P.N.CPolicy);pp.nd=D(a['policy']['nd']);pp.act=a['policy']['act'];pp.incident=a['policy']['incident'];pp.scopes={s:NS(**v) for s,v in a['policy']['scopes'].items()}
    pending={i['sid']:i for i in saved['pending']};bounds={r['sid']:r for r in b['original_targets']};bounds.update({r['sid']:r for r in b['rows']})
    # Source is the already verified OPEN-only readout; never inspect H/L/C/volume.
    quotes={s:dict(price=r['open'],known_at=at.isoformat(),session=at.date().isoformat(),source='frozen_raw_open|'+b['source_manifest_sha256'],kind='current_open_print') for s,r in bounds.items()}
    specs={};meta=a['capital_meta'];lots=[]
    for z in a['layers']:
        if not z['qty']:continue
        s=z['sid'];m=meta[str(z['id'])];br=next(r for r in b['rows'] if r['layer']==z['id']);ll=[copy.deepcopy(e) for e in a['policy']['locks'].values() if e['lot']==z['id'] and e['remaining']]
        lots.append(dict(id=z['id'],sid=s,sector=m['sector'],pool=m['pool'],role=m['role'],qty=z['qty'],floor=br['floor'],locks=ll))
    for sid in quotes:
        specs[sid]=dict(quantity=asdict(P.N.quantity(at,sid.startswith('688'))),fees=asdict(P.N.fees(at,sid.startswith('688'))))
    rank=orig['C_rank_binding']['stock_priority'];demands=[]
    for sid,q in parent['Q'].items():
        if not q:continue
        i=pending[sid];sec=i['sector'];use='S' if pp.allowed(sec,'S') else 'G'
        auths=[v for v in a.get('buys',{}).values() if v['quote']['security_id']==sid]
        filled=sum(int(v['filled']) for v in saved['authority']['orders'].values() if v['cid']==parent['certificate_id'] and v['sid']==sid)
        perm=sum(int(v['cancelled']) for v in saved['authority']['orders'].values() if v['cid']==parent['certificate_id'] and v['sid']==sid)
        pend=sum(v['remaining_shares'] for v in auths)
        demands.append(dict(sid=sid,sector=sec,use=use,role='mobile',pool='confirmed',priority=rank[sid]['C_key'],receipt=copy.deepcopy(parent['receipt_bindings'][sid]),deadline=parent['deadline'],
            i_valid=i['i_valid'],stock_q=i['stock_q'],permission_valid=pp.allowed(sec if use=='S' else 'G',use),floor=next(t['effective_floor'] for t in b['original_targets'] if t['sid']==sid),
            industry_target=str(pp.nd*(D('.8') if use=='S' else D('.2'))),quantity=specs[sid]['quantity'],fees=specs[sid]['fees'],authority=dict(filled=filled,permanent_reduction=perm,pending=pend,order_bound=any(v['cid']==parent['certificate_id'] and v['sid']==sid for v in saved['authority']['orders'].values()))))
    donors=[];parent_layers={}
    for z in orig['donors']['rows']:
        lid=z['layer'];sid=z['sid'];parent_layers[lid]=z['q'];active=[e for e in a['policy']['locks'].values() if e['lot']==lid and e['remaining'] and e['sid'] in a['exits'] and e.get('native_exit')==a['exits'][sid]['event_id']]
        qq=sum(e['remaining'] for e in active);order=a['exits'][sid]
        pure=all(a['exit_duties'][e['eid']]['reasons']==['actionable_S_funding'] for e in active)
        sellable=min([P.instant(v['sellable_at']) for v in a['inventory_map'].values() if v['layer']==lid],default=at)>at
        donors.append(dict(layer=lid,sid=sid,role=meta[str(lid)]['role'],original_cap=z['q'],max_remaining=min(z['q'],qq),sellable_qty=0 if sellable else min(z['q'],qq),lock_ids=[e['eid'] for e in active],
            mixed_mandatory=not pure,submitted_unacked=order['submitted_remaining'],quantity=specs[sid]['quantity'],fees=specs[sid]['fees'],paid=order['fees_local'],accrued=order['fee_accrued_local']))
    require_sum={}
    for d in donors:require_sum[d['sid']]=require_sum.get(d['sid'],0)+d['original_cap']
    assert require_sum==parent['D']
    donor_order=[d['layer'] for d in sorted(donors,key=lambda z:(rank[z['sid']]['C_key'],-z['layer']),reverse=True)]
    state=dict(available=a['balance']['available'],non_inventory_equity=str(D(a['balance']['nav'])-D(a['balance']['inventory'])),decision_nav=a['policy']['nd'],consumed_receipts=a['policy']['consumed'],
        lots=lots,pending_rows=[],pending_orders={},receiver_responsibilities=[d['sid'] for d in demands if d['sid'] in a['exits']],other_goal_cash_encumbrance='0')
    assert not a['buys'],'small real cases selected with no live pending buys; not silently dropping pending'
    required_scopes={d['sector'] for d in demands}|{'G'}
    permissions={s:{**{u:pp.allowed(s,u) for u in ('S','G','T')},**{'holding_'+u:pp.allowed(s,u,holding=True) for u in ('S','G','T')}} for s in required_scopes}
    result=dict(case=b['case'],parent=parent,trusted_parent_id=parent['certificate_id'],at=at.isoformat(),quote_session=at.date().isoformat(),decision_nav=a['policy']['nd'],state=state,quotes=quotes,specs=specs,demands=demands,donors=donors,
        parent_D_layers=parent_layers,frozen_donor_order=donor_order,frozen_priority={d['sid']:d['priority'] for d in demands},permissions=permissions,
        industry_targets={d['sector']:d['industry_target'] for d in demands},source=dict(snapshot=str(path),snapshot_bytes_sha256=sha(path if path.exists() else str(path)+'.gz'),open_only_bound_sha256=sha(RR/'g-s-pre-sell-recipient-readonly-20261102/PRICE_ONLY_PRESELL_BOUND.json'),original_manifest=b['source_manifest'],original_manifest_sha256=b['source_manifest_sha256'],no_financial_events=True,
            Jan13_action='saved original non-held rights ACTION has zero balance/share effect' if b['case']=='Jan13_C10' else 'saved ACTION already committed'))
    # JSON-normalized keys are the trust boundary used by the CLI and restore.
    result=json.loads(json.dumps(result,default=str));result['parent_D_layers']={int(k):v for k,v in result['parent_D_layers'].items()}
    assert sum((r['risk'] for r in P.actual_rows(result)),D(0))==D(b['pre_sell_open_risk'])
    assert D(state['non_inventory_equity'])+sum((r['capital'] for r in P.actual_rows(result)),D(0))==D(b['pre_sell_open_NAV'])
    return result

def load(p):
    x=read(p);x['parent_D_layers']={int(k):v for k,v in x['parent_D_layers'].items()};return x
def main():
    bounds=read(RR/'g-s-pre-sell-recipient-readonly-20261102/PRICE_ONLY_PRESELL_BOUND.json');manifest={}
    for b in bounds:
        x=build(b);p=O/'inputs'/(b['case']+'.json');save(p,x)
        assert P.digest(load(p))==P.digest(x)
        manifest[b['case']]=dict(path=str(p),bytes_sha256=sha(p),trusted_body_sha256=P.digest(x),parent=x['parent']['certificate_id'],sources=x['source'])
        print('READ_ONLY_PREPARED',b['case'],len(x['state']['lots']),len(x['demands']),len(x['donors']),flush=True)
    save(O/'INPUT_BINDING.json',dict(cases=manifest,financial_events=0,account_restore=False,source_changes=False))
if __name__=='__main__':main()
