"""Conditional raw-share transfer to cached HKD-cash-only stock samples."""
import hashlib
import json
import re
from pathlib import Path
from campaign_engine import run_campaign
from hk_stock_account_pilot import load
from portfolio_data import total_return_frame
from trend_tail_audit import summarize

ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/hk-cash-stock-campaign'
SYMBOLS={'00002':'utilities','00101':'property','00883':'energy','03690':'consumer_platform'}


def load_assets(increment=100):
    assets={};audit=[]
    for code,sector in SYMBOLS.items():
        if code=='00700':raise ValueError('Known in-kind distributions require recipient-share ledger')
        source=ROOT/f'data/hk-stock-raw/hk{code}.json';data=json.loads(source.read_text())
        for row in data['rows']:
            for e in row[6:]:
                if not isinstance(e,dict):continue
                if e.get('hgcgContent') or e.get('ggContent'):raise ValueError('Unmodeled share action')
                if e.get('HGcontent') and not re.fullmatch(r'回购[0-9.]+万股，均价[0-9.]+港元',e['HGcontent']):raise ValueError('Unknown non-cash annotation')
        raw,events=load(code);raw=raw.loc['2020-01-01':]
        if any(e['currency']!='HKD' for e in events):raise ValueError('Foreign currency dividend needs separate settlement ledger')
        div=[dict(ex_date=str(e['ex'].date()),pay_date=str(e['pay'].date()),amount=e['amount']) for e in events if e['ex'] in raw.index]
        assets['HK'+code]=dict(raw=raw,signal=total_return_frame(raw,div,[]),dividends=div,splits=[],lot=increment,currency='HKD',kind='equity',sector=sector,volume_multiplier=1)
        audit.append(dict(symbol=code,rows=len(raw),first=str(raw.index[0].date()),last=str(raw.index[-1].date()),cash_events=len(div),research_order_increment=increment,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),limitations='Vendor share-action completeness and dated exchange lots not issuer-certified. Repurchase annotations do not change this holder share count. No annotation is not independent proof of no action.'))
    return assets,audit


def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(symbols=SYMBOLS,exclusions={'00005':'USD dividends;issuer settlement data exists but not yet ported into campaign ledger','09618':'USD dividends require currency/payment ledger','00700':'In-kind JD/Meituan distributions not yet in campaign ledger'},
        selection='All four existing stocks with HKD-only cash annotations,not selected by returns. Deliberate accounting gate;not representative universe or survival-bias correction.',
        rule='Frozen55daybreakout,noadds,4ATRinitialstop and2closesbelowMA200 exit,0.5%entryrisk,4%aggregate;fullsymbolcapacity;allothercaps/guards unchanged.',
        scenarios='Individualstocks andcombined4stocks;base,doublecost,delay1,1000shareincrementstress. Default100shares is research increment,not certified historical board lot.',
        execution='CNY1m funded account,HKDshares,laggedFX,HKexposurecap50%,nextopen and1%laggedADV.15bps+10bpsFXbase;30+20stress,18HKDmin. Dated taxes/fees/queue not modeled.',
        status='Conditional accounting/mechanism pilot;not investable A/HK validation',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    file=OUT/'protocol.json'
    if file.exists():assert json.loads(file.read_text())==protocol
    file.write_text(json.dumps(protocol,indent=2));assets,audit=load_assets();(OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
    groups={n:[n] for n in assets};groups['combined']=list(assets);records=[]
    for group,names in groups.items():
        for scenario in ['base','cost2','delay1','increment1000']:
            case=group+'-'+scenario;chosen={n:dict(assets[n],lot=1000 if scenario=='increment1000' else 100) for n in names}
            m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,extra_delay=1 if scenario=='delay1' else 0)
            a=summarize(c);m.update(case=case,group=group,scenario=scenario,ordinary_pnl=a.get('ordinary_pnl'),tail_pnl=a.get('top10_pnl'))
            records.append(m);p.to_csv(OUT/(case+'-path.csv'));(OUT/(case+'-orders.json')).write_text(json.dumps(o));(OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)));(OUT/'results.json').write_text(json.dumps(records,indent=2));print(case,{k:m[k] for k in ['total_return','max_drawdown','closed_campaigns','open_campaigns']},flush=True)


if __name__=='__main__':main()
