"""Read saved books/source values only. Does not construct or run an account."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,json,hashlib
P=Path(__file__).resolve().parent;W=P.parent
def rd(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 states=rd(P/'STATE_AND_EVENT_PREFLIGHT.json');export=rd(P/'EXPORTED_INPUTS.json')
 meta=rd(P/'inputs/metadata.json');oldmeta=rd('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 assert len(meta)==1709 and len({v['sector'] for v in meta.values()})==90
 assert all(v['sector']==oldmeta[s]['sector_id'] for s,v in meta.items())
 for s in states['states'].values():assert sha(s['checkpoint'])==s['checkpoint_sha256']
 spec=importlib.util.spec_from_file_location('augsep_readonly_loader',W/'g-s-readonly-historical-loader-r2-20261101/loader.py');loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
 actions=rd(P/'inputs/augsep/actions.json')
 conditional=[];unsupported=[]
 for a in actions:
  try:conditional.append(loader.HistoricalInputs.check_action_support(None,a,None))
  except loader.UnsupportedInput as err:unsupported.append(dict(action=a,reason=str(err)))
 assert len(conditional)==266 and len(unsupported)==1 and all(x['ready']=='conditional' for x in conditional)
 months=rd(P/'OLD_SC_PVR_MONTHLY.json');sources=rd(P/'OLD_MONTHLY_SOURCES.json')
 semi=rd(W/'pvr-slot1-native-readiness-20261101/semiconductor-2026H1-readonly/SUMMARY.json')
 sc_cases=[x for x in rd(W/'q2-normal-continuation-20261031/THREE_POSTERIOR_CASES.json') if x['reference']=='B_diag']
 fields=['sector','industry','price_return_H1_pct','first_H1_industry_buy','first_full_account_industry_buy','H1_buy_fills','H1_new_stocks','buy_gross','mean_weight_pct','peak_weight','peak_day','end_weight','interval_net_contribution','closed_trading_PnL_excluding_dividends','unrealized_price_PnL_change','recognized_H1_dividends']
 summary=dict(status='READ_ONLY_PREPARATION_COMPLETE_HORIZON_WIRING_AND_SEP12_SCHEMA_BLOCK_REMAIN',financial_events=0,
  fixed_scope=dict(from_cursor='2025-07-31 15:10:00+08:00',next='2025-08-01',end='2025-09-30',sessions=43,accounts=['C10','C20','C10_R0','C20_R0'],fresh_cash=False),
  identity=dict(stock_id_order_exact=states['same_old_PVR_stock_id_order'],stock_sector_mapping_exact=True,stocks=1709,industries=90,original_start='2025-07-01',original_cash=1000000,original_pvr_source='5ec91c2323b2d3b8fa5c99df504139e2ac7af9b5b84359222c3d6353d0cd697c',input_manifest=export['manifest'],input_manifest_sha256=export['manifest_sha256'],old_input_file_prefix_exact=True),
  old_monthly={k:[x for x in a if x['month']<='2025-09'] for k,a in months.items()},
  old_2026_H1=dict(account_return_pct=semi['H1_account_return_pct'],mean_exposure_pct=semi['H1_mean_portfolio_exposure_pct'],separate_industries=[{k:r[k] for k in fields} for r in semi['industry_summary']]),
  old_SC_2026_Q2=dict(scope='Saved SC/Bdiag April1-June30 only; not like-for-like H1 contribution comparison',source='q2-normal-continuation-20261031/THREE_POSTERIOR_CASES.json',cases=[{k:x[k] for k in ['industry','sector','first_actual_buy','Q2_actual_buy_cash','peak_actual_weight_pct','peak_weight_day','Q2_net_contribution']} for x in sc_cases]),
  own_Jul31={k:{f:s[f] for f in ['checkpoint','checkpoint_sha256','NAV','available','inventory','dividend_receivable','reserved','stocks','layers','pending_intents','active_buys','exit_orders','ACT','consumed_receipts']} for k,s in states['states'].items()},
  input_ready=dict(export_seconds=export['seconds'],model_recomputations=0,source_files_verified=export['sources'],raw_fact_CP_observed_stocks=1649,identity_NA_not_deleted=60,PVR_identity_dates=73487,H1_stock_and_industry_dates=77357,F1_observation_nodes=91,canonical_receipts=7178,corporate_actions=267,split_actions=[a for a in actions if D(a['split_ratio'])!=1],unknown_cash_payment_dates=266,known_payment_events=0,ordinary_source_action_schemas_conditional_pass=266,unsupported_source_action_types=unsupported,immediate_boundary_blockers=[]),
  remaining_wiring=['Append fourth input group; existing MonthInputs ignores continuation_extension and execution grant remains July31. Do not overwrite old input manifest.',
   'Verify original checkpoint old binding first, then explicit same-account new horizon/source binding with old certificate verification views, R0 per-stock permanent consumption, C20 budget Carry/New, pending intents and all exits preserved.',
   'Under future financial authorization: Aug1 full-input vs physically truncated all-channel branch and cross-process restore; retain valid full prefix for continuing, no July rerun. No such financial test executed here.'],
  conditional_stops=['DEFINITE SOURCE-SCHEMA STOP Sep12 000656.SZ targeted_non_pro_rata_issuance. Source says minority-holder directed issuance, no automatic ordinary-holder entitlement/unit adjustment. Current C ordinary-only loader rejects even with no holding. Requires separately authorized audited semantics; no silent skip or pro-rata conversion.',
   'Sep19 000880.SZ split1.40: no own Jul31 inventory/queued C in this stock. Future per-layer fractional quantities, pending exits or unsubmitted positive C authorization cannot be decided from Jul31; original atomic unsupported guards must remain.',
   'General fractional attribution/G-backup subset/partial mandatory upgrade and unknown priority remain original unsupported guards; future account dependence cannot be certified by source-only input preflight.',
   '266 dividend source terms lack pay dates: original80% receivable research proxy, not spendable. No guessed payments or future financing.'],
  time_estimate=dict(measured_C10_21_sessions_seconds='957.571835',measured_C20_7_sessions_seconds='374.338720',estimate_each_43sessions_minutes=[33,39],four_cumulative_minutes=[130,155],two_parallel_wall_minutes=[65,80],uncertainty='Indicative extrapolation; exact-search state growth can exceed these values. Previously Jul22 reached190889 checks; keep explicit250k technical cap/atomic failure. No engine optimization or economic predicate change in this task.'),
  behavioral_acceptance=['Continuous Jul1-Sep30 wealth and each month, including losing segments; no August reset, no future mainline list.',
   'First market/stock eligible opportunity -> first actual buy delay/censor; active fresh funding versus passive appreciation, industry/stock concentration and idle cash.',
   'Sustained winners hold/add/protection/exit request versus fill and genuinely-flat fresh reentry; compare all four complete trajectories.',
   'Cumulative whole-account closed positive/negative, actual realized, residual unrealized, dividends paid/receivable and fractional writeoffs separately; open-layer category is not unrealized.',
   'False starts, repeat losses, role round trips, healthy winner funding exits/new back-row allocations, missed/lost positive tails and fees/turnover.',
   'Duration labels only hindsight evaluation fixed before four-arm outcome differences; short rallies can be caught or missed, not excluded from loss or tail denominators.',
   'Any unknown/unsupported event stops atomically with cursor/state; no silent deletion or invented zero value.'],
  research_boundary='Only readiness authorized now. No new financial grant, no account event, no parameter or formula change. Existing source-only failed export attempts retained under archives; EXPORT_ERROR.json is historical, successful export is EXPORTED_INPUTS.json.')
 save('READINESS_SUMMARY.json',summary)
 lines=['只读纠偏与四账户Aug–Sep接续准备；金融事件0。','', '旧SC / PVR_SLOT1月收益（承接原账，非月初重置）：']
 for month in ['2025-07','2025-08','2025-09']:
  rows=[next(x for x in months[k] if x['month']==month) for k in ['SC','PVR_SLOT1']]
  lines.append(month+'  SC '+str(round(D(rows[0]['month_return_pct']),4))+'%  PVR '+str(round(D(rows[1]['month_return_pct']),4))+'%')
 lines+=['','同1709身份顺序/90行业映射逐项核同；同2025Jul1原100万，原价格/信号缓存与日线执行代理。当前快照回看非PIT；H/L/volume日线成交代理不是开盘可执行认证。',
 '不同策略：旧SC/Bdiag原Q/stage+probe10/confirmed60池、行业risk1%、mobile每fresh2%；旧PVR只改变股票优先。现C为F1 G/S、行业H1→PVR、mobile补股10%、机会性卖健康mobile、行业risk5%/全账6%。不能把旧账与C差额归功或归罪PVR一个因子。',
 '', '月内财富来源（实际现金流+月末原价库存+已记股息；不是纯实卖收益，6个月底分股桥全对NAV）：']
 for k in ['SC','PVR_SLOT1']:
  for r in sources[k]:
   lines.append(k+' '+r['month']+' 正前三 '+', '.join(z['name']+':'+str(round(D(z['month_contribution']),2)) for z in r['top_positive'][:3])+'；负前二 '+', '.join(z['name']+':'+str(round(D(z['month_contribution']),2)) for z in r['top_negative'][:2]))
 lines+=['','旧PVR全窗已审+94.8967%/DD9.0593%，不因Jan/Jul亏损就否定肥尾哲学。2026H1实际主线必须分列：']
 for r in summary['old_2026_H1']['separate_industries']:
  first=r['first_H1_industry_buy'];first=first if isinstance(first,str) else str(first)[:100]
  lines.append(r['industry']+' firstH1buy '+first+'；贡献 '+str(round(D(r['interval_net_contribution']),2))+'；实际卖出净损益 '+str(round(D(r['closed_trading_PnL_excluding_dividends']),2))+'；未实现变化 '+str(round(D(r['unrealized_price_PnL_change']),2))+'；峰值权重 '+str(r['peak_weight'])+'。')
 lines+=['严格半导体贡献约0.92万，电子化学品30.76万、元件11.19万；不得合并冒称半导体重仓。6/30仍有大量未平利润。', '', '四个自有Jul31状态（下一天各自承接，不转旧SC/PVR，不重置）：']
 for x in sc_cases:
  first=x['first_actual_buy'];lines.insert(-1,'旧SC既存Q2记录（仅Apr-Jun，非上述H1同区间差）：'+x['industry']+' firstQ2buy '+(first['at'] if first else '无')+'；Q2贡献 '+str(round(D(x['Q2_net_contribution']),2))+'；Q2峰值权重 '+str(round(D(x['peak_actual_weight_pct']),4))+'%。')
 for k,s in summary['own_Jul31'].items():lines.append(k+' NAV '+s['NAV']+'；股票/层 '+str(s['stocks'])+'/'+str(s['layers'])+'；待意图 '+str(s['pending_intents'])+'，active buy '+str(s['active_buys'])+'，退出单 '+str(s['exit_orders'])+'；现金 '+s['available']+'。CP SHA '+s['checkpoint_sha256'])
 lines+=['','输入已导出冻结：Aug1–Sep30共43交易日，19.43秒，原数值导出不重算；完整1709身份保留，60股该段无facts/CP/raw观察为N/A，PVR/H1/90行业/F1原值完整域不删身份。旧输入三代全部文件前缀字节不变。新MANIFEST SHA '+export['manifest_sha256'],
 '267权息源条目，其中266普通权息通过源类型条件检查，1条Sep12金科000656定向少数股东转增为当前装载器确定不支持，不能因未持有跳过或按比例送转；须单独授权审定其财务语义，未关闭前不能宣称可跑完整Sep30。另1次000880.SZ Sep19×1.4，无配股；266现金支付日未知继续应收不可再投，0已知支付事件。Jul31四账无000880持仓/正C排队；不能因此预先跳Sep19事件，届时数量/未提交授权/零股守卫照旧。Aug1当前未发现确定阻断。',
 '仍需薄接线：现MonthInputs未读取第四代continuation_extension；原July日期闸门仍在。先旧绑定核验再显式新期限导入，旧证书源视图/R0/C20carry/旧退出和142意图全保留。未来获授权后做Aug1物理全通道截断/恢复门，复用有效前缀续跑，不重跑July。此轮未编新金融入口、未给金融grant。',
 '耗时：按最近真实45.6–53.5秒/交易日估计每43日约33–39分钟，四臂累计约130–155分钟，二并行约65–80分钟；精确搜索状态可再增长，不能视硬保证。可先在授权开头数日重新测时；只缓存不变纯输入/完整源键，禁止改解顺序或经济约束提速。',
 '', '预先验收：'+ '；'.join(summary['behavioral_acceptance']),
 '', '结论：短期减损不是晋升依据；下一有辨别力范围为四个原账户连续到Sep30，同时保留旧SC/PVR正负月份和持续尾部兑现对照。现在只读准备完成，等待金融授权。',
 '历史只读导出失败已保留：固定ids键误读和NPZ惰性重复解压；未执行金融事件。最新通过文件EXPORTED_INPUTS.json，旧EXPORT_ERROR.json不覆写。']
 (P/'READOUT.txt').write_text('\n'.join(lines)+'\n')
 files={str(x.relative_to(P)):sha(x) for x in P.rglob('*') if x.is_file() and x.name not in ('PACKAGE_SHA256.json',) and '__pycache__' not in str(x)}
 save('PACKAGE_SHA256.json',dict(financial_events=0,files=files,root_digest=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()))
 print('READINESS_FINAL',summary['status'],'financial_events',0,'stock_mapping_exact',1709,'source_action_schemas',len(conditional),'files',len(files))
if __name__=='__main__':main()
