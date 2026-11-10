"""Freeze selected full-run source identities without account events."""
from pathlib import Path
import argparse,json
import run_window as R


def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=R.WINDOWS,required=True);args=p.parse_args()
    out=R.O/'prepared'/args.window;out.mkdir(parents=True,exist_ok=True)
    R.I.configure_scores(args.window,out)
    files,sources=R.source_freeze(args.window)
    record=dict(approved=False,windows=[args.window],source_freeze=sources,
                start=R.WINDOWS[args.window][0],end=R.WINDOWS[args.window][1],arms=R.C.ARMS,
                prepared_without_account_initialization=True,
                root_authorization_still_required=True)
    R.save(out/'PROPOSED_FULL_AUTHORIZATION.json',record)
    print('PREPARED_WITHOUT_ACCOUNT',out,flush=True)


if __name__=='__main__':main()
