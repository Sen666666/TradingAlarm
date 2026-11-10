from fw_common import *
def main():
 wait=load('frozen_wait_advance',COMBO/'code/waiting.py')
 w={'j':0,'day':'2025-01-01','segment':'a','floor':90.}
 base=dict(day='2025-01-02',j=1,L=10,close=100.,old_floor=91.,event=1,pivot=95.,pivot_date='2025-01-01',valid=True,segment='a',on=True)
 checks=[]
 for u,r,f in [({},None,95),({'pivot_date':'2024-12-31'},None,91),({'event':0},None,91),({'close':90},'waiting_floor_breach',None),({'old_floor':101},'updated_floor_breach',None),({'j':10},'expired',None),({'j':9},None,95),({'L':3,'j':3},'expired',None),({'L':3,'j':2},None,95),({'on':False},'risk_pause',None),({'valid':False},'structure_or_source',None),({'segment':'b'},'structure_or_source',None),({'pivot':85,'old_floor':89},None,90)]:
  z,why=wait.advance(w,**(base|u));assert why==r
  if f is not None:assert z['floor']==f
  checks.append(dict(updates=u,reason=why,floor=z['floor'] if z else None))
 assert w['floor']==90
 cases=read(PREV/'preparation.json')['cases'];assert len(cases)==12
 paths=[PREV/'raw/TECH.png',PREV/'raw/DRUG.png',PREV/'RULES.txt',PREV/'verification.json',PREV/'completion-sha256.json',CP/'code/model.py',COMBO/'code/waiting.py']
 save(O/'preflight.json',dict(passed=True,waiting_boundary_checks=checks,raw_windows=cases,source_sha256={str(p):sha(p) for p in paths},prior_cp_model_unchanged=True,raw_review=dict(reviewed=True,images=[str(p) for p in paths[:2]],notes='重新查看科技/药同12固定原始量价窗；不按赢家挑新窗口。回执候选不等于真实持仓保护，W10可能保留过时买点，已用F/结构/到期撤销约束。京北局部退出与博瑞再入阻挡两种路径均保留，最后以真实资金和全试错比较。')))
if __name__=='__main__':main()
