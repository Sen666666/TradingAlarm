"""Join already observed exact native search results; no online activity."""
from pathlib import Path
import csv, json, hashlib
from collections import Counter

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent

def read_csv(name):
    with (OUT/name).open() as f: return list(csv.DictReader(f))

def save(name, rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def exact_results(name):
    path=ROOT/name/'results.json'
    results=json.loads(path.read_text())
    parsed={}
    for r in results:
        matches=r['exact_code_matches']
        if len(matches)!=1: raise ValueError(f'Nonunique exact search: {r["query"]}')
        match=matches[0]
        parsed[match['code']]={**match,'search_observed_at':r['observed_at'],
                              'search_source_file':str(path),'search_response_sha256':r['response_sha256']}
    return parsed

special=exact_results('special-hk-search-01')
indices=exact_results('industry-native-search-01')
bridge=read_csv('hk-industry-index-bridge.csv')
for r in bridge:
    hit=indices[r['index_code']]
    r.update(index_symbol=hit['symbol'],native_market=hit['market'],
             native_market_evidence=hit['search_source_file'],native_market_observed_at=hit['search_observed_at'],
             search_response_sha256=hit['search_response_sha256'],retrieval_status='exact native search verified; history availability evaluated separately')
save('hk-industry-index-bridge.resolved.csv',bridge)
by_block={r['industry_block_code']:r for r in bridge}
h=read_csv('current-hk-equity-master.csv')
for r in h:
    if r['ths_code'] in special:
        hit=special[r['ths_code']]
        if r['ths_symbol'] and r['ths_symbol']!=hit['symbol']:raise ValueError('Native contradiction')
        r.update(ths_symbol=hit['symbol'],ths_market=hit['market'],
                 native_market_basis='Exact current client search response',
                 native_search_observed_at=hit['search_observed_at'],
                 native_search_source_file=hit['search_source_file'],
                 native_search_response_sha256=hit['search_response_sha256'])
    b=by_block.get(r['industry_block_code'])
    if b:r['industry_index_symbol']=b['index_symbol']
save('current-hk-equity-master.resolved.csv',h)
a=read_csv('current-stock-master.industry-resolved.csv')
save('current-ah-security-master.resolved.csv',a+h)
membership=read_csv('hk-current-industry-members.csv')
for r in membership:
    b=by_block.get(r['industry_block_codes'])
    if b:
        r['industry_index_symbol']=b['index_symbol']
        r['industry_index_market_source']=b['native_market_evidence']
        r['industry_index_bridge_status']='Direct StockLink relation and unique exact native search verified; history availability evaluated separately'
save('hk-current-industry-members.resolved.csv',membership)
summary={'snapshot_date':'2026-10-22','source_observations_after_midnight':'Native identity resolution only; does not move membership or OHLCV cutoff',
         'hk_rows':len(h),'hk_native_markets':dict(Counter(r['ths_market'] for r in h)),
         'hk_native_missing':[r['symbol'] for r in h if not r['ths_symbol']],
         'hk_indices':len(bridge),'a_h_rows':len(a+h),'a_h_native_unique':len({r['ths_symbol'] for r in a+h}),
         'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.resolved.csv')}}
(OUT/'verification.resolved.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
