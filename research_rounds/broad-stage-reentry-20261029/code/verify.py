"""Full old identity, real prefix, frozen contracts and layer policy invariants."""
from study import *
import gzip
def load(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def main():
    full=rows(O/'results/daily.jsonl.gz');old=rows(BASE/'results/daily.jsonl.gz');controls=[]
    for name in ['P0','P1']:
        ds=[r for r in full if r['account']==name];dsold=[r for r in old if r['account']==name]
        assert ds==dsold,(name,'daily identity')
        obj=load(O/f'results/{name}.json');assert obj==load(BASE/f'results/{name}.json'),(name,'full object identity')
        controls.append(dict(account=name,daily_rows=len(ds),fills=len(obj['trades'])))
    ds=[r for r in full if r['account']=='N1'];obj=load(O/'results/N1.json')
    pre=rows(O/'technical-prefix/daily.jsonl.gz');expected=[r for r in ds if r['at'][:10]<='2025-12-31']
    assert pre==expected,'physical daily prefix'
    pp=load(O/'technical-prefix/N1.json');ft=[r for r in obj['trades'] if r['at'][:10]<='2025-12-31'];fd=[r for r in obj['decisions'] if r['at'][:10]<='2025-12-31']
    assert pp['trades']==ft and pp['decisions']==fd,'trade/decision prefix'
    frozen=load(O/'FREEZE-v2.json');assert all(sha(ROOT/k)==v for k,v in frozen['sha256'].items())
    prior=[]
    for rel in ['probe-pyramid-pilot-20261029','lot-risk-allocation-20261029','minimum-risk-block-diagnosis-20261029','trial-cash-exit-design-20261029']:
        base=ROOT/'research_rounds'/rel;manifest=load(base/'completion-sha256.json')['sha256']
        assert all(sha(base/k)==v for k,v in manifest.items());prior.append(dict(study=rel,files=len(manifest),changed=0))
    counts=collections.Counter();previous={};facts={};contracts={}
    for r in obj['decisions']:
        for i in r['intents']:
            assert D(i['budget'])<=D(r['nav'])*D('.1')
            assert i['kind'] in ('trial','mobile') and i['cap']>0
            assert i['prior_flat_exit'] is None or i['prior_flat_exit']<r['at']
            contracts[i['sid'],r['at']]=i;counts['past_close_contracts']+=1
    for d in ds:
        assert D(d['available'])>=0
        for x in d['layers']:
            sid=x['sid'];ident=x['id'];counts['physical_layer_observations']+=1
            if sid not in facts:facts[sid]=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet')
            if ident in previous:
                p=previous[ident];assert D(x['floor'])>=D(p['floor'])
                if p['kind']=='core':
                    assert x['kind']=='core'
                    if sid not in d['pending_sells']:
                        e=D(str(facts[sid].loc[:d['at'][:10]].iloc[-1].i_floor))
                        assert D(x['floor'])==max(D(p['floor']),e),'core accepted fast line'
                        counts['core_stops_fast_line_checks']+=1
            previous[ident]=x
    for r in obj['audit']:
        if r['kind']=='stage_promote':
            assert D(r['floor'])>D(r['entry_cost']) and r['sources'];counts['promotion_checks']+=1
        elif r['kind']=='lot_risk_funded':
            i=contracts[r['sid'],r['signal_at']]
            assert r['signal_at']<r['at'] and r['shares']<=i['cap'] and D(r['gross'])<=D(i['budget'])
            counts['actual_funding_bounds']+=1
    layers={z['id']:z for z in obj['layers']}
    for t in obj['trades']:
        if t['side']=='buy':
            i=contracts[t['security_id'],t['signal_at']];sid=t['security_id'];day=t['at'][:10]
            if sid not in facts:facts[sid]=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet')
            factor=D(str(facts[sid].loc[day].factor))
            assert t['shares']<=i['cap'] and D(t['gross_cny'])<=D(i['budget'])
            assert D(t['raw_open'])*factor>D(i['floor']) and D(t['price'])==D(t['raw_open'])*D('1.0005')
            assert t['signal_at']<t['at'];counts['buy_execution_contracts']+=1
        else:
            assert D(t['price'])==D(t['raw_open'])*D('.9995')
            for part in t['parts']:
                assert layers[part['layer']]['opened'][:10]<t['at'][:10],'same-day sell'
                counts['layer_t_plus_one_checks']+=1
    cachechecks=0
    for sid in pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').symbol:
        f=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet');fine=pd.read_parquet(FINE/f'{sid}.parquet');cp=pd.read_parquet(CP/f'{sid}.parquet')
        left=support_cache(f,fine,cp).loc[:'2025-12-31'];right=support_cache(f.loc[:'2025-12-31'],fine.loc[:'2025-12-31'],cp.loc[:'2025-12-31'])
        pd.testing.assert_frame_equal(left,right);cachechecks+=len(left)
    account=load(O/'analysis/accounting.json');assert account['passed'] and account['daily_rows']==len(full)
    save(O/'VERIFICATION.json',dict(passed=True,complete_old_controls=controls,independent_daily_accounting_rows=len(full),
        prefix_daily_rows=len(pre),prefix_fills=len(ft),prefix_decisions=len(fd),real_support_prefix_rows=cachechecks,
        invariant_checks=dict(counts),prior_artifacts=prior,parameter_changes_after_results=0,
        successful_new_economic_paths=1,new_economic_replays=0,
        preparation_failure='economic-v1.log; no financial loop entered; REPAIR-v1.json',unit_policy_tests=10))
    print('VERIFIED',len(full),len(pre),len(ft),cachechecks,dict(counts))
if __name__=='__main__':main()
