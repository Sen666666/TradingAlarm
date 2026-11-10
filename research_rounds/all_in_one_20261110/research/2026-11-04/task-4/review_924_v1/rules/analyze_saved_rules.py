"""Read completed original No60 records only; never construct a trading object."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter, defaultdict
import gzip, hashlib, json, time

O=Path(__file__).resolve().parent
ROOT=O.parents[1]
P=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
SOURCES={}

def bind(p):
    p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p

def read(p):return json.loads(bind(p).read_text())
def load(p,lines=False):
    with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
    start=time.monotonic();bind(__file__);O.mkdir(parents=True,exist_ok=True)
    b=load(P/'B.json.gz');daily=load(P/'daily.jsonl.gz',True);funding=load(P/'funding.jsonl.gz',True)
    meta={r['sid']:r for r in read(ROOT/'core_confirmed_v1/analysis/long_OFF_STOCKS.json')}
    layers={l['id']:l for l in b['layers']};by_day=defaultdict(list);exit_events=defaultdict(list)
    for t in b['trades']:by_day[t['at'][:10]].append(t)
    for a in b['audit']:
        if a['kind']=='pilot_layer_exit':
            for layer in a['layers']:exit_events[layer].append(a)
    rows=[];previous=None
    for r in daily:
        day=r['at'][:10]
        if '2024-09-23'<=day<='2024-12-31':
            fs=[x for x in funding if x['at'][:10]==day]
            opens=[x for x in fs if '09:30:00' in x['at']]
            closes=[x for x in fs if '15:10:00' in x['at']]
            ts=by_day[day]
            rows.append(dict(day=day,NAV=r['nav'],available=r['available'],inventory=r['inventory'],
                stock_count=len(r['positions']),exposure_pct=D(r['inventory'])/D(r['nav'])*100,
                ACT_on=r['on'],pending_sells=r['pending_sells'],pending_intents=r['pending_intents'],
                previous_CLOSE_NAV=previous['nav'],previous_CLOSE_available=previous['available'],
                previous_CLOSE_cash_after_tenpct_reference=D(previous['available'])-D(previous['nav'])*D('.1'),
                cash_reference_scope='Prior CLOSE reference only, not an exact pre-candidate snapshot; OPEN sells/actions/reservations may change cash.',
                actual_buy_fills=sum(t['side']=='buy'for t in ts),actual_sell_fills=sum(t['side']=='sell'for t in ts),
                buy_cash=sum((D(t['gross_cny'])+D(t['fees_cny'])for t in ts if t['side']=='buy'),D(0)),
                sell_net=sum((D(t['gross_cny'])-D(t['fees_cny'])for t in ts if t['side']=='sell'),D(0)),
                OPEN_funding_records=len(opens),OPEN_results=[dict(role=k[0],result=k[1],count=v)for k,v in sorted(Counter((x['role'],x['result'])for x in opens).items())],
                CLOSE_size_records=len(closes),CLOSE_size_results=[dict(role=k[0],result=k[1],count=v)for k,v in sorted(Counter((x['role'],x['result'])for x in closes).items())]))
        previous=r
    save('DAILY_RULES_AND_FUNDING.json',rows)

    post=[];same_sid_buy_sell=[];classification_checks=[]
    ds_by_day={r['at'][:10]:r for r in daily};days=sorted(ds_by_day)
    for t in b['trades']:
        if t['side']!='buy'or t['at'][:10]<'2024-10-09':continue
        l=layers[t['layer']];assert l['qty']==0
        old=[v for v in layers.values()if v['sid']==l['sid']and v['opened']<l['opened']]
        held=any(v['closed']is None or v['closed']>l['opened']for v in old)
        kind='existing_stock_add'if held else'flat_reentry'if old else'account_first_entry'
        day=t['at'][:10];pd=days[days.index(day)-1];prev_held=bool(ds_by_day[pd]['positions'].get(l['sid'],0))
        sell_today=any(v['side']=='sell'and v['security_id']==l['sid']for v in by_day[day])
        if sell_today:same_sid_buy_sell.append(dict(layer=l['id'],sid=l['sid'],day=day))
        else:assert held==prev_held,(l['id'],l['sid'],held,prev_held)
        events=exit_events[l['id']];first=events[0]if events else None
        sales=[v for v in b['trades']if v['side']=='sell'and any(z['layer']==l['id']for z in v['parts'])]
        post.append(dict(layer=l['id'],sid=l['sid'],name=meta.get(l['sid'],{}).get('name'),industry=meta.get(l['sid'],{}).get('industry'),
            category=kind,role_kind=l['kind'],signal_at=l['signal_at'],opened=l['opened'],closed=l['closed'],initial_qty=l['initial_qty'],
            entry_cash=D(t['gross_cny'])+D(t['fees_cny']),lifecycle_net=D(l['cash'])+D(l['dividend']),native_cash=l['cash'],recognized_dividend=l['dividend'],
            first_exit_decision=first,actual_sell_records=sales,final_reason=l['reason'],
            entry_trade=t,final_qty=l['qty'],classification_crosschecked_prior_CLOSE=held==prev_held and not sell_today))
    save('ALL_POSTPEAK_NEW_LAYERS.json',post)
    cats=[]
    for cat in ['existing_stock_add','flat_reentry','account_first_entry']:
        ls=[r for r in post if r['category']==cat]
        cats.append(dict(category=cat,layers=len(ls),stocks=len({r['sid']for r in ls}),buy_cash=sum((r['entry_cash']for r in ls),D(0)),
            lifecycle_net=sum((r['lifecycle_net']for r in ls),D(0)),positive_layers=sum(r['lifecycle_net']>0 for r in ls),negative_layers=sum(r['lifecycle_net']<0 for r in ls),
            positive_net=sum((r['lifecycle_net']for r in ls if r['lifecycle_net']>0),D(0)),negative_net=sum((r['lifecycle_net']for r in ls if r['lifecycle_net']<0),D(0)),role_kinds=dict(Counter(r['role_kind']for r in ls))))
    save('POSTPEAK_NEW_LAYER_SUMMARY.json',dict(layers=len(post),stocks=len({r['sid']for r in post}),lifecycle_net=sum((r['lifecycle_net']for r in post),D(0)),
        categories=cats,same_sid_buy_and_sell_same_OPEN=same_sid_buy_sell,
        category_definition='Existing stock if earlier layer remains live immediately before this OPEN buy; flat reentry if prior same-stock layer existed but no live holding; otherwise first account entry. Crosschecked prior CLOSE positions where no same-day sell. Mobile kind=add does not imply an actual existing-stock add.',
        finance_scope='Post-peak layer creation has zero wealth at Oct8 CLOSE and all303 are flat at yearend, so lifetime cash+recognized dividend is actual phase contribution. This is not an avoidable-loss or counterfactual claim.'))
    save('BALANCED_LARGE_POSTPEAK_CHAINS.json',dict(
        worst=sorted(post,key=lambda r:r['lifecycle_net'])[:15],best=sorted(post,key=lambda r:r['lifecycle_net'],reverse=True)[:8],
        selection='Largest actual closed layer losses and gains under one fixed post-Oct8 creation cohort. Evaluation only, not signal selection.'))

    events=[]
    for layer,a in exit_events.items():
        l=layers[layer]
        if not('2024-09-23'<=l['opened'][:10]<='2024-12-31'or any('2024-10-08'<=v['at'][:10]<='2024-12-31'for v in a)):continue
        first=a[0];sales=[t for t in b['trades']if t['side']=='sell'and any(v['layer']==layer for v in t['parts'])]
        events.append(dict(layer=layer,sid=l['sid'],name=meta.get(l['sid'],{}).get('name'),opened=l['opened'],first_exit_proposal=first,
            first_actual_sell_at=sales[0]['at']if sales else None,last_actual_sell_at=sales[-1]['at']if sales else None,
            actual_sells=sales,closed=l['closed'],final_reason=l['reason']))
    save('EXIT_PROPOSAL_TO_ACTUAL_SELL.json',events)
    save('SELECTED_ACT_RISK_CHECKPOINTS.json',[r for r in b['audit']if r['kind']=='risk_checkpoint'and r['at'][:10]in ['2024-09-23','2024-09-24','2024-10-08','2024-10-09','2024-10-10','2024-12-20','2024-12-23','2024-12-24','2024-12-31']])
    save('SOURCE_SHA256.json',SOURCES)
    save('SCOPE.json',dict(passed=True,seconds=time.monotonic()-start,Account=0,Runner=0,Market=0,RiskBook=0,new_marks=0,new_strategy_runs=0,
        data='Completed original No60 long_OFF only; no ON candidate',time='CLOSE sizing records and OPEN funding kept separate',
        financial_boundary='Layer lifecycle contribution is actual cash plus recognized dividend; no holding counterfactual or assumed avoidable loss. Price-limit causality is assessed separately from source raw bars.'))
    print('SAVED_RULES_COMPLETE',len(post),time.monotonic()-start)

if __name__=='__main__':main()
