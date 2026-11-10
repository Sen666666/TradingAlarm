"""Independent completed saved output aggregation; no new price/financial path."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime
import gzip,json,hashlib,time
P=Path(__file__).resolve().parent.parent;R=P/'review';A=P/'analysis';T=P.parent;Z=D(0);EPS=D('.00000001');start=time.monotonic();sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);sources[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def book(p):
 sources[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
 sources[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return [json.loads(s)for s in f]
def n(x):return D(str(x))
def eq(a,b,tag=''):assert abs(n(a)-n(b))<EPS,(tag,str(a),str(b))
def per(ds):
 a=n(ds[0]['begin_NAV']);end=n(ds[-1]['end_NAV']);peak=a;dd=Z
 for x in ds:
  v=n(x['end_NAV']);peak=max(peak,v);dd=max(dd,(peak-v)/peak*100)
 return {'begin_NAV':a,'end_NAV':end,'wealth_change':end-a,'return_pct':(end/a-1)*100,'max_CLOSE_DD_pct':dd,'mean_exposure_pct':sum((n(x['exposure_pct'])for x in ds),Z)/len(ds),'peak_exposure_pct':max(n(x['exposure_pct'])for x in ds),'actual_buy_cash':sum((n(x['buy_cash'])for x in ds),Z),'actual_sell_net':sum((n(x['sell_net'])for x in ds),Z),'actual_fees':sum((n(x['fees'])for x in ds),Z),'actual_fill_sides':sum(x['fill_sides']for x in ds),'actual_gross_turnover':sum((n(x['gross_turnover'])for x in ds),Z),'gross_turnover_over_mean_NAV':sum((n(x['gross_turnover'])for x in ds),Z)/(sum((n(x['end_NAV'])for x in ds),Z)/len(ds)),'actual_OPENs':sum(x['has_actual_OPEN']for x in ds),'active_OPENs':sum(x['has_actual_OPEN']and x['ACT_at_OPEN']for x in ds)}
def stamp(x):return datetime.fromisoformat(x).isoformat()
comparison=read(A/'ACCOUNT_COMPARISONS.json');meta=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json');rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');allids=set(read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/FREEZE.json')['stocks']);assert len(allids)==1709;semis={s for s in allids if meta[s]['industry']=='半导体'};assert len(semis)==126
failed=read(A/'failed_daily_decode/FAILED_INPUT_OUTPUT_IDENTITY.json');same=[]
for path,h in failed['successful_original_financial_outputs'].items():
 if Path(path).name!='long_OFF_PERIODS.json':assert sha(path)==h;same.append(Path(path).name)
oldprimary=T/'new_price_trend_v1/analysis/long_OFF_PERIODS.json';assert sha(oldprimary)==failed['successful_original_financial_outputs'][str(A.resolve()/'long_OFF_PERIODS.json')];origperiods=read(oldprimary);extended=read(A/'long_OFF_PERIODS.json')
for k,v in origperiods.items():assert all(extended[k][f]==x for f,x in v.items())
data={};report={};period_groups=stock_period_rows=sector_period_rows=event_rows=0
for window,count in [('long',726),('strong',242)]:
 data[window]={}
 for mode in ['OFF','ON']:
  name=window+'_'+mode;root=(T/'new_price_trend_v1/funding/runs'/(window+'_OFF'))if mode=='OFF'else P/'funding/runs'/(window+'_ON');assert read(root/'DONE.json')['completed'];b=book(root/'pair/B.json.gz');daily=read(A/(name+'_DAILY.json'));native=rows(root/'pair/daily.jsonl.gz');assert len(daily)==len(native)==count;periods=read(A/(name+'_PERIODS.json'));assert comparison[window][mode]==periods;fr={x['day']:x for x in daily};risk=read(A/(name+'_RISK_CASH_DAILY.json'));riskby={x['day']:x for x in risk};ip=read(A/(name+'_HELD_INDUSTRY_RISK_DAILY.json'));ipid=defaultdict(list)
  for x in ip:ipid[x['day']].append(x)
  nativeby={x['at'][:10]:x for x in native};prior=D(1000000);prior_on=True;tx=defaultdict(list);div=defaultdict(lambda:Z);stocktx=defaultdict(list);stockdiv=defaultdict(list)
  for t in b['trades']:tx[t['at'][:10]].append(t);stocktx[t['security_id']].append(t)
  for x in b['audit']:
   if x['kind']=='dividend_accrual':div[x['receivable']['ex_at'][:10]]+=n(x['receivable']['net_local']);stockdiv[x['receivable']['security_id']].append(x['receivable'])
  opens={str(x)[:10]for x in rules['calendars']['A']if datetime.fromisoformat(('2022-01-01'if window=='long'else'2025-07-01')+'T15:10:00+08:00')<=datetime.fromisoformat(x)<=datetime.fromisoformat(native[-1]['at'])}
  for x in daily:
   d=x['day'];v=nativeby[d];rr=riskby[d];eq(x['begin_NAV'],prior);eq(x['end_NAV'],v['nav']);eq(x['wealth_change'],n(x['end_NAV'])-prior);eq(x['inventory'],v['inventory']);eq(x['exposure_pct'],n(v['inventory'])/n(v['nav'])*100);eq(x['available'],v['available']);assert x['has_actual_OPEN']==(d in opens)and x['ACT_at_OPEN']==prior_on and x['ACT_after_CLOSE']==bool(v['on']);prior=n(x['end_NAV']);prior_on=bool(v['on'])
   ts=tx[d];eq(x['fees'],sum((n(t['fees_cny'])for t in ts),Z));eq(x['buy_cash'],sum((n(t['gross_cny'])+n(t['fees_cny'])for t in ts if t['side']=='buy'),Z));eq(x['sell_net'],sum((n(t['gross_cny'])-n(t['fees_cny'])for t in ts if t['side']=='sell'),Z));eq(x['gross_turnover'],sum((n(t['gross_cny'])for t in ts),Z));assert x['fill_sides']==len(ts)
   nav=n(v['nav']);eq(rr['budget_probe_risk'],v['pool_probe'][1]);eq(rr['budget_confirmed_risk'],v['pool_confirmed'][1]);eq(rr['budget_total_risk'],n(v['pool_probe'][1])+n(v['pool_confirmed'][1]));eq(rr['budget_total_risk_pct'],n(rr['budget_total_risk'])/nav*100);eq(rr['cash_equivalent'],nav-n(v['inventory']));eq(rr['available_pct'],n(v['available'])/nav*100)
   sec=ipid[d];eq(sum((n(z['held_inventory'])for z in sec),Z),v['inventory']);eq(sum((n(z['held_nominal_risk_known_subtotal'])for z in sec),Z),rr['held_nominal_mark_to_line_risk']);eq(sum((n(z['held_probe_risk'])for z in sec),Z),rr['held_probe_risk_known_subtotal']);eq(sum((n(z['held_confirmed_risk'])for z in sec),Z),rr['held_confirmed_risk_known_subtotal']);assert sum(z['industry_1pct_CLOSE_reference_exceeded']is True for z in sec)==rr['industry_1pct_CLOSE_reference_exceedances'];assert rr['probe_10pct_capital_CLOSE_reference_exceeded']==(n(rr['held_probe_capital_pct'])>10)
  eq(prior,b['ending_NAV']);layers=read(A/(name+'_LAYERS.json'));nl={x['id']:x for x in b['layers']};ids=read(A/(name+'_ENTRY_LAYER_IDENTITIES.json'));idmap={x['layer']:x for x in ids};jfills={x['layer']:x for x in b['journal']if x['kind']=='real_buy_fill'};buys={t['layer']:t for t in b['trades']if t['side']=='buy'};stocks=read(A/(name+'_STOCKS.json'));smap={x['sid']:x for x in stocks};events=read(A/(name+'_ACTUAL_FILLED_EVENTS.json'));emap={x['event_key']:x for x in events};expected=defaultdict(list);by_sid=defaultdict(list)
  assert set(nl)==set(idmap)==set(jfills)==set(buys)=={x['layer']for x in layers}
  for x in layers:
   lid=x['layer'];l=nl[lid];j=jfills[lid];t=buys[lid];i=idmap[lid];eq(x['cost'],n(t['gross_cny'])+n(t['fees_cny']));eq(x['net'],n(l['cash'])+n(l['dividend'])+n(x['value']));assert x['qty']==l['qty'];assert x['role']==j['role']and x['receipt']==j['CP1_id'];key=json.dumps([l['sid'],stamp(l['signal_at']),j['role'],l.get('epoch')or[],j['CP1_id']if j['role']=='mobile'else None],ensure_ascii=False,separators=(',',':'));assert i['event_key']==key and i['entry_pool']==j['pool']and i['is_direct_confirmed_CORE']==(j['role']=='core'and j['pool']=='confirmed');expected[key].append(x);by_sid[x['sid']].append(x)
  assert set(expected)==set(emap);event_rows+=len(events)
  for key,ll in expected.items():
   e=emap[key];assert e['layers']==[x['layer']for x in ll];eq(e['cost'],sum((n(x['cost'])for x in ll),Z));eq(e['net'],sum((n(x['net'])for x in ll),Z));assert e['entry_shares']==sum(buys[x['layer']]['shares']for x in ll);assert e['entry_pools']==[jfills[x['layer']]['pool']for x in ll]
  eq(sum((n(x['net'])for x in layers),Z),prior-1000000);eq(sum((n(x['net'])for x in stocks),Z),prior-1000000);eq(sum((n(x['net'])for x in events),Z),prior-1000000);eq(sum((n(x['value'])for x in layers),Z),daily[-1]['inventory'])
  for sid,ll in by_sid.items():eq(smap[sid]['cost'],sum((n(x['cost'])for x in ll),Z));eq(smap[sid]['net'],sum((n(x['net'])for x in ll),Z));assert smap[sid]['layers']==len(ll)and smap[sid]['open_layers']==sum(bool(x['qty'])for x in ll)
  sp=read(A/(name+'_ALL1709_STOCK_PERIODS.json'));secp=read(A/(name+'_ALL90_INDUSTRY_PERIODS.json'));rp=read(A/(name+'_ROLE_PERIOD_WEALTH.json'));spg=defaultdict(dict);sig=defaultdict(list);rg=defaultdict(list)
  for x in sp:spg[x['period']][x['sid']]=x
  for x in secp:sig[x['period']].append(x)
  for x in rp:rg[x['period']].append(x)
  for k,pv in periods.items():
   ds=[x for x in daily if pv['begin']<=x['day']<=pv['end']];basic=per(ds)
   for f,v in basic.items():eq(pv[f],v,(window,mode,k,f))
   assert pv['CLOSEs']==len(ds)and set(spg[k])==allids and len(sig[k])==90 and len({x['sector']for x in sig[k]})==90 and len(rg[k])==3;period_groups+=1;stock_period_rows+=1709;sector_period_rows+=90
   eq(sum((n(x['wealth_change'])for x in spg[k].values()),Z),pv['wealth_change']);eq(sum((n(x['wealth_change'])for x in sig[k]),Z),pv['wealth_change']);eq(sum((n(x['wealth_change'])for x in rg[k]),Z),pv['wealth_change']);eq(sum((n(x['mean_NAV_weight_pct'])for x in sig[k]),Z),pv['mean_exposure_pct'])
   inds=defaultdict(list)
   for sid,x in spg[k].items():
    inds[meta[sid]['sector_id']].append(x);ts=[t for t in stocktx[sid]if pv['begin']<=t['at'][:10]<=pv['end']];dv=sum((n(a['net_local'])for a in stockdiv[sid]if pv['begin']<=a['ex_at'][:10]<=pv['end']),Z);cash=sum((n(t['gross_cny'])-n(t['fees_cny'])if t['side']=='sell'else-n(t['gross_cny'])-n(t['fees_cny'])for t in ts),Z);eq(x['wealth_change'],cash+dv+n(x['ending_inventory'])-n(x['beginning_inventory']));assert x['buy_fills']==sum(t['side']=='buy'for t in ts);eq(x['buy_cash'],sum((n(t['gross_cny'])+n(t['fees_cny'])for t in ts if t['side']=='buy'),Z))
   for sec in sig[k]:ll=inds[sec['sector']];eq(sec['wealth_change'],sum((n(x['wealth_change'])for x in ll),Z));eq(sec['mean_NAV_weight_pct'],sum((n(x['mean_NAV_weight_pct'])for x in ll),Z))
   rs=[riskby[x['day']]for x in ds]
   for field,key in [('mean_available_pct','available_pct'),('mean_cash_equivalent_pct','cash_equivalent_pct'),('mean_budget_total_risk_pct','budget_total_risk_pct'),('mean_probe_risk_pct','budget_probe_risk_pct'),('mean_confirmed_risk_pct','budget_confirmed_risk_pct')]:eq(pv[field],sum((n(x[key])for x in rs),Z)/len(rs))
   for field,key in [('peak_budget_total_risk_pct','budget_total_risk_pct'),('peak_probe_risk_pct','budget_probe_risk_pct'),('peak_confirmed_risk_pct','budget_confirmed_risk_pct')]:eq(pv[field],max(n(x[key])for x in rs))
   assert pv['probe_0p5pct_CLOSE_reference_exceedance_days']==sum(x['probe_0p5pct_CLOSE_reference_exceeded']is True for x in rs)and pv['industry_1pct_CLOSE_reference_exceedance_days']==sum(x['industry_1pct_CLOSE_reference_exceedances']>0 for x in rs)
  adopt=read(A/(name+'_MECHANISM_ADOPTION_SUMMARY.json'));direct=[x for x in ids if x['is_direct_confirmed_CORE']];assert adopt['direct_confirmed_core_layers']==len(direct)and not adopt['unlinked_actual_layers']and not adopt['nonmatching_CP_actual_layers'];eq(adopt['actual_buy_cash'],sum((n(x['cost'])for x in direct),Z));eq(adopt['lifecycle_net'],sum((n(x['net'])for x in direct),Z))
  data[window][mode]={'b':b,'native':nativeby,'daily':daily,'periods':periods,'layers':layers,'stocks':smap,'events':emap,'sp':spg,'ids':ids,'adopt':adopt}
 a,b=data[window]['OFF'],data[window]['ON'];delta=n(b['periods']['all']['end_NAV'])-n(a['periods']['all']['end_NAV']);sd=read(A/(window+'_STOCK_DELTAS.json'));ed=read(A/(window+'_ALL_FILLED_EVENT_DELTAS.json'));assert {x['sid']for x in sd}==set(a['stocks'])|set(b['stocks']);assert {x['event_key']for x in ed}==set(a['events'])|set(b['events'])
 for x in sd:
  sid=x['sid'];assert x['OFF']==a['stocks'].get(sid)and x['ON']==b['stocks'].get(sid);eq(x['net_delta'],(n(x['ON']['net'])if x['ON']else Z)-(n(x['OFF']['net'])if x['OFF']else Z))
 for x in ed:
  k=x['event_key'];assert x['OFF']==a['events'].get(k)and x['ON']==b['events'].get(k);xx,yy=x['OFF'],x['ON'];status='common_actual_fill'if xx and yy else'OFF_only_actual_fill'if xx else'ON_only_actual_fill';changed=not(xx and yy)or any(xx[f]!=yy[f]for f in ['cost','net','entry_shares','entry_pools']);assert x['status']==status and x['actual_path_changed']==changed;eq(x['net_delta'],(n(yy['net'])if yy else Z)-(n(xx['net'])if xx else Z))
 eq(sum((n(x['net_delta'])for x in sd),Z),delta);eq(sum((n(x['net_delta'])for x in ed),Z),delta);eq(comparison[window]['terminal_NAV_delta'],delta)
 mobile=read(A/(window+'_ORIGINAL_MOBILE_PATH_CHANGES.json'));expected={x['event_key']:x for x in ed if x['OFF']and x['OFF']['role']=='mobile'and x['actual_path_changed']};assert {x['event_key']for x in mobile}==set(expected)
 for x in mobile:
  e=expected[x['event_key']];assert all(x[k]==v for k,v in e.items());same=[i for i in b['ids']if i['is_direct_confirmed_CORE']and i['sid']==e['OFF']['sid']and i['signal_at']==e['OFF']['signal_at']];assert x['same_signal_ON_confirmed_CORE']==same
 winners=read(A/(window+'_ORIGINAL_TOP10_WINNER_RETENTION.json'));oldtop=sorted(a['stocks'].values(),key=lambda x:-n(x['net']))[:10];assert [x['original_winner']for x in winners]==oldtop
 for x in winners:
  sid=x['original_winner']['sid'];assert x['ON']==b['stocks'].get(sid);days=[d for d,v in a['native'].items()if v['positions'].get(sid,0)];overlap=[d for d in days if b['native'][d]['positions'].get(sid,0)];assert x['original_holding_CLOSEs']==len(days)and x['ON_overlap_holding_CLOSEs']==len(overlap);eq(x['overlap_fraction'],D(len(overlap))/len(days));eq(x['capital_participation_ratio'],n(x['sum_ON_weights_on_same_original_days_pct'])/n(x['sum_original_holding_window_weights_pct']))
 grouped=defaultdict(lambda:dict(events=0,net_delta=Z))
 for x in ed:
  role=(x['OFF']or x['ON'])['role'];k=role+'|'+x['status'];grouped[k]['events']+=1;grouped[k]['net_delta']+=n(x['net_delta'])
 report[window]={'terminal_NAV_delta':str(delta),'events':len(ed),'event_groups':dict(grouped),'original_Mobile_changed_events':len(mobile),'original_Mobile_same_signal_replaced_by_confirmed_CORE':sum(bool(x['same_signal_ON_confirmed_CORE'])for x in mobile),'original_top10_net_OFF':str(sum((n(x['original_winner']['net'])for x in winners),Z)),'original_top10_net_ON':str(sum((n(x['ON']['net'])if x['ON']else Z for x in winners),Z)),'largest_negative_stock_deltas':[{k:x[k]for k in ['sid','name','industry','net_delta']}for x in sorted(sd,key=lambda x:n(x['net_delta']))[:5]],'direct_CORE_lifecycle_net':b['adopt']['lifecycle_net'],'returns':{p:{'OFF':a['periods'][p]['return_pct'],'ON':b['periods'][p]['return_pct']}for p in a['periods']}}
semi=read(A/'SEMICONDUCTOR_H1_COMPARISON.json');allsemi=read(A/'SEMICONDUCTOR_ALL126_H1_PARTICIPATION.json');assert len(allsemi)==252
for mode in ['OFF','ON']:
 s=semi[mode];x=data['strong'][mode];ll=[r for sid,r in x['sp']['2026H1'].items()if sid in semis];assert len(ll)==126 and s['stocks']==126 and s['actually_held_stocks']==sum(r['held_CLOSEs']>0 for r in ll)and s['actual_buy_fills']==sum(r['buy_fills']for r in ll)and s['new_buy_stocks']==sum(r['buy_fills']>0 for r in ll)
 for k,f in [('buy_cash','buy_cash'),('wealth_change','wealth_change'),('mean_NAV_weight_pct','mean_NAV_weight_pct'),('beginning_inventory','beginning_inventory'),('ending_inventory','ending_inventory')]:eq(s[k],sum((n(r[f])for r in ll),Z))
 eq(s['own_H1_start_NAV'],x['periods']['2026H1']['begin_NAV']);mapped={r['sid']:r for r in allsemi if r['mode']==mode};assert set(mapped)==semis
 for r in ll:assert all(mapped[r['sid']][k]==v for k,v in r.items());eq(mapped[r['sid']]['contribution_pct_own_H1_start_NAV'],n(r['wealth_change'])/n(s['own_H1_start_NAV'])*100)
# A reproducible saved distinction: new cohort profit is not policy value; period-risk denominators are own path NAV.
sourceindex=read(A/'SOURCE_SHA256.json');critical=[A/'analyze_confirmed_core_saved.py',T/'new_price_trend_v1/analyze_saved_accounts.py',T/'new_price_trend_v1/native_mark_reader.py']
for f in critical:assert sourceindex[str(f.resolve())]==sha(f)
assert sha(A/'analyze_confirmed_core_saved.py')=='2309fdf22a0dcc96c97451202ae3cb5f7a5e1ca32bbb91f7910bc564e6fcf183'
result={'passed':True,'scope':'All four completed saved books: independent actual-trade aggregation, daily/period wealth/return/DD/exposure/fees/turnover, risk references, every layer/stock/stable event, all1709/all90 period bridges, all126H1, Mobile changes and fixed original top10 identity. No new source-price valuation or financial path.','financial_reader_source_and_native_mark_reader_unchanged':True,'failed_attempt_identity':{'byte_identical_files':same,'PERIODS_original_SHA_anchored_in_prior_BB_file':sha(oldprimary),'PERIODS_all_original_groups_and_fields_identical':True,'final_PERIODS_extended_fields_and_extra_subperiods_not_claimed_byte_identical':True},'completed_books':4,'period_groups_checked':period_groups,'all1709_stock_period_rows_checked':stock_period_rows,'all90_industry_period_rows_checked':sector_period_rows,'actual_stable_events_checked':event_rows,'windows':report,'semiconductor_H1':semi,'stop_scope':'Supports stopping this frozen generic dual-proof CORE-confirmed allocation arm as a major-trend participation repair; does not disprove all CORE holding or sparse-right-tail strategies.','limits':['Inventory/source mark valuation uses the unchanged previously audited native financial reader plus its all-day assertions; this review independently checks saved equations/aggregation and did not rerun marks.','Daily risk references are not request-time violations or guaranteed future losses.','Cohort net includes open mark-to-market holdings; policy value is the full portfolio NAV delta with resource/holding/ACT feedback.','Current survivor/industry universe and daily execution/CA proxy, no PIT/OOS/live claim.'],'reviewer_new_accounts_market_marks_or_financial_pipeline_runs':0,'sources_sha256':sources,'seconds':time.monotonic()-start}
(R/'COMPLETED_ECONOMIC_ANALYSIS_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['sources_sha256','windows']},ensure_ascii=False,default=str));print('WINDOW_CONTEXT',json.dumps(report,ensure_ascii=False,default=str))
