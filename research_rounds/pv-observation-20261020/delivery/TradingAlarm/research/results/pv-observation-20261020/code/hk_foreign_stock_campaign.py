"""Extend fixed stock campaign rules with causal USD dividend receivables."""
import hashlib
import json
import re
from collections import defaultdict
import pandas as pd
from hk_cash_stock_campaign import ROOT,load_assets as cash_assets
from hk_stock_account_pilot import load
from campaign_engine import run_campaign,dividend_local_value
from portfolio_data import total_return_frame

OUT=ROOT/'results/hk-foreign-stock-campaign'


def load_assets():
    assets,audit=cash_assets()
    source=json.loads((ROOT/'data/hk-stock-pilot/usd-hkd.json').read_text());assert source['base']=='USD'
    rates=pd.Series({pd.Timestamp(d)+pd.Timedelta(days=1):v['HKD'] for d,v in source['rates'].items()}).sort_index()
    records=json.loads((ROOT/'results/hk-hsbc-dividend-audit/issuer-records.json').read_text())['records']
    for code,sector,lot in [('00005','banks',400),('09618','consumer_platform',100)]:
        path=ROOT/f'data/hk-stock-raw/hk{code}.json';blob=json.loads(path.read_text())
        for row in blob['rows']:
            for e in row[6:]:
                if not isinstance(e,dict):continue
                if e.get('hgcgContent') or e.get('ggContent'):raise ValueError('Unmodeled share action')
                if e.get('HGcontent') and not re.fullmatch(r'回购[0-9.]+万?股，均价[0-9.]+(?:港元)?',e['HGcontent']):raise ValueError('Unreviewed buyback annotation')
        raw,events=load(code);raw=raw.loc['2020-01-01':]
        div=[dict(ex_date=str(e['ex'].date()),pay_date=str(e['pay'].date()),amount=e['amount'],currency=e['currency']) for e in events if e['ex'] in raw.index]
        matched=0
        if code=='00005':
            bydate=defaultdict(list)
            for e in div:bydate[e['ex_date']].append(e)
            assert {e['ex_date'] for e in div if e['ex_date']>='2022-03-07'}=={x['ex'] for x in records}
            for rec in records:
                es=bydate[rec['ex']];assert all(e['currency']=='USD' and e['pay_date']==rec['pay'] for e in es)
                assert abs(sum(e['amount'] for e in es)-float(rec['usd']))<1e-10
                div=[e for e in div if e['ex_date']!=rec['ex']]
                div.append(dict(ex_date=rec['ex'],pay_date=rec['pay'],amount=float(rec['usd']),currency='USD',settlement=dict(fixing=rec['fixing'],hkd_per_share=float(rec['hkd']))));matched+=1
        a=dict(raw=raw,dividends=div,splits=[],lot=lot,currency='HKD',kind='equity',sector=sector,volume_multiplier=1,dividend_fx=rates)
        signal_div=[dict(ex_date=e['ex_date'],amount=dividend_local_value(a,e,e['ex_date'])) for e in div]
        a['signal']=total_return_frame(raw,signal_div,[]);assets['HK'+code]=a
        audit.append(dict(symbol=code,rows=len(raw),cash_events=len(div),issuer_settlements_matched=matched,order_increment=lot,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),limitations='HSBC400share increment supported by prior issuer evidence,not full dated lot certification;JD100 researchincrement. Fullhistoricaltax/fee/actioncompleteness not certified.'))
    return assets,audit


def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(rule='Frozen55breakout/noadd/4ATRstop/MA200exit;0.5%entry4%aggregate,fullcapacity,unchangedcaps/guards.',
        groups='HSBC,JD,combinedsixcashdividendstocks;Tencentstillgatedforin-kindshares',
        scenarios='base,doublecost,delay1,largeorderincrement;all12cases. HSBC400shares inallcases,others100base/1000largeincrement.',
        accounting='USD marked at laggedUSDHKD until strictlyafterissuerfixing;fixedHKD then used whenavailable;cash onlyonpayday. JD referenceFXconversion costs10bps plus usual HKDtoCNY charge;no futurefixedrates in signals.',
        limits='Reused surviving stocks. USDpay-currencychoice andbrokercharges simplified. NohistoricalPITstockpool or exchangeorderbook.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    f=OUT/'protocol.json'
    if f.exists():assert json.loads(f.read_text())==protocol
    f.write_text(json.dumps(protocol,indent=2));assets,audit=load_assets();(OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
    old,_=cash_assets();_,p,o,c,s=run_campaign(old,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(old))
    ref=ROOT/'results/hk-cash-stock-campaign';pd.testing.assert_frame_equal(p,pd.read_csv(ref/'combined-base-path.csv',index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-12)
    assert o==json.loads((ref/'combined-base-orders.json').read_text());assert dict(closed=c,open=s)==json.loads((ref/'combined-base-campaigns.json').read_text())
    print('HKD-only frozen control reproduced.',flush=True);rows=[]
    for group,names in {'HSBC':['HK00005'],'JD':['HK09618'],'combined':list(assets)}.items():
        for scenario in ['base','cost2','delay1','large_increment']:
            case=group+'-'+scenario;chosen={n:dict(assets[n],lot=400 if n=='HK00005' else 1000 if scenario=='large_increment' else 100) for n in names}
            m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,extra_delay=1 if scenario=='delay1' else 0)
            m.update(case=case);rows.append(m);p.to_csv(OUT/(case+'-path.csv'));(OUT/(case+'-orders.json')).write_text(json.dumps(o));(OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)));(OUT/'results.json').write_text(json.dumps(rows,indent=2));print(case,m['total_return'],m['max_drawdown'],flush=True)


if __name__=='__main__':main()
