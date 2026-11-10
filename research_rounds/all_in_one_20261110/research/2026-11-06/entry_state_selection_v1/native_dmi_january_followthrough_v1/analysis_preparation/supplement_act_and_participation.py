"""Pure CSV-derived actual ACT and holding-state diagnostics; no market/strategy run."""
from pathlib import Path
from decimal import Decimal as D
import csv,json,hashlib,argparse

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def rows(p):return list(csv.DictReader(p.open()))
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def writecsv(p,rr):
 if not rr:p.write_text('');return
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rr for k in r)));w.writeheader();w.writerows(rr)
def main(path):
 names=['DAILY_EQUITY_RISK.csv','2024_0924_ACTUAL_EARLY_PARTICIPATION.csv','CASE_ACTUAL_TRADES.csv','SUMMARY.json'];seal=read(path/'OUTPUT_SHA256.json');sources={str(path/n):sha(path/n) for n in names}
 for n in names:assert seal[n]==sha(path/n)
 out=path/'ACT_and_924_supplement';out.mkdir(exist_ok=False);dd=rows(path/names[0]);pp=rows(path/names[1]);tt=rows(path/names[2]);labels=sorted({r['account'] for r in dd});annual=[];segments=[];audit=[];p924=[];differences=[]
 by={a:{r['day']:r for r in dd if r['account']==a} for a in labels}
 def on(r):return r['ACT_on']=='True'
 def flat(r):return int(r['stock_count'])==0
 for a in labels:
  seq=sorted(by[a].values(),key=lambda r:r['day'])
  for y in sorted({r['day'][:4] for r in seq}):
   q=[r for r in seq if r['day'].startswith(y)];annual.append(dict(account=a,year=y,closes=len(q),ACT_on=sum(on(r) for r in q),ACT_off=sum(not on(r) for r in q),actual_flat=sum(flat(r) for r in q),actual_held=sum(not flat(r) for r in q),off_and_flat=sum(not on(r) and flat(r) for r in q),on_but_flat=sum(on(r) and flat(r) for r in q),off_but_held=sum(not on(r) and not flat(r) for r in q)))
  for kind,test in [('ACT_OFF',lambda r:not on(r)),('ACT_OFF_AND_ACTUAL_FLAT',lambda r:not on(r) and flat(r)),('ACTUAL_FLAT',flat)]:
   current=[]
   def emit():
    if current:segments.append(dict(account=a,state=kind,start=current[0]['day'],end=current[-1]['day'],closes=len(current),NAV_unique=len({D(r['nav']) for r in current}),NAV_first=current[0]['nav'],NAV_last=current[-1]['nav']))
   for r in seq:
    if test(r):current.append(r)
    else:emit();current=[]
   emit()
  q=[r for r in seq if '2023-07-31'<=r['day']<='2024-04-30'];audit.append(dict(account=a,start='2023-07-31',end='2024-04-30',closes=len(q),ACT_on=sum(on(r) for r in q),actual_held=sum(not flat(r) for r in q),NAV_unique=len({D(r['nav']) for r in q}),NAV_first=q[0]['nav'],NAV_last=q[-1]['nav']))
  q=[r for r in pp if r['account']==a];p924.append(dict(account=a,early_start='2024-09-24',early_end='2024-10-08',sessions=6,descriptive_scope_stocks=len(q),actual_held_stocks=sum(r['participated']=='True' for r in q),held_previous_20240923=sum(int(r['held_previous_close'])>0 for r in q),BUY_fills=sum(int(r['early_BUY_fills']) for r in q),new_0_to_position_rounds=sum(int(r['early_NEW_rounds']) for r in q),held_ADD_fills=sum(int(r['early_ADD_fills']) for r in q),other_buy_while_held=sum(int(r['early_OTHER_buy_while_held']) for r in q),native_kind_ADD_fills=sum(int(r['early_native_kind_ADD_fills']) for r in q),new_round_native_kind_ADD=sum(int(r['early_new_round_native_kind_ADD']) for r in q)))
 for a in labels:
  if a=='PVR_ORIGINAL':continue
  start='2026-01-01' if a=='DMI_FROM_2026JAN' else '2022-01-01';days=sorted(d for d in by[a] if d>=start);p=by['PVR_ORIGINAL'];q=by[a]
  differences.append(dict(account=a,scope_start=start,closes=len(days),ACT_different=sum(on(p[d])!=on(q[d]) for d in days),PVR_ON_DMI_OFF=sum(on(p[d]) and not on(q[d]) for d in days),PVR_OFF_DMI_ON=sum(not on(p[d]) and on(q[d]) for d in days),flat_state_different=sum(flat(p[d])!=flat(q[d]) for d in days)))
 newtrades=[r for r in tt if r['case']=='RALLY_2024' and '2024-09-24'<=r['at'][:10]<='2024-10-08' and r['side']=='buy'];writecsv(out/'ANNUAL_ACT_AND_ACTUAL_FLAT.csv',annual);writecsv(out/'CONTIGUOUS_STATE_INTERVALS.csv',segments);writecsv(out/'SPECIFIED_182_CLOSE_WINDOW.csv',audit);writecsv(out/'ACT_PATH_DIFFERENCES.csv',differences);writecsv(out/'2024_0924_PARTICIPATION_SUMMARY.csv',p924);writecsv(out/'2024_0924_ACTUAL_BUY_EVENTS.csv',newtrades)
 text=['# 原ACT反馈与924实际参与补充','只读最终封存daily派生；经济运行0。未新增ACT门、参数、UNKNOWN锁或任何策略修改。排序改变成交、数量、费用和收益路径后，可通过未改动的原ACT反馈改变开关轨迹。最终权益差不能直接解释成个股质量或入场排序的独立优势。','\n## 逐年ACT与实际空仓','ACT按每个CLOSE记录，空仓按实际stock_count=0；ACT关闭当天仍可能等待次日退出，因此两列不能混为一谈。2026分支2022—2025为原PVR继承历史。','|账户|年|CLOSE|ACT开|ACT关|实际空仓|关且空仓|开但空仓|关但有仓|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
 for r in annual:text.append('|'+ '|'.join(str(r[k]) for k in ['account','year','closes','ACT_on','ACT_off','actual_flat','off_and_flat','on_but_flat','off_but_held'])+'|')
 text.append('\n## 已指出的182个CLOSE区间')
 for r in audit:text.append(f"- {r['account']}，{r['start']}至{r['end']}：{r['closes']} CLOSE，ACT开{r['ACT_on']}，实际有仓{r['actual_held']}，NAV唯一值{r['NAV_unique']}个（{r['NAV_first']}→{r['NAV_last']}）。")
 for r in differences:text.append(f"- {r['account']}处理期ACT与PVR不同{r['ACT_different']}天：PVR开/DMI关{r['PVR_ON_DMI_OFF']}天，PVR关/DMI开{r['PVR_OFF_DMI_ON']}天；实际空仓状态不同{r['flat_state_different']}天。")
 text.append('\n## 924实际持有、新开和持有中ADD')
 for r in p924:text.append(f"- {r['account']} 9/24至10/8六交易日实际持有{r['actual_held_stocks']}股，9/23已有{r['held_previous_20240923']}股。实际BUY {r['BUY_fills']}笔=新开{r['new_0_to_position_rounds']}轮+持有中ADD {r['held_ADD_fills']}笔+其他持有中BUY {r['other_buy_while_held']}笔。native kind=add共{r['native_kind_ADD_fills']}笔，其中{r['new_round_native_kind_ADD']}笔属于新开首BUY，不重复计为持有中ADD。")
 text.append('这是真实交易/库存分母，不使用后来MFE或上涨标签判定当时可买、参与或赢家。各账户观察股票集合基于9/23—10/15实际持仓或交易，比较身份时另用并集，未声称统一机会池命中率。具体每笔代码、时间、股数、native kind及生命周期分类见2024_0924_ACTUAL_BUY_EVENTS.csv。')
 (out/'REPORT_ACT_AND_924.md').write_text('\n'.join(text)+'\n');save(out/'SUMMARY.json',dict(economic_runs=0,annual=annual,specified_182_close_window=audit,ACT_path_differences=differences,participation_924=p924,sources=sources))
 for p,h in sources.items():assert sha(Path(p))==h
 save(out/'OUTPUT_SHA256.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(dict(annual=annual,specified=audit,differences=differences,participation=p924),ensure_ascii=False))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);args=ap.parse_args();main(args.analysis)
