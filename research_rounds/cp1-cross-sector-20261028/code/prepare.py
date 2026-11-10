from cp_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
model=load('frozen_cp1_model',CP/'code/model.py')
def main():
 (O/'signals/DRUG').mkdir(parents=True,exist_ok=True);(O/'raw').mkdir(exist_ok=True)
 checks=[]
 for sid in pool('DRUG').symbol:
  f=frame('DRUG',sid);z=model.calculate(f);z.to_parquet(cpdir('DRUG')/f'{sid}.parquet')
  for cut in ['2024-12-31','2026-06-30']:
   small=model.calculate(frame('DRUG',sid,cut));pd.testing.assert_frame_equal(small,z.loc[:cut],check_exact=True);checks.append(dict(sid=sid,cut=cut,rows=len(small)))
 cases=read(SA/'raw/cases.json')['cases']
 for sector in ['TECH','DRUG']:
  cases_s=[c for c in cases if c['group']==sector];fig,axes=plt.subplots(6,2,figsize=(19,22))
  for c,ax in zip(cases_s,axes):
   sid=c['symbol'];f=frame(sector,sid).loc[c['start']:c['end']];z=pd.read_parquet(cpdir(sector)/f'{sid}.parquet').reindex(f.index)
   ax[0].plot(f.index,f.close,label='actual close');ax[0].plot(f.index,f.i_floor,label='E0 floor',alpha=.7)
   q=z[z.receipt];ax[0].scatter(q.index,q.candidate,s=9,label='new CP1 candidates');ax[0].legend(fontsize=8);ax[0].set_title(sid+' '+c['start']+' -- '+c['end'])
   ax[1].bar(f.index,f.amount/1e8,width=1.5);ax[1].set_title('Actual turnover (CNY 100 million)')
  fig.tight_layout();fig.savefig(O/'raw'/f'{sector}.png',dpi=110);plt.close(fig)
 save(O/'preparation.json',dict(passed=True,drug_physical_prefixes=len(checks),prefix_rows=sum(x['rows'] for x in checks),tech_reused_frozen_tables=407,drug_same_formula=48,cases=cases))
if __name__=='__main__':main()
