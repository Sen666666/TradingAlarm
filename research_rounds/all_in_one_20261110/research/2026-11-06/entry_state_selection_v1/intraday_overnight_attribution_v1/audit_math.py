from pathlib import Path
import ast,sys,json
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,'/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/pvr_information_v1/feature_design')
from features import original_pvr,original_observation_clock
W=.9**np.arange(20,-1,-1);W/=W.sum()
code=ast.parse((O/'compute.py').read_text());fn=next(n for n in code.body if isinstance(n,ast.FunctionDef) and n.name=='compute');calmap={}
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(O/'compute.py'),'exec'))
idx=pd.bdate_range('2020-01-01',periods=230);r=np.tile([.01,-.012],115);c=100*np.exp(np.cumsum(r));f=pd.DataFrame({'close':c,'open':c*np.exp(-.005),'amount':np.tile([100.,130.,80.,160.,90.],46),'segment_id':0},index=idx)
f.loc[idx[100],'close']=f.loc[idx[99],'close'];f.loc[idx[100],'open']=f.loc[idx[99],'close']*np.exp(.04)
a=compute(f);assert a.loc[idx[100],'r']==0;expected=(a.loc[idx[100],'prev_m']-1)*a.loc[idx[100],'n']/a.loc[idx[100],'scale'];assert abs(expected-a.loc[idx[100],'star_e'])<1e-14
assert a.e.first_valid_index()==idx[64] and a.star_e.first_valid_index()==idx[65] and a.score.first_valid_index()==idx[84] and a.star_score.first_valid_index()==idx[85]
g=f.copy();g.loc[idx[150],'open']=np.nan;b=compute(g);pd.testing.assert_series_equal(a.score,b.score);assert b.loc[idx[150:171],'star_score'].isna().all() and np.isfinite(b.loc[idx[171],'star_score'])
g=f.copy();g.loc[idx[120]:,'segment_id']=1;b=compute(g);assert pd.isna(b.loc[idx[120],'prev_m']) and b.loc[idx[120:205],'star_score'].isna().all();assert np.isfinite(b.loc[idx[205],'star_score'])
g=f.copy();g.loc[idx[120],'amount']=0;b=compute(g);assert pd.isna(b.loc[idx[121],'prev_m']);assert b.loc[idx[121:206],'star_score'].isna().all()
g=f.copy();g.loc[idx[150]:,['close','open','amount']]*=99;b=compute(g);pd.testing.assert_frame_equal(a.loc[:idx[149]],b.loc[:idx[149]],check_exact=True)
x=np.array([-100,-1,-1e-4,-1e-12,-1e-300,0,1e-300,1e-12,1e-4,1,100.]);rat=np.divide(np.tanh(x),x,out=np.ones_like(x),where=x!=0);xl=x.astype(np.longdouble);oracle=np.divide(np.tanh(xl),xl,out=np.ones_like(xl),where=xl!=0);err=float(np.max(abs(rat-oracle)));assert err<1e-15
report=dict(synthetic_tests_passed=6,zero_return_example={'e_original':float(a.loc[idx[100],'e']),'e_star':float(a.loc[idx[100],'star_e']),'continuous_formula':float(expected)},warmup_zero_based={'old_e':64,'new_e':65,'old_score':84,'new_score':85},missing_open='old PVR unchanged; new score unknown for affected21 windows',block_reset='source and amount-invalid reset previous m, full warmup required',future_poison='prefix exact',tanhc_longdouble_max_error=err,structural_floor_counterexample={'r':0,'s':1e-8,'n':.1,'m_t':1,'m_prev':1.5,'star_e':5000000,'note':'hypothetical mathematical witness, not measured data; no clipping'})
(O/'MATH_TESTS.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
# Exact21 contribution exports for fixed named cases, actual signal dates and largest score changes.
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz");cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]);calmap={d:i for i,d in enumerate(cal)}
sc=pd.read_parquet(O/'CANDIDATE_SCORES.parquet');cases=[('600056.SH','2022-03-03'),('600056.SH','2022-03-30'),('300182.SZ','2022-01-04'),('002385.SZ','2022-03-04'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29'),('300666.SZ','2026-01-14'),('301611.SZ','2026-01-14')];cases += [("300666.SZ","2026-01-15"),("301611.SZ","2026-01-15")];cases+=list(sc.loc[sc.score_delta.abs().nlargest(10).index,['sid','day']].itertuples(index=False,name=None))
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');manifest={x['symbol']:x for x in json.loads(M.read_text())};rows=[];checks=[]
for sid,day in cases:
 m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));f=pd.read_parquet(p).loc[:'2026-05-15'];a=compute(f);d=pd.Timestamp(day)
 if d not in a.index:continue
 ix=a.index.get_loc(d);g=a.iloc[max(0,ix-20):ix+1].copy()
 if len(g)!=21 or g.star_e.isna().any():continue
 g['sid']=sid;g['evaluation_day']=day;g['contribution_day']=g.index.strftime('%Y-%m-%d');g['weight']=W;g['weighted_old_e']=g.e*W;g['weighted_delta']=g.delta*W;g['weighted_star_e']=g.star_e*W
 assert abs(g.weighted_star_e.sum()-a.at[d,'star_E'])<1e-12
 assert abs(g.weighted_delta.sum()-a.at[d,'delta_E'])<1e-12
 rows.append(g);checks.append(dict(sid=sid,day=day,original_score=a.at[d,'score'],new_score=a.at[d,'star_score'],score_delta=a.at[d,'score_delta'],delta_E=a.at[d,'delta_E'],weighted_delta_sum=g.weighted_delta.sum(),max_contribution_day=g.loc[g.weighted_delta.abs().idxmax(),'contribution_day'],max_abs_contribution=g.weighted_delta.abs().max(),factor_change_days=int(g.factor_change.abs().gt(1e-12).sum()),net_flat_days=int(g.r.eq(0).sum()),outside_original_bound=int(g.star_e.abs().gt(1.5).sum())))
pd.concat(rows,ignore_index=True).to_csv(O/'EXACT_21_CONTRIBUTIONS.csv',index=False);pd.DataFrame(checks).to_csv(O/'EXACT_21_CHECKS.csv',index=False);print(pd.DataFrame(checks).to_string(index=False))
