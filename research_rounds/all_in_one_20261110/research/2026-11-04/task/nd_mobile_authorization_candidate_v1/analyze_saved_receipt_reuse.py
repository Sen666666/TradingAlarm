"""One saved-reservation association, not a new execution or risk contract."""
from pathlib import Path
from decimal import Decimal as D
from bisect import bisect_right
import collections,gzip,hashlib,json,time
O=Path(__file__).resolve().parent;W=O.parent
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stream(p):
    with gzip.open(p,'rt')as f:
        for l in f:yield json.loads(l)
def stats(rs):return dict(layers=len(rs),cost=str(sum((D(x['cost'])for x in rs),D(0))),original_net=str(sum((D(x['net'])for x in rs),D(0))),positive=str(sum((max(D(0),D(x['net']))for x in rs),D(0))),negative=str(sum((min(D(0),D(x['net']))for x in rs),D(0))))
begin=time.monotonic();orig=load(O/'ROWS.json');out={};saved={};sources={str(O/'ROWS.json'):sha(O/'ROWS.json')}
for w in ('long','strong'):
    base=W/'market_gross_admission_native_v1'/f'full-{w}-v1'/'pair'
    for name in ('D_GROSS10.json.gz','industry.jsonl.gz','funding.jsonl.gz'):sources[str(base/name)]=sha(base/name)
    book=json.loads(gzip.decompress((base/'D_GROSS10.json.gz').read_bytes()));rs=orig[w]
    sector={r['sid']:r['sector']for r in rs}
    assert all(sector[r['sid']]==r['sector']for r in rs)
    decisions={}
    for d in book['decisions']:
        for i in d['intents']:
            if i['role']=='mobile':
                k=(i['sid'],i['CP1_id']);assert k not in decisions;decisions[k]=d['at'][:10]
    events=collections.defaultdict(list)
    for e in stream(base/'industry.jsonl.gz'):events[e['sector']].append(e)
    for sec in events:events[sec].sort(key=lambda e:e['day'])
    clocks={sec:[e['day']for e in es]for sec,es in events.items()}
    used=set();classification={};reservations=[]
    for f in stream(base/'funding.jsonl.gz'):
        if f.get('result')!='reserved'or f.get('role')!='mobile'or f.get('pool')!='confirmed':continue
        k=(f['sid'],f['CP1_id']);assert k not in classification;kday=decisions[k];sec=sector.get(f['sid']);n=bisect_right(clocks.get(sec,[]),kday)
        if not sec or n==0:state='UNKNOWN_INHERITED_OR_NO_FILLED_METADATA';proof=None;ep=None
        else:
            e=events[sec][n-1];assert e['result']in ('probe','confirmed','expanded'),e
            ep=e['episode'];proof=(sec,ep,e['day']);state='REUSED_AFTER_ORIGINAL_RESERVE'if proof in used else'FIRST_ORIGINAL_RESERVE';used.add(proof)
        classification[k]=dict(state=state,proof=proof,signal_day=kday,episode=ep)
        reservations.append(dict(sid=k[0],CP1_id=k[1],at=f['at'],**classification[k]))
    mapped=[]
    for r in rs:
        if r['pool_at_fill']!='confirmed':state='ORIGINAL_PROBE_NO_CONFIRMED_GRANT_REQUIRED';proof=None
        else:
            c=classification[r['sid'],r['receipt']];state=c['state'];proof=c['proof'];assert c['signal_day']==r['signal_day']
            if c['episode']is not None:assert c['episode']==r['episode']
        mapped.append(dict(r,receipt_reuse_state=state,industry_proof=proof))
    groups={'all_mobile':mapped}
    if w=='long':
        for name,lo,hi in [('June22_ND','2022-06-07','2022-06-30'),('MarApr23_ND','2023-03-22','2023-04-21'),('Feb24_ND','2024-02-20','2024-02-29'),('Sep24_resume','2024-09-30','2024-10-08'),('post924_new','2024-10-09','2024-12-31')]:groups[name]=[r for r in mapped if lo<=r['opened'][:10]<=hi]
    else:
        for sid in ('688146.SH','301319.SZ','300489.SZ','601869.SH'):groups['fixed_'+sid]=[r for r in mapped if r['sid']==sid]
    out[w]=dict(reservations=len(reservations),reservation_classes=dict(collections.Counter(x['state']for x in reservations)),groups={k:{state:stats([r for r in v if r['receipt_reuse_state']==state])for state in sorted({r['receipt_reuse_state']for r in v})}for k,v in groups.items()})
    saved[w]=dict(reservations=reservations,actual_layers=mapped)
for p,h in sources.items():assert sha(Path(p))==h
(O/'P2_ROWS.json').write_text(json.dumps(saved,indent=2,ensure_ascii=False)+'\n')
(O/'P2_SUMMARY.json').write_text(json.dumps(dict(scope='original reserve association, not policy or original duplicate-consumption bug',results=out,seconds=time.monotonic()-begin,source_SHA256=sources,no_account_or_indicators=True),indent=2,ensure_ascii=False)+'\n')
for w in out:
    print(w,'reserve_classes',out[w]['reservation_classes'])
    for group,r in out[w]['groups'].items():print(group,r.get('REUSED_AFTER_ORIGINAL_RESERVE'))
