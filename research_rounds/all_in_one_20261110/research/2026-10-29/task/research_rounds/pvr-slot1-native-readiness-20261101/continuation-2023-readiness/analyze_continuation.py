"""Saved ledgers only: continuous wealth, all-opportunity funnel and cash bridge."""
from pathlib import Path
from decimal import Decimal as D
import sys,inspect,json,gzip,collections,statistics,time,hashlib
import pandas as pd
from opportunity_endpoints import annotate,summarize
O=Path(__file__).resolve().parent;P=O.parent;W=P.parent;Z=D(0)
sys.path.insert(0,str(P));import analyze_results as B
A,M,META=B.A,B.M,B.META
A.O=O;M.O=O
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p=O/p;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
# Reuse audited ledger math verbatim, solely change merged ledger row count.
src=inspect.getsource(A.account);assert src.count('==242')==1
src=src.replace('==242','==484');env=dict(A.__dict__);exec(compile(src,__file__+'::484-row-audited-account','exec'),env)
account484=env['account']

def real_bridge(b,end):
    costs=collections.defaultdict(lambda:Z);gross=collections.defaultdict(lambda:Z)
    for t in b['trades']:
        if t['side']=='buy':costs[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny']);gross[t['layer']]+=n(t['gross_cny'])
    realized=unrealized=div=Z;partials=[]
    sold={p['layer'] for t in b['trades'] if t['side']=='sell' for p in t['parts']}
    for l in b['layers']:
        lid=l['id'];value=D(l['qty'])*A.price(l['sid'],end) if l['qty'] else Z
        # Remaining gross basis follows actual split-adjusted native unit_cost;
        # original buy fees are allocated proportionally to that remaining basis.
        basis=D(l['qty'])*n(b['metadata'][str(lid)]['unit_cost'])*costs[lid]/gross[lid] if l['qty'] else Z
        realized+=n(l['cash'])+basis;unrealized+=value-basis;div+=n(l['dividend'])
        if l['qty'] and lid in sold:partials.append(lid)
    assert abs(D(1000000)+realized+unrealized+div-n(b['ending_NAV']))<D('.0000001')
    return dict(realized_trading_net=realized,unrealized_net_mark_minus_allocated_buy_cost=unrealized,
        recognized_dividends=div,open_layers_with_partial_sales=partials,
        remaining_basis_rule='actual remaining qty * native split-adjusted unit_cost, original buy fees allocated pro rata; fractional split writeoff stays realized',
        residual=D(1000000)+realized+unrealized+div-n(b['ending_NAV']))

def analyze(ref,root,parent,states):
    assert read(root/'DONE.json')['completed'];a=account484('2023',ref,root);b=a['book'];old=book(parent/'pair/B.json.gz')
    ds=[x for x in a['daily'] if day(x['at']).startswith('2023')];assert len(ds)==242
    initial=n(old['ending_NAV']);end=n(b['ending_NAV']);olds={x['id']:x for x in old['layers']}
    changed=[];new=[]
    for l in a['layers']:
        if l['layer'] in olds:
            x=olds[l['layer']];before=n(x['cash'])+n(x['dividend'])+D(x['qty'])*A.price(x['sid'],'2022-12-30')
            changed.append(dict(layer=l['layer'],sid=l['sid'],old_live=bool(x['qty']),year_change=l['net']-before))
        else:new.append(l)
    oldchange=sum((x['year_change'] for x in changed),Z);assert abs(oldchange+sum((x['net'] for x in new),Z)-(end-initial))<D('.00000001')
    rb=real_bridge(b,'2023-12-29');ob=real_bridge(old,'2022-12-30')
    realyear={k:rb[k]-ob[k] for k in ['realized_trading_net','unrealized_net_mark_minus_allocated_buy_cost','recognized_dividends']}
    assert abs(sum(realyear.values(),Z)-(end-initial))<D('.0000001')
    tx=[x for x in b['trades'] if day(x['at']).startswith('2023')]
    actions=B.entry_actions(a);exits=B.exit_chain(a);actions23=[x for x in actions if day(x['at']).startswith('2023')]
    contributions=M.contribution(new);metrics=dict(reference=ref,initial2023_NAV=initial,end_NAV=end,
        return2023_pct=(end/initial-1)*100,DD2023=A.dd([('2022-12-30',initial)]+[(day(x['at']),n(x['nav'])) for x in ds]),
        continuous_from_original1m_return_pct=(end/D(1000000)-1)*100,
        continuous_DD=A.dd([('initial1m',D(1000000))]+[(day(x['at']),n(x['nav'])) for x in a['daily']]),
        mean_exposure_pct=sum((n(x['inventory'])/n(x['nav'])*100 for x in ds),Z)/242,
        peak_exposure_pct=max(n(x['inventory'])/n(x['nav'])*100 for x in ds),
        mean_cash_pct=sum((n(x['available'])/n(x['nav'])*100 for x in ds),Z)/242,
        mean_probe_pct=sum((n(x['pool_probe'][0])/n(x['nav'])*100 for x in ds),Z)/242,
        mean_confirmed_pct=sum((n(x['pool_confirmed'][0])/n(x['nav'])*100 for x in ds),Z)/242,
        fees2023=sum((n(x['fees_cny']) for x in tx),Z),buy_cash2023=sum((n(x['gross_cny'])+n(x['fees_cny']) for x in tx if x['side']=='buy'),Z),
        actual_buy_fills=sum(x['side']=='buy' for x in tx),actual_sell_fills=sum(x['side']=='sell' for x in tx),
        paused_closes=sum(not x['on'] for x in ds),
        ACT_events=[x for x in a['metrics']['ACT_events'] if day(x['at']).startswith('2023')],
        old_layer2023_wealth_change=oldchange,new2023_layers=contributions,
        new2023_confirmed_mobile=M.contribution([x for x in new if x['role']=='mobile' and x['pool_at_fill']=='confirmed']),
        year_realized_unrealized_dividend_change=realyear,terminal_realized_unrealized_dividend_cumulative=rb,
        terminal_dividend_AR=ds[-1]['dividend_receivable'],
        cumulative_record_only_loss=ds[-1]['shared_loss'],new_record_only_loss=n(ds[-1]['shared_loss'])-n(a['daily'][241]['shared_loss']),
        first_actual_new_buy=next((x for x in tx if x['side']=='buy'),None),
        pending_exit_stocks=len(b['exits']),entry_actions={k:M.contribution([l for l in new if l['layer'] in {x['layer'] for x in actions23 if x['action']==k}]) for k in ['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']})
    quarters=[];prev=initial
    for q in ['2023Q1','2023Q2','2023Q3','2023Q4']:
        rr=[x for x in ds if str(pd.Timestamp(day(x['at'])).to_period('Q'))==q]
        quarters.append(dict(quarter=q,start_NAV=prev,end_NAV=rr[-1]['nav'],return_pct=(n(rr[-1]['nav'])/prev-1)*100,
            DD=A.dd([('prior_close',prev)]+[(day(x['at']),n(x['nav'])) for x in rr]),
            mean_exposure_pct=sum((n(x['inventory'])/n(x['nav'])*100 for x in rr),Z)/len(rr),paused_closes=sum(not x['on'] for x in rr)))
        prev=n(rr[-1]['nav'])
    metrics['quarters']=quarters
    stock=collections.defaultdict(lambda:Z)
    for l in new:stock[l['sid']]+=l['net']
    for x in changed:stock[x['sid']]+=x['year_change']
    assert abs(sum(stock.values(),Z)-(end-initial))<D('.00000001')
    ordered=sorted(stock,key=lambda s:(-stock[s],s));chosen=list(dict.fromkeys(ordered[:10]+ordered[-3:]+['300308.SZ','300502.SZ']))
    paths=[]
    for sid in chosen:
        p=B.path(a,sid,actions,exits);p['year2023_contribution']=stock[sid]
        p['year2023_weights']=[x for x in p.pop('weights') if x['day'].startswith('2023')]
        p['year2023_peak']=max(p['year2023_weights'],key=lambda x:x['weight_pct'])
        p['actual2023_actions']=[x for x in p['actions'] if day(x['at']).startswith('2023')]
        p['actual2023_exit_chains']=[x for x in p['exit_requests_and_fills'] if day(x['request_at']).startswith('2023')]
        paths.append(p)
    ops=[x for x in rows(root/'pair/opportunities.jsonl.gz') if x['day'].startswith('2023')]
    candidates=[x for x in ops if x['CP1_id'] and x['mobile_Q'] is True and states[x['sector']][x['day']]['E0_valid'] and states[x['sector']][x['day']]['stage']>=2]
    keys={(x['sid'],x['day'],x['CP1_id']) for x in candidates};assert len(keys)==len(candidates)
    fund=[x for x in rows(root/'pair/funding.jsonl.gz') if day(x['at']).startswith('2023')]
    reserves={x['CP1_id']:x for x in fund if x['result']=='reserved' and x.get('role')=='mobile'}
    filled={x['receipt']:x for x in new if x['role']=='mobile'}
    intent={(i['sid'],day(d['at']),i['CP1_id']) for d in b['decisions'] if day(d['at']).startswith('2023') for i in d['intents'] if i['role']=='mobile'}
    attempt_start={}
    for sector,ss in states.items():
        for d,st in ss.items():
            aid=st['attempt_id']
            if isinstance(aid,str):attempt_start.setdefault((sector,aid),d)
    groups=collections.defaultdict(list)
    for x in candidates:groups[x['sid'],x['sector'],states[x['sector']][x['day']]['attempt_id']].append(x)
    cal=[day(x['at']) for x in ds];ix={d:i for i,d in enumerate(cal)};delays=[]
    for (sid,sector,aid),rs in groups.items():
        first=rs[0];opdays={x['day'] for x in rs};receipts={x['CP1_id'] for x in rs}
        fills=sorted((l for l in new if l['sid']==sid and l['role']=='mobile' and l['receipt'] in receipts),key=lambda x:x['opened'])
        got=fills[0] if fills else None
        delays.append(dict(sid=sid,sector=sector,market_attempt=aid,attempt_start=attempt_start.get((sector,aid)),
            attempt_inherited_left_censor=attempt_start.get((sector,aid),'')<'2023-01-03',first_market_eligible=first['day'],
            held_at_first_eligibility=first['held'],first_no_recorded_account_barrier=next((x['day'] for x in rs if not x['barriers'] and 'mobile' in x['roles']),None),
            first_nonzero_mobile_intent=next((x['day'] for x in rs if (sid,x['day'],x['CP1_id']) in intent),None),
            first_reserved=next((reserves[x['CP1_id']]['at'] for x in rs if x['CP1_id'] in reserves),None),
            first_actual_mobile_fill=got['opened'] if got else None,first_filled_pool=got['pool_at_fill'] if got else None,
            market_sessions_from_first_eligible_to_fill=ix[day(got['opened'])]-ix[first['day']] if got else None,
            no_observed_mobile_funding=got is None,receipt_count=len(rs)))
    delays=[annotate(g,states,cal) for g in delays]
    lags=[x['market_sessions_from_first_eligible_to_fill'] for x in delays if not x['no_observed_mobile_funding']]
    metrics['all_market_qualified_CP1_funnel']=dict(mother=len(candidates),unique_stock_attempts=len(delays),
        ACT_paused=sum('ACT_paused' in x['barriers'] for x in candidates),with_recorded_role_and_no_barrier=sum(not x['barriers'] and 'mobile' in x['roles'] for x in candidates),
        nonzero_mobile_intents=sum(k in intent for k in keys),actual_reserved_receipts=sum(x['CP1_id'] in reserves for x in candidates),
        actual_filled_receipts=sum(x['CP1_id'] in filled for x in candidates),
        actual_confirmed_filled_receipts=sum(x['CP1_id'] in filled and filled[x['CP1_id']]['pool_at_fill']=='confirmed' for x in candidates),
        first_eligible_groups_later_funded=len(lags),no_observed_mobile_funding=len(delays)-len(lags),
        mobile_competing_endpoints=summarize(delays,'mobile_funding_endpoint'),
        funded_only_first_eligible_to_fill_sessions_median=statistics.median(lags) if lags else None,
        funded_only_first_eligible_to_fill_sessions_max=max(lags,default=None),
        denominator_scope='all market Q-pass fresh canonical CP1 at active confirmed/expanded, ACT not removed; first eligible is not a proof of opening resource feasibility',
        source_last_close_censored=sum(x['day']=='2023-12-29' for x in candidates))
    metrics['raw_opening_rejection_reasons']=dict(collections.Counter(x['result'] for x in fund if '09:30' in x['at'] and x['result']!='reserved'))
    for sid in ['300308.SZ','300502.SZ']:
        p=next(x for x in paths if x['sid']==sid);oo=[x for x in ops if x['sid']==sid]
        p['year2023_signal_funnel']=dict(first_core_Q_pass=next((x['day'] for x in oo if x['core_Q'] is True),None),first_fresh_CP1=next((x['day'] for x in oo if x['CP1_id']),None),
          first_Q_pass_CP1=next((x['day'] for x in oo if x['CP1_id'] and x['mobile_Q'] is True),None),market_confirmed_qualified=sum(x['sid']==sid for x in candidates),
          opening_funding_records=[x for x in fund if x['sid']==sid and '09:30' in x['at']])
    base=Path('analysis-2023')/ref
    save(base/'METRICS.json',metrics);save(base/'LAYERS_ALL.json',a['layers']);save(base/'LAYERS_NEW2023.json',new)
    save(base/'OLD_LAYER_YEAR_CHANGE.json',changed);save(base/'ALL_FIRST_ELIGIBLE_DELAYS.json',delays)
    save(base/'TOP10_WORST3_FIXED_PATHS.json',paths);save(base/'STOCK_YEAR_CONTRIBUTIONS.json',[dict(sid=s,name=META[s]['name'],year_net=stock[s]) for s in ordered])
    return metrics,keys

def main():
    begun=time.monotonic();im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
    states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in im}
    outputs=[];mothers=[]
    for ref,root,parent in [('SC',W/'recovery-2023-readiness-20261101/runs/Bdiag',W/'2022-normal-reference-20261031/runs/B_diag'),('PVR_SLOT1',O/'run-2023',P/'runs/2022')]:
        m,keys=analyze(ref,root,parent,states);outputs.append(m);mothers.append(keys)
        print('PVR2023_SAVED_RESULT',ref,'return',m['return2023_pct'],'DD',m['DD2023']['percent'],'end',m['end_NAV'],flush=True)
    assert mothers[0]==mothers[1],'market opportunity mother differs'
    save('COMPARISON_2023.json',outputs);save('analysis-2023/COMPLETION.json',dict(passed=True,saved_books_only=True,baseline_not_rerun=True,
        common_market_mother=len(mothers[0]),seconds=time.monotonic()-begun,analysis_sha256=sha(__file__)))
if __name__=='__main__':
    try:main()
    except BaseException as e:save('analysis-2023/ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
