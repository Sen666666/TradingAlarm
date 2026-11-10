"""Control the number of sectors: same three names, cash stays with its owner."""
from common import *
from fast_single import run

def main():
 out=HERE/'fixed-three-reference';out.mkdir(exist_ok=False);z=np.load(OLD/'h1/matrix.npz');dates=pd.DatetimeIndex(z['dates']);dates=dates[(dates>=START)&(dates<=END)];sectors=sorted(str(s) for s in z['symbols'] if str(s).startswith('URFI'));rec={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']};nvs=[];expos=[]
 for sid in sectors:
  s=pd.read_parquet(HERE/'sector-states'/f'{sid}.parquet');raw=pd.read_parquet(OLD/'prepared-v2'/rec[sid]['files']['signal']['path']).loc[s.index];d=raw.loc[START:END];q=s.loc[d.index];n=s.index.searchsorted(START);prev=s.iloc[n-1] if n else None;active=bool(prev is not None and prev.ready and prev.ix_target and prev.grade>=2);ini=dict(active=active,floor=float(prev.ix_floor) if active else None);state=pd.DataFrame(dict(target=q.ix_target,floor=q.ix_floor,buy_event=q.buy_event),index=q.index);st,nav,_=run(d,state,ini);nvs.append(pd.Series(nav,index=d.index).reindex(dates).ffill().fillna(1).to_numpy());expos.append(st['exposure'])
 matrix=np.array(nvs);rows=[];curves=[]
 for seed in range(20):
  scores=np.random.default_rng(seed).permutation(len(sectors));ids=np.argsort(-scores)[:3];nav=.1+.3*matrix[ids].sum(axis=0);dd=nav/np.maximum.accumulate(np.r_[1,nav])[1:]-1;rows.append(dict(seed=seed,sectors='|'.join(sectors[j] for j in ids),net_return=float(nav[-1]-1),max_drawdown=float(-dd.min()),mean_initial_sleeve_participation=float(.3*np.array(expos)[ids].sum())))
  for i,day in enumerate(dates):curves.append(dict(seed=seed,date=str(day.date()),nav=float(nav[i])))
 a=pd.DataFrame(rows);a.to_csv(out/'all-seeds.csv',index=False);pd.DataFrame(curves).to_csv(out/'curves.csv',index=False);write(out/'summary.json',dict(recorded_at=now(),seeds=20,positive=int(a.net_return.gt(0).sum()),mean_return=float(a.net_return.mean()),median_return=float(a.net_return.median()),median_drawdown=float(a.max_drawdown.median()),mean_initial_sleeve_participation=float(a.mean_initial_sleeve_participation.mean()),initial_sleeves=3,initial_fraction_each=.3,initial_cash=.1,cash_not_reassigned_to_other_sectors=True,no_best_seed_selected=True,proxy_only=True));print(read(out/'summary.json'),flush=True)
if __name__=='__main__':main()
