from driver import *
if __name__=='__main__':
 root=O/'CONTROL';root.mkdir(exist_ok=True);prep=R/'research_rounds/e0-reclaim-accounts-20261026/prepared';runner.PREP=prep;engine.PREP=prep;audit.PREP=prep;audit.HERE=root
 rp=root/'execution-rules-v2.json'
 if not rp.exists():rp.symlink_to(BASE/'execution-rules-v2.json')
 runner.run(root/'accounts-v2',modes=['E0','I'],technical=False);audit.main('full')
