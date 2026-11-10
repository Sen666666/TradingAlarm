"""Trace episode returns to actual purchase cash; explicit tail thresholds, no trade filter."""
import json,hashlib
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
SOURCES=[
 ('strength-pairwise','hk7-pairwise_price-daily-base'),
 ('strength-pairwise','hk7-pairwise_volume-daily-base'),
 ('strength-symmetric-exit','hk7-symmetric_pairwise_volume-daily-base'),
 ('trend-slot-workbench','hk7-symmetric_pairwise_volume-rank_slots-base'),
 ('strength-uniform-pairwise','hk7-uniform_pairwise_volume-daily-base'),
 ('strength-calibrated-order','hk7-calibrated_pair_order_volume-daily-base'),
]

def attach_cash(episodes,orders):
    rows=[dict(e,buy_cash=0.,buy_orders=0,matched_trade_fees=0.) for e in episodes]
    for o in orders:
        owners=[e for e in rows if e['symbol']==o['symbol'] and e['entry_date']<=o['date'] and (not e['exit_date'] or o['date']<=e['exit_date'])]
        if len(owners)!=1:raise ValueError('Order does not have exactly one episode owner')
        ep=owners[0];ep['matched_trade_fees']+=o['fee']
        if o['units']>0:
            ep['buy_cash']+=o['units']*o['raw_open']*o['fx']+o['fee'];ep['buy_orders']+=1
    for ep in rows:
        assert ep['buy_cash']>0
        assert abs(ep['matched_trade_fees']-ep['trade_fees'])<1e-6
        ep['return_on_buy_cash']=ep['pnl']/ep['buy_cash']
        ep['parent_closed']=bool(ep['exit_date'])
        ep['retained_claim']=ep.get('nontradable_claim_value',0)>0
    return rows

def main():
    out=ROOT/'results/episode-capital-tail-audit';out.mkdir(exist_ok=True)
    allrows=[];checks=[];summaries=[]
    for directory,case in SOURCES:
        root=ROOT/'results'/directory
        epfile=root/f'{case}-episodes.json';orderfile=root/f'{case}-orders.json';pathfile=root/f'{case}-path.parquet'
        episodes=attach_cash(json.loads(epfile.read_text()),json.loads(orderfile.read_text()))
        f=pd.DataFrame(episodes);path=pd.read_parquet(pathfile)
        error=abs(f.pnl.sum()-(float(path.nav.iloc[-1])-1)*1e6);assert error<1e-6
        checks.append(dict(case=case,account_error=error,hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [epfile,orderfile,pathfile]}))
        for threshold in [.30,.80]:
            for status in ['all','closed','open']:
                a=f if status=='all' else f.loc[f.status.eq(status)]
                tail=a.return_on_buy_cash.ge(threshold);loss=a.pnl.lt(0);ordinary_win=a.pnl.ge(0)&~tail
                t=float(a.loc[tail,'pnl'].sum());l=float(a.loc[loss,'pnl'].sum());w=float(a.loc[ordinary_win,'pnl'].sum())
                assert abs(t+l+w-a.pnl.sum())<1e-6
                summaries.append(dict(case=case,threshold=threshold,status=status,count=len(a),tail_count=int(tail.sum()),tail_pnl=t,loss_pnl=l,ordinary_win_pnl=w,ordinary_net=w+l,ordinary_win_loss_coverage=w/-l if l<0 else None,total_pnl=t+w+l,tail_share_count=float(tail.mean()) if len(a) else None,retained_claim_count=int(a.retained_claim.sum())))
        f['case']=case;allrows.append(f)
    pd.concat(allrows,ignore_index=True).to_parquet(out/'episodes.parquet',index=False)
    s=pd.DataFrame(summaries);s.to_csv(out/'tail-summary.csv',index=False)
    (out/'validation.json').write_text(json.dumps(dict(checks=checks,limits=[
      'Return denominator is sum of actual positive-order CNY cash including purchase fees; profit includes all episode fees/dividends/marked claims.',
      'This is return on cumulative deployed cash, not time-weighted/annualized return, R multiple, or whole-account cycle return.',
      'Parent-closed episodes can still retain marked distributed shares; open episodes separately reported and right censored.',
      '30% and80% episode cutoffs are descriptive, not executable filters or proof of whole-account80% target.',
      'Cashloss and ordinarygain compare accounting contributions, not exante risk-matched outcomes. HK7 selected development universe only.'
    ]),indent=2))
    print(s.loc[s.threshold.eq(.3)&s.status.eq('all'),['case','count','tail_count','tail_pnl','loss_pnl','ordinary_win_pnl','ordinary_net','ordinary_win_loss_coverage']].to_string(index=False))
if __name__=='__main__':main()
