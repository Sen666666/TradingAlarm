"""Read saved merged484-day ledger/checkpoints; never call event loop."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,pickle,collections,hashlib
import horizon_import as H
N,J,IO,O,P,W=H.N,H.J,H.IO,H.O,H.P,H.W
ROOT=O/'run-2023'
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):IO.write_json(p,J.W.canon(x))
def byte_prefix(prefix,full):
    count=0;hh=hashlib.sha256()
    with gzip.open(prefix,'rb') as a,gzip.open(full,'rb') as b:
        for line in a:
            assert line==next(b),('past stream byte changed',prefix,count)
            hh.update(line);count+=1
    return dict(records=count,uncompressed_line_bytes_exact=True,sha256=hh.hexdigest())
def main():
    assert read(ROOT/'DONE.json')['completed'];freeze=read(ROOT/'EXECUTION_FREEZE.json')
    assert all(H.sha(p)==h for p,h in freeze['entry_sources'].items())
    ds=rows(ROOT/'pair/daily.jsonl.gz');br=rows(ROOT/'pair/balances.jsonl.gz');assert len(ds)==len(br)==484
    b=json.load(gzip.open(ROOT/'pair/B.json.gz','rt'));events=[];splits=[x for x in b['audit'] if x['kind']=='split']
    for k,x in enumerate(splits):events.append((str(x['at']),0,k,'split',x))
    for k,x in enumerate(b['trades']):events.append((str(x['at']),1,k,'trade',x))
    q=collections.defaultdict(int);fees=D(0);i=0;events.sort(key=lambda x:x[:3])
    for d in ds:
        while i<len(events) and events[i][0]<=d['at']:
            _,_,_,kind,x=events[i];i+=1
            if kind=='split':q[x['sid']]=int(D(q[x['sid']])*D(x['ratio']))
            else:q[x['security_id']]+=(1 if x['side']=='buy' else -1)*x['shares'];fees+=D(x['fees_cny'])
        assert {s:v for s,v in q.items() if v}=={s:v for s,v in d['positions'].items() if v}
        assert fees==D(d['fees_cny'])
    for d in br:
        for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:
            assert abs(D(str(d[k])))<D('.000001'),(d['at'],k,d[k])
        assert all(abs(D(str(x)))<D('.000001') for x in d['pool_occupancy_difference'].values())
    prefixes={}
    for ref,path in [('old2022',P/'runs/2022/pair'),('Jan3',O/'first-session/full-input/pair')]:
        prefixes[ref]={name:byte_prefix(path/(name+'.jsonl.gz'),ROOT/'pair'/(name+'.jsonl.gz')) for name in ['daily','funding','opportunities','industry','balances','rank-policy']}
        old=json.load(gzip.open(path/'B.json.gz','rt'))
        for k in ['trades','journal','audit','decisions']:
            a=old[k];assert b[k][:len(a)]==a
    cp=[];snap={x['at'][:10]:x for x in ds}
    for path in sorted(ROOT.glob('checkpoint-*.pkl')):
        p=pickle.loads(path.read_bytes());prov=read(path.with_suffix('.provenance.json'));e=prov['engine_identity']
        assert prov['checkpoint_sha256']==H.sha(path)
        assert e['trading_class']['module_sha256']==H.sha(H.__file__)
        for key,fn in [('planning',N.Runner.planning),('opening',J.Runner.opening),('route',N.BASE.Runner.route)]:
            assert e['functions'][key]['code_sha256']==IO._code_fingerprint(fn.__code__)
        assert p['source_freeze']==freeze['checkpoint_source_freeze_preserved']
        date=str(p['last_completed_event'].date());a=p['accounts']['B']
        assert a['current_nav']==D(snap[date]['nav']) and {s:v.shares for s,v in a['positions'].items()}==snap[date]['positions']
        assert p['runner']['horizon_last_completed']==p['last_completed_event'] and not p['runner']['_cursor_claimed']
        assert p['runner']['rank_mode']=='PVR_SLOT1' and p['runner']['rank_scores_manifest_sha256']==H.NEW_SCORE_SHA
        assert type(a['budget']) is N.BASE.NoAccountBudget and a['cost_multiplier']==1 and a['delay_events']==0 and not a['add_enabled']
        assert all(x['rank']==x['priority_rank'] and 'original_H1_rank' in x for x in a['pending'])
        cp.append(dict(day=date,sha256=H.sha(path),NAV=str(a['current_nav']),native_functions_exact=True))
    assert [x['day'] for x in cp]==['2023-03-31','2023-06-30','2023-09-28','2023-12-29']
    N.configure_scores(O/'SCORES_MANIFEST.json');slots=0
    for d in b['decisions']:
        if d['at'][:4]!='2023':continue
        original=[dict(x,rank=x['original_H1_rank']) for x in d['intents']]
        keys,log=N.priority_plan(original,N.SCORES.at,d['at'][:10]);slots+=len(log)
        assert all(keys[x['sid']]==x['priority_rank']==x['rank'] for x in d['intents'])
    cache={}
    for mf in [W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json']:
        for rec in read(mf):cache.update(rec['output_sha256'])
    for rec in read(W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json'):cache[rec['output_path']]=rec['output_sha256']
    for rec in read(O/'SCORES_MANIFEST.json')['entries']:cache[str(O/'scores'/(rec['symbol']+'.parquet'))]=rec['output_sha256']
    assert all(H.sha(p)==h for p,h in cache.items())
    save(ROOT/'END_CACHE_SHA256.json',cache)
    save(ROOT/'VERIFICATION.json',dict(passed=True,merged_daily_cash_share_equity_fee_pool_bridges=484,
        fills=len(b['trades']),splits=len(splits),source_and_input_hashes_verified=True,cache_files=len(cache),
        original2022_and_Jan3_history_byte_prefixes=prefixes,original_book_array_prefixes_exact=True,
        old_checkpoints_immutable=True,quarter_checkpoints=cp,year2023_rank_slots_recomputed_exact=slots,
        account_replays_during_verification=0,source_schema_and_constraints_unchanged=True))
    print('PVR2023_VERIFY_PASS',len(b['trades']),'fills',len(splits),'splits',len(cache),'cache files',flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as e:save(ROOT/'failure/VERIFY_ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
