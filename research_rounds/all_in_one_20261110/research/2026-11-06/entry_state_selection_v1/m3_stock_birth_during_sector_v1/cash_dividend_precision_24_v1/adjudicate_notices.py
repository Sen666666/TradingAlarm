from pathlib import Path
from decimal import Decimal as D
import re,json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent/'cash_dividend_source_feasibility_v1';a=pd.read_csv(P/'PRECISION_DIFFERENCES.csv',dtype=str);u=pd.read_csv(O.parent/'corporate_action_path_audit_v1/UNKNOWN_FIRST_INTERRUPTION_AUDIT.csv',dtype=str).set_index('round_id');rows=[];evidence=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for r in a.to_dict('records'):
 sid=r['sid'];txt=O/'notice_pdf'/(sid+'.txt');pdf=txt.with_suffix('.pdf');meta=json.loads(txt.with_suffix('.json').read_text());t=re.sub(r'\s+','',txt.read_text());d=D(r['public_gross_cash_per_share']);ds=D(r['cash_per_old_share']);x=u.loc[r['round_id']]
 assert meta['metadata']['secCode']==sid[:6] and sid[:6] in t and sha(pdf)==meta['sha256']
 numeric=[(m,D(m.group())) for m in re.finditer(r'(?<![0-9.])[0-9]+\.[0-9]+(?![0-9.])',t)]
 # Verify source number and its actual dividend context, not a search-snippet rounded display.
 cashhits=[t[max(0,m.start()-80):m.end()+100] for m,v in numeric if v==d*10 and '每10股' in t[max(0,m.start()-40):m.start()]]
 if not cashhits:cashhits=[t[max(0,m.start()-80):m.end()+100] for m,v in numeric if v==d and ('每股现金红利' in t[max(0,m.start()-20):m.start()] or '每股派发现金红利' in t[max(0,m.start()-20):m.start()])]
 assert cashhits,(sid,'cash context absent')
 dates=set()
 for z in re.finditer(r'(20\d{2})\s*(?:年|/)\s*(\d{1,2})\s*(?:月|/)\s*(\d{1,2})(?:日)?',txt.read_text()):dates.add(f'{int(z[1]):04}-{int(z[2]):02}-{int(z[3]):02}')
 assert set([r['record_date'],r['pay_date'],r['status_day']])<=dates,(sid,'dates absent')
 # Source API exact row is independently tied to this named, coded issuer implementation notice.
 raw=json.loads(Path(r['source_path']).read_text(),parse_float=D);rs=[z for z in raw['raw']['records'] if z['F020D']==r['status_day']];assert len(rs)==1
 z=rs[0];assert D(str(z['F012N']))/10==d and z['F018D']==r['record_date'] and z['F023D']==r['pay_date']
 assert not z.get('F010N') and not z.get('F011N') and '送' not in z['F007V'] and '转' not in z['F007V']
 prev=D(x['raw_close_previous']);f0=D(x['factor_previous']);f1=D(x['factor_current']);err_source=abs((f0*prev/(prev-ds))/f1-1);err_cash=abs((f0*prev/(prev-d))/f1-1)
 assert err_source<D('1e-11') and err_cash>D('1e-11')
 refs=re.findall(r'(?:登记日|交易日|前一日)收盘价[-—−]([0-9]+\.[0-9]+)',t)
 dr=sorted(set(refs));dr=dr[0] if len(dr)==1 else None
 if dr is not None:assert D(dr)>0
 q=D(r['register_held_qty_in_original_simulation']);r.update(d_source=str(ds),d_cash=str(d),d_ref=dr,source_factor_relative_error=str(err_source),wrong_cash_factor_relative_error=str(err_cash),net80_delta_at_original_register_qty=str(q*D('.8')*(d-ds)),notice_url=meta['url'],notice_pdf_sha256=sha(pdf),notice_text_sha256=sha(txt),notice_code_verified=True,notice_cash_context_verified=True,notice_clock_context_verified=True,scenario_permission_basis='DOCUMENTED_CASH_WITH_FROZEN_SOURCE_COORDINATE_ONLY',d_ref_usage='Disclosure only; never substituted into source signal factor')
 rows.append(r);evidence.append({'sid':sid,'url':meta['url'],'cash_excerpts':cashhits,'date_excerpts':[t[max(0,m.start()-20):m.start()+140] for m in re.finditer('股权登记日|现金红利将于|相关日期',t)][:8],'d_ref_if_explicit':dr,'identity_current_name_may_differ':'Code and implementation issuer body checked; e.g. 002129 中环股份 vs current TCL中环.'})
assert len(rows)==24
pd.DataFrame(rows).to_csv(O/'ADJUDICATED_24.csv',index=False);(O/'NOTICE_EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
(O/'FACT_SUMMARY.json').write_text(json.dumps({'cases':24,'official_implementation_pdfs':24,'code_cash_clock_checks':24,'source_factor_matches':24,'precise_cash_cannot_replace_source_factor':24,'explicit_d_ref_extracted':sum(r['d_ref'] is not None for r in rows),'net80_register_delta_abs_max':str(max(abs(D(r['net80_delta_at_original_register_qty'])) for r in rows)),'net80_register_delta_abs_sum':str(sum(abs(D(r['net80_delta_at_original_register_qty'])) for r in rows)),'note':'These are point cash differences, not path-PnL bounds. Corporate facts retrieved currently, not archived PIT or actual investor tax.'},ensure_ascii=False,indent=2)+'\n')
print('24 coded issuer implementation notices matched; source coordinates and precise cash separated.')
