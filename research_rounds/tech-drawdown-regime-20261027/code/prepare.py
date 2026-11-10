from diagnose import *
VERSIONS=['CONTROL','FAST','SECTOR','MARKET_NEW','MARKET_ALL','MARKET_SLOW','MARKET_PRICE']
def latch(s):
 state=False;out=[]
 for x in s:
  if not np.isfinite(x):state=False
  elif x<.4:state=False
  elif x>.6:state=True
  out.append(state)
 return pd.Series(out,index=s.index)
def generate(cutoff=None):
 roster=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv');tr={};sec={};all_dates=set()
 for sid in roster.symbol:
  raw=eligible_prices(pd.read_parquet(BASE/'prepared-v2/signals'/f'{sid}.parquet'))
  if cutoff:raw=raw.loc[:cutoff]
  parts=[]
  for seg,g in raw.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();p=r*np.minimum(1,np.sqrt(q));z=pd.DataFrame({'m21':p.ewm(span=21,adjust=False).mean(),'m63':p.ewm(span=63,adjust=False).mean(),'price21':r.ewm(span=21,adjust=False).mean()},index=g.index);z.iloc[:64]=np.nan;parts.append(z)
  tr[sid]=pd.concat(parts).sort_index() if parts else pd.DataFrame(index=pd.DatetimeIndex([],name='date'),columns=['m21','m63','price21'],dtype=float);all_dates.update(tr[sid].index)
 dates=pd.DatetimeIndex(sorted(all_dates))
 for sid,rs in roster.groupby('sector_id'):
  z=pd.DataFrame(index=dates)
  for k in ['m21','m63','price21']:
   v=pd.concat({s:tr[s][k] for s in rs.symbol},axis=1).reindex(dates);n=v.notna().sum(axis=1);z[k]=(v.gt(0).sum(axis=1)/n).where(n>=5)
  sec[sid]=z
 agg=pd.DataFrame({k:pd.concat({s:z[k] for s,z in sec.items()},axis=1).mean(axis=1).where(pd.concat({s:z[k] for s,z in sec.items()},axis=1).notna().sum(axis=1)>=8) for k in ['m21','m63','price21']})
 gates=pd.DataFrame({k:latch(agg[k]) for k in agg});sector_gates={s:latch(z.m21) for s,z in sec.items()};return roster,tr,agg,gates,sector_gates
if __name__=='__main__':
 out=O/'signals-v1';out.mkdir(exist_ok=False);roster,tr,agg,gates,sg=generate();agg.to_csv(out/'breadth.csv');gates.to_csv(out/'market-gates.csv');pd.DataFrame(sg).to_csv(out/'sector-gates.csv');mapping=dict(zip(roster.symbol,roster.sector_id))
 for v in VERSIONS:
  root=O/v/'prepared';(root/'facts').mkdir(parents=True,exist_ok=False);(root/'h1.npz').symlink_to(BASE/'prepared-v2/h1.npz')
 for path in sorted((NR/'facts').glob('*.parquet')):
  f=pd.read_parquet(path);sid=path.stem
  for v in VERSIONS:
   z=f.copy()
   if sid in mapping and v!='CONTROL':
    if v=='FAST':gate=tr[sid].m21.ge(0).reindex(f.index).fillna(False)
    elif v=='SECTOR':gate=sg[mapping[sid]].reindex(f.index).fillna(False)
    else:gate=gates['m63' if v=='MARKET_SLOW' else 'price21' if v=='MARKET_PRICE' else 'm21'].reindex(f.index).fillna(False)
    z['i_buy']=z.i_buy & gate
    if v!='MARKET_NEW':z['i_target']=z.i_target & gate
   z.to_parquet(O/v/'prepared/facts'/path.name)
 # Original OHLC/amount examples, fixed by earlier study not performance selection.
 for sid in ['688498.SH','300308.SZ','300502.SZ','603256.SH']:
  raw=eligible_prices(pd.read_parquet(BASE/'prepared-v2/signals'/f'{sid}.parquet')).loc['2024':];fig,ax=plt.subplots(3,1,figsize=(14,8),sharex=True)
  for t,r in raw.iterrows():
   color='#c54538' if r.close>=r.open else '#348774';ax[0].plot([t,t],[r.low,r.high],color=color,lw=.5);ax[0].plot([t,t],[r.open,r.close],color=color,lw=1)
  ax[0].set_title(sid+' 原始OHLC（因果复权坐标）');ax[1].bar(raw.index,raw.amount/1e8,width=1);ax[1].set_ylabel('成交金额亿元');z=tr[sid].loc['2024':];ax[2].plot(z.index,z.m21,label='个股方向金额m21');ax[2].plot(z.index,z.m63,label='m63');ax[2].axhline(0,color='grey');ax[2].legend()
  for a in ax:a.grid(alpha=.2)
  fig.tight_layout();fig.savefig(out/f'raw-{sid}.png',dpi=110);plt.close(fig)
 fig,ax=plt.subplots(2,1,figsize=(14,7),sharex=True);a=agg.loc['2024':];a.plot(ax=ax[0]);gates.loc['2024':].astype(int).plot(ax=ax[1]);fig.tight_layout();fig.savefig(out/'gates.png',dpi=120);plt.close(fig)
 print('prepared',len(VERSIONS),'versions',len(mapping),'stocks',flush=True)
