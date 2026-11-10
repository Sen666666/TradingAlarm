"""Only four named saved No60 histories and bounded existing facts; no model/run."""
from pathlib import Path
import gzip,hashlib,json,math
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent
PAIR=ROOT/'new_price_trend_v1/funding/runs';SOURCE={}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SOURCE[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def gz(p,lines=False):
 with gzip.open(bind(p),'rt')as f:return list(map(json.loads,f))if lines else json.load(f)

spec=[('strong','688146.SH','中船特气','2025-08-15'),('strong','301319.SZ','唯特偶','2025-10-20'),('long','300489.SZ','光智科技','2024-11-04'),('long','002583.SZ','海能达','2024-11-05')]
manifest=rj('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');by={r['symbol']:r for r in manifest}
books={};days={};ops={};fund={};stocks={};layer_summary={}
for win in ['long','strong']:
 p=PAIR/(win+'_OFF')/'pair';books[win]=gz(p/'B.json.gz');days[win]={r['at'][:10]:r for r in gz(p/'daily.jsonl.gz',True)}
 ids={sid for w,sid,_,_ in spec if w==win};ops[win]=[r for r in gz(p/'opportunities.jsonl.gz',True)if r['sid']in ids];fund[win]=[r for r in gz(p/'funding.jsonl.gz',True)if r['sid']in ids]
 stocks[win]={r['sid']:r for r in rj(ROOT/'new_price_trend_v1/analysis'/(win+'_OFF_STOCKS.json'))}
 layer_summary[win]={r['layer']:r for r in rj(ROOT/'new_price_trend_v1/analysis'/(win+'_OFF_LAYERS.json'))}
out=[]
for win,sid,name,exitday in spec:
 b=books[win];d=days[win];calendar=list(d);idx=calendar.index(exitday);trade=next(t for t in b['trades']if t['security_id']==sid and t['side']=='sell'and t['at'][:10]==exitday)
 ids={r['layer']for r in trade['parts']};proposals=[r for r in b['audit']if r.get('kind')=='pilot_layer_exit'and r.get('sid')==sid and ids.intersection(r.get('layers',[]))]
 firstday=min(r['at'][:10]for r in proposals);start=calendar.index(firstday);selected=calendar[start:idx+4]
 rec=by[sid];fp=bind(rec['refs']['facts']);cp=bind(rec['refs']['CP1']);assert SOURCE[str(fp)]==rec['output_sha256'][str(fp)]and SOURCE[str(cp)]==rec['output_sha256'][str(cp)]
 facts=pd.read_parquet(fp);cpf=pd.read_parquet(cp);points=[]
 for day in selected:
  at=pd.Timestamp(day);f=facts.loc[at]if at in facts.index else None;c=cpf.loc[at]if at in cpf.index else None
  points.append(dict(day=day,same_coordinate='continuous adjusted CLOSE and layer floors; raw_CLOSE explicitly separate',facts=None if f is None else {k:f[k]for k in ['close','raw_close','factor','segment_id','e0_target','i_target','i_floor','i_buy','g_grade','g_ready','g_fresh_up']},
    CP=None if c is None else {k:c[k]for k in ['ready','receipt','candidate','e0_valid','e0_floor','reset_reason']},
    original_stock_qty_at_CLOSE=d[day]['positions'].get(sid,0),original_live_layers_at_CLOSE=[r for r in d[day]['layers']if r['sid']==sid],
    original_opportunities=[r for r in ops[win]if r['sid']==sid and r['day']==day]))
 ts=[t for t in b['trades']if t['security_id']==sid];buys=[t for t in ts if t['side']=='buy'and t['at']>trade['at']]
 later=[layer_summary[win][t['layer']]for t in buys]
 out.append(dict(window=win,sid=sid,name=name,first_exit_proposal=proposals[0],all_matching_exit_proposals=proposals,actual_protection_sell=trade,
   exited_layer_summaries=[layer_summary[win][i]for i in sorted(ids)],observations_after_sell_OPEN_including_same_day_CLOSE=calendar[idx:idx+3],strict_later_three_session_CLOSEs=calendar[idx+1:idx+4],
   original_case_points=points,original_funding_in_fixed_interval=[r for r in fund[win]if r['sid']==sid and firstday<=r['at'][:10]<=selected[-1]],
   all_original_trades_for_this_stock_in_this_account=ts,next_actual_buy_after_exit=buys[0]if buys else None,later_actual_layer_summaries=later,original_whole_window_stock_summary=stocks[win][sid],
   claim_limits=['No full-flat requirement imposed; partial MOBILE exits preserved with real remaining stock qty.','A profitable CP exit is not relabeled as a realized-loss stop.','Later stock profit may contain terminal open inventory; actual period/account identity retained.','Same-day new signal and next-OPEN funds rejection do not prove a durable immediate V or missed strategy profit.']))
save('FOUR_EXISTING_NO60_CASES.json',out)
save('SOURCE_SHA256.json',SOURCE)
save('SCOPE.json',dict(status='FOUR_NAMED_SAVED_CASES_EXTRACTED',new_accounts=0,new_models_or_indicators=0,new_backtests=0,new_financial_paths_or_routes=0,case_price_reads='Only existing frozen facts/CP at first original exit decision through actual sell plus3 market CLOSEs, four prelisted stocks. No price scan or new indicator.',no_full_stock_flat_filter=True,calendar='Original saved daily CLOSE sequence; same-sell-day CLOSE and next3 later sessions both explicit.',source_case_count=4,top10_note='Before follow-up scope clarification, existing fixed-top10 transaction rows were read only; no extra top10 price window extracted here.'))
print(json.dumps(dict(cases=len(out),new_models=0,new_accounts=0)))
