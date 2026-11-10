"""Frozen saved sources, native flow/quantity and real checkpoint identity only."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,pickle,hashlib,collections,argparse,sys
import runner as R
O=R.O
sys.path.insert(0,str(R.W/'q2-normal-continuation-20261031'))
import continuation as E
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(win):
    root=O/'runs'/win;assert read(root/'DONE.json')['completed']
    frozen=read(root/'FREEZE.json')['sources'];assert all(sha(p)==h for p,h in frozen.items())
    with gzip.open(root/'pair/B.json.gz','rt') as f:b=json.load(f)
    ds=rows(root/'pair/daily.jsonl.gz');balances=rows(root/'pair/balances.jsonl.gz');assert len(ds)==len(balances)==242
    splits=[x for x in b['audit'] if x['kind']=='split'];events=[]
    for index,t in enumerate(b['trades']):events.append((str(t['at']),1,index,'trade',t))
    for index,s in enumerate(splits):events.append((str(s['at']),0,index,'split',s))
    events.sort(key=lambda x:x[:3]);q=collections.defaultdict(int);fee=D(0);at=0
    for d in ds:
        while at<len(events) and events[at][0]<=d['at']:
            _,_,_,kind,x=events[at];at+=1
            if kind=='split':q[x['sid']]=int(D(q[x['sid']])*D(x['ratio']))
            else:
                q[x['security_id']]+=(1 if x['side']=='buy' else -1)*x['shares'];fee+=D(x['fees_cny'])
                assert q[x['security_id']]>=0
        assert {s:v for s,v in q.items() if v}=={s:v for s,v in d['positions'].items() if v},(win,d['at'],'journal quantity')
        assert fee==D(d['fees_cny']),(win,d['at'],'cumulative actual fees')
    for x in balances:
        for key in ('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):
            assert abs(D(str(x[key])))<D('.000001'),(win,x['at'],key,x[key])
        assert all(abs(D(str(v)))<D('.000001') for v in x['pool_occupancy_difference'].values())
    snap={x['at'][:10]:x for x in ds};checkpoints=[]
    for path in sorted(root.glob('checkpoint-*.pkl')):
        prov=read(path.with_suffix('.provenance.json'));assert prov['checkpoint_sha256']==sha(path)
        identity=prov['engine_identity'];assert identity['trading_class']['module_sha256']==sha(Path(R.__file__))
        assert identity['trading_class']['class_name']=='Runner'
        for name,fn in [('planning',R.J.Runner.planning),('opening',R.J.Runner.opening),('route',R.Runner.route)]:
            assert identity['functions'][name]['code_sha256']==R.IO._code_fingerprint(fn.__code__)
        blob=pickle.loads(path.read_bytes());d=str(blob['last_completed_event'].date());a=blob['accounts']['B']
        assert type(a['budget']) is R.N.DecoupledBudget and blob['runner']['integration_policy']=='original_singlepass_decoupled'
        assert a['cost_multiplier']==1 and a['delay_events']==0 and not a['add_enabled'] and a['mode']=='ACT'
        assert not hasattr(a['budget'],'c1') and not hasattr(a['budget'],'grants')
        assert a['current_nav']==D(snap[d]['nav'])
        assert {s:p.shares for s,p in a['positions'].items()}==snap[d]['positions']
        assert blob['source_freeze']==frozen
        checkpoints.append(dict(path=str(path),day=d,NAV=str(a['current_nav']),source_identity_bound=True,all_cumulative_native_state_saved=True))
    assert len(checkpoints)==4
    full=pickle.loads((root/'prefix-full-source/checkpoint.pkl').read_bytes())
    cut=pickle.loads((root/'prefix-physical-source/checkpoint.pkl').read_bytes())
    assert E.equal(full['accounts'],cut['accounts']),'strict physical prefix native account mismatch'
    checked=[];derived={}
    for key,value in full['runner'].items():
        if key=='run_seconds':continue
        if key=='episode_starts':
            end=full['last_completed_event'].date().toordinal()
            known={k:v for k,v in value.items() if v<=end};future={k:v for k,v in value.items() if v>end}
            assert E.equal(known,cut['runner'][key]),'physical known E0 start lookup mismatch'
            derived=dict(known_episode_starts=len(known),future_input_lookup_entries=len(future),all_extras_strictly_after_cut=True)
        else:assert E.equal(value,cut['runner'][key]),('strict physical saved runner mismatch',key)
        checked.append(key)
    result=dict(passed=True,window=win,source_and_input_hashes_unchanged=True,daily_money_equity_pool_and_stock_bridges=242,
        independently_rebuilt_stock_quantities=242,cumulative_actual_fee_checks=242,
        actual_trade_fills=len(b['trades']),actual_split_events=len(splits),quarter_checkpoints=checkpoints,
        physical_prefix_strict_saved_native_accounts=True,physical_prefix_runner_fields=checked,
        physical_prefix_future_input_lookup=derived,
        full_financial_SD_paths=1,baseline_replays=0)
    R.IO.write_json(root/'VERIFICATION.json',result);print('VERIFIED',win,len(b['trades']),'fills',len(splits),'splits',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);args=p.parse_args()
    try:run(args.window)
    except BaseException as e:
        R.IO.write_json(O/'failure/VERIFICATION_ERROR.json',dict(window=args.window,type=type(e).__name__,reason=str(e)));raise
