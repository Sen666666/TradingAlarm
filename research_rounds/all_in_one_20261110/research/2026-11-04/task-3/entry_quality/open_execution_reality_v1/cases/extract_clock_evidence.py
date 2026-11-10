"""Saved nine original fills and one original rejection: execution-clock evidence."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,csv,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(l) for l in f] if lines else json.load(f)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp,Path)):return str(x)
 if hasattr(x,'item'):return x.item()
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')
base=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair';book=read(base/'B.json.gz',True);fund=read(base/'funding.jsonl.gz',True,True);dec={r['at'][:10]:r for r in book['decisions']};ids=[68,69,75,78,113,122,1994,2017,2039]
mp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/manifest.json');market=read(mp);raw={};records={}
for sid in ['000620.SZ','002583.SZ']:
 rec=next(r for r in market['series'] if r['series_id']==sid);p=Path(rec['raw']['path']);assert sha(p)==rec['raw']['sha256'];SRC[str(p)]=sha(p);f=pd.read_parquet(p);f['day']=f.trade_date.astype(str).str[:10];raw[sid]=f.set_index('day',drop=False);records[sid]=rec
rows=[];compact=[]
for lid in ids:
 t=next(t for t in book['trades'] if t['side']=='buy' and t['layer']==lid);sid=t['security_id'];d=t['signal_at'][:10];od=t['at'][:10];ai,fill=next((i,a) for i,a in enumerate(book['audit']) if a['kind']=='fill' and a['receipt']['receipt_id']==t['receipt_id']);ri,reserve=next((i,a) for i,a in enumerate(book['audit']) if a['kind']=='reserve' and a['order_id']==fill['order_id']);funding=next(a for a in fund if a.get('account')=='B' and a['sid']==sid and a['at']==reserve['at'] and a['result']=='reserved');role='core' if t['kind']=='core' else 'mobile';intent=next(a for a in dec[d]['intents'] if a['sid']==sid and a['role']==role);rb=raw[sid].loc[od];sig=raw[sid].loc[d]
 assert D(str(rb.open))==D(t['raw_open']);assert D(t['raw_open'])*D('1.0005')==D(t['price']);assert reserve['at']==t['at']==fill['receipt']['at']==funding['at'];assert reserve['decision_at']==t['signal_at'];assert reserve['known_open_funding'] is True;assert reserve['target_shares']==t['shares'];assert reserve['quote_source']==records[sid]['raw']['sha256']==fill['source'];assert ri<ai
 r=dict(layer=lid,sid=sid,role=role,signal_CLOSE=t['signal_at'],signal_day_raw_close=sig.close,signal_intent=intent,raw_OPEN_day=od,raw_OPEN=rb.open,raw_OPEN_source=records[sid]['raw'],raw_OPEN_read_clock='Runner.opening(at='+reserve['at']+') source phase; no separate per-read timestamp saved',
  OPEN_preview_route_clock='same opening(at) by source call order; successful result logged by reserve/funding',reserve_clock=reserve['at'],reserve_decision_at=reserve['decision_at'],known_open_funding=reserve['known_open_funding'],reserve_target_shares=reserve['target_shares'],fill_clock=fill['receipt']['at'],original_actual_fill_shares=t['shares'],fill_price=t['price'],raw_OPEN_plus_5bps=D(t['raw_open'])*D('1.0005'),fill_equality=True,
  quote_source=reserve['quote_source'],declared_source_close_available_time=records[sid].get('close_available_time'),quote_read_price_cutoff=t['signal_at'],exact_quote_object_known_at_in_saved_book=None,quote_known_at_evidence='DecisionQuote.read_price checks known_at<=the supplied prior signal cutoff; exact stored quote known_at is not in these saved audit rows',
  reserve_audit_index=ri,fill_audit_index=ai,original_reserve=reserve,original_fill_audit=fill,original_trade=t,original_funding=funding,
  exchange_order_send_timestamp=None,exchange_ack_timestamp=None,exchange_fill_timestamp=None,exchange_order_id=None,exchange_trade_id=None,missing_evidence='Only internal generated order/receipt IDs and research-ledger timestamps. No broker/exchange order/ACK/tick/fill reports in this saved chain.',scope='ORIGINAL_REALIZED_RESEARCH_LEDGER_FILL_ONLY_NO_NEW_RISK_CANDIDATE')
 rows.append(r);compact.append(dict(stock=sid,layer=lid,signal_CLOSE=t['signal_at'],signal_raw_close=sig.close,raw_OPEN=rb.open,reserve_at=reserve['at'],original_target=reserve['target_shares'],fill_at=t['at'],original_filled=t['shares'],fill_price=t['price'],OPEN_times_1_0005=r['raw_OPEN_plus_5bps'],decision_at_still_prior_CLOSE=reserve['decision_at'],known_open_funding=True))
save('NINE_ORIGINAL_EXECUTION_CLOCKS.json',rows)
with (O/'NINE_ORIGINAL_EXECUTION_CLOCKS.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(compact[0]));w.writeheader();w.writerows(compact)
# Original failed funding: no new target, order or fill is invented.
reject=next(r for r in fund if r.get('account')=='B' and r['sid']=='000620.SZ' and r['at']=='2022-01-21 09:30:00+08:00' and r['role']=='mobile');intent=next(r for r in dec['2022-01-20']['intents'] if r['sid']=='000620.SZ' and r['role']=='mobile');rb=raw['000620.SZ'].loc['2022-01-21'];assert not any(t['side']=='buy' and t['security_id']=='000620.SZ' and t['at'][:10]=='2022-01-21' for t in book['trades'])
rejectcase=dict(signal_CLOSE=dec['2022-01-20']['at'],original_intent=intent,next_OPEN=reject['at'],raw_OPEN_from_saved_native_bar=rb.open,source=records['000620.SZ']['raw'],code_preview_price_from_known_OPEN=D(str(rb.open))*D('1.0005'),preview_price_is_not_a_saved_fill=True,original_rejection=reject,original_order_or_fill_created=False,original_reserved_shares=None,original_filled_shares=None,quantity_attempt_trace='NOT_SAVED',clock_evidence='opening reads raw.open, calls preview, then route; this route-specific failure is logged after that read. Funding row itself does not include raw_OPEN or previous signal timestamp; linked to the original previous-session pending intent.')
save('ORIGINAL_KNOWN_OPEN_REJECTION_JAN20_21.json',rejectcase)
codefiles=dict(native_opening=W/'case-stage-ledger-20261031/v3/joint_v3.py',known_open_reserve=RR/'lot-risk-allocation-20261029/code/study.py',quote_cutoff_and_BuyOrder=RR/'rs-h1-execution-20261025/code/sector_account.py',native_daily_window=RR/'rs-h1-execution-20261025/code/history_runner.py',active_fast_market=RR/'temperature-sizing-20261026/code/fast_market.py')
for p in codefiles.values():SRC[str(p)]=sha(p)
save('SOURCE_MANIFEST.json',dict(sources=SRC,code_references=codefiles,script_sha256=sha(__file__),model_calls=0,new_accounts=0,new_risk_quantity_calculations=0))
lines=['# 原执行时钟：盈新6笔、海能达3笔','',
'这九笔是已保存研究账的原成交，不是新风险纸算数量或实盘成交。代码先在前一CLOSE保存信号/intent；次OPEN读取已知raw OPEN，再preview定量、route、reserve；随后成交代理按raw OPEN加5bp写fill。九笔均逐Decimal核同该价格公式。','',
'|股票/层|signal CLOSE|前CLOSE raw价|nextOPEN rawO|原route/reserve时钟|原target/filled|fill时钟/price|','|---|---|---:|---:|---|---:|---|']
for r in compact:lines.append(f'|{r["stock"]}/{r["layer"]}|{r["signal_CLOSE"]}|{r["signal_raw_close"]}|{r["raw_OPEN"]}|{r["reserve_at"]}|{r["original_target"]}/{r["original_filled"]}|{r["fill_at"]} / {r["fill_price"]}|')
lines+=['','## 先看OPEN后仍可拒绝：盈新1/20→1/21','',
'1/20 15:10原mobile intent：cap5900、gross budget19567.320460227788090、调整线3.4053609072125717。1/21原raw OPEN3.28，源码preview对应买价3.281640；随后09:30 funding原记录为cash_or_original_reserve,sector_capital，没有reserve/fill。3.281640是源码公式对应预览价，不是假造实际成交价，尝试过的逐个股数没有保存。1/21下午另一个新信号到1/24才成交，两个时钟不可混。','',
'## 看14元OPEN后定量：海能达10/21→10/22','',
'10/21原收盘raw13.15、原intent cap1100、gross budget14575.426586994384950；10/22 raw OPEN14。原reserve实际target1000，原fill1000，价格14.00700。reserve.at与fill.at均为程序09:30，reserve.decision_at仍是10/21 15:10；known_open_funding=True。这里的1000是原交易，未加入任何新风险候选数量。','',
'## decision_at、quote cutoff与真实报单时间不能混用','',
f'- [Runner.opening]({codefiles["native_opening"]}:302)：读取`raw.loc[day].open`后调用LR.preview，再`route`，成功才`reserve_quantity`；全部funding后才查询执行window并fill。raw OPEN读取和route调用没有单独的更细时间戳，代码逻辑顺序可查，实际耗时未记录。',
f'- [LR.reserve_quantity]({codefiles["known_open_reserve"]}:94)：先`quote.read_price(clock.decision_at)`验证原CLOSE quote，再`self._time(at)`；实际在OPEN构造BuyOrder，但其`created_at`参数沿旧signal decision_at，`earliest_at`为nextOPEN。audit另存真实程序reserve.at、原decision_at与known_open_funding=True。created_at/decision_at不证明前晚已向交易所报单。',
f'- [DecisionQuote.read_price]({codefiles["quote_cutoff_and_BuyOrder"]}:175)：验证quote.known_at不晚于传入cutoff以及source/FX；此处传的是前CLOSE signal cutoff。实际OPEN价格另从raw条读取，不是用这一CLOSE quote读取未来OPEN。九行quote_source是原raw数据文件hash；源声明close_available_time=15:05，不是交易所逐笔送达记录。具体quote对象known_at未另存在这些audit行中，明确缺失。',
f'- [FastMarket.window]({codefiles["active_fast_market"]}:45)：成交代理除了raw OPEN与5bp，还读当日H/L是否flat及当日完整volume，并以past20正量均值1%与当日volume取min做容量。J.opening将该检查放在funding之后；不能把这个后验执行代理称为开盘时已经知道全天H/L/V。',
'','原日志缺失：没有交易所报单发送时间、券商/交易所ACK、交易所订单号/成交号、逐笔成交时间/队列、竞价分配或开盘价公布延迟。`buy:...`和`fill:...`是程序内部ID，09:30是研究时钟。现存代码能证明“按已知OPEN定量后，以同OPEN加滑点的日线代理成交”的模型规则，不能证明现实中能先见最终开盘价、再以该价拿到同样数量。','',
'源文件：NINE_ORIGINAL_EXECUTION_CLOCKS.json/csv逐笔保reserve、fill、funding、原intent和audit逻辑序号；ORIGINAL_KNOWN_OPEN_REJECTION_JAN20_21.json保失败例。没有运行新策略/账户、没有求新数量，也没有将新纸算数量写入原成交。']
(O/'EVIDENCE.md').write_text('\n'.join(lines)+'\n')
save('VALIDATION.json',dict(original_buy_fills=9,original_rejection_examples=1,all_fill_prices_equal_rawOPEN_times_1_0005=True,all_known_open_funding_true=True,all_reserve_decision_at_prior_CLOSE=True,all_reserve_before_fill_in_internal_audit_order=True,exchange_timing_evidence='NOT_SAVED',new_accounts=0,new_models=0,new_risk_candidates=0))
save('DELIVERABLE_SHA256.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json' and p.suffix!='.log'})
print('nine original OPEN clocks and one known-OPEN rejection saved; exchange timing missing; no new sizing')
