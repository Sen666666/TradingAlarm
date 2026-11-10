"""Extend the frozen native old-Q export without signal/lifecycle/account recomputation."""
from pathlib import Path
import ast
BASE=Path(__file__).resolve().parents[2]
ORIGINAL=BASE/'fast_entry_equity_2022_v1/prepare_inputs.py'
source_text=ORIGINAL.read_text()
# Import only the identical read-only helper definitions and dependency setup.
exec(compile(source_text[:source_text.index('\ndef main():')],str(ORIGINAL)+':helpers','exec'),globals())
O=Path(__file__).resolve().parent;R=BASE;E=R/'m3_stock_birth_during_sector_v1'
OUT=O/'OLD_NATIVE_Q_EXTENDED.parquet'
if OUT.exists():raise RuntimeError('Do not overwrite a completed native export')
main=next(n for n in ast.parse(source_text).body if isinstance(n,ast.FunctionDef) and n.name=='main')
body=ast.get_source_segment(source_text,main)
import textwrap
body=textwrap.dedent('\n'.join(body.splitlines()[1:]))
# Exactly the original definition-only Facts/FastMarket constructor.
exec(compile(body[:body.index("tpath=W/")],str(ORIGINAL)+':native_setup','exec'),globals())
source(ORIGINAL)
all22=pd.read_parquet(source(R/'fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet'))
cpd=pd.read_parquet(source(R/'fast_entry_equity_2022_v1/CANONICAL_CP_2022_2026.parquet'));cpmap=cpd.set_index(['sid','day']).to_dict('index')
pv=pd.read_parquet(source(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')).set_index(['sid','day'])
ab=pd.read_csv(source(E/'SEALED_ALL_BIRTH_EVENTS.csv'),parse_dates=['day'],low_memory=False)
ab=ab[ab.event_type.isin(['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'])].copy();assert not ab.duplicated(['sid','day']).any();abmap=ab.set_index(['sid','day']).to_dict('index')
qa_dates={pd.Timestamp('2022-01-05'),pd.Timestamp('2022-11-07')}
targetcal=cal[((cal>='2024-09-01')&(cal<='2024-12-31'))|((cal>='2026-01-01')&(cal<='2026-06-30'))|cal.isin(list(qa_dates))]
raw={};cp={};epochs={}
epoch_source=body[body.index('last=None;counter=0;'):body.index('epochs[sid]=rows')+len('epochs[sid]=rows')]
epoch_source=textwrap.dedent(epoch_source)
# Source slice had one leading indentation level removed by its first line; restore dedent.
epoch_lines=epoch_source.splitlines();epoch_source=epoch_lines[0]+'\n'+'\n'.join(l[1:] if l.startswith(' ') else l for l in epoch_lines[1:])
epoch_source=epoch_source.replace('targets=set(cal22)','targets=set(targetcal)')
for n,sid in enumerate(ids):
 r=manifest[sid]
 for p,h in r['source_sha256'].items():source(p,h)
 for p,h in r['output_sha256'].items():source(p,h)
 ff=pd.read_parquet(r['refs']['facts']).loc[:END]
 f.f[sid]=ff;b.series[sid].states=ff[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 sp=next(p for p in r['source_sha256'] if p.endswith('/signal.parquet'));raw[sid]=pd.read_parquet(sp).loc[:END]
 cp[sid]=pd.read_parquet(r['refs']['CP1']).loc[:END]
 exec(compile(epoch_source,str(ORIGINAL)+':native_epoch','exec'),globals())
 if (n+1)%250==0:print('OLD_FACTS',n+1,round(timer.monotonic()-began,1),flush=True)
row_source=body[body.index('ev=native_elig(s,ss,clock,'):body.index('if keep22:rows22.append(row)')]
row_lines=row_source.splitlines();row_source=row_lines[0]+'\n'+'\n'.join(l[2:] if l.startswith('  ') else l for l in row_lines[1:])
rows=[]
for n,d in enumerate(targetcal):
 clock,stocks,sectors=f.packet(datetime.combine(d.date(),time(15,10),TZ),'I');ss={s.sector_id:s for s in sectors};buyable=m.market_buyable(clock.decision_at)
 for s in stocks:
  sid=s.security_id
  exec(compile(row_source,str(ORIGINAL)+':identical_native_row','exec'),globals())
  rows.append(row)
 if (n+1)%20==0:print('OLD_Q_DAYS',n+1,len(targetcal),round(timer.monotonic()-began,1),flush=True)
x=pd.DataFrame(rows)
for c in ['event_Q','continuing_Q','i_buy','i_target','cp_fresh','cp_trace_known','AB_I_qualified','AB_PVR_known']:x[c]=x[c].astype('boolean')
assert len(x)==len(ids)*len(targetcal) and not x.duplicated(['sid','day']).any()
qa=x[x.day.isin(qa_dates)].sort_values(['sid','day']).reset_index(drop=True)
oldqa=all22[all22.day.isin(qa_dates)].sort_values(['sid','day']).reset_index(drop=True)
for c in all22.columns:pd.testing.assert_series_equal(qa[c],oldqa[c],check_dtype=False,check_exact=True)
extended=x[~x.day.isin(qa_dates)].copy();extended.to_parquet(OUT,index=False)
for mod in list(sys.modules.values()):
 pp=getattr(mod,'__file__',None)
 if pp and (str(pp).startswith(str(RR)) or str(pp).startswith(str(W))) and str(pp).endswith('.py'):source(pp)
source(Path(__file__))
for p,h in SOURCES.items():assert sha(p)==h,(p,'end source drift')
save('OLD_NATIVE_Q_SOURCE_HASHES.json',SOURCES)
save('OLD_NATIVE_Q_QA.json',dict(passed=True,rows=len(extended),stocks=len(ids),days=len(extended)//len(ids),equivalence_2022_stockdays=len(qa),every_original_column_exact=True,no_accounts=True,no_lifecycles=True,no_signal_recompute=True))
print('DONE',len(extended),round(timer.monotonic()-began,1),flush=True)
