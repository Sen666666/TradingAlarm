from common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

def main():
 out=HERE/'raw';out.mkdir(exist_ok=False)
 scope=read(SEC/'scope.json');cases=[];sources={}
 choices=[('2022-05-05','strong'),('2023-02-01','middle'),('2025-04-09','weak')]
 for group,ids in scope['groups'].items():
  frames={}
  for sid in ids:
   p=IX/'signals'/f'{sid}.parquet';f=pd.read_parquet(p,columns=['open','high','low','close','volume','segment_id']);frames[sid]=f;sources[str(p.relative_to(ROOT))]=sha(p)
  for day,role in choices:
   d=pd.Timestamp(day);candidates=[]
   for sid,f in frames.items():
    if d not in f.index:continue
    h=f.loc[f.index<d];seg=f.loc[d,'segment_id'];h=h[h.segment_id.eq(seg)]
    if len(h)<64:continue
    candidates.append((float(h.close.iloc[-1]/h.close.iloc[-64]-1),sid))
   candidates.sort();assert candidates,(group,day)
   pos={'strong':len(candidates)-1,'middle':len(candidates)//2,'weak':0}[role];ret,sid=candidates[pos];f=frames[sid];i=f.index.get_loc(d);g=f.iloc[max(0,i-80):i+81]
   case=group+'_'+role;c=dict(case=case,group=group,anchor=day,role=role,symbol=sid,name=scope['meta'][sid]['name'],past63_return=ret,eligible_count=len(candidates),ranking_position=pos,rows=len(g));cases.append(c)
   fig,(ax,v)=plt.subplots(2,1,figsize=(12,6.5),sharex=True,gridspec_kw={'height_ratios':[4,1]})
   colors=np.where(g.close>=g.open,'#be4b48','#2c8577');ax.vlines(g.index,g.low,g.high,colors=colors,linewidth=.8);ax.vlines(g.index,g.open,g.close,colors=colors,linewidth=2.5);v.bar(g.index,g.volume/1e6,color=colors,width=1)
   for a in [ax,v]:a.axvline(d,color='#32587b',linestyle='--');a.axvspan(d,g.index[-1],color='#718fa6',alpha=.07);a.grid(alpha=.15)
   ax.set_title(f'{case} {sid} | fixed anchor {day} | selection uses only pre-anchor prices');ax.set_ylabel('Causal signal price');v.set_ylabel('Vol / 1e6');fig.tight_layout();fig.savefig(out/(case+'.png'),dpi=120);plt.close(fig)
 pd.DataFrame(cases).to_csv(out/'cases.csv',index=False)
 sources.update({str((HERE/'PROTOCOL.md').relative_to(ROOT)):sha(HERE/'PROTOCOL.md'),str(Path(__file__).relative_to(ROOT)):sha(__file__),str((SEC/'scope.json').relative_to(ROOT)):sha(SEC/'scope.json')})
 write(HERE/'raw-freeze.json',dict(recorded_at=now(),before_candidate_results=True,selection='fixed dates, pre-anchor 63-return rank; no old fills or E0/G1 filtering',sha256=sources,cases=cases))
 for part,groups in enumerate([['SEMI','COMM'],['DRUG','BANK']]):
  sheet=Image.new('RGB',(2160,780),'white')
  for row,group in enumerate(groups):
   for col,(_,role) in enumerate(choices):
    im=Image.open(out/(group+'_'+role+'.png'));im.thumbnail((720,390));sheet.paste(im,(720*col,390*row))
  sheet.save(out/f'contact-{part+1}.png')
 print(pd.DataFrame(cases).to_string(index=False),flush=True)
if __name__=='__main__':main()
