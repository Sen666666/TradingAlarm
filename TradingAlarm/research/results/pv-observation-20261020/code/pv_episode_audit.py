"""Independent episode ownership and daily PNL bridge, mixed currencies and claims."""
from collections import defaultdict
import numpy as np
import pandas as pd
from portfolio_data import fx_series
from campaign_engine import dividend_local_value


def audit_episodes(assets, path, orders, fx_cost):
    fx=fx_series(path.index);fills=defaultdict(list);splits=defaultdict(list);divs=defaultdict(list);distribution=defaultdict(list)
    for o in orders:fills[pd.Timestamp(o['date'])].append(o)
    for s,a in assets.items():
        for e in a['splits']:splits[pd.Timestamp(e['date'])].append((s,e['ratio']))
        for e in a['dividends']:divs[pd.Timestamp(e['ex_date'])].append((s,e))
        for e in a.get('in_kind',[]):distribution[pd.Timestamp(e['ex_date'])].append((s,e))
    active={};episodes=[];receipts=[];claims=[];daily=[];error=0.
    marks={s:a['raw'].close.reindex(path.index,method='ffill') for s,a in assets.items()}
    for day,row in path.iterrows():
        rates={s:float(fx.loc[day]) if a['currency']=='HKD' else 1. for s,a in assets.items()}
        for s,ratio in splits[day]:
            if s in active:active[s]['quantity']*=ratio
        for s,e in distribution[day]:
            if s in active:
                ep=active[s];q=int(ep['quantity'])*e['numerator']//e['denominator']
                if q:claims.append((ep,e['recipient'],q))
        for s,e in divs[day]:
            if s in active:receipts.append((active[s],s,active[s]['quantity'],e))
            for ep,child,q in claims:
                if child==s:receipts.append((ep,s,q,e))
        unpaid=[]
        for ep,s,q,e in receipts:
            value=q*dividend_local_value(assets[s],e,day)*rates[s]
            if pd.Timestamp(e['pay_date'])<=day:
                fee=value*fx_cost/10000 if assets[s]['currency']=='HKD' else 0.
                if e.get('currency',assets[s]['currency'])!=assets[s]['currency'] and not(e.get('settlement') and day>pd.Timestamp(e['settlement']['fixing'])):fee+=value*e.get('conversion_bps',10)/10000
                ep['cashflow']+=value-fee;ep['dividend_cash']+=value;ep['fees']+=fee
            else:unpaid.append((ep,s,q,e))
        receipts=unpaid
        for o in fills[day]:
            s=o['symbol'];q=o['units'];value=q*o['raw_open']*o['fx']
            if s not in active:
                assert q>0
                ep=dict(id=len(episodes),symbol=s,entry=str(day.date()),exit=None,quantity=0.,cashflow=0.,buy_cash=0.,fees=0.,dividend_cash=0.,pnl=0.)
                episodes.append(ep);active[s]=ep
            ep=active[s];ep['quantity']+=q;ep['cashflow']-=value+o['fee'];ep['fees']+=o['fee']
            if q>0:ep['buy_cash']+=value+o['fee']
            if abs(ep['quantity'])<1e-8:
                ep['quantity']=0.;ep['exit']=str(day.date());del active[s]
        for ep in episodes:ep['mark']=0.;ep['receivable']=0.;ep['claim_value']=0.
        for s,ep in active.items():ep['mark']=ep['quantity']*float(marks[s].loc[day])*rates[s]
        for ep,s,q,e in receipts:ep['receivable']+=q*dividend_local_value(assets[s],e,day)*rates[s]
        for ep,s,q in claims:ep['claim_value']+=q*float(marks[s].loc[day])*rates[s]
        for ep in episodes:
            value=ep['cashflow']+ep['mark']+ep['receivable']+ep['claim_value'];delta=value-ep['pnl'];ep['pnl']=value
            if delta:daily.append(dict(date=str(day.date()),id=ep['id'],pnl=delta))
        err=abs(sum(e['pnl'] for e in episodes)-(row.nav-1)*1e6);error=max(error,err)
        assert err<1e-6,(day,err)
    for ep in episodes:
        ep['status']='closed' if ep['exit'] and ep['receivable']==0 and ep['claim_value']==0 else 'open_or_claim'
        ep['ret']=ep['pnl']/ep['buy_cash'];ep['label']='tail' if ep['status']=='closed' and ep['ret']>=.3 else 'ordinary' if ep['status']=='closed' else 'open_or_claim'
        s=ep['symbol'];prices=assets[s]['signal'].close.loc[ep['entry']:ep['exit'] or str(path.index[-1].date())]
        rel=prices/prices.iloc[0]-1
        ep['signal_close_mfe']=float(rel.max());ep['signal_close_mae']=float(rel.min());ep['sessions']=len(prices)
    for d in daily:d['label']=episodes[d['id']]['label']
    closed=[e for e in episodes if e['status']=='closed'];wins=[e['ret'] for e in closed if e['ret']>0];losses=[e['ret'] for e in closed if e['ret']<0]
    summary={'closed_n':len(closed),'win_rate':len(wins)/len(closed) if closed else None,'payoff':float(np.mean(wins)/-np.mean(losses)) if wins and losses else None,'max_daily_error':error}
    for label in ['tail','ordinary','open_or_claim']:
        part=[e for e in episodes if e['label']==label]
        summary[label]={'n':len(part),'net_pnl':sum(e['pnl'] for e in part),'gross_pnl_same_labels':sum(e['pnl']+e['fees'] for e in part),'fees':sum(e['fees'] for e in part)}
    assert abs(sum(summary[x]['net_pnl'] for x in ['tail','ordinary','open_or_claim'])-(path.nav.iloc[-1]-1)*1e6)<1e-6
    return episodes,daily,summary
