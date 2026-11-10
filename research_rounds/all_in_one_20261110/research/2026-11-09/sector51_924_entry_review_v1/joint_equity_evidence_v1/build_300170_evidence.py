"""Fact-only supplement for 300170.SZ 2024-09-18. Never changes engine or account."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,datetime
import pandas as pd
O=Path(__file__).resolve().parent
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
sid='300170.SZ'; ex='2024-09-18'; record='2024-09-13'; pay='2024-09-18'
ap=AS/'inputs-v1/actions'/f'{sid}.json'; a=read(ap)
pairs=[(i+1,e) for i,e in enumerate(a['events']) if e['effective_date']==ex]; assert len(pairs)==1
ordinal,term=pairs[0]; assert D(term['split_ratio'])==1 and D(term['cash_per_old_share'])==D('.01')
m=next(x for x in read(U/'STOCK_MANIFEST.json') if x['symbol']==sid)
sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
assert sha(sp)==m['source_sha256'][str(sp)]
z=pd.read_parquet(sp); dt=pd.Timestamp(ex); old=z.loc[z.index<dt].iloc[-1]; new=z.loc[dt]
fo,fn,pc=map(lambda x:D(str(x)),[old.adjustment_factor,new.adjustment_factor,old.raw_close])
ds=D(term['cash_per_old_share']); dc=D('.01'); dr=D('.0099946')
res=fo*pc/(pc-ds)/fn-1; ref_res=fo*pc/(pc-dr)/fn-1
lineage=lambda x:tuple(str(x.get(k)) for k in ('source_kind','source_path','segment_id'))
assert lineage(old)==lineage(new) and abs(res)<D('1e-11') and str(old.name.date())==record
hp=O/'300170.SZ_20240909_sina.html'; h=hp.read_text()
for s in ['公告日期:2024-09-09','公告编号：2024-057','2024年9月13日','2024年9月18日','0.100000元人民币现金','0.0099946元/股','不送红股','不转增股本','直接划入其资金账户']: assert s in h,s
pdf=O/'300170.SZ_1221176837.pdf'; mirror=O/'300170.SZ_20240909_2024-057.pdf'
assert sha(pdf)==sha(mirror)
qp=O/'300170.SZ_cninfo_query.json'; q=read(qp); ann=q['response']['announcements']; assert len(ann)==1 and ann[0]['secCode']=='300170' and ann[0]['announcementId']=='1221176837'
ev={
'sid':sid,'economic_event_id_candidate':f'{sid}|LOCAL_DISTRIBUTION_{ordinal:03}',
'event_type':'PURE_CASH','record_date':record,'ex_date':ex,'pay_date':pay,
'd_source':str(ds),'d_cash':str(dc),'d_ref':str(dr),
'local_action_ordinal':ordinal,'local_action_path':str(ap),'local_action_sha256':sha(ap),
'signal_path':str(sp),'signal_sha256':sha(sp),'factor_old':str(fo),'factor_new':str(fn),
'previous_close':str(pc),'previous_day':record,'source_coordinate_residual':str(res),
'official_reference_coordinate_residual':str(ref_res),'same_lineage':True,'record_is_previous_observation':True,
'scenario_not_PIT':True,'net80_per_registered_share':str(dc*D('.8')),
'admission_scope':'BOUNDED_2024_09_02_TO_10_31_RESEARCH_FACTS_AND_COORDINATE_ONLY_NOT_PRODUCTION',
'notice_url':'https://static.cninfo.com.cn/finalpage/2024-09-09/1221176837.PDF',
'notice_number':'2024-057','notice_date':'2024-09-09',
'source_type':'OFFICIAL_CNINFO_NOTICE_PDF_WITH_IDENTICAL_SINA_PDF_AND_HTML_CONTEXT',
'notice_date_scope':'document_or_publication_date_only_not_intraday_known_at',
'notice':{'pdf_path':str(pdf),'pdf_sha256':sha(pdf),'url':'https://static.cninfo.com.cn/finalpage/2024-09-09/1221176837.PDF'},
'evidence_hashes':{str(p):sha(p) for p in [hp,pdf,mirror,qp]},
'fact_notes':['Gross cash per participating share 0.01 CNY; source adjustment also uses 0.01, verified independently.','Official reference-price decrement is 0.0099946 CNY due to repurchased shares excluded; it is not the cash entitlement and must not replace source factor convention.','Company says cash transfer through custodian on 2024-09-18; intraday availability is unspecified. Existing close-payment and NET80 scenario rules unchanged.','No bonus shares or capital conversion. No engine or original actions edits.']
}
save(O/'EXTRA_REVIEWED_EQUITY_EVENTS_300170_V1.json',[ev])
report={'status':'PASS_FACT_AND_SOURCE_COORDINATE_ONLY','retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'facts':ev,'short_verbatim_excerpts':['每10股派','0.100000元人民币现金','不送红股，不转增股本。','直接划入其资金账户。'],'excerpt_context':'Announcement sections II (cash), III-IV (record/ex dates), V (payment), and special notice 2 (reference price). See archived HTML and identical official/mirror PDFs.','independent_review_required':True,'no_production_admission':True,'no_account_run':True}
save(O/'300170_FACT_REVIEW.json',report)
(O/'READOUT.md').write_text('汉得信息 300170.SZ 2024-09-18 权益事件事实补证\n\n公告2024-057，公告日2024-09-09。登记日2024-09-13；除息和A股派息日2024-09-18；纯现金，每股税前0.01元。官方除息参考额0.0099946元，应与实际现金、source复权额分离。\n\n巨潮官方PDF与新浪公告原文PDF SHA256完全相同。公司公告HTML含全部日期和现金条款，已保存及封印。source因子桥以0.01验证，残差 '+str(res)+'；误用官方参考额时残差 '+str(ref_res)+'。\n\n仅公司事实及source坐标核验，不声明PIT可知、不改税制/到账时序、不更改引擎、不运行账户。需独立审核后由实现者按既有NET80及收盘到账约定接入。\n')
save(O/'OUTPUT_SEAL.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SEAL.json'})
print(json.dumps({'adapter':str(O/'EXTRA_REVIEWED_EQUITY_EVENTS_300170_V1.json'),'adapter_sha256':sha(O/'EXTRA_REVIEWED_EQUITY_EVENTS_300170_V1.json'),'factor_old':str(fo),'factor_new':str(fn),'residual':str(res),'event_id':ev['economic_event_id_candidate'],'official_pdf_sha256':sha(pdf)},ensure_ascii=False,indent=2))
