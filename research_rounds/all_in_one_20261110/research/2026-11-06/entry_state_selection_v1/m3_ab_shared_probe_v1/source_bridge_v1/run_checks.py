"""No shared account runs. One explicit original baseline replay per invocation."""
from pathlib import Path
import argparse,json,time,sys
import bridge
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--window',choices=sorted(bridge.ENGINES),required=True)
    parser.add_argument('--stage',choices=['prefix','full'],required=True);args=parser.parse_args()
    fixture=json.loads((bridge.HERE/'NONEMPTY_FIXTURE_SEAL.json').read_text())
    target=next(x for x in fixture['fixtures'] if x['window']==args.window)
    stop=target['first_execution_open'] if args.stage=='prefix' else None
    destination=bridge.HERE/(args.stage+'_'+args.window)
    assert not destination.exists(),'Refuse overwrite'
    started=time.monotonic();module=bridge.load_original(args.window)
    print('LOADED',args.window,round(time.monotonic()-started,3),flush=True)
    bridge.replay_no_budget(module,stop)
    checks=bridge.compare_original(module,stop)
    if args.stage=='prefix':
        assert module.actions and any(x['side']=='buy_core' for x in module.actions),'Nonempty original OPEN required'
        assert not any(x['event_type']=='OTHER_UNKNOWN_OR_LEFT' for x in module.decisions)
    before=bridge.verified_manifest()
    hashes=bridge.export_new(module,destination,checks)
    result={'status':'PASS_ORIGINAL_NO_BUDGET_'+args.stage.upper(),'window':args.window,'stop':stop,
            'seconds':time.monotonic()-started,'source_sha256':module._no_budget_source_sha256,
            'checks':checks,'output_sha256':hashes,'shared_account':False,'new_economics':False,
            'comparison':'latest sealed original A_UNION_B consumer; unchanged fixed budgets/OPEN sizing/equity callbacks',
            'limits':['NON_PIT','NET80_NOT_ACTUAL_TAX','ORDERABILITY_UNKNOWN','2026_NOT_REPLAYED']}
    with (destination/'RESULT.json').open('x') as f:json.dump(result,f,indent=2,default=str);f.write('\n')
    print(json.dumps(result,default=str),flush=True)
if __name__=='__main__':main()
