"""Bounded saved-source market context; no account event or indicator calculation."""
import month_runtime as M
def main():
 M.guard();m=M.MonthInputs(M.read(M.HERE/'POLICY_INPUT_IDENTITY.json')['inputs']['2025_26']['path']);f=m.table('f1_observations');g=f[f.policy_scope=='URFI881268'].sort_values('day');base=float(g.iloc[0]['industry_close_as_source']);rows=[]
 for day in ['2025-07-01','2025-07-18','2025-07-21','2025-07-22','2025-07-23','2025-07-24','2025-07-25','2025-07-28','2025-07-30','2025-07-31']:
  row=g[g.day==day].iloc[0];p=M.HERE/'runs/2025_26-C10'/(day+'-CLOSE.json');state=M.read(p) if p.exists() else None
  rows.append(dict(day=day,sector_close=float(row['industry_close_as_source']),price_return_since_Jul1_close=float(row['industry_close_as_source'])/base-1,breadth=float(row['breadth']),policy_scope=state['account']['policy']['scopes']['URFI881268'] if state else None))
 M.E.IO.write_json(M.HERE/'july_end_analysis/ENGINEERING_PRICE_CHAIN.json',dict(rows=rows,financial_events=0,source='unchanged original F1 observation price/breadth; return only descriptive; CLOSE state cannot decide earlier same-day OPEN'),encoder=M.E.encode)
if __name__=='__main__':main()
