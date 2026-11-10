"""Four approved next days only; same reusable month entry and locked grant."""
import subprocess,sys
import month_runtime as M
def main():
 gate=M.read(M.HERE/'READ_ONLY_GATE.json');assert gate['passed'] and gate['outside_cutoff_and_old_date_guards_tested'];M.guard()
 for window in ('2022','2025_26'):
  for mode in ('C10','C_BATCH20'):
   root=M.HERE/'runs'/(window+'-'+mode)
   assert M.read(root/'PROGRESS.json')['phase']=='IMPORT','no silent completed path rerun'
   with (M.HERE/(window+'-'+mode+'-RUN.out')).open('w') as so,(M.HERE/(window+'-'+mode+'-RUN.err')).open('w') as se:
    result=subprocess.run([sys.executable,'-B',str(M.HERE/'run_month.py'),'--window',window,'--mode',mode,'--grant',str(M.HERE/'grants/001_first_migration.json')],stdout=so,stderr=se)
   if result.returncode:raise RuntimeError('stop; preserve ERROR and last correct checkpoint '+str(root))
   print('COMPLETED_LIMITED',window,mode,flush=True)
if __name__=='__main__':main()
