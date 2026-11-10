"""Pure-feature entry controller. Only ACT gate currently root-authorized."""
from pathlib import Path
import argparse,json
from shared_act import run_gate

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['act-gate']);p.add_argument('--freeze-file',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 passed=run_gate(a.freeze_file,a.out);print(json.dumps({'ACT_gate_passed':passed,'full_1799_workers_started':0,'output':str(Path(a.out).resolve())},ensure_ascii=False));return 0 if passed else 2
if __name__=='__main__':raise SystemExit(main())
