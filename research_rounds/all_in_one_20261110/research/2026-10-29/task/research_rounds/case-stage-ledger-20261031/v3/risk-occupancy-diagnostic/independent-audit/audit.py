import sys,json,gzip,hashlib,pickle,collections,inspect,ast,textwrap
from pathlib import Path
from datetime import datetime
from bisect import bisect_right
from decimal import Decimal as D
from types import SimpleNamespace
import pandas as pd,numpy as np
sys.dont_write_bytecode=True
V=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3')
OUT=V/'risk-occupancy-diagnostic'
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money')
sys.path.insert(0,str(V));import joint_v3 as J;import diagnose_risk as R
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tracked=[V/'joint_v3.py',V/'run-universe/pair/B.json.gz',V/'run-universe/pair/funding.jsonl.gz',V/'run-universe/pair/opportunities.jsonl.gz',OUT/'THREE_EXACT_SAVED_PIPELINE_FUNNEL.json',OUT/'THREE_EARLIEST_BLOCKS_SUMMARY.json',OUT/'POSTHOC_STOCK_CONTRIBUTIONS.json']
before={str(p):sha(p) for p in tracked}
read=lambda p:json.loads(Path(p).read_text())
book=json.load(gzip.open(V/'run-universe/pair/B.json.gz','rt'))
meta=read(ROOT/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
sm={x['symbol']:x for x in read(V.parent.parent/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
records={x['series_id']:x for x in read(J.M.P/'manifest.json')['series']}
rules=read(ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
opens=sorted(datetime.fromisoformat(x) for x in rules['calendars']['A'])
def rows(p):
    for line in gzip.open(p,'rt'):yield json.loads(line)
def next_open(day):return opens[bisect_right(opens,datetime.fromisoformat(day+'T15:10:00+08:00'))]
canonical=read(OUT/'THREE_CANONICAL_INPUTS.json')
observed={s:{} for s in canonical};named_op=collections.defaultdict(list);global_seen=set();duplicate=0
for r in rows(V/'run-universe/pair/opportunities.jsonl.gz'):
    if r['account']!='B':continue
    if r['sid'] in ['300308.SZ','300502.SZ']:named_op[r['sid']].append(r)
    if r['CP1_id'] and r['mobile_Q'] is True:
        duplicate+=r['CP1_id'] in global_seen;global_seen.add(r['CP1_id'])
        if R.in_case(r['sector'],r['day']):observed[r['sector']][r['CP1_id']]=r
assert duplicate==0 and len(global_seen)==21411
assert {s:set(x) for s,x in observed.items()}=={s:set(x) for s,x in canonical.items()}
fund=collections.defaultdict(list)
for r in rows(V/'run-universe/pair/funding.jsonl.gz'):
    if r['account']=='B':fund[(r['at'][:10],r['sid'],r['role'])].append(r)
intent={i['CP1_id']:i for d in book['decisions'] for i in d['intents'] if i['role']=='mobile'}
mobile_fills=collections.defaultdict(list)
for x in book['journal']:
    if x['kind']=='real_buy_fill' and x['role']=='mobile':mobile_fills[x['CP1_id']].append(x)
states={s:{x['day']:x for x in read(V.parent.parent/'industry-mobile-stage-20261031'/f'{s}_STATE.json')} for s in canonical}
pre_route={'missing_open','open_at_or_below_protection','open_minimum_exceeds_frozen_contract'}
funnels={};inactive_routes=[];first_exclusive={}
for sector,rr in observed.items():
    c=collections.Counter(canonical_Q_pass=len(rr));partition=collections.Counter()
    for rid,r in rr.items():
        active=states[sector][r['day']]['stage']>0;c['industry_attempt_active']+=active
        c['mobile_intent_created']+=rid in intent
        op=next_open(r['day']);day=op.date().isoformat();events=fund[(day,r['sid'],'mobile')]
        # Every target has at most one opening mobile funding record.
        events=[x for x in events if x['at'][11:16]=='09:30'];assert len(events)<=1
        if not events:
            core=[x for x in fund[(day,r['sid'],'core')] if x['result']=='reserved']
            assert core,(sector,rid,'unexplained pre-route absence')
            partition['same_stock_core_priority_skipped_mobile']+=1;continue
        result=events[0]['result']
        if result in pre_route:partition['pre_route_price_lot_or_sizing_refusal']+=1;continue
        c['entered_real_route']+=1
        if not active:inactive_routes.append(dict(sector=sector,day=r['day'],sid=r['sid'],reason=result));assert result=='industry_invalidated'
        if result=='reserved':
            assert rid in mobile_fills;partition['actual_mobile_filled']+=1;c['actual_mobile_fill_receipt']+=1
        else:
            c['route_zero_legal_quantity']+=1
            if result=='account_risk':
                partition['strict_raw_account_risk_only']+=1;c['strict_raw_account_risk_only']+=1
                first_exclusive.setdefault(sector,dict(at=events[0]['at'],sid=r['sid'],receipt=rid))
            elif 'account_risk' in result:
                partition['raw_account_risk_with_other_route_reasons']+=1;c['raw_account_risk_with_other_route_reasons']+=1
            else:partition['other_route_refusal']+=1
    assert sum(partition.values())==len(rr)
    funnels[sector]=dict(counts=dict(c),partition=dict(partition))
expected=read(OUT/'THREE_EXACT_SAVED_PIPELINE_FUNNEL.json')
for e in expected:
    assert all(funnels[e['sector']]['counts'].get(k,0)==v for k,v in e['counts'].items())
    assert funnels[e['sector']]['partition']==e['mutually_exclusive_actual_pipeline_partition']

daily={r['at'][:10]:r for r in rows(V/'run-universe/pair/daily.jsonl.gz') if r['account']=='B'}
native_buys={str(x['layer']):x for x in book['trades'] if x['side']=='buy'}
raw_cache={};facts_cache={}
def raw(sid):
    if sid not in raw_cache:
        rec=records[sid];p=Path(rec['raw']['path']);assert sha(p)==rec['raw']['sha256'];f=J.M.N.read_raw(p,rec)
        f['valid_price']=f.index.isin(J.M.N.eligible_prices(f).index)
        f['observed_bar']=J.M.N.boolean_column(f,'observed_bar',True)
        raw_cache[sid]=f
        market.actions[sid]=J.M.N.read_actions(rec,J.M.P)[0]
    return raw_cache[sid]
def facts(sid):
    if sid not in facts_cache:
        p=Path(sm[sid]['refs']['facts']);assert sha(p)==sm[sid]['output_sha256'][str(p)];facts_cache[sid]=pd.read_parquet(p)
    return facts_cache[sid]
h=np.load(J.M.P/'h1.npz');hdates=pd.DatetimeIndex(h['dates']);hcols={str(s):i for i,s in enumerate(h['symbols'])}
def h1(sid,day):
    i=hdates.searchsorted(pd.Timestamp(day),side='right')-1;v=float(h['score'][i,hcols[sid]])
    return v if np.isfinite(v) else None
market=J.M.E.FastMarket.__new__(J.M.E.FastMarket);market.rules=rules;market.protocol=read(ROOT/'research_rounds/rs-h1-execution-20261025/inputs-v2/economic-protocol.json');market.cache_at=None
market.bundle=SimpleNamespace(series={s:SimpleNamespace(record=r) for s,r in records.items()})
market.lines={s:SimpleNamespace(market='A') for s in records};market.raw=raw_cache;market.actions={};market.sessions={'A':opens}
snapshot_results=[]
for sector in canonical:
    snap=read(OUT/f'FIRST_EXCLUSIVE_{sector}.json');at=datetime.fromisoformat(snap['at']);known=datetime.fromisoformat(snap['signal_evidence_known_at']);day=known.date().isoformat();rid=snap['candidate']['receipt'];sid=snap['candidate']['stock']
    assert first_exclusive[sector]==dict(at=snap['at'],sid=sid,receipt=rid)
    assert next_open(day)==at and known<at and observed[sector][rid]['day']==day
    assert abs(h1(sid,day)-snap['candidate']['H1'])<1e-10
    prior={str(x['id']):x for x in daily[day]['layers']};max_partition_gap=0.;max_floor_gap=0.
    for z in snap['lots']:
        q=z['quantity'];m=z['mark'];cost=z['unit_raw_fill_cost_split_adjusted'];f=z['effective_raw_floor'];p=q*max(min(m,cost)-f,0);g=q*max(m-max(cost,f),0);risk=q*max(m-f,0)
        max_partition_gap=max(max_partition_gap,abs(p+g-risk));assert abs(p-z['principal_downside'])<1e-7 and abs(g-z['profit_giveback'])<1e-7 and abs(risk-z['risk'])<1e-7
        trade=native_buys[z['batch']];assert abs(cost-float(D(trade['gross_cny'])/D(trade['shares'])))<1e-10
        raw(z['stock']);mark=J.M.N.FrozenMarket.latest_mark(market,z['stock'],at)
        assert mark.known_at<=at and mark.cny_price(at)==D(str(m))
        ff=facts(z['stock']);rr=ff.loc[:pd.Timestamp(day)].iloc[-1];factor=float(ff.loc[:pd.Timestamp(at.date())].iloc[-1]['factor'])
        assert bool(rr.i_target)==z['known_stock_I'] and bool(rr.e0_target)==z['known_stock_E0']
        assert abs(h1(z['stock'],day)-z['known_stock_H1'])<1e-10
        previous=prior[z['batch']];line=float(previous['last_core_line'] if z['role']=='core' else previous['floor']);gap=abs(line/factor-f);max_floor_gap=max(max_floor_gap,gap);assert gap<1e-8
    pending=sum(z['quantity']*max(z['unit_limit']-z['floor'],0) for z in snap['pending_orders'])
    total=sum(z['risk'] for z in snap['lots'])+pending;assert abs(total-snap['resources']['total_risk'])<1e-6 and pending==snap['pending_buy_risk']
    # Reconstruct the saved authorization view, not a runner/account trajectory.
    b=SimpleNamespace(expand=True,nav=snap['resources']['marked_NAV'],cash=float(D(snap['resources']['available_cash']))+snap['resources']['pending_reserve'],consumed=set(book['budget']['consumed']))
    assert rid not in b.consumed
    b.lots=[J.V.Lot(z['batch'],z['stock'],z['sector'],'unused',z['pool'],z['quantity'],z['unit_raw_fill_cost_split_adjusted'],z['effective_raw_floor'],z['role'],z['attempt']) for z in snap['lots']]
    b.prices={z['stock']:z['mark'] for z in snap['lots']};b.orders={}
    assert not snap['pending_orders']
    sr=states[sector][day];allstate=list(states[sector].values());first=next(z for z in allstate if z['attempt_id']==sr['attempt_id'] and z['action']=='probe');epstart=next(z['day'] for z in allstate if z['E0_episode']==sr['E0_episode'] and z['E0_valid'])
    b.sectors={sector:J.V.Sector(sr['E0_episode'],J.ordinal(first['day']),level=sr['stage']-1,active=True,attempt=sr['E0_episode']+':'+first['receipt_id'],episode_started=J.ordinal(epstart))}
    def resources(pool=None,sector=None):
        lots=[z for z in b.lots if (pool is None or z.pool==pool) and (sector is None or z.sector==sector)]
        return sum(z.qty*b.prices[z.stock] for z in lots),sum(z.qty*max(0,b.prices[z.stock]-z.floor) for z in lots),0.
    b.resources=resources;b.valid=lambda token,source,bar:J.V.Contract.valid(b,token,source,bar)
    # All three target industries have no existing lots here, so migration can
    # change only its status. The exact capital eligibility check is retained.
    assert not any(z.sector==sector for z in b.lots)
    b.migrate=lambda s:R.can_migrate(b,s)
    a=SimpleNamespace(budget=b,available=D(snap['resources']['available_cash']),current_nav=D(snap['resources']['last_decision_NAV']),quantity=lambda stock:sum(z.qty for z in b.lots if z.stock==stock),core_epoch={},pools_from_model=lambda:None)
    i=dict(intent[rid]);i.update(clock=SimpleNamespace(decision_at=known,earliest_execution_at=at),quote=SimpleNamespace(par_value=D(rules.get('security_metadata',{}).get(sid,{}).get('par_value','1'))),CP1_trace=next(z for z in read(sm[sid]['refs']['receipts']) if z['receipt_id']==rid));i['budget']=D(i['budget']);i['floor']=D(i['floor'])
    rule=market.quantity(sid,at);schedule=market.fees(sid,at);op=D(str(raw(sid).loc[pd.Timestamp(at.date()),'open']));factor=D(str(facts(sid).loc[:pd.Timestamp(at.date())].iloc[-1]['factor']))
    x,why=J.LR.preview(i,op,factor,rule,schedule);assert why is None
    runner=SimpleNamespace(sector_by_sid={sid:sector});actual,why=J.Runner.route(runner,a,i,x,at);assert actual is None and why=='account_risk'
    cf,reason=R.no_account_check(runner,a,i,x,at);assert list(cf)==snap['route']['without_account_check_route'] and reason is None
    assert not b.orders
    snapshot_results.append(dict(sector=sector,at=snap['at'],known_at=snap['signal_evidence_known_at'],lots=len(snap['lots']),max_risk_partition_gap=max_partition_gap,max_previous_decision_floor_gap=max_floor_gap,pending_risk=pending,minimum_legal_quantity=rule.buy_minimum,preview_maximum=x['maxq'],only_remove_account_result=cf,existing_risk=total,account_limit_before_new_fee=.03*b.nav))

# Rebuild stock contributions from the same saved B ledger and final mark view.
cp=pickle.loads((V/'run-universe/checkpoint.pkl').read_bytes());ending=cp['accounts']['B'];assert str(ending['current_nav'])==book['ending_NAV']
unit={str(t['layer']):(D(t['gross_cny'])+D(t['fees_cny']))/D(t['shares']) for t in book['trades'] if t['side']=='buy'}
stock=collections.defaultdict(lambda:dict(realized=D(0),remaining_cost=D(0),dividend=D(0),terminal_value=D(0),buy_cash=D(0)))
for t in book['trades']:
    s=stock[t['security_id']]
    if t['side']=='buy':s['buy_cash']+=D(t['gross_cny'])+D(t['fees_cny'])
    else:
        for part in t['parts']:s['realized']+=D(part['net_cash'])-unit[str(part['layer'])]*D(part['shares'])
assert not any(z['kind'] in ('split','split_fraction_floor_proxy') for z in book['audit'])
for z in book['layers']:
    s=stock[z['sid']];s['dividend']+=D(z['dividend']);s['remaining_cost']+=unit[str(z['id'])]*D(z['qty'])
    if z['qty']:s['terminal_value']+=D(z['qty'])*D(str(ending['budget'].prices[z['sid']]))
for s in stock.values():s['contribution']=s['realized']+s['terminal_value']-s['remaining_cost']+s['dividend']
post=read(OUT/'POSTHOC_STOCK_CONTRIBUTIONS.json');top=sorted(stock,key=lambda k:stock[k]['contribution'],reverse=True)[:10];assert top==[z['sid'] for z in post['top10_positive']]
max_contribution_gap=D(0)
for z in post['top10_positive']:
    s=stock[z['sid']];gap=abs(s['contribution']-D(z['total_contribution']));max_contribution_gap=max(max_contribution_gap,gap);assert gap<D('.00001')
total_gap=sum((z['contribution'] for z in stock.values()),D(0))-(D(book['ending_NAV'])-D(1000000));assert abs(total_gap)<D('.00001')
named=[]
for sid in ['300308.SZ','300502.SZ']:
    ff=facts(sid).loc[J.START:J.END];ts=[t for t in book['trades'] if t['security_id']==sid]
    assert not ts and not any(z['sid']==sid for z in book['layers'])
    named.append(dict(sid=sid,identity=meta[sid],fact_rows=len(ff),first_day=str(ff.index.min().date()),last_day=str(ff.index.max().date()),positive_raw_close_rows=int(ff.raw_close.gt(0).sum()),required_CP1_receipts=sm[sid]['required_account_CP1_receipts'],saved_opportunity_rows=len(named_op[sid]),Q_pass_CP1=sum(z['CP1_id'] is not None and z['mobile_Q'] is True for z in named_op[sid]),actual_trades=0,actual_layers=0))
source_matches=ast.dump(ast.parse(textwrap.dedent(R.pure)))==ast.dump(ast.parse(textwrap.dedent((OUT/'COUNTERFACTUAL_SOURCE.py').read_text())))
assert source_matches
after={str(p):sha(p) for p in tracked};assert before==after
evidence=dict(passed=True,no_economic_replay_or_main_policy_write=True,original_inputs_unchanged=True,source_sha256=after,global_canonical=21411,duplicate_receipts=duplicate,funnels=funnels,inactive_routes=inactive_routes,snapshot_checks=snapshot_results,counterfactual_source_matches_current_derived_one_check_removal=source_matches,contributions=dict(top10_sids=top,maximum_top10_contribution_difference=str(max_contribution_gap),total_account_gap=str(total_gap),source='same saved universe B ledger; final checkpoint shares/marks',posthoc_not_online=True),named_stocks=named)
Path(__file__).with_name('EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in evidence.items() if k!='source_sha256'},ensure_ascii=False,indent=2))
