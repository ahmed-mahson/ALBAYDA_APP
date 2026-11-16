"""Serialized, optimistic Git-backed account store. Never falls back to empty data."""
import copy, json, os, subprocess, sys, threading, time
from pathlib import Path
LOCK=threading.RLock()
CACHE=None
CACHE_AT=0
ROOT=Path(os.getenv('COURT_STORE_DIR','/tmp/court-accounts'))
def git(*args):
    env=os.environ.copy()
    key=Path('/tmp/court-github-key')
    if os.getenv('COURT_GIT_PRIVATE_KEY'):
        key.write_text(os.environ['COURT_GIT_PRIVATE_KEY']);key.chmod(0o600)
        env['COURT_GIT_KEY_FILE']=str(key)
    env['GIT_SSH_COMMAND']=sys.executable+' '+str(Path(__file__).with_name('github_ssh.py'))
    env['GIT_SSH_VARIANT']='ssh'
    result=subprocess.run(['git',*args],cwd=ROOT if ROOT.exists() else None,env=env,capture_output=True,timeout=70)
    if result.returncode:raise RuntimeError('تعذر الاتصال بمخزن الحسابات. أعد المحاولة لاحقًا.')
    return result.stdout

def refresh():
    if not (ROOT/'.git').exists():
        git('clone','--depth','1','--single-branch','--branch','court-data','git@github.com:ahmed-mahson/ALBAYDA_APP.git',str(ROOT))
    else:
        git('fetch','--depth','1','origin','court-data')
        git('reset','--hard','FETCH_HEAD')
    return json.loads((ROOT/'accounts.json').read_text())
def read():
    global CACHE,CACHE_AT
    with LOCK:
        if CACHE is None or time.monotonic()-CACHE_AT>10:
            CACHE=refresh();CACHE_AT=time.monotonic()
        return copy.deepcopy(CACHE)
def change(operation):
    global CACHE,CACHE_AT
    with LOCK:
        for attempt in range(3):
            data=refresh()
            result=operation(data)
            (ROOT/'accounts.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
            git('add','accounts.json')
            git('-c','user.name=ALBAYDA Service','-c','user.email=service@albayda.invalid','commit','-m','Record account activity')
            try:git('push','origin','HEAD:court-data')
            except RuntimeError:
                if attempt==2:raise
                continue
            CACHE=data;CACHE_AT=time.monotonic()
            return result
