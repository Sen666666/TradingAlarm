"""Read saved signal outputs only; independent counting and order-statistic audit."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,time

P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def quant(a,p):
    a=sorted(a);f=(len(a)-1)*p;i=math.floor(f);j=math.ceil(f)
    return a[i] if i==j else a[i]*(j-f)+a[j]*(f-i)
def close(a,b):return a==b or finite(a) and finite(b) and abs(a-b)<=1e-12*max(1,abs(a),abs(b))
def distcheck(a,out):
    a=[x for x in a if finite(x)];assert len(a)==out['n']
    for p in [0,.1,.5,.9,1]:
        if a:assert close(quant(a,p),out[f'q{int(p*100):02}']),(p,out)
def relation(x):
    c,a=x['CP'],x['ATR3']
    if c['outcome']==a['outcome']=='EXIT_SIGNAL':
        return 'ATR_EARLIER' if a['exit_day']<c['exit_day'] else 'ATR_LATER' if a['exit_day']>c['exit_day'] else 'SAME_DAY'
    return 'CP_'+c['outcome']+'__ATR_'+a['outcome']

start=time.monotonic();agg=load(P/'AGGREGATE_DIAGNOSTICS.json')
run_roots=[P/n/'run_v1' for n in ['shard_a','shard_b','semiconductor_full']]
windows=defaultdict(list);eventcounts=defaultdict(Counter);identities=set();files={};receipts=[]
unknown_flags=Counter();pair_count=0;na_branches=0;raw_exit_samples=[]
for run in run_roots:
    receipt=load(run/'RUN_RECEIPT.json');assert receipt['status']=='COMPLETE' and receipt['errors']==0
    for path,h in receipt['code_sha256'].items():assert sha(path)==h,path
    saved=next(x for x in agg['receipts'] if x['run']==str(run.relative_to(P)))
    assert saved['receipt']==receipt and saved['receipt_sha256']==sha(run/'RUN_RECEIPT.json')
    receipts.append({'run':str(run.relative_to(P)),'receipt_sha256':sha(run/'RUN_RECEIPT.json'),
                     'complete':receipt['symbols_completed'],'not_applicable':receipt['symbols_not_applicable'],
                     'raw_anchors':receipt['raw_CP_anchors'],'code_sha256':receipt['code_sha256']})
    local=0
    for path in sorted(run.glob('*/CP_ANCHOR_PAIRS.json')):
        files[str(path)]=sha(path);rows=load(path);local+=len(rows)
        for x in rows:
            w=x['window'];lo,hi=w.split('__');assert lo<=x['anchor_day']<=hi
            identity=(x['sid'],x['anchor_id'],w);assert identity not in identities;identities.add(identity)
            windows[w].append(x);pair_count+=1
            if x['status']!='PAIRED_SHADOWS':continue
            S=x['common_risk_denominator_ATR'];assert finite(S) and S>0 and S==x['anchor_ATR_prior']
            assert x['P0']==max(x['original_candidate'],x['original_I_floor'])
            assert x['position_or_fill_claim'] is False
            assert x['common_end_day']>=x['anchor_day']
            if finite(x.get('common_max_close')):
                assert x['common_max_close']>=x['anchor_C']
                assert close(x['common_favorable_excursion_ATR'],(x['common_max_close']-x['anchor_C'])/S)
            for arm in ['CP','ATR3']:
                b=x[arm];held=b['effective_observations_held'];n=b['post20_observations'];dd=b['post20_max_close_drawdown_ATR']
                assert b['no_price_return_or_PnL'] is True
                assert n==max(held-20,0),(identity,arm,held,n)
                if held<20:
                    assert b['twentieth_observation'] is None and n==0 and dd is None;na_branches+=1
                if n==0:assert dd is None
                else:assert finite(dd) and dd>=0
                if b['outcome']=='EXIT_SIGNAL':
                    assert x['anchor_day']<b['exit_day']<=x['common_end_day']
                    assert b['status_at20']==('EXIT_BEFORE_20' if held<20 else 'EXIT_AT_20' if held==20 else 'ALIVE_AT_20')
                if b['twentieth_observation'] is not None:
                    tw=b['twentieth_observation'];assert tw['day']>x['anchor_day']
                    if tw['status']=='EXIT_AT_20':assert tw['stop_distance_ATR'] is None
                    elif tw['status']=='ALIVE_AT_20':assert close(tw['stop_distance_ATR'],(tw['C']-tw['P_after'])/S)
                unknown_flags[b['outcome']]+=1
    assert local==receipt['raw_CP_anchors']
    for path in sorted(run.glob('*/MARKET_EVENTS.json')):
        # Only event-row counts, not rerunning any state or price formula.
        files[str(path)]=sha(path)
        for e in load(path):
            lo,hi=e['window'].split('__');assert lo<=e['day']<=hi
            eventcounts[e['window']][e['kind']]+=1
assert len({r['version'] for r in [x['receipt'] for x in agg['receipts']]})==1
assert pair_count==agg['raw_anchors_total']==51026
assert {k:dict(v) for k,v in eventcounts.items()}==agg['main_market_event_counts_not_orders']

checks={}
for w,rows in windows.items():
    a=agg['windows'][w];paired=[x for x in rows if x['status']=='PAIRED_SHADOWS']
    assert len(rows)==a['raw_anchors']
    assert len({x['sid'] for x in rows})==a['distinct_stocks']
    assert dict(Counter(x['status'] for x in rows))==a['status_counts']
    assert len({x['sid'] for x in paired})==a['paired_distinct_stocks']
    assert dict(Counter(x['common_end_reason'] for x in paired))==a['common_end_counts']
    assert dict(Counter(relation(x) for x in paired))==a['exit_relation']
    assert dict(Counter('CP:'+x['CP']['status_at20']+'|ATR:'+x['ATR3']['status_at20'] for x in paired))==a['status20_cross']
    both_exit=[x for x in paired if x['CP']['outcome']==x['ATR3']['outcome']=='EXIT_SIGNAL']
    distcheck([x['ATR3']['effective_observations_held']-x['CP']['effective_observations_held'] for x in both_exit],a['held_delta_ATR_minus_CP_both_exit'])
    for arm in ['CP','ATR3']:
        b=a['branches'][arm]
        assert dict(Counter(x[arm]['outcome'] for x in paired))==b['outcomes']
        assert dict(Counter(x[arm]['status_at20'] for x in paired))==b['status_at20']
        distcheck([x[arm]['effective_observations_held'] for x in paired],b['held_observations'])
        vals=[x for x in paired if finite(x[arm]['post20_max_close_drawdown_ATR'])]
        distcheck([x[arm]['post20_max_close_drawdown_ATR'] for x in vals],b['post20_close_drawdown_in_initial_ATR'])
        assert len({x['sid'] for x in vals})==b['post20_nonmissing_distinct_stocks']
    both=[x for x in paired if all(finite(x[b]['post20_max_close_drawdown_ATR']) for b in ['CP','ATR3'])]
    assert len(both)==a['both_post20_comparable']['n']
    for arm in ['CP','ATR3']:distcheck([x[arm]['post20_max_close_drawdown_ATR'] for x in both],a['both_post20_comparable'][arm+'_drawdown'])
    distcheck([x['ATR3']['post20_max_close_drawdown_ATR']-x['CP']['post20_max_close_drawdown_ATR'] for x in both],a['both_post20_comparable']['ATR_minus_CP_drawdown'])
    values=[x['common_favorable_excursion_ATR'] for x in paired if finite(x.get('common_favorable_excursion_ATR'))]
    q=quant(values,.9);s=a['strong_common_price_opportunities'];assert close(q,s['global_window_q90_initial_ATR'])
    # Use the frozen producer's exact threshold after independently checking interpolation.
    threshold=s['global_window_q90_initial_ATR']
    strong=[x for x in paired if finite(x.get('common_favorable_excursion_ATR')) and x['common_favorable_excursion_ATR']>=threshold]
    assert len(strong)==s['n'] and len({x['sid'] for x in strong})==s['distinct_stocks']
    assert dict(Counter(x['common_end_reason'] for x in strong))==s['common_end_counts']
    assert dict(Counter(relation(x) for x in strong))==s['exit_relation']
    for arm in ['CP','ATR3']:distcheck([x[arm]['effective_observations_held'] for x in strong],s[arm+'_held_observations'])
    early=[x for x in strong if relation(x)=='ATR_EARLIER' and x['ATR3']['common_peak_after_shadow_truncation_ATR']>0]
    assert len(early)==s['ATR_earlier_with_later_higher_common_close']
    after_both=sum(x['CP']['common_peak_after_shadow_truncation_ATR']>0 for x in early)
    # Counterexamples are descriptive top-per-stock rows, not return estimates.
    for x in agg['counterexamples_global_strong_decile_ATR_earlier'][w]:
        assert any(x==z for z in early)
    checks[w]={'raw':len(rows),'status_counts':a['status_counts'],'paired':len(paired),
       'CP_post20_n':a['branches']['CP']['post20_close_drawdown_in_initial_ATR']['n'],
       'ATR3_post20_n':a['branches']['ATR3']['post20_close_drawdown_in_initial_ATR']['n'],
       'both_post20_n':len(both),'future_label_q90':threshold,'future_label_n':len(strong),
       'strong_ATR_earlier_with_later_higher_common_close':len(early),
       'of_those_common_peak_also_after_CP_exit':after_both,
       'of_those_CP_had_observed_common_peak_before_its_exit':len(early)-after_both}

files[str(P/'AGGREGATE_DIAGNOSTICS.json')]=sha(P/'AGGREGATE_DIAGNOSTICS.json')
files[str(P/'aggregate_signals.py')]=sha(P/'aggregate_signals.py')
out={'status':'PASS_BOUNDED_ALL_SAVED_PAIR_AGGREGATE_WITH_LIMITS','receipts':receipts,
     'saved_pair_files':sum(x.endswith('/CP_ANCHOR_PAIRS.json') for x in files),'all_raw_anchors':pair_count,
     'all_saved_pair_branches_checked':sum(1 for rows in windows.values() for x in rows if x['status']=='PAIRED_SHADOWS')*2,
     'less_than20_NA_branches_checked':na_branches,'window_checks':checks,
     'scope':'Read all saved raw pair rows and event counts, recompute aggregate counters/conditioned distributions/linear quantiles; static read aggregate and prior engine. No FSM/indicator/price-path/account run.',
     'limits':['Not independent validation of every underlying pair shadow trajectory or common price maximum',
       'Future common excursion label is post hoc and uses common original-I/source endpoint, not fixed equal duration across anchors',
       'Repeated anchors/stocks are dependent; per-window global q90 is not a trading-time signal',
       'An ATR-earlier/later-higher-common-close count does not establish relative CP profit or actual execution; common peak often occurs after both exit',
       'Conditional own-horizon post20 survivors are not all-anchor risk; early/unknown/censored never zero',
       'Missing market-session calendar and historical execution/receive evidence remain unverified'],
     'source_output_bindings':files,'remaining_blocks_for_statistical_scope':[],
     'new_FSM_runs':0,'new_accounts':0,'parameter_searches':0,'elapsed_seconds':time.monotonic()-start}
(O/'AGGREGATE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':out['status'],'windows':checks,'less_than20_NA_branches':na_branches,'elapsed':out['elapsed_seconds']},ensure_ascii=False))
