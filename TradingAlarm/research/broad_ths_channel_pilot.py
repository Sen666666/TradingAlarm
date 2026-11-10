"""Frozen input signal-only transfer using shared signals and episode execution."""
import json,hashlib,math
import pandas as pd
from build_stock_features import ROOT
from strategy_signals import build_signals
from a_stock_monthly252 import simulate
from geometric_strength import geometric_frame,strength_exposure
from adaptive_geometric_strength import adaptive_frame


def main(output='broad-ths-channel-pilot'):
    out=ROOT/'results'/output;protocol=json.loads((out/'protocol.json').read_text());manifest=json.loads((ROOT/protocol['manifest']).read_text());data=ROOT/'data/ths-refresh-20261018';frames={};dates=set()
    for r in manifest['records']:
        p=data/f"{r['ths_symbol']}-signal.parquet"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256']
        f=pd.read_parquet(p);frames[r['symbol']]=f;dates.update(f.index[f.observed_bar])
    calendar=pd.DatetimeIndex(sorted(dates));cuts=[pd.Timestamp(x) for x in protocol['cutoffs']];assert all(c in calendar for c in cuts)
    gates=None
    if any(name.startswith('peer_') for name in protocol['strategies']):
        from peer_gate_signal import load_gates,gate_exposure
        gates=load_gates()
    rows=[]
    for n,(s,f) in enumerate(frames.items()):
        sig=f[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'))
        cached_pairwise=None
        for name in protocol['strategies']:
            if name.startswith('peer_'):
                if cached_pairwise is None:raise ValueError('Run pairwise_volume control first')
                exposure=gate_exposure(cached_pairwise,gates[s][name])
            elif name=='calibrated_pair_order_volume':
                from ths_volume_units import ths_split_consistent_volume
                from calibrated_order_signal import reset_signal
                record=next(r for r in manifest['records'] if r['symbol']==s)
                rights_path=data/'rights'/f"{record['ths_symbol']}.json"
                assert hashlib.sha256(rights_path.read_bytes()).hexdigest()==record['rights_sha256']
                volume=ths_split_consistent_volume(f.volume,json.loads(rights_path.read_text()))
                observed=f[f.observed_bar & f.volume.gt(0)]
                exposure=reset_signal(observed.signal_close,volume.reindex(observed.index),name).reindex(f.index,method='ffill').fillna(0)
            elif name in ('adaptive_geometry_price_volume_split_units','anchored_price_volume','anchored_neutral_price_volume','range_direction_volume','close_direction_volume','pairwise_price','pairwise_volume','uniform_pairwise_volume','linear_geometry_price_volume_split_units'):
                from ths_volume_units import ths_split_consistent_volume
                from anchored_trend_strength import anchored_strength_frame
                record=next(r for r in manifest['records'] if r['symbol']==s)
                rights_path=data/'rights'/f"{record['ths_symbol']}.json"
                assert hashlib.sha256(rights_path.read_bytes()).hexdigest()==record['rights_sha256']
                volume=ths_split_consistent_volume(f.volume,json.loads(rights_path.read_text()))
                observed=f[f.observed_bar & f.volume.gt(0)]
                if name.startswith('adaptive_'):
                    strength=adaptive_frame(observed.signal_close,observed.close,volume.reindex(observed.index)).strength
                elif name.startswith('pairwise_') or name=='uniform_pairwise_volume':
                    from pairwise_trend_strength import pairwise_frame
                    strength=pairwise_frame(observed.signal_close,volume.reindex(observed.index),joint=name.endswith('_volume'),recency=not name.startswith('uniform_')).strength
                elif name=='linear_geometry_price_volume_split_units':
                    strength=geometric_frame(observed.signal_close,observed.close,volume.reindex(observed.index),joint=True,degree=1).strength
                elif name in ('range_direction_volume','close_direction_volume'):
                    from range_direction_strength import range_frame
                    strength=range_frame(sig.reindex(observed.index),volume.reindex(observed.index),joint=True,close_only=name.startswith('close_')).strength
                else:
                    strength=anchored_strength_frame(observed.signal_close,volume.reindex(observed.index),neutral='neutral' in name).strength
                exposure=strength_exposure(strength).reindex(f.index,method='ffill').fillna(0)
            elif name in ('geometry_price','geometry_price_volume','linear_geometry_price','linear_geometry_price_volume','adaptive_geometry_price','adaptive_geometry_price_volume'):
                observed=f[f.observed_bar & f.volume.gt(0)]
                if name.startswith('adaptive_'):
                    strength=adaptive_frame(observed.signal_close,observed.close,observed.volume,joint=name.endswith('_volume')).strength
                else:
                    strength=geometric_frame(observed.signal_close,observed.close,observed.volume,joint=name.endswith('_volume'),degree=1 if name.startswith('linear_') else 2).strength
                exposure=strength_exposure(strength).reindex(f.index,method='ffill').fillna(0)
            else:
                exposure=build_signals({s:{'signal':sig}},name)[s]
            if name=='pairwise_volume':cached_pairwise=exposure.copy()
            if not exposure.isin([0.,1.]).all():raise ValueError('Episode-only engine cannot model staged exposure; use inventory accounting')
            scores=exposure.reindex(calendar,method='ffill').fillna(0).to_numpy(bool)
            active=f.bar_allows_trade.reindex(calendar,fill_value=False).to_numpy(bool);execute=(f.high>f.low).reindex(calendar,fill_value=False).to_numpy(bool)
            for delay in (0,1):
                snaps=simulate(calendar,f.signal_open.reindex(calendar).to_numpy(),f.signal_close.reindex(calendar).to_numpy(),scores,active,execute,cuts,s,delay=delay,cadence='daily',start=protocol['start'])
                for cutoff,episodes in snaps.items():
                    for e in episodes:
                        r=dict(e,strategy=name,delay=delay,cutoff=cutoff)
                        for cost in protocol['costs_bps']:r[f'return{cost}']=(e['exit_price']*(1-cost/10000) if e['status']=='closed' else e['exit_price'])/(e['entry_price']*(1+cost/10000))-1
                        rows.append(r)
        if (n+1)%100==0:print('symbols',n+1,flush=True)
    table=pd.DataFrame(rows);table.to_parquet(out/'episodes.parquet',index=False);summaries=[]
    for (strategy,delay,cutoff),g in table.groupby(['strategy','delay','cutoff']):
        for cohort in ('all','entries2026'):
            h=g if cohort=='all' else g[g.entry_date.ge('2026-01-01')]
            for cost in protocol['costs_bps']:
                v=h.loc[h.status.eq('closed'),f'return{cost}'].sort_values();wins=v[v>0];losses=v[v<0];tail=math.ceil(len(v)*.1)
                summaries.append(dict(strategy=strategy,delay=int(delay),cutoff=cutoff,cohort=cohort,cost=cost,counts=h.status.value_counts().to_dict(),closed_win_rate=float((v>0).mean()) if len(v) else None,closed_mean=float(v.mean()) if len(v) else None,average_win=float(wins.mean()) if len(wins) else None,average_loss=float(losses.mean()) if len(losses) else None,payoff=float(wins.mean()/abs(losses.mean())) if len(wins) and len(losses) else None,closed_bottom90_mean=float(v.iloc[:-tail].mean()) if tail and len(v)>tail else None))
    for r in summaries:
        h=table[table.strategy.eq(r['strategy']) & table.delay.eq(r['delay']) & table.cutoff.eq(r['cutoff'])]
        if r['cohort']=='entries2026':h=h[h.entry_date.ge('2026-01-01')]
        column=f"return{r['cost']}";known=h[~h.status.eq('terminal_unknown')];opened=h[h.status.eq('open_at_cutoff')];values=known[column].sort_values();tail=math.ceil(len(values)*.1)
        r.update(known_marked_mean=float(values.mean()) if len(values) else None,open_marked_mean=float(opened[column].mean()) if len(opened) else None,known_bottom90_mean=float(values.iloc[:-tail].mean()) if tail and len(values)>tail else None)
    (out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n');(out/'validation.json').write_text(json.dumps(dict(input_hashes_verified=len(frames),attempted=manifest['attempted'],excluded=len(manifest['excluded']),episode_rows=len(table),account_return_computed=False),indent=2)+'\n')
    for r in summaries:
        if r['cutoff']=='2026-10-16' and r['delay']==0 and r['cost']==15:print(r,flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='broad-ths-channel-pilot');main(parser.parse_args().output)
