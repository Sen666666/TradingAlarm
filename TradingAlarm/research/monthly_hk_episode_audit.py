"""Episode cash-flow audit with causal dividend ownership and exact FX decomposition.
Only paths with zero in-kind claims: reject instead of silently losing claims.
"""
import json
import math
from collections import defaultdict
import pandas as pd
from build_stock_features import ROOT
from hk_in_kind_campaign import load_assets
from portfolio_data import fx_series
from campaign_engine import dividend_local_value


def audit(assets,path,orders,fx_cost,fx_override=None,allow_claims=False,daily_output=None):
    for key in ('security_claim_value','claim_dividend_receivable','claim_dividend_cash_paid'):
        if key in path and not allow_claims:assert path[key].eq(0).all(), 'Nonzero in-kind path needs episode claim ownership'
    assert all(a['currency']=='HKD' for a in assets.values())
    fx=fx_series(path.index) if fx_override is None else fx_override.reindex(path.index).ffill()
    fills=defaultdict(list);events=defaultdict(list);splits=defaultdict(list)
    for o in orders:fills[pd.Timestamp(o['date'])].append(o)
    for s,a in assets.items():
        for e in a['dividends']:events[pd.Timestamp(e['ex_date'])].append((s,e))
        for e in a['splits']:splits[pd.Timestamp(e['date'])].append((s,e['ratio']))
    active={};episodes=[];receipts=[];max_error=0.;claims=[];previous_symbol={}
    for day,row in path.iterrows():
        rate=float(fx.loc[day])
        for s,ratio in splits[day]:
            if s in active:active[s]['quantity']*=ratio
        if allow_claims:
            for s,a in assets.items():
                for e in a.get('in_kind',[]):
                    if pd.Timestamp(e['ex_date'])==day and s in active:
                        ep=active[s];assert ep['quantity']==int(ep['quantity'])
                        recipient=e['recipient'];assert not assets[recipient]['splits']
                        claims.append((ep,recipient,int(ep['quantity'])*e['numerator']//e['denominator']))
        for s,e in events[day]:
            if s in active:receipts.append((active[s],active[s]['quantity'],e,s))
            for ep,recipient,q in claims:
                if recipient==s and q:receipts.append((ep,q,e,s))
        remaining=[]
        for ep,q,e,owner in receipts:
            if pd.Timestamp(e['pay_date'])<=day:
                value=q*dividend_local_value(assets[owner],e,day)*rate
                fee=value*fx_cost/10000
                if e.get('currency','HKD')!='HKD' and not(e.get('settlement') and day>pd.Timestamp(e['settlement']['fixing'])):fee+=value*e.get('conversion_bps',10)/10000
                ep['paid_dividends']+=value;ep['dividend_fees']+=fee
            else:remaining.append((ep,q,e,owner))
        receipts=remaining
        for o in fills[day]:
            s=o['symbol'];q=o['units'];price=o['raw_open']
            assert abs(o['fx']-rate)<1e-12
            if s not in active:
                assert q>0
                ep=dict(id=len(episodes)+1,symbol=s,entry_date=str(day.date()),exit_date=None,entry_fx=rate,
                    quantity=0.,local_price_pnl=0.,security_fx_pnl=0.,paid_dividends=0.,dividend_fees=0.,trade_fees=0.)
                episodes.append(ep);active[s]=ep
            ep=active[s];ep['quantity']+=q
            # Fix FX at episode entry for the local-price component; the
            # remainder is FX including the price/FX interaction by convention.
            ep['local_price_pnl']-=q*price*ep['entry_fx']
            ep['security_fx_pnl']-=q*price*(rate-ep['entry_fx'])
            ep['trade_fees']+=o['fee']
            assert ep['quantity']>=-1e-8
            if abs(ep['quantity'])<1e-8:ep['quantity']=0.;ep['exit_date']=str(day.date());del active[s]
        for ep in episodes:
            ep['unpaid_dividends']=0.;ep['terminal_market_value']=0.;ep['mark_local']=0.;ep['mark_fx']=0.
        for ep,q,e,owner in receipts:ep['unpaid_dividends']+=q*dividend_local_value(assets[owner],e,day)*rate
        for s,ep in active.items():
            value=ep['quantity']*float(assets[s]['raw'].loc[:day,'close'].iloc[-1])
            ep['terminal_market_value']=value*rate;ep['mark_local']=value*ep['entry_fx'];ep['mark_fx']=value*(rate-ep['entry_fx'])
        if allow_claims:
            for ep in episodes:ep['nontradable_claim_value']=0.
            for ep,recipient,q in claims:
                value=q*float(assets[recipient]['raw'].loc[:day,'close'].iloc[-1])
                ep['terminal_market_value']+=value*rate;ep['mark_local']+=value*ep['entry_fx'];ep['mark_fx']+=value*(rate-ep['entry_fx'])
                ep['nontradable_claim_value']+=value*rate
            assert abs(sum(e['nontradable_claim_value'] for e in episodes)-row.security_claim_value)<1e-6
        total=sum(ep['local_price_pnl']+ep['mark_local']+ep['security_fx_pnl']+ep['mark_fx']+ep['paid_dividends']+ep['unpaid_dividends']-ep['trade_fees']-ep['dividend_fees'] for ep in episodes)
        error=abs(total-(row.nav-1)*1e6);max_error=max(max_error,error)
        assert error<1e-6,(day,error)
        if daily_output is not None:
            by_symbol={s:dict(pnl=0.,fees=0.) for s in assets}
            for ep in episodes:
                value=ep['local_price_pnl']+ep['mark_local']+ep['security_fx_pnl']+ep['mark_fx']+ep['paid_dividends']+ep['unpaid_dividends']-ep['trade_fees']-ep['dividend_fees']
                by_symbol[ep['symbol']]['pnl']+=value
                by_symbol[ep['symbol']]['fees']+=ep['trade_fees']+ep['dividend_fees']
            for symbol,values in by_symbol.items():
                previous=previous_symbol.get(symbol,dict(pnl=0.,fees=0.))
                daily_output.append(dict(date=str(day.date()),symbol=symbol,pnl=values['pnl']-previous['pnl'],fees=values['fees']-previous['fees']))
            previous_symbol=by_symbol
    for ep in episodes:
        ep['local_price_pnl']+=ep.pop('mark_local');ep['security_fx_pnl']+=ep.pop('mark_fx')
        ep['pnl']=ep['local_price_pnl']+ep['security_fx_pnl']+ep['paid_dividends']+ep['unpaid_dividends']-ep['trade_fees']-ep['dividend_fees']
        end=ep['exit_date'] or str(path.index[-1].date())
        ep['observed_holding_sessions']=len(assets[ep['symbol']]['raw'].loc[ep['entry_date']:end])
        ep['status']='closed' if ep['exit_date'] else 'open'
    return episodes,max_error


def summary(episodes):
    closed=sorted((e for e in episodes if e['status']=='closed'),key=lambda e:e['pnl'])
    opened=[e for e in episodes if e['status']=='open'];all_sorted=sorted(episodes,key=lambda e:e['pnl'])
    nt=math.ceil(len(closed)*.1);na=math.ceil(len(episodes)*.1)
    wins=[e['pnl'] for e in closed if e['pnl']>0];losses=[e['pnl'] for e in closed if e['pnl']<0]
    return dict(closed_count=len(closed),open_count=len(opened),closed_pnl=sum(e['pnl'] for e in closed),open_pnl=sum(e['pnl'] for e in opened),
        closed_win_rate=len(wins)/len(closed) if closed else None,
        average_win=sum(wins)/len(wins) if wins else None,average_loss=sum(losses)/len(losses) if losses else None,
        ordinary_closed_bottom90=sum(e['pnl'] for e in closed[:-nt]) if nt else 0,
        ordinary_all_bottom90=sum(e['pnl'] for e in all_sorted[:-na]) if na else 0,
        top_all=[dict(symbol=e['symbol'],pnl=e['pnl'],status=e['status']) for e in all_sorted[-na:]] if na else [],
        components={k:sum(e[k] for e in episodes) for k in ('local_price_pnl','security_fx_pnl','paid_dividends','unpaid_dividends','trade_fees','dividend_fees')},
        asset_pnl={s:sum(e['pnl'] for e in episodes if e['symbol']==s) for s in sorted(set(e['symbol'] for e in episodes))})


def main():
    out=ROOT/'results/monthly-hk-stock-transfer';assets,_=load_assets();reports=[]
    for result in json.loads((out/'results.json').read_text()):
        case=result['case'];path=pd.read_parquet(out/f'{case}-path.parquet');orders=json.loads((out/f'{case}-orders.json').read_text())
        episodes,error=audit(assets,path,orders,20 if result['scenario']=='cost2' else 10)
        report=dict(case=case,**summary(episodes),max_daily_accounting_error=error)
        (out/f'{case}-episodes.json').write_text(json.dumps(episodes,indent=2));reports.append(report)
        if case.startswith('0-'):print(json.dumps(report),flush=True)
    (out/'episode-attribution.json').write_text(json.dumps(dict(results=reports,limits=['All paths had zero in-kind claims; nonzero claims are rejected by this episode audit.','Entry FX decomposition is an accounting convention; FX-price interaction assigned to FX. Dividends including currency conversion are shown separately.','Top10percent sorted retrospectively;not a trading filter. Open holding PNL is marked,not realized. Closed episode can still have a dividend receivable.','No inference of fixed2week holding,80percentcycle performance or futureportability.']),indent=2))

if __name__=='__main__':main()
