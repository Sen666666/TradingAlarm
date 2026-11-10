"""One bounded saved-trace association; no prices/features/native/account imports."""
from pathlib import Path
from decimal import Decimal as D
from bisect import bisect_right
import collections,csv,gzip,hashlib,json,time
O=Path(__file__).resolve().parent;W=O.parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def rows(p):
    with gzip.open(p,'rt')as f:
        for line in f:yield json.loads(line)
def stats(rs):
    return dict(layers=len(rs),buy_cash=str(sum((D(r['cost'])for r in rs),D(0))),
      original_net=str(sum((D(r['net'])for r in rs),D(0))),
      original_positive=str(sum((max(D(0),D(r['net']))for r in rs),D(0))),
      original_negative=str(sum((min(D(0),D(r['net']))for r in rs),D(0))))
beg=time.monotonic();sources={};answer={};allrows={}
for window in ('long','strong'):
    base=W/'market_gross_admission_native_v1'/f'full-{window}-v1'/'pair'
    bp=base/'D_GROSS10.json.gz';ip=base/'industry.jsonl.gz'
    lp=W/'market_gross_admission_outcome_analysis_v1'/f'full_{window}_v1'/'analysis'/window/'D_GROSS10'/'LAYERS.json'
    for p in (bp,ip,lp):sources[str(p)]=sha(p)
    book=json.loads(gzip.decompress(bp.read_bytes()));layers=read(lp);meta=book['metadata']
    assert {int(r['layer'])for r in layers}=={int(r['id'])for r in book['layers']}
    failures=collections.defaultdict(list);failure_sources=collections.defaultdict(list)
    for event in book['audit']:
        if event['kind']!='pilot_layer_exit' or event['reason']!='CP1_add_protection':continue
        for lid in event['layers']:
            m=meta[str(lid)];assert m['role']=='mobile'
            key=(m['sector'],m['episode']);day=event['at'][:10]
            failures[key].append(day);failure_sources[(key,day)].append(int(lid))
    confirmations=collections.defaultdict(list)
    for event in rows(ip):
        if event['result'] in ('probe','confirmed','expanded'):
            confirmations[event['sector'],event['episode']].append(event['day'])
        else:assert event['result']=='invalidated',event['result']
    for lists in (failures,confirmations):
        for key in lists:lists[key]=sorted(set(lists[key]))
    result=[]
    for r in layers:
        if r['role']!='mobile':continue
        m=meta[str(r['layer'])];key=(r['sector'],m['episode']);day=r['signal_day']
        fs=failures[key];cs=confirmations[key];f=bisect_right(fs,day);c=bisect_right(cs,day)
        fd=fs[f-1]if f else None;cd=cs[c-1]if c else None
        revoked=fd is not None and(cd is None or cd<=fd)
        # Already-probe fills are not falsely claimed to lose confirmed rights.
        candidate_affected=revoked and r['pool_at_fill']=='confirmed'
        result.append(dict(r,episode=m['episode'],prior_structure_failure_CLOSE=fd,
          latest_accepted_industry_CP1_CLOSE=cd,confirmed_right_revoked=revoked,
          candidate_affected=candidate_affected,
          failure_layer_ids=failure_sources.get((key,fd),[])))
    groups={'all_mobile':result}
    if window=='long':
        for name,lo,hi in [('June22_ND','2022-06-07','2022-06-30'),
          ('MarApr23_ND','2023-03-22','2023-04-21'),('Feb24_ND','2024-02-20','2024-02-29'),
          ('Sep24_resume','2024-09-30','2024-10-08'),('post924_new','2024-10-09','2024-12-31')]:
            groups[name]=[r for r in result if lo<=r['opened'][:10]<=hi]
        post=groups['post924_new'];assert len(post)==227
        assert abs(sum((D(r['net'])for r in post),D(0))-D('-107345.1888428824907416640311'))<D('.00000001')
        groups['Shanghai_film_601595']=[r for r in result if r['sid']=='601595.SH']
    else:
        fp=W/'market_gross_admission_outcome_analysis_v1/full_strong_v1/FIXED_LEADER_AND_COUNTEREXAMPLE_STOCKS.csv'
        sources[str(fp)]=sha(fp)
        fixed=list(csv.DictReader(fp.open()))
        for f in fixed:groups['fixed_'+f['sid']+'_'+f['name']]=[r for r in result if r['sid']==f['sid']]
    answer[window]={name:dict(all=stats(rs),affected_confirmed=stats([r for r in rs if r['candidate_affected']]),
        revoked_but_original_probe=stats([r for r in rs if r['confirmed_right_revoked']and not r['candidate_affected']]),
        not_affected=stats([r for r in rs if not r['candidate_affected']]))for name,rs in groups.items()}
    allrows[window]=result
for p,h in sources.items():assert sha(Path(p))==h
save(O/'ROWS.json',allrows);save(O/'SUMMARY.json',dict(scope='original path association only; no new quantities, account, prices or indicators',
    candidate='P1 same sector/episode structural failure withdraws confirmed-new-mobile until strictly later accepted original industry CP1',
    results=answer,elapsed_seconds=time.monotonic()-beg,source_SHA256=sources,
    no_counterfactual_savings=True,no_account_runs=True))
print(json.dumps({w:{k:v for k,v in answer[w].items()if not k.startswith('fixed_')}for w in answer},indent=2))
