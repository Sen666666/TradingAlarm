"""Fixed-budget completion on raw-share ETF/HK accounts, with frozen controls."""
import hashlib
import json
import math
import pandas as pd
from campaign_engine import run_campaign,features
from campaign_claims import CampaignClaims
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from trend_tail_audit import summarize
from build_stock_features import ROOT


def verify_budget(assets,path,orders,decisions):
    fs={n:features(a) for n,a in assets.items()}
    sizing={(r['date'],r['symbol']):r for r in decisions if r['event']=='sizing'}
    budgets={};spent={};stops={};last={};fills=[]
    for o in orders:
        if o['units']<=0:continue
        n=o['symbol'];cid=o['campaign_id'];date=pd.Timestamp(o['date']);a=assets[n];f=fs[n].loc[date]
        d=sizing[o['date'],n]
        assert o['units']==d['units'] and o['units']%a['lot']==0
        assert o['units']<=d['adv_units'] and o['units']<=d['cash_units'] and o['units']<=d['exposure_units']
        assert d['planned_risk_before']+d['planned_risk_added']<=d['planned_risk_limit']+1e-6
        adjusted=o['raw_open']*f.factor+f.cash_adjustment
        assert abs(adjusted-o['adjusted_open'])<1e-8
        if o['type']=='entry':
            q=fs[n].loc[:pd.Timestamp(o['signal_date'])].iloc[-1]
            stops[cid]=adjusted-4*q.atr;spent[cid]=0.
            distance=4*q.atr/f.factor*o['fx']
            prev=path.loc[path.index<date]
            nav=1e6 if prev.empty else float(prev.nav.iloc[-1]*1e6)
            target=math.floor(nav*.005*(.5 if d['drawdown']<=-.10 else 1.)/distance/a['lot'])*a['lot']
            assert target==d['target_units']
            budgets[cid]=target*distance
        else:
            assert o['type']=='complete' and cid in budgets
            assert adjusted>=last[cid] and d['drawdown']>-.10
            assert fs[n].loc[:pd.Timestamp(o['signal_date'])].iloc[-1].close>fs[n].loc[:pd.Timestamp(o['signal_date'])].iloc[-1].upper
        assert abs(o['stop']-stops[cid])<1e-8
        spent[cid]+=o['units']*(adjusted-stops[cid])/f.factor*o['fx']
        assert abs(spent[cid]-o['committed_risk'])<1e-6 and spent[cid]<=budgets[cid]+1e-6
        assert abs(o['completion_budget']-budgets[cid])<1e-6
        last[cid]=adjusted
        fills.append(dict(date=o['date'],symbol=n,type=o['type'],campaign_id=cid,
            fixed_budget=budgets[cid],committed=spent[cid],units=o['units']))
    return fills


def main():
    out=ROOT/'results/campaign-completion-transfer';out.mkdir(exist_ok=True)
    protocol=dict(rule='Same55breakout,4ATRinitialstop,2closesbelowMA200exit,lowATRpriority. Complete partialinitialallocation withinfirst roundedlot targetCNYriskbudget;neverresetstop orraisebudget. Perbuycommittedrisk usesfillFX andsplitfactor. Existingopenriskmaydriftwithprices/FX;4percentportfolioriskcap stilllimitsnewbuys.',
        gates='Continuedbreakout,adjustedfill>=lastfill,no pendingexit/drawdown>=10percent;cash,lots,minfees,1percentprior20dayADV,gross90/single35/sector45/HK50 caps unchanged.',
        cases='ETF17 andHK7 xbase,doublecost,delay1;all6controland6completionpaths. No newparameters.',
        limitations='Selectedsurvivors andETFproxies;historicalHKlots/taxes/actioncompleteness notcertified. Notfutures/property validation,notindependentholdout;stopbudgetisnotguaranteedrealizedloss.',
        engine_sha256=hashlib.sha256((ROOT/'campaign_engine.py').read_bytes()).hexdigest())
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    etf,_=load_extended();hk,_=load_assets();results=[]
    for group,assets,reference,prefix in [('etf17',etf,'campaign-asset-transfer','all'),('hk7',hk,'hk-in-kind-campaign','combined')]:
        for scenario in ('base','cost2','delay1'):
            chosen={n:dict(a,lot=400 if n=='HK00005' else 100) for n,a in assets.items()} if group=='hk7' else assets
            for completion in (False,True):
                claims=CampaignClaims(chosen,{n:assets[n] for n in ['HK09618','HK03690']}) if group=='hk7' else None
                trace=[]
                m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),
                    eligible_kinds=('equity','defensive'),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,
                    extra_delay=1 if scenario=='delay1' else 0,security_claims=claims,decision_audit=trace,complete_initial=completion)
                if not completion:
                    ref=ROOT/'results'/reference;key=f'{prefix}-{scenario}'
                    assert o==json.loads((ref/f'{key}-orders.json').read_text())
                    assert dict(closed=c,open=s)==json.loads((ref/f'{key}-campaigns.json').read_text())
                    pd.testing.assert_frame_equal(p,pd.read_csv(ref/f'{key}-path.csv',index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-9)
                    continue
                case=f'{group}-{scenario}';fills=verify_budget(chosen,p,o,trace);stats=summarize(c)
                m.update(case=case,group=group,scenario=scenario,completion_orders=sum(x['type']=='complete' for x in o),
                    closed_pnl=sum(x['pnl'] for x in c),ordinary_closed_pnl=stats.get('ordinary_pnl'),tail_closed_pnl=stats.get('top10_pnl'))
                results.append(m);p.to_csv(out/f'{case}-path.csv')
                (out/f'{case}-orders.json').write_text(json.dumps(o));(out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=c,open=s)))
                (out/f'{case}-budget-audit.json').write_text(json.dumps(fills,indent=2))
                if claims is not None:(out/f'{case}-claims.json').write_text(json.dumps(dict(events=claims.events,quantities=claims.quantities(),cash_paid=claims.cash_paid),indent=2))
                (out/'results.json').write_text(json.dumps(results,indent=2))
                print(case,{k:m[k] for k in ['total_return','max_drawdown','completion_orders','ordinary_closed_pnl']},flush=True)


if __name__=='__main__':main()
