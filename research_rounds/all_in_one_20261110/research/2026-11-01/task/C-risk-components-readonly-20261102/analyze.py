"""Read saved JSON only; exact additive attribution, no financial engines."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib,gc
O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
M=W/'g-s-C-month-continuation-20261102'
A=W/'g-s-C-August-continuation-v1-20261102'
Z=D(0);TOL=D('1e-16');SOURCES={};ROWS=[];DETAIL={};DECISIONS=[]
archive=json.loads((A/'LOSSLESS_OUTPUT_ARCHIVE.json').read_text())['entries']

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def account(p):
    """Decode the first top-level account; SHA still covers all original bytes."""
    p=Path(p);q=p if p.exists() else A/archive[str(p.relative_to(A))]['archive']
    compressed=q.suffix=='.gz'
    storage_sha=sha(q)
    if compressed:assert storage_sha==archive[str(p.relative_to(A))]['gzip_sha256']
    h=hashlib.sha256();prefix=bytearray();value=None;dec=json.JSONDecoder()
    with (gzip.open(q,'rb') if compressed else q.open('rb')) as f:
        while b:=f.read(1024*1024):
            h.update(b)
            if value is None:
                prefix.extend(b)
                try:
                    s=prefix.decode();i=s.index('"account"');i=s.index(':',i)+1
                    value,end=dec.raw_decode(s[i:].lstrip())
                    prefix.clear()
                except (ValueError,UnicodeDecodeError,json.JSONDecodeError):pass
    assert value is not None
    if compressed:assert h.hexdigest()==archive[str(p.relative_to(A))]['original_sha256']
    SOURCES[str(p)]={'storage':str(q),'storage_sha256':storage_sha,'original_sha256':h.hexdigest()}
    return value

def cost_map(a):
    buys={int(t['layer']):t for t in a['trades'] if t['side']=='buy'}
    sold=defaultdict(list)
    for t in a['trades']:
        if t['side']=='sell':
            for p in t['parts']:sold[int(p['layer'])].append(p)
    out={}
    for z in a['layers']:
        if not z['qty']:continue
        lid=int(z['id']);b=buys[lid];qty=int(b['shares']);total=D(b['gross_cny'])+D(b['fees_cny'])
        assert D(a['share_ratio'][z['sid']])==1,'uncovered share conversion'
        assert int(z['initial_qty'])==qty,'uncovered initial quantity adjustment'
        remain=qty;allocated=Z
        for p in sold[lid]:
            basis=total-allocated if p['shares']==remain else total*D(p['shares'])/qty
            allocated+=basis;remain-=p['shares']
        assert remain==z['qty'] and remain>0
        out[lid]=(total-allocated)/D(remain)
    return out

def decomp(a,label,day,phase):
    costs=cost_map(a);out=[]
    for z in a['layers']:
        if not z['qty']:continue
        lid=int(z['id']);sid=z['sid'];q=D(z['qty']);m=D(a['market_marks'][sid]);k=costs[lid]
        f=D(a['facts_floors'][sid] if z['kind']=='core' else z['floor'])/D(a['market_factors'][sid])
        locks=[e for e in a['policy']['locks'].values() if int(e['lot'])==lid and e['remaining']]
        locked=sum((D(e['remaining']) for e in locks),Z);assert 0<=locked<=q
        p_unit=max(Z,min(m,k)-f);g_unit=max(Z,m-max(k,f));r_unit=max(Z,m-f)
        assert abs(p_unit+g_unit-r_unit)<TOL
        lock_rows=[];lock_total=Z
        for e in locks:
            for key in ['q0','e0','ratio','h']:assert e[key] is not None
            for key in ['source','cursor','mark','floor','ratio','quantity']:assert e['h'][key] is not None
            n=D(e['remaining']);base=n*r_unit;frozen=D(e['e0'])*n/(D(e['ratio'])*D(e['q0']))
            charge=max(base,frozen);lock_total+=charge
            lock_rows.append({'id':e['eid'],'qty':n,'reason':e['reason'],'base':base,'frozen':frozen,'charge':charge,'premium':charge-base})
        premium=lock_total-locked*r_unit;meta=a['capital_meta'][str(lid)]
        out.append(dict(layer=lid,sid=sid,sector=meta['sector'],role=meta['role'],pool=meta['pool'],purpose=meta['purpose'],
            opened=z['opened'],qty=q,mark=m,cost_including_allocated_buy_fees=k,raw_floor=f,
            capital=q*m,remaining_cost=q*k,unrealized=q*(m-k),already_unrealized_loss=max(Z,q*(k-m)),
            principal=q*p_unit,profit_giveback=q*g_unit,lock_premium=premium,
            free_principal=(q-locked)*p_unit,free_profit=(q-locked)*g_unit,
            locked_total=lock_total,risk=(q-locked)*r_unit+lock_total,locks=lock_rows))
    orders=[]
    for sid,b in a['buys'].items():
        info=a['order_meta'][b['order_id']];support=a['supports'][b['order_id']]
        floor=D(info['floor'])/D(a['market_factors'][sid])
        rr=D(b['remaining_shares'])*max(Z,D(support['limit'])-floor)
        orders.append(dict(sid=sid,order=b['order_id'],risk=rr,qty=b['remaining_shares'],limit=support['limit'],floor=floor))
    totals={k:sum((r[k] for r in out),Z) for k in ['principal','profit_giveback','lock_premium','free_principal','free_profit','locked_total','risk','already_unrealized_loss','capital']}
    totals['pending_risk']=sum((r['risk'] for r in orders),Z)
    totals['reconstructed_risk']=totals['risk']+totals['pending_risk']
    totals['original_risk']=D(a['balance']['resources']['risk'])
    totals['difference']=totals['reconstructed_risk']-totals['original_risk']
    assert abs(totals['difference'])<TOL,(label,day,phase,totals)
    assert abs(totals['principal']+totals['profit_giveback']+totals['lock_premium']+totals['pending_risk']-totals['original_risk'])<TOL
    assert abs(totals['free_principal']+totals['free_profit']+totals['locked_total']+totals['pending_risk']-totals['original_risk'])<TOL
    totals.update(cell=label,day=day,phase=phase,NAV=D(a['balance']['nav']),cap6=D(a['balance']['nav'])*D('.06'),available=a['balance']['available'])
    totals['profit_share']=totals['profit_giveback']/totals['original_risk'] if totals['original_risk'] else Z
    totals['principal_share']=totals['principal']/totals['original_risk'] if totals['original_risk'] else Z
    ROWS.append(totals);DETAIL[label+'|'+day+'|'+phase]={'layers':out,'orders':orders,'summary':totals}
    return totals

def saved_case(p,cell,day,phase,full=False):
    a=account(p);s=decomp(a,cell,day,phase)
    if full:
        x=json.loads(Path(p).read_text())
        result=next((r for r in reversed(x['results']) if r['at'][:10]==day),None)
        if result:
            pr=result['projection'];DECISIONS.append(dict(cell=cell,day=day,Q=pr['Q'],D=pr['D'],donors=pr['donors'],trace=pr['trace'],validation=pr['validation'],rank_binding=pr.get('C_rank_binding')))
        del x
    print(cell,day,phase,'risk',round(s['original_risk'],2),'P',round(s['principal'],2),'G',round(s['profit_giveback'],2),'L',round(s['lock_premium'],2),'B',round(s['pending_risk'],2),flush=True)
    del a;gc.collect()

for cell,arm in [('C10','C10'),('C20','C_BATCH20')]:
    for day,phase in [('2025-07-08','CLOSE'),('2025-07-22','CLOSE'),('2025-07-23','OPEN')]:
        saved_case(M/'runs'/('2025_26-'+arm)/(day+'-'+phase+'.json'),cell,day,phase,phase=='CLOSE')
    saved_case(M/'runs'/('2022-'+arm)/'2022-01-12-CLOSE.json',cell,'2022-01-12','CLOSE',True)
for day,phase in [('2025-08-22','CLOSE'),('2025-08-25','OPEN')]:
    saved_case(A/'runs/C20'/(day+'-'+phase+'.json'),'C20',day,phase)
op=json.loads((A/'analysis/C10-OPPORTUNITIES.json').read_text())
op=[r for r in op if r['sid']=='603516.SH' and r['day'].startswith('2025-08') and r['offered_use']=='S']
assert len(op)==9
for r in op:saved_case(A/'runs/C10'/(r['day']+'-CLOSE.json'),'C10',r['day'],'CLOSE')
for cell,arm in [('C10','C10'),('C20','C_BATCH20')]:
    saved_case(O/('2022-'+arm+'-2022-01-13-OPEN.json'),cell,'2022-01-13','OPEN')
save(O/'SUMMARY.json',ROWS);save(O/'LAYER_COMPONENTS.json',DETAIL);save(O/'ORIGINAL_DECISIONS.json',DECISIONS)
save(O/'CHUNZHONG_NINE.json',op)
save(O/'SOURCE_SHA256.json',SOURCES)
save(O/'CHECKS.json',dict(passed=True,snapshots=len(ROWS),financial_events=0,all_risk_bridges_within=str(TOL),new_thresholds=0,new_indicators=0,no_negative_unrealized_counted_as_profit=True,all_source_archives_hash_verified=True))
