"""Paired scientific figures; trajectories are qualification, never account NAV."""
from common_rc1 import *
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from html import escape
FONT=FontProperties(fname='/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
def plot(sid,z,c,path):
 a=z.loc[c['start']:c['end']];ev=pd.read_parquet(HERE/'inputs'/sid/'evidence.parquet').loc[a.index]
 fig,axs=plt.subplots(6,1,figsize=(14,11.5),sharex=True,gridspec_kw={'height_ratios':[3,0.8,1.3,1,1.2,1]})
 axs[0].plot(a.index,a.close,color='#283e48',lw=.9);axs[0].set_yscale('log');axs[0].set_ylabel('price (log)')
 old=a.ix_entered.eq(1);new=a.new_only_entry
 axs[0].scatter(a.index[old],a.loc[old,'close'],marker='^',s=25,facecolors='none',edgecolors='#9b7462',label='original IX start')
 axs[0].scatter(a.index[new],a.loc[new,'close'],marker='o',s=35,facecolors='#087c95',edgecolors='white',linewidth=.4,label='IX-RC1 added start',zorder=4)
 axs[0].legend(fontsize=8,ncol=2,loc='upper left');axs[0].set_title(NAMES[sid]+'｜'+c['id']+'：原IX与渐进恢复RC1（无资金回测）',fontproperties=FONT,loc='left',fontsize=12)
 axs[1].bar(a.index,ev.strength_activity,width=1,color='#98a8b0');axs[1].set_ylabel('V / prev21')
 axs[2].step(a.index,a.old_score,where='post',color='#a99b8f',lw=.8,label='original G1',alpha=.9);axs[2].step(a.index,a.new_score,where='post',color='#067d95',lw=.85,label='G1 + RC1');axs[2].set_ylim(-85,110);axs[2].legend(fontsize=8,ncol=2,loc='upper left')
 context=a.rc_context.map({'down':-1,'mixed':0,'up':1});axs[3].step(a.index,context,color='#9ba8ae',lw=.65,label='causal long background')
 r=a.rc_receipt;u=a.new_rc_only_fresh;weak=r&a.rc_context.eq('down')
 axs[3].scatter(a.index[r],context[r],color='#b2b7b8',s=10,label='local receipt')
 axs[3].scatter(a.index[u],context[u],color='#087c95',s=17,label='new warm-usable receipt')
 axs[3].scatter(a.index[weak],context[weak],color='#a75d72',marker='x',s=19,label='down-background local rebound')
 axs[3].set_yticks([-1,0,1],['down','mixed','up']);axs[3].set_ylim(-1.6,2.1);axs[3].legend(fontsize=7,ncol=2,loc='upper left')
 axs[4].plot(a.index,a.mu21*1e4,lw=.65,color='#cf854f',label='EW21 bp/day');axs[4].plot(a.index,a.mu63*1e4,lw=.75,color='#699166',label='EW63 bp/day');axs[4].plot(a.index,a.mu126*1e4,lw=.9,color='#457e91',label='EW126 bp/day');axs[4].axhline(0,color='gray',lw=.4);axs[4].legend(fontsize=7,ncol=3,loc='upper left')
 axs[5].step(a.index,a.ix_target*.65,where='post',color='#9b7462',lw=.9,label='original IX qualified');axs[5].step(a.index,a.nix_target*.65+1,where='post',color='#087c95',lw=.9,label='IX-RC1 qualified');axs[5].set_yticks([.3,1.3],['IX','IX-RC1']);axs[5].set_ylim(-.15,1.9);axs[5].legend(fontsize=8,ncol=2,loc='upper left')
 for ax in axs:ax.grid(alpha=.15)
 fig.text(.035,.008,'局部恢复不等于长期反转；下降背景的新增收据最多为修复。旧IX快速通道不改，仍可能参与失败反弹。资格段不是实际成交。',fontproperties=FONT,fontsize=9)
 fig.tight_layout(rect=(0,.025,1,1));fig.savefig(path,dpi=115);plt.close(fig)

def main():
 verify();out=HERE/'report';out.mkdir(exist_ok=False);(out/'figures').mkdir();cases=read(M1/'report/figure-manifest.json');traces={sid:pd.read_parquet(HERE/'analysis'/f'{sid}-trace.parquet') for sid in NAMES}
 for c in cases:plot(c['symbol'],traces[c['symbol']],c,out/'figures'/f"{c['id']}.png")
 windows=pd.read_csv(HERE/'analysis/window-summary.csv');events=pd.read_parquet(HERE/'analysis/local-receipts.parquet')
 # Browser payload includes only finite display values; full journals remain local files.
 display=[]
 for r in events.itertuples():
  display.append(dict(symbol=r.symbol,name=r.name,date=r.date,context=r.context,tier=r.tier,close=r.close,anchor=r.anchor,below_pre_high=r.below_pre_high,old_grade=r.old_grade,new_grade=r.new_grade,added_buy_event=r.added_buy_event,new_only_entry=r.new_only_entry,ret21=r.ret21,anchor_broken21=r.anchor_broken21,complete21=r.complete21))
 payload=dict(cases=cases,windows=windows.to_dict('records'),events=display)
 write(out/'data.json',payload);write(out/'figure-manifest.json',cases)
 template=(HERE/'code/report_rc1.html').read_text();options=''.join('<option value="'+escape(c['id'])+'">'+escape(NAMES[c['symbol']]+' / '+c['id'])+'</option>' for c in cases)
 (out/'index.html').write_text(template.replace('OPTIONS',options).replace('EMBEDDED_DATA',json.dumps(clean(payload),ensure_ascii=False,allow_nan=False)))
 write(out/'build.json',dict(recorded_at=now(),figures=len(cases),accounts=0,external_resources=0));print(dict(figures=len(cases)),flush=True)
if __name__=='__main__':main()
