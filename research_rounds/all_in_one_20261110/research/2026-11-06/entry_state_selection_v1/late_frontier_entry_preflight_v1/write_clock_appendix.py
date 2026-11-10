from pathlib import Path
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;H={}
def read(n):
 p=O/n;H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return pd.read_csv(p,low_memory=False)
e=read('REGISTERED_ENTRY_PREFLIGHT.csv');t=read('ORIGINAL_SECTOR_CP1_FULL_RECEIPTS.csv');cases=[];cross=[]
for year in [2022,2024]:
 allp=e[e.year.eq(year)&~e.born&e.sector_market_reason.eq('CURRENT_AUTH_NOT_STRICTLY_POST_BIRTH')];r=allp.sort_values(['signal_day','sid']).iloc[0]
 nxt=t[t.canonical_series.eq(r.sector)&t.confirmed_day.gt(r.signal_day)&t.accepted_by_original_stage].sort_values(['confirmed_day','receipt_id']).head(1)
 z={k:r[k] for k in ['year','sid','name','signal_day','root_day','sector','native_sector_authorization_id','native_sector_authorization_usable','native_sector_stage','native_sector_action','current_authorization_confirmed_day','current_authorization_formation_start','current_authorization_formation_end','current_authorization_clock_relation','current_authorization_same_attempt','current_authorization_same_native_episode','current_authorization_source_consistent','ticket_fact','prewindow_root_fact','window_participation_fact']}
 z.update(selection_rule='Lexicographically first signal_day then sid among original registered late entries with current accepted usable auth confirmed_day <= original stock root birth; no outcome used',birth_day_missed_status='UNKNOWN_ROOT_BIRTH_BEFORE_WINDOW_NO_EXECUTION_HISTORY',window_start='2022-01-04' if year==2022 else '2024-09-02',not_a_claim_of_birth_day_queue_rejection=True,next_accepted_day=nxt.confirmed_day.iloc[0] if len(nxt) else None,next_accepted_receipt_id=nxt.receipt_id.iloc[0] if len(nxt) else None,next_accepted_formation_start=nxt.formation_start_exclusive.iloc[0] if len(nxt) else None,next_accepted_episode=nxt.native_E0_episode_at_confirmation.iloc[0] if len(nxt) else None,next_date_is_potential_sector_fact_only=True,no_assumed_stock_root_survival_new_receipt_queue_or_fill=True)
 cases.append(z)
 g=allp[allp.common&allp.actual_buy]
 for cols in [['current_authorization_clock_relation'],['prewindow_root_fact'],['prewindow_root_fact','window_participation_fact'],['current_authorization_clock_relation','ticket_fact']]:
  for key,q in g.groupby(cols,dropna=False):
   key=key if isinstance(key,tuple) else (key,);cross.append(dict(year=year,denominator='COMMON_ORIGINAL_PROXY_BUY_PURE_POSTBIRTH_INCREMENT',grouping='|'.join(cols),n=len(q),**dict(zip(cols,key))))
pd.DataFrame(cases).to_csv(O/'MECHANICAL_PURE_INCREMENT_CASES.csv',index=False,mode='x');pd.DataFrame(cross).to_csv(O/'PURE_INCREMENT_CLOCK_DECOMPOSITION.csv',index=False,mode='x')
text='''# 严格晚于与机械例附录

此附录不改唯一公式、不新增第二式、不按盈亏选例、不计算任何新成交或新收益。

## 纯新增时钟职责

共同原BUY中，2022纯新增163条=行业当前授权确认与stockroot生日同日86条+早于生日77条；2024纯新增31条=同日16条+早于15条。**同日行业新确认不能叫作出生前旧票。** 严格“晚于”要求的是birth之后独立新增确认，而不是容许同日共振；本轮不改为大于等于。

2022纯新增163条中窗前root20、窗内root143；窗内143又分已有先前实际BUY103、本窗尚无实际BUY40。2024纯新增31条中窗前root7、窗内24；窗内为已有先前BUY5、尚无BUY19。前次已买并退出后新root内延后首次参与仍属合法重入来源，不把它描成复用退出前旧root。

## 机械选择两个例子

固定规则是各窗“当前授权有效但confirmed_day<=stockroot.birth”的原登记回合按signal_day、sid排序第一行。没有查看、比较或筛选其盈利标签。

- 2022：美年健康002044，2022-01-04续票且仍破rolling20High；root2021-12-31；当前行业授权d892a2480ae2439c6011ec60b9b3490d277f1fe0cb544a67b4f3e81e4c8db435于2021-12-29确认，formation从12-24至12-29，当前stage1 hold且usable。原active门有资格，但新严格postbirth条件不通过。后来下一张accepted行业票为2022-02-25（formation2-24→2-25）。
- 2024：湖北宜化000422，2024-09-02续票且仍破rolling20High；root8-30；当前行业授权c002cc8e51558cd2c8fbe19ec97bf6274237ddd858e05ca71b4f05311cdf4b2b于8-08确认，formation8-05→8-08，当前stage1 hold且usable。原active门有资格，新严格postbirth条件不通过。后来下一张accepted行业票为9-24（formation9-18→9-24）。

两例root生日都在研究窗前，原经济窗分别从2022-01-04和2024-09-02独立FLAT开始。不能说birth当天被行业/队列挡住或错过：窗前执行历史UNKNOWN。下一张行业accepted日期也不证明原stockroot仍活跃、同股有新frontier、排上行业槽、next OPEN成交或任何新收益。

## 安全标签版本

v1仅已知历史样本计数正确，独审发现bool(NaN)边界。最终安全解释以unknown_hardening_v2为准，原v1与独审漏洞复现材料保留。v2只严格化三态读取，不改变公式或已知标签，也不是执行consumer。
'''
(O/'MECHANICAL_AND_CLOCK_APPENDIX.md').write_text(text)
assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in H.items())
with (O/'CLOCK_APPENDIX_SOURCE_HASHES.json').open('x') as f:json.dump(H,f,indent=2)
print(pd.DataFrame(cross).to_string(index=False));print('APPENDIX_DONE')
