from shadow_prepare import *
def shock(n):
 on=True;anchor=np.nan;out=[];anchors=[]
 for i,x in enumerate(n):
  if on and i>=5 and x/n.iloc[i-5]-1<=-.1:on=False;anchor=n.iloc[i-5]
  elif not on and x>=anchor:on=True
  out.append(on);anchors.append(anchor)
 return pd.DataFrame({'on':out,'anchor':anchors},index=n.index)
if __name__=='__main__':
 n=pd.read_csv(O/'shadow-signals/reference.csv',index_col=0,parse_dates=True).nav;z=shock(n);out=O/'shock-signals';out.mkdir(exist_ok=False);z.to_csv(out/'gates.csv')
 for end in ['2024-12-31','2025-12-31','2026-06-30']:pd.testing.assert_frame_equal(shock(n.loc[:end]),z.loc[:end])
 # Synthetic: no rolling anchor reduction while stopped; recovery at fixed anchor.
 syn=pd.Series([100]*5+[89,80,90,95,99,100],index=pd.date_range('2020-01-01',periods=11));zz=shock(syn);assert zz.on.tolist()==[True]*5+[False]*5+[True];assert zz.anchor.iloc[5:].eq(100).all()
 root=O/'SHOCK10/prepared';(root/'facts').mkdir(parents=True,exist_ok=False);(root/'h1.npz').symlink_to(BASE/'prepared-v2/h1.npz')
 for path in sorted((NR/'facts').glob('*.parquet')):
  f=pd.read_parquet(path)
  if not path.stem.startswith('URFI'):
   mask=z.on.reindex(f.index,method='ffill').fillna(True);f['i_target']=f.i_target&mask;f['i_buy']=f.i_buy&mask
  f.to_parquet(root/'facts'/path.name)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False;fig,ax=plt.subplots(2,1,figsize=(14,7),sharex=True);ax[0].plot(n.index,n/1e6,label='原I影子NAV');ax[0].plot(z.index,z.anchor/1e6,label='触发时固定恢复锚',alpha=.6);ax[0].legend();ax[1].plot(z.index,z.on.astype(int),label='SHOCK10开关');ax[1].legend();fig.tight_layout();fig.savefig(out/'reference.png',dpi=110)
 (out/'validation.json').write_text(json.dumps({'passed':True,'prefixes':3,'fixed_anchor_synthetic':True},indent=2));print('shock prepared');print(z.loc[z.on.ne(z.on.shift())].to_string())
