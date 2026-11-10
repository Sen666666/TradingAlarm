"""Standard-library regression suite; temporary fixtures, no research execution."""
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from archive_paths import ArchivePaths

HERE = Path(__file__).resolve().parent
STATUS = Path('research/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2')

class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='research relocation 中文 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'moved archive'
        (self.root / 'manifest').mkdir(parents=True)
        shutil.copytree(HERE, self.root / 'tools', ignore=shutil.ignore_patterns('__pycache__'))
        self.old = '/nonexistent-original-research-root'
        (self.root / 'manifest/SOURCE_MAP.json').write_text(json.dumps({'roots':[{'source':self.old,'destination':'project','kind':'directory'}]}))
        (self.root / 'project').mkdir()
        data = self.root / 'project/input.txt'; data.write_text('frozen evidence\n')
        self.digest = hashlib.sha256(data.read_bytes()).hexdigest()
        (self.root / 'inputs.csv').write_text('absolute_path,expected_sha256_from_frozen_manifest\n' + self.old + '/input.txt,' + self.digest + '\n')
        (self.root / 'manifest/FILES.csv').write_text('destination,kind,bytes,sha256\nproject/input.txt,file,'+str(data.stat().st_size)+','+self.digest+'\n')
        for rel in ['RUN_STATUS.json','runtime_checkpoint/LATEST.json']:
            dest=self.root/STATUS/rel;dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(HERE.parent/STATUS/rel,dest)

    def cli(self, *args, env=None):
        clean = dict(os.environ);clean.pop('RESEARCH_ARCHIVE_ROOT',None)
        clean['PYTHONDONTWRITEBYTECODE']='1'
        if env:clean.update(env)
        return subprocess.run([sys.executable,str(self.root/'tools/research.py'),*args],cwd='/',env=clean,text=True,capture_output=True)

    def test_moved_status(self):
        r=self.cli('status');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['certified_day'],'2024-09-30')

    def test_moved_legacy_and_relative_resolve(self):
        for path in [self.old+'/input.txt','project/input.txt']:
            r=self.cli('resolve',path);self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(r.stdout)['archive_path'],str(self.root/'project/input.txt'))

    def test_root_override_and_precedence(self):
        r=self.cli('status',env={'RESEARCH_ARCHIVE_ROOT':str(self.root)})
        self.assertEqual(r.returncode,0,r.stderr)
        r=self.cli('--project-root',str(self.root),'status',env={'RESEARCH_ARCHIVE_ROOT':'/nonexistent'})
        self.assertEqual(r.returncode,0,r.stderr)

    def test_moved_hash_checks(self):
        r=self.cli('--input-manifest','inputs.csv','verify','--current-inputs','--archive')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(json.loads(r.stdout)['passed'])
        (self.root/'project/input.txt').write_text('changed')
        self.assertNotEqual(self.cli('--input-manifest','inputs.csv','verify','--current-inputs','--archive').returncode,0)

    def test_unknown_traversal_and_external_link_rejected(self):
        external=Path(self.temp.name).resolve()/'outside.txt';external.write_text('outside')
        (self.root/'project/link.txt').symlink_to(external)
        for bad in ['/unmapped/input.txt','../outside.txt',self.old+'/../outside.txt','project/link.txt']:
            r=self.cli('resolve',bad);self.assertNotEqual(r.returncode,0,bad)
            self.assertIn('Error:',r.stderr)

    def test_bad_map_rejected(self):
        path=self.root/'manifest/SOURCE_MAP.json'
        for dest in ['../outside','/outside','.']:
            path.write_text(json.dumps({'roots':[{'source':self.old,'destination':dest,'kind':'directory'}]}))
            self.assertNotEqual(self.cli('status').returncode,0)

    def test_missing_input_does_not_fall_back(self):
        (self.root/'project/input.txt').unlink()
        r=self.cli('--input-manifest','inputs.csv','verify','--current-inputs')
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(json.loads(r.stdout)['passed'])

    def test_builder_configurable_and_non_destructive(self):
        source=Path(self.temp.name).resolve()/'tiny source';source.mkdir();(source/'evidence.txt').write_text('retain bytes')
        (source/'relative.txt').symlink_to('evidence.txt')
        config=Path(self.temp.name).resolve()/'sources.json';config.write_text(json.dumps({'roots':[{'source':str(source),'destination':'project','kind':'directory'}]}))
        output=Path(self.temp.name).resolve()/'new archive'
        cmd=[sys.executable,str(self.root/'tools/build_archive.py'),'--source-map',str(config),'--output',str(output)]
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
        dry=subprocess.run(cmd+['--dry-run'],cwd='/',env=env,capture_output=True,text=True)
        self.assertEqual(dry.returncode,0,dry.stderr);self.assertFalse(output.exists())
        if sys.platform=='darwin':
            run=subprocess.run(cmd,cwd='/',env=env,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual((output/'project/evidence.txt').read_bytes(),(source/'evidence.txt').read_bytes())
            self.assertNotEqual((output/'project/evidence.txt').stat().st_ino,(source/'evidence.txt').stat().st_ino)
            self.assertEqual((output/'project/relative.txt').resolve(),output/'project/evidence.txt')
            again=subprocess.run(cmd,cwd='/',env=env,capture_output=True,text=True)
            self.assertNotEqual(again.returncode,0)

if __name__=='__main__':unittest.main(verbosity=2)
