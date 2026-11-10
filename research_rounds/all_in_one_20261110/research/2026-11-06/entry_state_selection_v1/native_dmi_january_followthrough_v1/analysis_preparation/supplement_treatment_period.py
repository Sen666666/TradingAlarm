"""Read sealed analysis CSVs; no account, market context, or strategy run."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import csv,json,hashlib,ast,argparse
import numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');Z=D(0)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str,allow_nan=False))
def writecsv(p,rows):
 if not rows:p.write_text('');return
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def readcsv(p):return list(csv.DictReader(p.open()))
def stat(rr,layer=False):
 p=[D(r['pnl']) for r in rr];w=[v for v in p if v>0];lo=[v for v in p if v<0];mw=sum(w,Z)/len(w) if w else None;ml=sum(lo,Z)/len(lo) if lo else None;tt=[r for r in rr if D(r['pnl'])/D(r['buy_cost'])>=D('.30')]
 return dict(n=len(p),wins=len(w),losses=len(lo),flat=len(p)-len(w)-len(lo),win_rate=len(w)/len(p) if p else None,mean_win=mw,mean_loss=ml,payoff_ratio=mw/-ml if mw and ml else None,net_pnl=sum(p,Z),fee_net_30pct_tails=len(tt),fee_net_30pct_tail_pnl=sum((D(r['pnl']) for r in tt),Z),denominator='First actual BUY layer cost only' if layer else 'Every actual BUY gross and fee in full round, including ADD')
def main(path):
 inputs={str(path/n):sha(path/n) for n in ['SUMMARY.json','ALL_ROUNDS.csv','ALL_LAYERS.csv','JANUARY_FIRST_BUY_LAYERS.csv','JANUARY_IDENTITY_COMPARISON.csv','OUTPUT_SHA256.json']}
 sealed=read(path/'OUTPUT_SHA256.json')
 for n in ['SUMMARY.json','ALL_ROUNDS.csv','ALL_LAYERS.csv','JANUARY_FIRST_BUY_LAYERS.csv','JANUARY_IDENTITY_COMPARISON.csv']:assert sha(path/n)==sealed[n]
 out=path/'treatment_period_supplement';out.mkdir(exist_ok=True);assert not any(out.iterdir()),'supplement overwrite forbidden';src=read(path/'SUMMARY.json');rr=readcsv(path/'ALL_ROUNDS.csv');ll=readcsv(path/'ALL_LAYERS.csv');stats={};scoperounds=[];scopelayers=[];tailcomp=[];deltas=[];janfirsttails=[]
 for year in src['analyzed_DMI_branches']:
  branches=['PVR_ORIGINAL','DMI_FROM_'+year+'JAN'];birth=year+'-01-01';by={}
  for branch in branches:
   q=[r for r in rr if r['account']==branch and r['opened'][:10]>=birth];ids={r['round_id'] for r in q};l=[r for r in ll if r['account']==branch and r['round_id'] in ids and r['initial_layer']=='True'];c=[r for r in q if r['closed']];lc=[r for r in l if r['closed']];o=[r for r in q if not r['closed']]
   assert len(q)==len(l)
   stats[branch+'_'+year]=dict(account=branch,scope_start=birth,as_of='2026-05-15',new_rounds=len(q),unique_stocks=len({r['sid'] for r in q}),closed_rounds=stat(c),closed_first_BUY_layers=stat(lc,True),open_rounds=len(o),open_marked_PnL=sum((D(r['pnl']) for r in o),Z),open_first_BUY_layers=len(l)-len(lc),first_layer_closed_round_still_open=sum(bool(r['closed']) and any(z['round_id']==r['round_id'] and not z['closed'] for z in q) for r in l),closed_bookkeeping_UNKNOWN=0,external_tradability_and_dividend_payout='UNKNOWN, retained rather than excluded',total_new_round_marked_PnL=sum((D(r['pnl']) for r in q),Z))
   by[branch]={(r['sid'],r['opened']):r for r in q};scoperounds.extend(dict(treatment_start=birth,**r) for r in q);scopelayers.extend(dict(treatment_start=birth,**r) for r in l)
  p,d=[by[b] for b in branches]
  for key in sorted(set(p)|set(d)):
   row=dict(treatment_start=birth,sid=key[0],opened=key[1],presence='BOTH' if key in p and key in d else 'DMI_ONLY' if key in d else 'PVR_ONLY')
   for tag,m in [('PVR',p),('DMI',d)]:
    r=m.get(key);row[tag+'_state']='ABSENT' if r is None else 'CLOSED' if r['closed'] else 'RIGHT_CENSORED';row[tag+'_pnl']=r['pnl'] if r else None;row[tag+'_return']=r['return_on_all_buy_cost'] if r else None;row[tag+'_initial_kind']=r['initial_kind'] if r else None;row[tag+'_tail30']=bool(r and r['closed'] and D(r['pnl'])/D(r['buy_cost'])>=D('.30'))
   row['tail_change']='BOTH_TAIL' if row['PVR_tail30'] and row['DMI_tail30'] else 'DMI_ONLY_OBSERVED_TAIL' if row['DMI_tail30'] else 'PVR_ONLY_OBSERVED_TAIL' if row['PVR_tail30'] else 'NEITHER_TAIL'
   tailcomp.append(row)
  groups=[('BEFORE_TREATMENT',lambda r:r['opened'][:10]<birth),('JANUARY_TREATMENT_COHORT',lambda r:r['opened'].startswith(year+'-01')),('AFTER_JANUARY_NEW_ROUNDS',lambda r:r['opened'][:10]>year+'-01-31')]
  diff=Z
  for group,test in groups:
   vals={branch:sum((D(r['pnl']) for r in rr if r['account']==branch and test(r)),Z) for branch in branches};delta=vals[branches[1]]-vals[branches[0]];diff+=delta;deltas.append(dict(treatment_start=birth,group=group,DMI_minus_PVR_marked_PnL=delta,note='Group difference only; before-treatment lifetime common-prefix PnL cancels. Not a standalone calendar contribution or isolated causal effect.'))
  assert abs(diff-(D(src['full_accounts'][branches[1]]['end_nav'])-D(src['full_accounts'][branches[0]]['end_nav'])))<D('1e-8')
 janfirsttails=[r for r in readcsv(path/'JANUARY_FIRST_BUY_LAYERS.csv') if r['closed'] and D(r['pnl'])/D(r['buy_cost'])>=D('.3')]
 writecsv(out/'TREATMENT_PERIOD_ROUNDS.csv',scoperounds);writecsv(out/'TREATMENT_PERIOD_FIRST_BUY_LAYERS.csv',scopelayers);writecsv(out/'TREATMENT_PERIOD_IDENTITY_AND_TAIL_COMPARISON.csv',tailcomp);writecsv(out/'NAV_DIFFERENCE_BY_ROUND_ENTRY_PERIOD.csv',deltas);writecsv(out/'JANUARY_FIRST_BUY_LAYER_TAIL_IDENTITIES.csv',janfirsttails)
 save(out/'SUMMARY.json',dict(economic_runs=0,sources=inputs,stats=stats,tail_changes={year:dict(Counter(r['tail_change'] for r in tailcomp if r['treatment_start']==year+'-01-01')) for year in src['analyzed_DMI_branches']},scope='First actual BUY opened on or after branch treatment start, excluding inherited prior years',unknown_and_censoring='Open rounds never enter closed win rates or >=30% tail counts; external data unknown is not silently excluded'))
 def money(x):return 'NA' if x is None else f'{float(x):,.2f}'
 def per(x):return 'NA' if x is None else f'{float(x)*100:.2f}%'
 def st(q):return f"{q['wins']}胜/{q['losses']}负/{q['flat']}平，分母{q['n']}；胜率{per(q['win_rate'])}，均赢{money(q['mean_win'])}、均亏{money(q['mean_loss'])}，赔率{money(q['payoff_ratio'])}，净额{money(q['net_pnl'])}，完整≥30%费后尾部{q['fee_net_30pct_tails']}个/净{money(q['fee_net_30pct_tail_pnl'])}"
 text=['# 处理期全部新开round补充','只读已封存分析CSV，经济运行0次。2026从实际首BUY opened≥2026-01-01筛选，不包含继承的2022—2025首BUY。2022分支则从2022-01-01筛选。各臂截至2026-05-15；每一同股重入仍为独立round。']
 for k,c in stats.items():
  text.extend(['\n## '+k,f"新开{c['new_rounds']}round，涉及{c['unique_stocks']}股。",'完整闭合round：'+st(c['closed_rounds'])+'。','首BUY层独立闭合：'+st(c['closed_first_BUY_layers'])+'。',f"未闭round {c['open_rounds']}个、标记净额{money(c['open_marked_PnL'])}；首层未闭{c['open_first_BUY_layers']}个，首层已闭但round未闭{c['first_layer_closed_round_still_open']}个。所有新round闭合+未闭合标记净额{money(c['total_new_round_marked_PnL'])}。闭合账目UNKNOWN=0；外部可交易性/股息付款证据UNKNOWN不据此剔除样本。"])
 text.append('\n## 完整尾部的同sid+opened身份变化')
 for y in src['analyzed_DMI_branches']:
  cc=[r for r in tailcomp if r['treatment_start']==y+'-01-01'];counts=Counter(r['tail_change'] for r in cc);text.append(f"- {y}：双方同身份均为尾部{counts['BOTH_TAIL']}，仅DMI观察到尾部{counts['DMI_ONLY_OBSERVED_TAIL']}，仅PVR观察到尾部{counts['PVR_ONLY_OBSERVED_TAIL']}。后两项包括一臂缺席/另一臂未闭或未达阈值，明细状态明确列示。")
  for r in cc:
   if r['tail_change'] not in ['NEITHER_TAIL','BOTH_TAIL']:text.append(f"  - {r['tail_change']} {r['sid']} {r['opened']}：PVR={r['PVR_state']}, 净{money(r['PVR_pnl'])}, 回报{per(r['PVR_return'])}；DMI={r['DMI_state']}, 净{money(r['DMI_pnl'])}, 回报{per(r['DMI_return'])}。")
 text.append('\n## 为什么一月cohort和全账户可以相反')
 for r in deltas:text.append(f"- {r['treatment_start']} {r['group']}：DMI−PVR的闭合+期末标记净额差{money(r['DMI_minus_PVR_marked_PnL'])}。三项相加严格等于末NAV差；共同处理前历史相消，非独立因果归因。")
 text.extend(['\n## 一月首BUY层尾部身份','首层尾部与完整round尾部不是同一单位，不能混计。'])
 for r in janfirsttails:text.append(f"- {r['account']} cohort{r['cohort']} {r['sid']} {r['opened']} → {r['closed']}：kind={r['kind']}，首层净{money(r['pnl'])}，首层费后{per(r['return_on_all_buy_cost'])}。")
 text.append('\n同sid+opened也可能对应不同native角色、数量和后续资金路径，身份比较不代表相同处理的因果配对。002859的2026一月同日期首BUY即为例：PVR为add 500股，3/20 CP1_add_protection闭合；DMI为core 100股，截至5/15未闭。该未闭标记即使超过30%仍不是完整尾部。')
 (out/'REPORT_SUPPLEMENT.md').write_text('\n'.join(text)+'\n')
 for p,h in inputs.items():assert sha(Path(p))==h
 save(out/'OUTPUT_SHA256.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(dict(stats=stats,tail_changes={year:dict(Counter(r['tail_change'] for r in tailcomp if r['treatment_start']==year+'-01-01')) for year in src['analyzed_DMI_branches']},deltas=deltas),ensure_ascii=False,default=str))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);args=ap.parse_args();main(args.analysis)
