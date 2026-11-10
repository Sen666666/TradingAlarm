from common import *
from local_model import receipts,shadow
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def main():
 out=HERE/'signals';out.mkdir(exist_ok=False);charts=HERE/'model-charts';charts.mkdir(exist_ok=False)
 scope=read(SEC/'scope.json');stats=[];sources={};cases=pd.read_csv(HERE/'raw/cases.csv');total=0
 for sid in sorted(scope['meta']):
  p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p);r=receipts(f);a=shadow(f,r,True);b=shadow(f,r,False);z=r.join(a.add_prefix('shadow_')).join(b.add_prefix('lh_shadow_'));z.to_parquet(out/f'{sid}.parquet');sources[str(p.relative_to(ROOT))]=sha(p)
  total+=int(r.receipt.sum());stats.append(dict(symbol=sid,rows=len(f),local_receipts=int(r.receipt.sum()),new_dates_not_old_IX=int((r.receipt&~f.IX).sum()),old_IX_events=int(f.IX.sum()),shadow_entries=int(a.entered.sum()),shadow_local_exits=int(a.exit_reason.eq('local').sum())))
  for row in cases[cases.symbol.eq(sid)].to_dict('records'):
   d=pd.Timestamp(row['anchor']);i=f.index.get_loc(d);g=f.iloc[max(0,i-80):i+81];rr=r.loc[g.index];aa=a.loc[g.index]
   fig,(ax,v)=plt.subplots(2,1,figsize=(12,6.5),sharex=True,gridspec_kw={'height_ratios':[4,1]});colors=np.where(g.close>=g.open,'#be4b48','#2c8577');ax.vlines(g.index,g.low,g.high,colors=colors,linewidth=.7);ax.vlines(g.index,g.open,g.close,colors=colors,linewidth=2.1);v.bar(g.index,g.volume/1e6,color=colors,width=1)
   ax.plot(g.index,g.e0_floor.where(g.e0_target),'#b89b68',label='E0 support (resets across structures)',alpha=.8);ax.plot(g.index,aa.floor,'#274e75',linewidth=1.5,label='LER signal-only protection')
   sel=rr.receipt;ax.scatter(g.index[sel],g.loc[sel,'low']*.985,marker='^',s=23,color='#2762a0',label='New local receipt')
   sell=aa.exited;ax.scatter(g.index[sell],g.loc[sell,'close'],marker='x',s=40,color='#c34459',label='Signal-only exit')
   for x in [ax,v]:x.axvline(d,color='#718fa6',linestyle='--');x.grid(alpha=.15)
   ax.set_title(f"{row['case']} {sid} | signal sketch, no assumed execution");ax.legend(fontsize=7,loc='best');ax.set_ylabel('Signal price');v.set_ylabel('Vol / 1e6');fig.tight_layout();fig.savefig(charts/(row['case']+'.png'),dpi=120);plt.close(fig)
 pd.DataFrame(stats).to_csv(out/'summary.csv',index=False)
 sources.update({str(p.relative_to(ROOT)):sha(p) for p in list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'RULES.md',HERE/'RAW_REVIEW.md',HERE/'raw-freeze.json']})
 write(HERE/'model-freeze.json',dict(recorded_at=now(),economic_accounts=0,before_economic_results=True,rules='LER-01 v1, one candidate, no parameter search',source_sha256=sources,receipts=total,signal_files={str(p.relative_to(HERE)):sha(p) for p in out.glob('*.parquet')}))
 for part,groups in enumerate([['SEMI','COMM'],['DRUG','BANK']]):
  sheet=Image.new('RGB',(2160,780),'white')
  for row,group in enumerate(groups):
   for col,role in enumerate(['strong','middle','weak']):
    im=Image.open(charts/(group+'_'+role+'.png'));im.thumbnail((720,390));sheet.paste(im,(720*col,390*row))
  sheet.save(charts/f'contact-{part+1}.png')
 print(pd.DataFrame(stats).sum(numeric_only=True).to_dict(),flush=True)
if __name__=='__main__':main()
