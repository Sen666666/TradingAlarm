"""Existing F1 event attribution only; no native account/model/selector imports."""
from pathlib import Path
from decimal import Decimal as D
from datetime import date
from collections import defaultdict
import hashlib,json,csv,math
import pandas as pd

O=Path(__file__).resolve().parent;W=O.parent
B=W/'g-s-B-joint-target-v2-20261102';C=W/'g-s-C-industry-first-projection-v1-20261102'
F=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101/industry-evidence-ranking-readonly-v1')
SRC={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p):
    p=Path(p);h=sha(p)
    if str(p) in SRC:assert SRC[str(p)]==h
    SRC[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,list):return [clean(v) for v in x]
    if isinstance(x,D):return str(x)
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def save(n,x):
    p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def csvsave(n,rows):
    p=O/n;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))
def dayof(n):return date.fromordinal(n).isoformat() if n is not None else None
def evout(e):
    if not e:return None
    return dict(e,confirmed_date=dayof(e['confirmed']),known_date=dayof(e['known']))

def scope_facts(p,sec,day):
    s=p['scopes'][sec];ordinal=date.fromisoformat(day).toordinal()
    history=[e for e in p['proof_history'] if e['scope']==sec and e['source']==s['source'] and e['known']<=ordinal and e['confirmed']<=ordinal]
    ctx=sorted([e for e in history if e['context']==s['context'] and e['kind']=='price_advance'],key=lambda e:(e['confirmed'],e['seq'],e['event_id'])) if s['context'] else []
    old=sorted([e for e in history if e['kind']=='price_advance'],key=lambda e:(e['confirmed'],e['seq'],e['event_id']))
    today=[e for e in ctx if e['confirmed']==ordinal]
    return dict(source=s['source'],current_context=s['context'],support=s['support'],permit=s['permit'],mature=s['mature'],
        has_current_context_advance_today=bool(today),today_current_context_advances=[evout(e) for e in today],
        today_native_events_all_contexts=[evout(e) for e in history if e['confirmed']==ordinal],
        first_current_context_advance=evout(ctx[0]) if ctx else None,last_current_context_advance=evout(ctx[-1]) if ctx else None,
        current_context_advance_count=len(ctx),last_historical_advance=evout(old[-1]) if old else None,
        migration_event_used_or_unused='UNKNOWN_original_policy_has_no_migration_consumption_ledger')

def main():
    names=pd.read_parquet(bind(F/'LOCAL2026-RANKS_AND_OPPORTUNITIES.parquet'),columns=['sector','industry']).drop_duplicates().set_index('sector')['industry'].to_dict()
    receiving=[];selling=[];groups=[];all_facts={};controls={};summary={}
    for k,day in [('2022','2022-01-06'),('2025_26','2025-07-03')]:
        actual=read(W/'g-s-historical-native-nextsession-20261101/run'/k/'close'/(day+'-CLOSE.json'))
        p=actual['account']['policy'];x=read(B/'inputs'/(k+'.json'));ds={d['sid']:d for d in x['B_demands']};comp={r['sid']:r for r in x['evidence']['full_union']}
        facts={s:scope_facts(p,s,day) for s in p['scopes']};all_facts[k]=facts
        now=date.fromisoformat(day).toordinal();controls[k]=[dict(evout(e),industry=names.get(e['scope'],'global')) for e in p['proof_history'] if e['confirmed']==now and e['known']<=now]
        summary[k]={}
        for policy,root in [('B',B),('C',C)]:
            r=read(root/'results'/k/(policy+'.json'));beforeD={};increments={}
            marks={z['sid']:D(z['mark']) for z in x['snapshot']['lots']}
            for step in r['trace']:
                current=step.get('D',beforeD);inc={s:q-beforeD.get(s,0) for s,q in current.items() if q>beforeD.get(s,0)}
                dec={s:q-current.get(s,0) for s,q in beforeD.items() if q>current.get(s,0)}
                if step['q']:increments[step['sid']]=dict(positive_D_mark=sum((D(q)*marks[s] for s,q in inc.items()),D(0)),restored_D_mark=sum((D(q)*marks[s] for s,q in dec.items()),D(0)),positive_D=inc,restored_D=dec)
                beforeD=dict(current)
            group=defaultdict(lambda:dict(names=[],qty=0,new_mark_capital=D(0)))
            for sid,q in r['Q'].items():
                if not q:continue
                d=ds[sid];sec=d['sector'];sf=facts[sec];a=group[sec];a['names'].append(comp[sid]['name']);a['qty']+=q;a['new_mark_capital']+=D(q)*D(d['mark'])
                row=dict(window=k,day=day,policy=policy,sid=sid,name=comp[sid]['name'],sector=sec,industry=names[sec],use=d['use'],
                    quantity=q,new_mark_capital=D(q)*D(d['mark']),mark=d['mark'],canonical_receipt_id=d['receipt_id'],
                    stock_fresh_CP1=True,has_new_industry_price_advance=sf['has_current_context_advance_today'],
                    classification='ADVANCE_ACCOMPANIED' if sf['has_current_context_advance_today'] else 'NO_NEW_INDUSTRY_ADVANCE_FRESH_STOCK_PRIORITY_TARGET',
                    first_context_advance=sf['first_current_context_advance']['confirmed_date'] if sf['first_current_context_advance'] else None,
                    last_context_advance=sf['last_current_context_advance']['confirmed_date'] if sf['last_current_context_advance'] else None,
                    context=sf['current_context'],source=sf['source'],permit=sf['permit'],mature=sf['mature'],support=sf['support'],
                    migration_token_state='UNKNOWN',**increments[sid])
                receiving.append(row)
            for sec,a in group.items():groups.append(dict(window=k,day=day,policy=policy,sector=sec,industry=names[sec],**a,**facts[sec]))
            dg=defaultdict(lambda:dict(names=[],layers=[],sold_mark=D(0),saved_net_sell=D(0),saved_projected_risk_release=D(0),all_stored_retention_legal=True))
            for part in r['donors']['rows']:
                z=next(z for z in x['snapshot']['lots'] if z['id']==part['layer']);a=dg[z['sector']]
                a['names'].append(comp[z['sid']]['name']);a['layers'].append(dict(sid=z['sid'],layer=z['id'],q=part['q'],role=z['role'],pool=z['pool'],purpose=z['purpose'],mark=z['mark'],floor=z['floor'],retention_legal=z.get('retention_legal'),holding_S=z['holding_S']))
                a['sold_mark']+=D(part['capital']);a['saved_net_sell']+=D(part['net']);a['saved_projected_risk_release']+=D(part['risk_release']);a['all_stored_retention_legal']&=bool(z['retention_legal'])
            for sec,a in dg.items():selling.append(dict(window=k,day=day,policy=policy,sector=sec,industry=names[sec],**a,**facts[sec],allocation_not_independent_protective_failure=True,global_scope=facts['G']))
            summary[k][policy]=dict(positive_requests=sum(bool(q) for q in r['Q'].values()),receiving_industries=len(group),
                same_day_advance_receiving_industries=sum(facts[s]['has_current_context_advance_today'] for s in group),
                new_mark_capital=sum((a['new_mark_capital'] for a in group.values()),D(0)),
                with_same_day_advance_mark_capital=sum((a['new_mark_capital'] for s,a in group.items() if facts[s]['has_current_context_advance_today']),D(0)),
                donor_industries=len(dg),same_day_advance_donor_industries=sum(facts[s]['has_current_context_advance_today'] for s in dg),
                donor_mark_capital=sum((a['sold_mark'] for a in dg.values()),D(0)),
                saved_net_sell=sum((a['saved_net_sell'] for a in dg.values()),D(0)),unimplemented_event_gate=True)
    save('RECEIVING_DEMANDS.json',receiving)
    csvsave('RECEIVING_DEMANDS.csv',[{k:(json.dumps(clean(v),ensure_ascii=False) if isinstance(v,dict) else v) for k,v in r.items()} for r in receiving])
    save('RECEIVING_INDUSTRIES.json',groups);save('DONOR_INDUSTRIES.json',selling);save('NATIVE_CONTEXT_FACTS.json',all_facts);save('OTHER_TODAY_EVENT_CONTROLS.json',controls)
    # Select only as-of columns; never load price outcome label columns.
    cols=['day','sector','industry','F1_mode','F1_permit','F1_support','F1_mature','context_started','context_first_advance','last_current_context_native_advance','context_advance_count','events','canonical_CP1_Q','industry_H1_score']
    daily=pd.read_parquet(bind(F/'LOCAL2026-FULL_TABLE_WITH_HISTORY.parquet'),columns=cols)
    daily=daily[daily['day'].astype(str).str[:10]=='2026-05-07'];assert len(daily)==90
    lists=read(C/'market-2026/2026-05-07-STOCK_ORDER.json');market=[]
    for rec in daily.to_dict('records'):
        items=[v for v in lists if v['sector']==rec['sector']]
        # Retain all sectors with permit, new advance or actual frozen-list opportunities.
        events=list(rec['events']);advance='price_advance' in events
        if not (rec['F1_permit'] or advance or items):continue
        market.append(dict(day='2026-05-07',sector=rec['sector'],industry=rec['industry'],market_context_started=rec['context_started'],
            context_first_advance=rec['context_first_advance'],last_current_context_advance=rec['last_current_context_native_advance'],
            current_context_advance_count=int(rec['context_advance_count']),events=events,price_advance_today=advance,
            permit=bool(rec['F1_permit']),support=bool(rec['F1_support']),mature=bool(rec['F1_mature']),
            canonical_CP1_Q=int(rec['canonical_CP1_Q']),frozen_expansion_list_count=len(items),names=[v['name'] for v in items],
            GS_account_or_migration_consumption_state='UNKNOWN',same_day_label='ADVANCE_ACCOMPANIED' if advance else 'NO_NEW_ADVANCE',
            native_GS_policy_context_id='UNKNOWN_no_GS_account_for_this_date'))
    save('MAY7_MARKET_DIRECTIONS.json',market);save('SUMMARY.json',summary)
    save('SOURCE_SHA256.json',SRC)
    print(json.dumps(clean(dict(summary=summary,receiving_rows=len(receiving),market=[{k:v for k,v in a.items() if k in ('industry','price_advance_today','context_first_advance','last_current_context_advance','frozen_expansion_list_count')} for a in market])),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
