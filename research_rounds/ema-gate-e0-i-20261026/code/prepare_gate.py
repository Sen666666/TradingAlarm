from gate_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def main():
 out=HERE/'facts';out.mkdir(exist_ok=False);charts=HERE/'charts';charts.mkdir();diag=HERE/'diagnosis';diag.mkdir()
 scope=read(SEC/'scope.json');sources={};frames={};gates={};stats=[];prefixes=[]
 cases=pd.read_csv(VIDEO/'raw/cases.csv');caseids=set(cases.symbol)
 for group,ids in scope['groups'].items():
  for sid in ids:
   p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p);q=gate(f);v=pd.read_parquet(VIDEO/'daily-facts'/f'{sid}.parquet',columns=['typical_EMA_alignment']);np.testing.assert_array_equal(q.gate.to_numpy(),v.typical_EMA_alignment.to_numpy())
   sources[str(p.relative_to(ROOT))]=sha(p);q.to_parquet(out/f'{sid}.parquet');frames[sid]=f;gates[sid]=q
   if sid in caseids:
    day=str(cases.loc[cases.symbol.eq(sid),'anchor'].iloc[0]);re=gate(f.loc[:day].copy());pd.testing.assert_frame_equal(re,q.loc[:day],check_exact=True);prefixes.append(dict(symbol=sid,cutoff=day,rows=len(re),passed=True))
   h=q.loc[START:END];stats.append(dict(group=group,symbol=sid,rows=len(h),ordering_days=int(h.ordering.sum()),rising_days=int(h.rising.sum()),gate_days=int(h.gate.sum())))
 pd.DataFrame(stats).to_csv(diag/'daily-gate-counts.csv',index=False)
 cf=pd.read_csv(LER/'analysis-v1/campaigns.csv');cf=cf[cf.policy.eq('I')&cf.scenario.eq('base')].copy();cf['gate']=[bool(gates[r.symbol].loc[r.decision_day,'gate']) for r in cf.itertuples()]
 cf.to_csv(diag/'old-I-trades-labelled.csv',index=False);summary=[]
 for group in GROUPS:
  for label,part in [('all',cf[cf.group.eq(group)]),('pass',cf[cf.group.eq(group)&cf.gate]),('blocked',cf[cf.group.eq(group)&~cf.gate])]:
   cl=part[part.closed];tails=cl[cl.tail_closed];loss=cl[cl.net_pnl<0]
   summary.append(dict(group=group,subset=label,cycles=len(part),closed=len(cl),winners=int((cl.net_pnl>0).sum()),tails=len(tails),tail_pnl=float(tails.net_pnl.sum()),all_loss=float(-loss.net_pnl.sum()),ordinary_pnl=float(cl.loc[~cl.tail_closed,'net_pnl'].sum()),open_pnl=float(part.loc[~part.closed,'net_pnl'].sum()),fixed_old_path_only=True))
 pd.DataFrame(summary).to_csv(diag/'old-I-filter-attribution.csv',index=False)
 for _,z in cases.iterrows():
  f=frames[z.symbol];q=gates[z.symbol];day=pd.Timestamp(z.anchor);i=f.index.get_loc(day);d=f.iloc[max(0,i-80):i+81];a=q.loc[d.index]
  fig,(ax,vol)=plt.subplots(2,1,figsize=(12,6.5),sharex=True,gridspec_kw={'height_ratios':[4,1]});colors=np.where(d.close>=d.open,'#bd4e4b','#2b897c');ax.vlines(d.index,d.low,d.high,colors=colors,lw=.7);ax.vlines(d.index,d.open,d.close,colors=colors,lw=2.2);vol.bar(d.index,d.volume/1e6,color=colors,width=1)
  for n,c in [(9,'#216ca7'),(21,'#d98729'),(50,'#7d66ad')]:ax.plot(d.index,a['ema'+str(n)],color=c,lw=1.2,label='EMA'+str(n))
  for ok,c,marker in [(True,'#216b55','^'),(False,'#b94b48','x')]:
   sel=d.IX.astype(bool)&a.gate.eq(ok);ax.scatter(d.index[sel],d.high[sel]*1.025,color=c,marker=marker,s=28,label='Original I event '+('passes' if ok else 'blocked'))
  eo=d.e0_entered.astype(bool);ax.scatter(d.index[eo],d.low[eo]*.975,marker='o',facecolors='none',edgecolors='#777',s=25,label='E0 structure starts (not all candidates)')
  for x in [ax,vol]:x.axvline(day,color='#345a7b',ls='--');x.grid(alpha=.15)
  ax.legend(fontsize=7,ncol=3);ax.set_title(f'{z["case"]} {z.symbol} | gate only at entry, never an exit | no actual fills');vol.set_ylabel('Vol / 1e6');fig.tight_layout();fig.savefig(charts/(z['case']+'.png'),dpi=125);plt.close(fig)
 for k,groups in enumerate([['SEMI','COMM'],['DRUG','BANK']],1):
  sheet=Image.new('RGB',(2160,780),'white')
  for row,g in enumerate(groups):
   for col,role in enumerate(['strong','middle','weak']):
    im=Image.open(charts/(g+'_'+role+'.png'));im.thumbnail((720,390));sheet.paste(im,(col*720,row*390))
  sheet.save(charts/f'contact-{k}.png')
 for p in [HERE/'PROTOCOL.md',Path(__file__),HERE/'code/gate_common.py',SEC/'scope.json',VIDEO/'raw/cases.csv',LER/'analysis-v1/campaigns.csv']:sources[str(p.relative_to(ROOT))]=sha(p)
 write(HERE/'preparation.json',dict(recorded_at=now(),economic_accounts=0,sources=sources,files={str(p.relative_to(HERE)):sha(p) for p in out.glob('*.parquet')},prefixes=prefixes,gate_equal_verified_video_EMA=True,old_I_labelled_cycles=len(cf),rules='EMA9>21>50 and each greater than preceding observation, source-segment reset; entry-only'))
 print(pd.DataFrame(summary).to_string(index=False),flush=True)

if __name__=='__main__':main()
