"""Small research-output I/O only. No strategy, market or account logic."""
from contextlib import contextmanager
from pathlib import Path
import gzip,json,os,pickle,tempfile,hashlib,inspect,marshal,sys
from datetime import datetime,timezone

@contextmanager
def atomic_binary(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:
   yield f
   f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 except BaseException:
  try:os.unlink(tmp)
  except FileNotFoundError:pass
  raise

def write_bytes(path,data):
 with atomic_binary(path) as f:f.write(data)

def write_json(path,value,*,encoder=None):
 data=(json.dumps(value,ensure_ascii=False,indent=2,default=encoder,allow_nan=False)+'\n').encode('utf-8')
 write_bytes(path,data)

def write_pickle(path,value):
 with atomic_binary(path) as f:pickle.dump(value,f,protocol=5)

def write_gzip_jsonl(path,records,*,encoder=None):
 with atomic_binary(path) as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:
   for value in records:f.write((json.dumps(value,ensure_ascii=False,default=encoder,allow_nan=False)+'\n').encode('utf-8'))

def prepare_targets(targets,*,directory_keys=()):
 """Check every prefix/checkpoint/final/failure destination before running.

 File-level atomicity only. A multi-file checkpoint must publish/check its
 manifest and hashes; this helper does not promise a multi-file transaction.
 """
 result={}
 for name,target in targets.items():
  path=Path(target);parent=path if name in directory_keys else path.parent
  parent.mkdir(parents=True,exist_ok=True)
  fd,probe=tempfile.mkstemp(prefix='.research-io-probe-',dir=parent);os.close(fd)
  try:
   write_bytes(probe,b'atomic research output probe\n')
   assert Path(probe).read_bytes()==b'atomic research output probe\n'
  finally:Path(probe).unlink(missing_ok=True)
  result[name]=dict(target=str(path),parent=str(parent),parent_created_or_existing=True,atomic_write_probe_passed=True)
 return result

def _publish_tree(staged,destination):
 for source in sorted(Path(staged).rglob('*')):
  if source.is_file():
   target=Path(destination)/source.relative_to(staged)
   target.parent.mkdir(parents=True,exist_ok=True);os.replace(source,target)

def _class_identity(cls):
 module=sys.modules.get(cls.__module__);path=getattr(module,'__file__',None)
 if path is None and cls.__module__==__name__:path=__file__
 if path is None:
  try:path=inspect.getsourcefile(cls)
  except (OSError,TypeError):path=None
 path=str(Path(path).resolve()) if path and Path(path).is_file() else None
 return dict(module=cls.__module__,class_name=cls.__qualname__,module_path=path,module_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None)

def runner_identity(runner):
 """Actual bound methods, including overrides; never inferred from a filename."""
 trading_class=getattr(type(runner),'_research_trading_class',type(runner));functions={}
 for name in ('planning','opening','route'):
  method=getattr(runner,name,None)
  if method is None:continue
  fn=getattr(method,'__func__',method)
  owner=next((cls for cls in trading_class.__mro__ if cls.__dict__.get(name) is fn),None)
  code=fn.__code__
  functions[name]=dict(qualified_name=fn.__qualname__,declared_module=fn.__module__,code_filename=code.co_filename,code_first_line=code.co_firstlineno,code_sha256=hashlib.sha256(marshal.dumps(code)).hexdigest(),defining_class=_class_identity(owner) if owner else None)
 return dict(runtime_class=_class_identity(type(runner)),trading_class=_class_identity(trading_class),functions=functions,python_version=sys.version)

def assert_checkpoint_identity(runner,path):
 path=Path(path);side=path.with_suffix('.provenance.json')
 if not side.exists():raise ValueError('Checkpoint has no generation-time engine identity; legacy identity must not be backfilled: '+str(path))
 record=json.loads(side.read_text());actual=runner_identity(runner)
 if hashlib.sha256(path.read_bytes()).hexdigest()!=record['checkpoint_sha256']:raise ValueError('Checkpoint provenance SHA mismatch')
 if actual!=record['engine_identity']:raise ValueError('Checkpoint engine identity mismatch before restore')
 return actual

class _AtomicRunnerExports:
 """Only export boundaries change; no trading method is overridden."""
 def checkpoint(self,out,last_event):
  out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='.checkpoint-staging-',dir=out.parent) as tmp:
   super().checkpoint(Path(tmp),last_event)
   for checkpoint in Path(tmp).glob('*.pkl'):
    write_json(checkpoint.with_suffix('.provenance.json'),dict(created_at_UTC=datetime.now(timezone.utc).isoformat(),last_completed_event=str(last_event),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),engine_identity=runner_identity(self),scope='created now by this actual runner; not a legacy backfill'))
   _publish_tree(tmp,out)
 def dump_joint(self,path):
  path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='.journal-staging-',dir=path.parent) as tmp:
   staged=Path(tmp)/path.name
   super().dump_joint(staged)
   _publish_tree(tmp,path.parent)
 def restore(self,path):
  expected=assert_checkpoint_identity(self,path)
  result=super().restore(path)
  if runner_identity(self)!=expected:raise ValueError('Checkpoint changed bound engine identity after restore')
  return result

@contextmanager
def atomic_runner_outputs(runner,save_module,root,*,canonicalize=lambda x:x):
 """Serial research runner boundary, including original gzip/quarter exports.

 Original exporters write a private staging tree; only completed files are
 atomically published. DONE/manifest remains the caller's completeness gate.
 This serial context temporarily wraps the module's save function. Do not use
 it concurrently with other runners sharing that module.
 """
 root=Path(root)
 old_class=runner.__class__;old_save=save_module.save
 output_class=type('AtomicOutputs_'+old_class.__name__,(_AtomicRunnerExports,old_class),{'_research_trading_class':old_class})
 try:
  prepare_targets(dict(prefix_full=root/'prefix-full-source/pair',prefix_physical=root/'prefix-physical-source/pair',checkpoint=root/'checkpoint.pkl',final=root/'pair',failure=root/'failure/ERROR.json'),directory_keys={'prefix_full','prefix_physical','final'})
  runner.__class__=output_class
  save_module.save=lambda path,value:write_json(path,canonicalize(value))
  yield runner
 except BaseException as error:
  try:write_json(root/'failure/ERROR.json',dict(action='research runner/preflight/export',error_type=type(error).__name__,reason=str(error)))
  except BaseException as report_error:error.add_note('Failure report could not be saved at '+str(root/'failure/ERROR.json')+': '+str(report_error))
  raise
 finally:
  runner.__class__=old_class;save_module.save=old_save
