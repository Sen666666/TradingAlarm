"""Future separately approved Jan13 ACTION entry. Never invoked by preparation."""
from pathlib import Path
import argparse
import upgrade_runtime as U
def main():
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--checkpoint-sha',required=True);p.add_argument('--grant',type=Path,required=True);p.add_argument('--grant-sha',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute-action',action='store_true');a=p.parse_args()
 U.require(a.execute_action,'explicit future ACTION request required');U.require(U.sha(a.checkpoint)==a.checkpoint_sha,'wrong upgraded checkpoint')
 r=U.UpgradedRunner.restore(a.checkpoint);U.validate_action_grant(r,a.grant,a.grant_sha,a.checkpoint_sha)
 r.rights_future_grant=dict(path=str(a.grant.resolve()),sha256=a.grant_sha,base_checkpoint_sha256=a.checkpoint_sha)
 r.corporate_actions('2022-01-13');a.out.mkdir(parents=True,exist_ok=False);r.checkpoint(a.out/'2022-01-13-ACTION.pkl')
if __name__=='__main__':main()
