"""Past-known trend evidence at first adverse close; outcome labels for audit only."""
import json,hashlib
from pathlib import Path
import pandas as pd
from range_direction_strength import range_frame
from adaptive_geometric_strength import adaptive_frame
from ths_volume_units import ths_split_consistent_volume

OUT=Path('results/trend-adverse-evidence')
SOURCE=Path('results/strength-range-transfer485')


def first_adverse(close,strength,start,end,entry,closed):
    held=close.loc[(close.index>=pd.Timestamp(start))&((close.index<pd.Timestamp(end)) if closed else (close.index<=pd.Timestamp(end)))]
    bad=held.loc[held.le(entry*.95)]
    if bad.empty:return None
    date=bad.index[0];past=strength.loc[:date];lag5=float(past.iloc[-6]) if len(past)>=6 else None
    return dict(date=str(date.date()),price=float(close.loc[date]),strength=float(strength.loc[date]),change5=float(past.iloc[-1]-lag5) if lag5 is not None else None)


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',anchor='First observed close <=95% of episode entry adjustedopen, beforeexitopen; 5%only diagnostic nottradingrule',features='Existing fixedscore and past5observedbar scorechange; no future in snapshot',outcomes='Existing episode loss<0,tail>=30%,other; closed/open separately; all episodes denominator',scope='Same485Ashare frozen3models,base15bps,cutoff2026Oct16',limits='Condition on surviving original strategy until adverse close; no causal early-exit profitability inference; labels retrospectively selected; repeated correlated trades.'),indent=2))
    manifest=json.loads(Path('data/ths-refresh-20261018/validated-input-balanced-second500.json').read_text())
    episodes=pd.read_parquet(SOURCE/'episodes.parquet');episodes=episodes.loc[episodes.delay.eq(0)&episodes.cutoff.eq('2026-10-16')];rows=[]
    for r in manifest['records']:
        root=Path('data/ths-refresh-20261018');p=root/f"{r['ths_symbol']}-signal.parquet";q=root/'rights'/f"{r['ths_symbol']}.json"
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['signal_sha256'];assert hashlib.sha256(q.read_bytes()).hexdigest()==r['rights_sha256']
        f=pd.read_parquet(p);v=ths_split_consistent_volume(f.volume,json.loads(q.read_text()));obs=f.loc[f.observed_bar&f.volume.gt(0)];sig=obs[['signal_open','signal_high','signal_low','signal_close']].rename(columns=lambda x:x.removeprefix('signal_'))
        scores=dict(adaptive_geometry_price_volume_split_units=adaptive_frame(obs.signal_close,obs.close,v.reindex(obs.index)).strength,range_direction_volume=range_frame(sig,v.reindex(obs.index),True).strength,close_direction_volume=range_frame(sig,v.reindex(obs.index),True,True).strength)
        for e in episodes.loc[episodes.symbol.eq(r['symbol'])].itertuples():
            hit=first_adverse(obs.signal_close,scores[e.strategy],e.entry_date,e.mark_date,e.entry_price,e.status=='closed')
            outcome='loss' if e.return15<0 else ('tail30' if e.return15>=.3 else 'other')
            row=dict(strategy=e.strategy,symbol=e.symbol,entry_date=e.entry_date,year=int(e.entry_date[:4]),status=e.status,outcome=outcome,net_return=e.return15,hit=hit is not None)
            if hit:row.update(hit,terminal_from_hit=e.exit_price/hit['price']-1)
            rows.append(row)
    f=pd.DataFrame(rows);f.to_parquet(OUT/'episodes.parquet',index=False)
    summaries=[]
    for key,g in f.groupby(['strategy','status','outcome']):
        hit=g.loc[g.hit]
        summaries.append(dict(zip(['strategy','status','outcome'],key),episodes=len(g),hits=len(hit),hit_fraction=float(g.hit.mean()),median_strength=float(hit.strength.median()) if len(hit) else None,median_change5=float(hit.change5.median()) if len(hit) else None,falling5_fraction=float(hit.change5.lt(0).mean()) if len(hit) else None,median_terminal_from_hit=float(hit.terminal_from_hit.median()) if len(hit) else None))
    (OUT/'summary.json').write_text(json.dumps(summaries,indent=2));print(pd.DataFrame(summaries).to_string(index=False))
    (OUT/'validation.json').write_text(json.dumps(dict(signal_and_rights_hashes=2*len(manifest['records']),episodes=len(f)),indent=2))


if __name__=='__main__':main()
