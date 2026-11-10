import importlib.util,json,hashlib
from pathlib import Path
import pandas as pd
from trend_cash_book import simulate,WINDOWS,window_stats
from trend_quiet_book import load_one,NAMES
from trend_equal_weight import equal_scores
from trend_half_slow import quiet_half_slow
from trend_thrust_fail import thrust_state


def main(out):
    spec=importlib.util.spec_from_file_location('cash_original',out/'original-trend_cash_book.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    frames={};states={}
    for code,_,first in NAMES:
        f=load_one(code,first);plain=equal_scores(f.close,f.amount);op=quiet_half_slow(f.close,f.amount,plain)
        frames[code]=f;states[code]=pd.Series(thrust_state(op.to_numpy(),plain.fast.to_numpy(),plain.slow.to_numpy(),f.close.to_numpy()),index=f.index)
        states[code].to_csv(out/f'repair-{code}-frozen-signal.csv')
    starts={s:f.index[0] for s,f in frames.items()};result={}
    for name,func,kwargs in [('original',old.simulate,{}),('quantity_and_mark',simulate,{'budget_after_sells':False}),('sell_first',simulate,{'budget_after_sells':True})]:
        ep=[];orders=[];snap=[]
        if name!='original':kwargs.update(orders=orders,snapshots=snap)
        nav=func(frames,states,starts,ep,lot=100,**kwargs)
        nav.to_csv(out/f'repair-{name}-nav.csv');(out/f'repair-{name}-episodes.json').write_text(json.dumps(ep,indent=2))
        errors={'cash':0.,'quantity':0.,'nav':0.}
        if snap:
            cash=1e6;qty={s:0. for s in frames};byday={}
            for o in orders:byday.setdefault(o['date'],[]).append(o)
            for row in snap:
                for o in byday.get(row['date'],[]):cash-=o['units']*o['price']+o['fee'];qty[o['symbol']]+=o['units']
                value=cash+sum(qty[s]*float(f.loc[:row['date'],'close'].iloc[-1]) for s,f in frames.items() if qty[s])
                errors['cash']=max(errors['cash'],abs(cash-row['cash']));errors['quantity']=max(errors['quantity'],max(abs(qty[s]-row['quantities'][s]) for s in qty));errors['nav']=max(errors['nav'],abs(value-row['nav']))
            assert max(errors.values())<1e-6
            assert abs(sum(e['pnl'] for e in ep)-(nav.iloc[-1]-1e6))<1e-6
            (out/f'repair-{name}-orders.json').write_text(json.dumps(orders))
            (out/f'repair-{name}-snapshots.json').write_text(json.dumps(snap))
        result[name]={'windows':{k:window_stats(nav,a,b) for k,a,b in WINDOWS if k in ['2013-2016','2018-2021','2022-2026']},'total_pnl':float(nav.iloc[-1]-1e6),'ledger_pnl':sum(e['pnl'] for e in ep),'independent_replay':errors if snap else 'not instrumented original','orders':len(orders) if snap else None,'closed':sum(not e['open'] for e in ep),'open':sum(e['open'] for e in ep)}
        print(name,result[name],flush=True)
    (out/'repair-summary.json').write_text(json.dumps(result,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
