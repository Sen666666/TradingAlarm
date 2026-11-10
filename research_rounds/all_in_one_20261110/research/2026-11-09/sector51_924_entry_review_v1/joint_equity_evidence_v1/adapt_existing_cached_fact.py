"""Adapt one explicitly requested existing cached CNINFO pure-cash fact. No engine/account work."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,re,sys
import pandas as pd
O=Path(__file__).resolve().parent
ROOT=O.parent
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
BASE=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/m3_stock_birth_during_sector_v1')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
sid,ex=sys.argv[1:3]
inventory=read(ROOT/'joint51_candidate_v1/UNADMITTED_ACTION_INVENTORY.json')
item=next(x for x in inventory if x['sid']==sid and x['ex_date']==ex)
fp=Path(item['existing_fact_cache']);assert fp.is_file()
f=read(fp);assert f['sid']==sid and f['requested_code']==sid[:6] and f['params']=={'scode':sid[:6]} and f['endpoint']=='https://webapi.cninfo.com.cn/api/sysapi/p_sysapi1139'
j=f['raw'];assert j['resultcode']==200 and j['count']==j['total']==len(j['records'])
rows=[r for r in j['records'] if r.get('F020D')==ex];assert len(rows)==1
r=rows[0];ann,rec,xd,pay=[r[k] for k in ['F006D','F018D','F020D','F023D']]
assert all(re.fullmatch(r'\d{4}-\d{2}-\d{2}',x) for x in [ann,rec,xd,pay]) and ann<=rec<xd<=pay
amt=D(str(r['F012N']))/10
t=re.fullmatch(r'10派([0-9.]+)元\(含税\)',r['F007V'])
assert t and D(t.group(1))/10==amt and r.get('F010N') in [None,0] and r.get('F011N') in [None,0]
ap=Path(item['action_path']);assert sha(ap)==item['action_sha256'];a=read(ap);assert a['series_id']==sid
terms=[(i+1,x) for i,x in enumerate(a['events']) if x['effective_date']==ex];assert len(terms)==1
ordinal,term=terms[0];assert D(term['split_ratio'])==1 and D(term['cash_per_old_share'])==amt
m=next(x for x in read(U/'STOCK_MANIFEST.json') if x['symbol']==sid)
sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(sp)==m['source_sha256'][str(sp)]
z=pd.read_parquet(sp);dt=pd.Timestamp(ex);old=z[z.index<dt].iloc[-1];new=z.loc[dt]
fo,fn,pc=map(lambda x:D(str(x)),[old.adjustment_factor,new.adjustment_factor,old.raw_close])
res=fo*pc/(pc-amt)/fn-1
lineage=lambda x:tuple(str(x.get(k)) for k in ('source_kind','source_path','segment_id'))
assert lineage(old)==lineage(new) and abs(res)<D('1e-11') and str(old.name.date())==rec
ev={'sid':sid,'economic_event_id_candidate':f'{sid}|LOCAL_DISTRIBUTION_{ordinal:03}','event_type':'PURE_CASH','record_date':rec,'ex_date':ex,'pay_date':pay,'d_source':term['cash_per_old_share'],'d_cash':str(amt),'d_ref':None,'local_action_ordinal':ordinal,'local_action_path':str(ap),'local_action_sha256':sha(ap),'signal_path':str(sp),'signal_sha256':sha(sp),'source_fact_path':str(fp),'source_fact_sha256':sha(fp),'factor_old':str(fo),'factor_new':str(fn),'previous_close':str(pc),'previous_day':rec,'source_coordinate_residual':str(res),'same_lineage':True,'record_is_previous_observation':True,'scenario_not_PIT':True,'net80_per_registered_share':str(amt*D('.8')),'notice_date':ann,'source_type':'EXISTING_CNINFO_HISTORICAL_API_CACHE','raw_fact_row':r,'source_endpoint':f['endpoint'],'source_retrieved_at_utc':f['retrieved_at_utc'],'identity_basis':'request scode + market-qualified sid + local source terms; API record omits identity','admission_scope':'BOUNDED_2024_09_02_TO_10_31_RESEARCH_FACTS_AND_COORDINATE_ONLY_NOT_PRODUCTION','evidence_hashes':{str(p):sha(p) for p in [fp,ap,sp]},'fact_notes':['Exact single cached row; no new retrieval. F018D record date, F020D ex date, F023D cash pay date, F012N gross cash per ten shares.','No stock dividend or capitalization in cached fields. d_ref is unverified, not assumed equal to cash.','No claim of historical PIT knowledge or individual tax timing. Existing NET80 and close-payment scenario unchanged.']}
out=O/f'EXTRA_REVIEWED_EQUITY_EVENTS_{sid[:6]}_V1.json'
out.write_text(json.dumps([ev],ensure_ascii=False,indent=2)+'\n')
report=O/f'{sid[:6]}_FACT_REVIEW.json'
report.write_text(json.dumps({'status':'PASS_EXISTING_CACHED_FACT_AND_COORDINATE_ONLY','event':ev,'adapter_path':str(out),'adapter_sha256':sha(out),'no_account_run':True,'independent_review_required':True},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'adapter':str(out),'sha256':sha(out),'record_date':rec,'ex_date':ex,'pay_date':pay,'cash_per_share':str(amt),'residual':str(res),'factor_old':str(fo),'factor_new':str(fn)},ensure_ascii=False,indent=2))
