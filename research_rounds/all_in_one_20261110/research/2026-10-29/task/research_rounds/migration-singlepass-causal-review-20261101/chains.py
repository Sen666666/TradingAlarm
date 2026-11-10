"""Existing opportunity/order/fill chains and conditional-permission labels only."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,collections,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent
ROOTS={'SC':W/'q2-normal-continuation-20261031/runs/B_diag/pair','SD':W/'migration-admission-singlepass-economics-20261101/runs/2025_26/pair'}
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def save(n,x):
    p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
META=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};FF={};ST={}
def price_state(sid,d):
    if sid not in FF:
        p=Path(SM[sid]['refs']['facts']);assert hashlib.sha256(p.read_bytes()).hexdigest()==SM[sid]['output_sha256'][str(p)]
        FF[sid]=pd.read_parquet(p,columns=['raw_close','close','factor','i_target'])
    f=FF[sid];ix=f.index.searchsorted(pd.Timestamp(d),side='right')-1;assert ix>=0
    r=f.iloc[ix];return dict(source_day=str(r.name.date()),raw_close=float(r.raw_close),factor=float(r.factor),original_adjusted_close=float(r['close']),I_valid=bool(r.i_target))
def stage(sid,d):
    sector=META[sid]['sector_id']
    if sector not in ST:
        r=next(x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json') if x['series']==sector)
        p=Path(r['refs']['state']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['output_sha256'][str(p)]
        q=pd.read_parquet(p);ST[sector]={x['day']:x for x in q.to_dict('records')}
    r=ST[sector][d];return dict(stage=r['stage_name'],attempt=r['attempt_id'],E0_valid=r['E0_valid'])

def main():
    ids={'601869.SH','301511.SZ','301489.SZ','688585.SH','603268.SH'}
    data={}
    for ref,p in ROOTS.items():
        b=obj(p/'B.json.gz');ds=rows(p/'daily.jsonl.gz');dates=[x['at'][:10] for x in ds]
        opp={(x['sid'],x['day']):x for x in rows(p/'opportunities.jsonl.gz') if x['sid'] in ids}
        funding=rows(p/'funding.jsonl.gz');decisions={x['at'][:10]:x for x in b['decisions']}
        data[ref]=dict(book=b,daily=ds,dates=dates,opps=opp,funding=funding,decisions=decisions)
    chains={}
    for sid in sorted(ids):
        result={}
        for ref,a in data.items():
            b=a['book'];es=[];fills=[x for x in b['journal'] if x['kind']=='real_buy_fill' and x['sid']==sid]
            for k,d in enumerate(a['dates']):
                x=a['opps'].get((sid,d));assert x is not None
                if not x['roles'] and not x['CP1_id']:continue
                nextday=a['dates'][k+1] if k+1<len(a['dates']) else None
                intents=[i for i in a['decisions'][d]['intents'] if i['sid']==sid]
                ff=[r for r in a['funding'] if r['sid']==sid and ((r['at'][:10]==nextday and '09:30:00' in r['at']) or(r['at'][:10]==d and '15:10:00' in r['at']))]
                actual=[j for j in fills if j['signal_at'][:10]==d]
                key=(tuple(x['roles']),tuple(x['barriers']),tuple((r.get('role'),r['result'],r.get('pool')) for r in ff))
                es.append(dict(signal_day=d,next_open_day=nextday,core_Q=x['core_Q'],mobile_Q=x['mobile_Q'],canonical_CP1=x['CP1_id'],
                    current_price_state=price_state(sid,d),industry=stage(sid,d),ACT_on=a['daily'][k]['on'],
                    roles=x['roles'],barriers=x['barriers'],held_previous_close=x['held'],rank=x['rank'],funding=ff,
                    actual_fill=[dict(at=j['at'],shares=j['shares'],role=j['role'],pool=j['pool'],attempt=j['attempt'],layer=j['layer']) for j in actual],
                    frozen_targets=[{k:i[k] for k in ['role','budget','cap','floor','risk_budget','CP1_id'] if k in i} for i in intents],_key=str(key)))
            # Consecutive observed signal records with the same outcome form an episode;
            # keep every distinct canonical receipt inside it rather than treating as one.
            episodes=[]
            for e in es:
                if episodes and episodes[-1]['key']==e['_key'] and a['dates'].index(e['signal_day'])==a['dates'].index(episodes[-1]['last_day'])+1:
                    g=episodes[-1];g['last_day']=e['signal_day'];g['observations']+=1;g['rows'].append(e)
                else:episodes.append(dict(first_day=e['signal_day'],last_day=e['signal_day'],observations=1,key=e['_key'],rows=[e]))
            layers=[]
            for x in b['layers']:
                if x['sid']!=sid:continue
                j=next(t for t in fills if t['layer']==x['id']);layers.append(dict(**x,role=j['role'],pool_at_fill=j['pool'],attempt=j['attempt'],receipt=j['CP1_id']))
            result[ref]=dict(episodes=episodes,actual_layers=layers,trades=[x for x in b['trades'] if x['security_id']==sid],
                distinct_mobile_receipts_Qtrue=len({e['canonical_CP1'] for e in es if e['canonical_CP1'] and e['mobile_Q'] is True}),
                actual_buy_reservations=[x for x in b['journal'] if x['kind']=='real_reserve' and x['sid']==sid],
                actual_buy_fill_layers=len(layers))
        chains[sid]=dict(name=META[sid]['name'],**result)
        for d in data['SC']['dates']:
            for field in ('core_Q','mobile_Q','CP1_id','rank','sector'):
                assert data['SC']['opps'][sid,d][field]==data['SD']['opps'][sid,d][field],(sid,d,'external source differs',field)
    save('CHAINS.json',chains)
    # Classify the 33 local SD permission uses against ACTUAL SC behavior. No
    # attempt is made to pretend SC had the same state at those later points.
    used=read(W/'migration-admission-singlepass-economics-20261101/analysis/2025_26/NEW_PERMISSION.json')['reservations']
    sc=data['SC'];b=sc['book'];classified=[]
    for r in used:
        sid=r['sid'];d=r['signal_day'];receipt=r['receipt'];at=r['at']
        same=[j for j in b['journal'] if j['kind']=='real_reserve' and j['sid']==sid and j['at']==at]
        mobile=[j for j in same if j['role']=='mobile' and j['receipt']==receipt]
        if mobile:kind='SC_same_receipt_confirmed_too' if mobile[0]['pool']=='confirmed' else 'SC_same_receipt_probe'
        elif any(j['role']=='core' for j in same):kind='SC_core_reserved_suppressed_mobile'
        else:kind='SC_no_same_open_reservation'
        outcomes=[x for x in sc['funding'] if x['sid']==sid and x['at']==at]
        classified.append(dict(**r,SC_observed_class=kind,SC_actual_reservations=same,SC_funding=outcomes,
            direct_effect_claim='locally bypasses failed migration in SD own state; not necessarily a SC incremental opportunity'))
    save('THIRTY_THREE_CLASSIFICATION.json',dict(unit='SD locally gate-dependent canonical receipt reservation',count=len(classified),
        SC_observed_classes=dict(collections.Counter(x['SC_observed_class'] for x in classified)),
        only_global_first_divergence_has_common_state_identification='2025-07-02 603268.SH, SC probe200 vs SD confirmed400',
        reservations=classified))
    save('CHAIN_SUMMARY.json',{sid:dict(name=x['name'],SC_receipts=x['SC']['distinct_mobile_receipts_Qtrue'],SD_receipts=x['SD']['distinct_mobile_receipts_Qtrue'],
        SC_filled_layers=x['SC']['actual_buy_fill_layers'],SD_filled_layers=x['SD']['actual_buy_fill_layers'],
        SC_episodes=len(x['SC']['episodes']),SD_episodes=len(x['SD']['episodes'])) for sid,x in chains.items()})
    print('CHAIN_SUMMARY',read(O/'CHAIN_SUMMARY.json'));print('LOCAL33',dict(collections.Counter(x['SC_observed_class'] for x in classified)),flush=True)

if __name__=='__main__':main()
