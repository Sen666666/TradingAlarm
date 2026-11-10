"""Cross-market incidence of partial entries; prospective shapes, not add fills."""
import json
import math
import pandas as pd
from campaign_engine import run_campaign,features
from campaign_claims import CampaignClaims
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from portfolio_data import fx_series
from build_stock_features import ROOT


def summarize(chosen,path,orders,closed,state,decisions):
    sizing={(x['date'],x['symbol']):x for x in decisions if x['event']=='sizing' and x['order_type']=='entry'}
    end={x['id']:pd.Timestamp(x['exit_date']) for x in closed}
    records=[]
    for order in orders:
        if order['type']!='entry':continue
        key=order['date'],order['symbol'];d=sizing[key]
        assert d['units']==order['units']
        target=d['target_units'];actual=order['units']
        assert target>=actual>0
        record=dict(symbol=order['symbol'],entry_date=order['date'],campaign_id=order['campaign_id'],
            actual_units=actual,target_units=target,fill_fraction=actual/target,
            planned_risk_filled=d['planned_risk_added'],binding_constraints=[k for k in ['adv_units','exposure_units','risk_units','cash_units'] if d[k]<=actual],
            candidate_completion_dates=[])
        if actual<target:
            a=chosen[order['symbol']];f=features(a);raw=a['raw'];entry=pd.Timestamp(order['date'])
            first=f.loc[entry];stop=float(first.open-4*f.loc[:pd.Timestamp(order['signal_date'])].iloc[-1].atr)
            first_open=float(first.open)
            risk_per_unit=d['planned_risk_added']/actual
            remaining=(target-actual)*risk_per_unit
            fx=fx_series(raw.index);q=f.shift(1)
            adv=raw.volume.rolling(20).mean().shift(1)*a.get('volume_multiplier',1)
            eligible=raw.index[(raw.index>entry)&(raw.index<end.get(order['campaign_id'],path.index[-1]+pd.Timedelta(days=1)))]
            pending=False
            for date in eligible:
                prior=q.loc[date];row=f.loc[date]
                pending=pending or bool(prior.close<stop or prior.trend_exit)
                if pending or not(prior.close>prior.upper) or row.open<first_open or raw.loc[date,'volume']<=0:continue
                previous_path=path.loc[path.index<date]
                if previous_path.empty or previous_path.drawdown.iloc[-1]<=-.10:continue
                rate=float(fx.loc[date]) if a['currency']=='HKD' else 1.
                distance=(row.open-stop)/row.factor*rate
                if distance<=0 or remaining+1e-9<a['lot']*distance:continue
                if not pd.notna(adv.loc[date]) or math.floor(adv.loc[date]*.01/a['lot'])*a['lot']<a['lot']:continue
                record['candidate_completion_dates'].append(str(date.date()))
        records.append(record)
    partial=[r for r in records if r['fill_fraction']<1]
    return dict(entries=len(records),partial_entries=len(partial),partial_entries_with_later_price_volume_shape=sum(bool(r['candidate_completion_dates']) for r in partial),
        partial_with_no_later_shape=sum(not r['candidate_completion_dates'] for r in partial),
        limitation='Rounded original target units define budget here. Later dates only meet unchanged breakout/price/lot/ADV/drawdown shape on frozen no-add paths;cash/portfolio/sector/HK/claim risk room NOT re-simulated. Not feasible fill count or strategy profit. Globaldrawdown screen is valid here onlybecause reference paths neverreach16percenthalt.',records=records)


def main():
    out=ROOT/'results/campaign-partial-entry-audit';out.mkdir(exist_ok=True)
    etf,_=load_extended();hk,_=load_assets();summaries=[]
    for group,assets,reference,prefix in [('etf17',etf,'campaign-asset-transfer','all'),('hk7',hk,'hk-in-kind-campaign','combined')]:
        for scenario in ('base','cost2'):
            # Preserve exact lots from the prior HK combined run.
            chosen={n:dict(a,lot=400 if n=='HK00005' else 100) for n,a in assets.items()} if group=='hk7' else assets
            claims=CampaignClaims(chosen,{n:assets[n] for n in ['HK09618','HK03690']}) if group=='hk7' else None
            trace=[]
            m,p,o,c,s=run_campaign(chosen,entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),
                eligible_kinds=('equity','defensive'),cost_bps=30 if scenario=='cost2' else 15,fx_bps=20 if scenario=='cost2' else 10,
                security_claims=claims,decision_audit=trace)
            ref=ROOT/'results'/reference;key=f'{prefix}-{scenario}'
            assert o==json.loads((ref/f'{key}-orders.json').read_text())
            assert dict(closed=c,open=s)==json.loads((ref/f'{key}-campaigns.json').read_text())
            pd.testing.assert_frame_equal(p,pd.read_csv(ref/f'{key}-path.csv',index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-9)
            assert p.drawdown.min()>-.16,'Riskepoch reset requires replayed halt state for diagnostic'
            result=summarize(chosen,p,o,c,s,trace);result.update(group=group,scenario=scenario)
            (out/f'{group}-{scenario}.json').write_text(json.dumps(result,indent=2))
            summary={k:v for k,v in result.items() if k not in ('records','limitation')};summaries.append(summary)
            print(summary,flush=True)
    (out/'summary.json').write_text(json.dumps(dict(cases=summaries,interpretation='Exact4existingrawshare/accountcontrols reproduced;diagnostic only. ETFproxies and7selectedsurvivingHKstocks,not broadPITstock/futures/property evidence.'),indent=2))


if __name__=='__main__':main()
