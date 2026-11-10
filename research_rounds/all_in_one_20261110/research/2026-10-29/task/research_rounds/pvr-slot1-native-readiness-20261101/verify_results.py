"""Read-only daily/quantity/fee/source/checkpoint/rank verification, no replay."""
from pathlib import Path
from decimal import Decimal as D
import gzip,json,pickle,collections,argparse
import native_rank as N
J,L,IO,O=N.J,N.L,N.IO,N.O
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def run(win):
    root=O/'runs'/win;assert read(root/'DONE.json')['completed']
    frozen=read(root/'FROZEN_RUN_METADATA.json')['sources'];assert all(N.sha(p)==h for p,h in frozen.items())
    with gzip.open(root/'pair/B.json.gz','rt') as f:b=json.load(f)
    ds=rows(root/'pair/daily.jsonl.gz');balances=rows(root/'pair/balances.jsonl.gz');assert len(ds)==len(balances)==242
    events=[];splits=[x for x in b['audit'] if x['kind']=='split']
    for i,t in enumerate(b['trades']):events.append((str(t['at']),1,i,'trade',t))
    for i,x in enumerate(splits):events.append((str(x['at']),0,i,'split',x))
    q=collections.defaultdict(int);fee=D(0);k=0;events.sort(key=lambda x:x[:3])
    for d in ds:
        while k<len(events) and events[k][0]<=d['at']:
            _,_,_,kind,x=events[k];k+=1
            if kind=='split':q[x['sid']]=int(D(q[x['sid']])*D(x['ratio']))
            else:q[x['security_id']]+=(1 if x['side']=='buy' else -1)*x['shares'];fee+=D(x['fees_cny'])
        assert {s:v for s,v in q.items() if v}=={s:v for s,v in d['positions'].items() if v}
        assert fee==D(d['fees_cny'])
    for r in balances:
        for key in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference',
                    'capital_occupancy_difference','maximum_stock_quantity_difference']:
            assert abs(D(str(r[key])))<D('.000001'),(win,r['at'],key,r[key])
        assert all(abs(D(str(v)))<D('.000001') for v in r['pool_occupancy_difference'].values())
    N.configure_scores();ranked=0;NA=0
    for d in b['decisions']:
        original=[dict(i,rank=i['original_H1_rank']) for i in d['intents']]
        keys,log=N.priority_plan(original,N.SCORES.at,d['at'][:10])
        for i in d['intents']:
            assert keys[i['sid']]==i['priority_rank']==i['rank']
            assert i['priority_policy']==N.POLICY
        ranked+=len(log);NA+=sum(not x['PVR_ready'] for x in log)
    snapshots={x['at'][:10]:x for x in ds};checkpoints=[]
    for path in sorted(root.glob('checkpoint-*.pkl')):
        prov=read(path.with_suffix('.provenance.json'));assert prov['checkpoint_sha256']==N.sha(path)
        e=prov['engine_identity'];assert e['trading_class']['module_sha256']==N.sha(N.__file__)
        for name,fn in [('planning',N.Runner.planning),('opening',J.Runner.opening),('route',N.BASE.Runner.route)]:
            assert e['functions'][name]['code_sha256']==IO._code_fingerprint(fn.__code__)
        p=pickle.loads(path.read_bytes());d=str(p['last_completed_event'].date());a=p['accounts']['B']
        assert p['runner']['rank_mode']=='PVR_SLOT1' and p['runner']['integration_policy']==N.POLICY+':PVR_SLOT1'
        assert p['runner']['rank_scores_manifest_sha256']==N.SCORES.manifest_sha256
        assert type(a['budget']) is N.BASE.NoAccountBudget and a['mode']=='ACT'
        assert a['cost_multiplier']==1 and a['delay_events']==0 and not a['add_enabled']
        assert not hasattr(a['budget'],'c1') and not hasattr(a['budget'],'grants')
        assert p['source_freeze']==frozen and a['current_nav']==D(snapshots[d]['nav'])
        assert {s:x.shares for s,x in a['positions'].items()}==snapshots[d]['positions']
        assert all(i['rank']==i['priority_rank'] and 'original_H1_rank' in i for i in a['pending'])
        checkpoints.append(dict(path=str(path),day=d,identity_bound=True,NAV=str(a['current_nav'])))
    assert len(checkpoints)==4
    out=dict(passed=True,window=win,source_input_cache_hashes_exact=True,daily_cash_equity_pool_bridges=242,
      independently_rebuilt_daily_stock_quantities=242,cumulative_fee_checks=242,actual_fill_records=len(b['trades']),
      actual_splits=len(splits),quarter_checkpoints=checkpoints,
      all_242_decisions_slot_priority_recomputed_exact=True,distinct_stock_day_rank_slots=ranked,NA_fixed_slots=NA,
      new_economic_replays=0,original_opening_route_callbacks_unchanged=True)
    IO.write_json(root/'VERIFICATION.json',out)
    print('VERIFIED_PVR_SLOT1',win,len(b['trades']),'fills',len(splits),'splits','slots',ranked,'NA',NA,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);a=p.parse_args()
    try:run(a.window)
    except BaseException as e:
        IO.write_json(O/'failure/VERIFICATION_ERROR.json',dict(window=a.window,type=type(e).__name__,reason=str(e)));raise
