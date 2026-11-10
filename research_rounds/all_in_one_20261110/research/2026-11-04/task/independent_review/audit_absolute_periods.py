"""Independent interval wealth and remaining-basis reconstruction, saved books.

Original trade cost / split-adjusted initial shares times current layer qty
reconstructs remaining basis without replaying the primary sell allocator.
No model, strategy, account or runner imports; no counterfactual policy.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict
import gzip,hashlib,importlib.util,json
getcontext().prec=60
HERE=Path(__file__).parent;R=HERE.parent/'risk_constraints/absolute_loss_2022_2023'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=read(R/'SOURCE_MANIFEST.json');assert all(sha(p)==h for p,h in manifest['sources'].items())
spec=importlib.util.spec_from_file_location('ro_marks',HERE/'audit_pvr_saved.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PERIODS=read(R/'PERIODS.json');SECTORS=read(R/'SECTORS.json');Z=D(0);EPS=D('0.000001')
def eq(a,b,label):assert abs(D(a)-D(b))<EPS,(label,str(a),str(b),str(D(a)-D(b)))
def rows(p):return [json.loads(s)for s in gzip.decompress(Path(p).read_bytes()).decode().splitlines()]
def keys(day):return [('all','all'),('year',day[:4]),('quarter',day[:4]+'Q'+str((int(day[5:7])-1)//3+1)),('month',day[:7])]
FIELDS=['net_trade_cash','inventory_change','realized_trade_net','unrealized_change','recognized_dividend','wealth_change','actual_buy_cash','actual_sell_net','actual_fees','buy_fills','sell_fills']
specs=[('NO60_2022_2023',HERE.parent/'pvr_pool_feasibility/continuation2023/run-2023'),
       ('PVR_2022_2023',m.W/'pvr-slot1-native-readiness-20261101/continuation-2023-readiness/run-2023'),
       ('NO60_STRONG',HERE.parent/'pvr_pool_feasibility/runs/2025_26'),('PVR_STRONG',m.W/'pvr-slot1-native-readiness-20261101/runs/2025_26')]
out={};checks=0
for ref,root in specs:
    b=json.loads(gzip.decompress((root/'pair/B.json.gz').read_bytes()));ds=rows(root/'pair/daily.jsonl.gz')
    lookup={x['id']:b['metadata'][str(x['id'])]['sector']for x in b['layers']}
    sidsector={x['sid']:lookup[x['id']]for x in b['layers']};sectors=set(sidsector.values())
    flows=defaultdict(lambda:defaultdict(lambda:defaultdict(lambda:Z)));buys={}
    for t in b['trades']:
        day=t['at'][:10];s=sidsector[t['security_id']];f=flows[day][s];gross=D(t['gross_cny']);fee=D(t['fees_cny']);f['actual_fees']+=fee
        if t['side']=='buy':
            assert t['layer']not in buys;buys[t['layer']]=t;f['net_trade_cash']-=gross+fee;f['actual_buy_cash']+=gross+fee;f['buy_fills']+=1
        else:f['net_trade_cash']+=gross-fee;f['actual_sell_net']+=gross-fee;f['sell_fills']+=1
    split=defaultdict(list)
    for x in b['audit']:
        if x['kind']=='split':split[x['sid']].append(x)
        if x['kind']=='dividend_accrual':
            z=x['receivable'];assert z['paid_at']is None
            flows[z['ex_at'][:10]][sidsector[z['security_id']]]['recognized_dividend']+=D(z['net_local'])
    before_values=defaultdict(lambda:Z);before_real=defaultdict(lambda:Z);before_unreal=defaultdict(lambda:Z);cashcum=defaultdict(lambda:Z)
    ag=defaultdict(lambda:defaultdict(lambda:Z));starts={};ends={};counts=defaultdict(int)
    previous_on=True;act=defaultdict(lambda:defaultdict(lambda:Z));navprev=D(1000000)
    for d in ds:
        day=d['at'][:10];values=defaultdict(lambda:Z);basis=defaultdict(lambda:Z)
        for sid,q in d['positions'].items():values[sidsector[sid]]+=D(q)*m.price(sid,day)
        for l in d['layers']:
            t=buys[l['id']];adjusted_initial=D(t['shares'])
            for sp in split[l['sid']]:
                if t['at']<sp['at']<=d['at']:adjusted_initial*=D(sp['ratio'])
            basis[lookup[l['id']]]+=D(l['qty'])*(D(t['gross_cny'])+D(t['fees_cny']))/adjusted_initial
        daily_net=Z
        for s in sectors:
            f=flows[day][s];cashcum[s]+=f['net_trade_cash'];real=cashcum[s]+basis[s];unreal=values[s]-basis[s]
            z={k:f[k]for k in FIELDS};z.update(inventory_change=values[s]-before_values[s],realized_trade_net=real-before_real[s],unrealized_change=unreal-before_unreal[s])
            z['wealth_change']=z['net_trade_cash']+z['inventory_change']+z['recognized_dividend'];daily_net+=z['wealth_change']
            eq(z['realized_trade_net']+z['unrealized_change']+z['recognized_dividend'],z['wealth_change'],'independent daily split')
            for grain,period in keys(day):
                key=(grain,period,s);counts[key]+=1
                if key not in starts:starts[key]=before_values[s]
                ends[key]=values[s]
                for k,v in z.items():ag[key][k]+=v
            for k,v in z.items():act[previous_on][k]+=v
            before_values[s]=values[s];before_real[s]=real;before_unreal[s]=unreal
        eq(daily_net,D(d['nav'])-navprev,'independent daily NAV delta');navprev=D(d['nav']);previous_on=d['on']
    sr=[x for x in SECTORS if x['reference']==ref]
    for r in sr:
        key=(r['grain'],r['period'],r['sector']);assert counts[key]==r['closes']
        for f in FIELDS:eq(ag[key][f],D(r[f]),(ref,key,f));checks+=1
        eq(starts[key],D(r['inventory_begin']),'industry beginning inventory');eq(ends[key],D(r['inventory_end']),'industry terminal inventory')
    for p in [x for x in PERIODS if x['reference']==ref]:
        for f in FIELDS:eq(sum((ag[(p['grain'],p['period'],s)][f]for s in sectors),Z),D(p[f]),(ref,p['period'],f));checks+=1
        eq(D(p['begin_NAV'])+D(p['wealth_change']),D(p['end_NAV']),'period NAV bridge')
    for r in [x for x in read(R/'ACT_CLOCK_GROUPS.json')if x['reference']==ref]:
        for f in FIELDS:eq(act[r['ACT_at_OPEN']][f],D(r[f]),(ref,'previous_CLOSE_ACT_group',f));checks+=1
    out[ref]=dict(passed=True,observed_closes=len(ds),funded_industry_mother=len(sectors),full90_unfunded_industries=90-len(sectors),period_rows=len([x for x in PERIODS if x['reference']==ref]),sector_rows=len(sr))
out.update(independently_checked_numeric_cells=checks,source_SHA_checks=len(manifest['sources']),reviewer_account_events=0,
    scope='Every period/sector wealth and strictreal+unreal interval split independently reconstructed from actual trades, raw frozen marks, current qty and split-adjusted original buy-cost. Sectors are whole-book funded industry mothers; missing identities are0, not a changed90industry universe. ACT group uses previousCLOSE and is descriptive, not a causal pause experiment. Cumulative buycash recycles capital and net/buycash is not alpha. Ordinary/tail membership is not used here.',reviewer_source_SHA256=sha(__file__))
(HERE/'PVR_ABSOLUTE_PERIOD_SECTOR_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
