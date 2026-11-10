from pathlib import Path
import json,gzip,hashlib,html,math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];SEC=ROOT/'research_rounds/sector-ix-i-20261026';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 out=HERE/'review-v1';out.mkdir(exist_ok=False);s=pd.read_csv(HERE/'analysis-v1/summary.csv');c=pd.read_csv(HERE/'analysis-v1/campaigns.csv');cl=pd.read_csv(HERE/'analysis-v1/structure-clusters.csv');curves=pd.read_csv(HERE/'analysis-v1/curves.csv');scope=read(SEC/'scope.json');meta={x['series_id']:x for x in read(OLD/'prepared-v2/manifest.json')['series']}
 cluster_summaries=[]
 for aid,g in cl.groupby('account'):
  row=s[s.account.eq(aid)].iloc[0];tail=g[g.tail_count>0];no=g[g.tail_count.eq(0)];complete=g[g.structure_ended&g.all_positions_closed]
  cluster_summaries.append(dict(account=aid,group=row.group,policy=row.policy,scenario=row.scenario,funded_E0_structures=len(g),multi_attempt_structures=int((g.attempts>1).sum()),max_attempts=int(g.attempts.max()),total_attempts=int(g.attempts.sum()),tail_structures=len(tail),tail_structure_all_trial_loss=float(tail.all_closed_loss.sum()),tail_structure_tail_pnl=float(tail.tail_pnl.sum()),tail_structure_net_pnl=float(tail.net_pnl.sum()),no_tail_structure_net_pnl=float(no.net_pnl.sum()),complete_structures=len(complete),unfinished_structures=len(g)-len(complete),all_structure_net_pnl=float(g.net_pnl.sum())))
  assert abs(g.net_pnl.sum()-(row.final_nav-1e6))<1e-6
 cs=pd.DataFrame(cluster_summaries);cs.to_csv(out/'structure-summary.csv',index=False)
 base=s[s.scenario.eq('base')].copy();base.to_csv(out/'base-summary.csv',index=False)
 comparisons=[]
 for g in ['SEMI','COMM','DRUG','BANK']:
  for scenario in ['base','cost2','delay1']:
   a=s[s.group.eq(g)&s.policy.eq('I')&s.scenario.eq(scenario)].iloc[0];b=s[s.group.eq(g)&s.policy.eq('LER')&s.scenario.eq(scenario)].iloc[0]
   comparisons.append(dict(group=g,scenario=scenario,I_return=a.net_return,LER_return=b.net_return,return_difference=b.net_return-a.net_return,I_drawdown=a.max_drawdown,LER_drawdown=b.max_drawdown,drawdown_difference=b.max_drawdown-a.max_drawdown,I_tail_pnl=a.tail_pnl,LER_tail_pnl=b.tail_pnl,I_ordinary_pnl=a.ordinary_pnl,LER_ordinary_pnl=b.ordinary_pnl,I_closed=a.closed,LER_closed=b.closed,I_exposure=a.mean_exposure,LER_exposure=b.mean_exposure))
 pd.DataFrame(comparisons).to_csv(out/'comparisons.csv',index=False)
 # Post-result explanation cases: every group gets its biggest tail structure
 # and worst net structure, both explicitly retrospective and never new rules.
 cases=[]
 for g in ['SEMI','COMM','DRUG','BANK']:
  q=cl[cl.group.eq(g)&cl.policy.eq('LER')&cl.scenario.eq('base')]
  for role,sort in [('tail','tail_pnl'),('loss','net_pnl')]:
   z=q.sort_values([sort,'first_entry','symbol'],ascending=[role=='loss',True,True]).iloc[0].to_dict();z['case']=g+'_'+role;cases.append(z)
 pd.DataFrame(cases).to_csv(out/'posthoc-cases.csv',index=False)
 for z in cases:
  sid=z['symbol'];f=pd.read_parquet(IX/'signals'/f'{sid}.parquet');f['seq']=f.groupby('segment_id',sort=False).e0_entered.cumsum();seg=str(z['source_segment']);seq=z['e0_seq'];mask=f.segment_id.astype(str).eq(seg)&f.seq.eq(seq)&(f.e0_target.astype(bool)|f.e0_exited.astype(bool));indices=np.flatnonzero(mask.to_numpy()&(f.index<=pd.Timestamp('2026-10-16')));assert len(indices)
  lo=max(0,indices[0]-20);hi=min(len(f),indices[-1]+8);d=f.iloc[lo:hi];d=d[d.index<=pd.Timestamp('2026-10-16')];factor=pd.read_parquet(OLD/'prepared-v2'/meta[sid]['files']['signal']['path'],columns=['adjustment_factor']).adjustment_factor
  a=c[c.account.eq(z['account'])&c.symbol.eq(sid)&c.source_segment.astype(str).eq(seg)&c.e0_seq.eq(seq)].sort_values('entry_at');obj=read(HERE/'accounts'/(z['account']+'.json'));bind={(x['sid'],x['first_fill_at']):x for x in obj['audit_log'] if x['kind']=='local_bound'};protected=pd.Series(np.nan,index=d.index)
  fig,(ax,v)=plt.subplots(2,1,figsize=(13,7),sharex=True,gridspec_kw={'height_ratios':[4,1]});colors=np.where(d.close>=d.open,'#be4b48','#2c8577');ax.vlines(d.index,d.low,d.high,colors=colors,linewidth=.7);ax.vlines(d.index,d.open,d.close,colors=colors,linewidth=2.2);v.bar(d.index,d.volume/1e6,color=colors,width=1)
  for num,(_,trade) in enumerate(a.iterrows(),1):
   ed=pd.Timestamp(trade.entry_at).tz_localize(None).normalize();xd=pd.Timestamp(trade.exit_at).tz_localize(None).normalize() if bool(trade.closed) else pd.Timestamp('2026-10-17');b=bind[sid,trade.entry_at];held=(d.index>=ed)&(d.index<xd);protected.loc[held]=np.maximum(d.loc[held,'e0_floor'].fillna(b['local_floor']),b['local_floor']);ep=trade.first_fill_price*float(factor.loc[ed]);ax.scatter([ed],[ep],marker='^',s=60,color='#245f9d');ax.annotate(str(num),(ed,ep),xytext=(3,-13),textcoords='offset points',fontsize=8)
   if bool(trade.closed):
    # Locate actual first sell corresponding to this independently audited cycle.
    sells=[x for x in obj['audit_log'] if x['kind']=='fill' and x['receipt']['side']=='sell' and x['receipt']['security_id']==sid and x['receipt']['at']==trade.exit_at]
    if sells:ax.scatter([xd],[float(sells[0]['price'])*float(factor.loc[xd])],marker='x',s=55,color='#bc3652')
  ax.plot(d.index,protected,'#2b527b',linewidth=1.5,label='Actual holding protection');ax.plot(d.index,d.e0_floor.where(d.e0_target.astype(bool)),'#b99553',alpha=.6,label='E0 support');ax.legend(fontsize=8)
  ax.set_title(f"{z['case']} {sid} | ACTUAL LER base, all {len(a)} attempts | net CNY {z['net_pnl']:,.0f}");ax.set_ylabel('Causal signal price');v.set_ylabel('Vol / 1e6')
  for aa in [ax,v]:aa.grid(alpha=.15)
  fig.tight_layout();fig.savefig(out/(z['case']+'.png'),dpi=120);plt.close(fig)
 # Full NAV comparison includes cash, costs and unfinished positions.
 fig,axes=plt.subplots(2,2,figsize=(14,9))
 for ax,g in zip(axes.flat,['SEMI','COMM','DRUG','BANK']):
  for policy,color in [('I','#a78b4b'),('LH','#599380'),('LER','#315f8d')]:
   q=curves[curves.group.eq(g)&curves.policy.eq(policy)&curves.scenario.eq('base')];ax.plot(pd.to_datetime(q.date),q.nav/1e6,label=policy,color=color)
  ax.set_title(g);ax.set_ylabel('NAV / 1,000,000');ax.grid(alpha=.18);ax.legend()
 fig.suptitle('Same pools and cash engine: I vs local-entry LH vs full LER');fig.tight_layout();fig.savefig(out/'nav-base.png',dpi=140);plt.close(fig)
 for part,groups in enumerate([['SEMI','COMM'],['DRUG','BANK']]):
  sheet=Image.new('RGB',(1560,1680),'white')
  for row,g in enumerate(groups):
   for col,role in enumerate(['tail','loss']):
    im=Image.open(out/(g+'_'+role+'.png'));im.thumbnail((780,840));sheet.paste(im,(col*780,row*840))
  sheet.save(out/f'actual-cases-{part+1}.png')
 def table(frame):return frame.to_html(index=False,border=0,float_format=lambda x:f'{x:,.4f}')
 body='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>A股局部入场/失效/再入有限检验</title><style>body{font:16px/1.65 system-ui;color:#263746;max-width:1500px;margin:30px auto;padding:0 25px}img{max-width:100%;height:auto}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px}td,th{padding:7px 10px;border-bottom:1px solid #ddd;white-space:nowrap}a{color:#245d8b}.note{padding:16px;background:#f1f5f8}</style><h1>A股局部入场、局部失效与再次入场</h1><p class="note">一个冻结候选。四固定池、每户100万元、28路径，其中4旧I基础控制、24新增经济。当前存续/分类快照、已见开发历史。低胜率允许，但必须评价全部失败、费用、尾部和未闭合权益。</p><p><a href="../CONCLUSION.md">完整结论</a> · <a href="../RULES.md">冻结规则</a> · <a href="../analysis-v1/accounting.json">独立核账</a> · <a href="../technical/prefix-receipt-v1.json">真实前缀</a></p><img src="nav-base.png"><h2>全部账户</h2><div class="scroll">'''
 body+=table(s)+'</div><h2>同一事前E0结构的全部实际尝试</h2><div class="scroll">'+table(cs)+'</div><h2>事后正反例：整个结构内每次尝试均保留</h2><p>按最大尾部与最差净损益选择解释例，不用于修改规则。</p>'
 for z in cases:body+=f"<h2>{html.escape(z['case'])} {html.escape(z['name'])}</h2><img src=\"{z['case']}.png\">"
 body+='<h2>先看原始量价，再看候选信号</h2>'
 for p in ['../raw/contact-1.png','../raw/contact-2.png','../model-charts-v1/contact-1.png','../model-charts-v1/contact-2.png']:body+=f'<img src="{p}">'
 body+='</html>';(out/'index.html').write_text(body)
 (out/'receipt.json').write_text(json.dumps({'passed':True,'all_account_cluster_PnL_reconciled':True,'posthoc_explanation_cases':8,'new_rules':0,'new_economic_runs':0,'code_sha256':sha(__file__)},ensure_ascii=False,indent=2)+'\n')
 print(base[['group','policy','net_return','max_drawdown','closed','win_rate','profit_factor','tail_count','tail_pnl','ordinary_pnl','open_pnl']].to_string(index=False));print(cs[cs.scenario.eq('base')].to_string(index=False))
if __name__=='__main__':main()
