from pathlib import Path
O=Path(__file__).parent
p=O/'manual_decisions.py';s=p.read_text();s=s.replace('旧备注“非全周期新高”与实际收盘不符：7月已超过2月峰；仍因幅度与后续长回撤维持普通，纠正事实不自动升级。','旧备注“非全周期新高”口径含混：7月确已超过2月峰，但不能据此断言更长期全历史新高；仍因幅度与后续长回撤维持普通，明确比较基准而不自动升级。');p.write_text(s)
p=O/'build_review.py';s=p.read_text();s=s.replace("r.update(stats(sec,a,b));m,mr=members(r);", "r.update(stats(sec,a,b));r['last_aux_status']=aa.iloc[-1]['status'];r['last_aux_down_confirm']=aa.iloc[-1]['down_confirm'];r['observed_cycle_status']='截至观察日尚无20%峰后回撤确认' if str(aa.iloc[-1]['status']).startswith('open') else '截至观察日已有20%峰后回撤确认，非经济退出判据';m,mr=members(r);")
s=s.replace('旧备注称非全周期新高，但源日线2020-07-13高于2020-02-25；该文字事实纠正，普通级不变。','旧备注“非全周期新高”未说明比较基准；源日线2020-07-13高于2020-02-25，但这不等于全历史新高。本次明确基准，普通级不变。')
s=s.replace('软件M063原备注“非全周期新高”有误：2020-07已超过2月峰；本次仅纠正事实，未自动升级。','软件M063原备注“非全周期新高”口径含混：2020-07已超过2月峰，但不等于更长期全历史新高；本次明确基准，未自动升级。')
s=s.replace("for name,d in [('MANUAL_CYCLES.csv',C)", "for name,d in [('GENUINELY_NEW_PRIORITIES.csv',C[C.is_genuinely_new_priority]),('MANUAL_CYCLES.csv',C)")
s=s.replace("('PHASES.csv',pd.DataFrame(phases))", "('PHASES.csv',pd.DataFrame(phases).sort_values(['canonical_id','start','end']))")
p.write_text(s)
p=O/'inspect_paths.py';s=p.read_text();s=s.replace("import matplotlib.pyplot as plt", "import matplotlib.pyplot as plt\nfrom matplotlib.font_manager import FontProperties\nTITLEFONT=FontProperties(fname='/System/Library/Fonts/STHeiti Light.ttc')")
s=s.replace("ax.set_title(name+' / '+sid+' / '+a[:4]+'-'+b[:4])", "ax.set_title(name+' / '+sid+' / '+a[:4]+'-'+b[:4],fontproperties=TITLEFONT)")
p.write_text(s)
