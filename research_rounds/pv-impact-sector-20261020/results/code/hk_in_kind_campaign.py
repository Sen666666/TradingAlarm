"""Fixed trend transfer with Tencent non-tradable recipient-share subledger."""
import hashlib
import json
import pandas as pd
from hk_foreign_stock_campaign import ROOT,load_assets as cash_assets
from hk_stock_account_pilot import load,IN_KIND
from portfolio_data import total_return_frame
from campaign_engine import run_campaign
from campaign_claims import CampaignClaims

OUT=ROOT/'results/hk-in-kind-campaign'


def load_assets():
    assets,audit=cash_assets();raw,events=load('00700');raw=raw.loc['2020-01-01':]
    if any(e['currency']!='HKD' for e in events):raise ValueError('Unexpected parent currency')
    div=[dict(ex_date=str(e['ex'].date()),pay_date=str(e['pay'].date()),amount=e['amount']) for e in events if e['ex'] in raw.index]
    distributions=[]
    for date,(child,den) in IN_KIND.items():
        name='HK'+child;history=assets[name]['raw'].loc[assets[name]['raw'].index<pd.Timestamp(date)]
        if history.empty or pd.Timestamp(date) not in raw.index:raise ValueError('Missing in-kind reference')
        distributions.append(dict(ex_date=date,recipient=name,numerator=1,denominator=den,signal_reference_value=float(history.close.iloc[-1])/den,reference_date=str(history.index[-1].date())))
    # Ex adjustment known before that day's open; not a cash receipt.
    signal_events=div+[dict(ex_date=e['ex_date'],amount=e['signal_reference_value']) for e in distributions]
    assets['HK00700']=dict(raw=raw,signal=total_return_frame(raw,signal_events,[]),dividends=div,in_kind=distributions,splits=[],lot=100,currency='HKD',kind='equity',sector='consumer_platform',volume_multiplier=1)
    audit.append(dict(symbol='00700',in_kind=distributions,source_sha256=hashlib.sha256((ROOT/'data/hk-stock-raw/hk00700.json').read_bytes()).hexdigest(),limitation='Ratios/exdates reused from prior reviewed pilot. Delivery/liquidation not assumed;whole-share claims held indefinitely, fractions zero. Signals use prior recipient close,account uses current dated marks.'))
    return assets,audit


def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(rule='Frozen55breakout/noadd/4ATR/MA200exit,existingrisk/exposurecaps and guards.',
        groups='Tencent alone and seven-stock combined;base,doublecost,delay1,largeincrement;all8cases.',
        claims='Separate nontradable whole-share claims,never spendable cash or active inventory. Subsequent recipient dividends accrued/payable. Fractions valuedzero. Claims counted in gross/sector/single/HK exposure and100%ofclaimvalue in riskbudget. Halt cannot reset while claims remain.',
        signal='Knownpriorrecipientclose/ratio at exdate;no same-dayfutureclose in open sizing. Not an assumedcashdividend.',
        limits='Conditional survivingstockpilot;recipient delivery and actualsale notmodeled;historical lots/taxes/actions notfullycertified;notA-share/universal validation.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    f=OUT/'protocol.json'
    if f.exists():assert json.loads(f.read_text())==protocol
    f.write_text(json.dumps(protocol,indent=2));assets,audit=load_assets();(OUT/'data-audit.json').write_text(json.dumps(audit,indent=2))
    old,_=cash_assets();_,p,o,c,s=run_campaign(old,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(old))
    ref=ROOT/'results/hk-foreign-stock-campaign';pd.testing.assert_frame_equal(p,pd.read_csv(ref/'combined-base-path.csv',index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-12);assert o==json.loads((ref/'combined-base-orders.json').read_text());assert dict(closed=c,open=s)==json.loads((ref/'combined-base-campaigns.json').read_text())
    print('Six-stock control reproduced.',flush=True);rows=[]
    for group,names in {'Tencent':['HK00700'],'combined':list(assets)}.items():
        for scenario in ['base','cost2','delay1','large_increment']:
            case=group+'-'+scenario;chosen={n:dict(assets[n],lot=400 if n=='HK00005' else 1000 if scenario=='large_increment' else 100) for n in names}
            claims=CampaignClaims(chosen,{n:assets[n] for n in ['HK09618','HK03690']})
            m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,extra_delay=1 if scenario=='delay1' else 0,security_claims=claims)
            m.update(case=case,claim_events=len(claims.events),terminal_claim_value=float(p.security_claim_value.iloc[-1]),claim_dividend_cash=claims.cash_paid);rows.append(m)
            p.to_csv(OUT/(case+'-path.csv'));(OUT/(case+'-orders.json')).write_text(json.dumps(o));(OUT/(case+'-campaigns.json')).write_text(json.dumps(dict(closed=c,open=s)));(OUT/(case+'-claims.json')).write_text(json.dumps(dict(events=claims.events,quantities=claims.quantities()),indent=2));(OUT/'results.json').write_text(json.dumps(rows,indent=2));print(case,{k:m[k] for k in ['total_return','max_drawdown','claim_events','terminal_claim_value']},flush=True)


if __name__=='__main__':main()
