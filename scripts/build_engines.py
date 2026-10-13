"""Build the incorporated engines and desktop editors from this repository."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('--engine',choices=('layers','develop','all'),default='all')
    parser.add_argument('--toolchain',default='1.95.0')
    args=parser.parse_args()
    profile='debug' if args.debug else 'release'
    dest=ROOT/'native/bin';dest.mkdir(parents=True,exist_ok=True)
    receipts=[]
    for engine in ('layers','develop') if args.engine=='all' else (args.engine,):
        source=ROOT/'native'/engine
        name='daguerre-'+engine
        command=['cargo','+'+args.toolchain,'build','--locked','-p',name+'-cli','-p',name]
        if not args.debug:command.append('--release')
        subprocess.run(command,cwd=source,check=True)
        target=Path(os.environ.get('CARGO_TARGET_DIR',source/'target')).resolve()/profile
        for binary in (name+'-cli',name):
            filename=binary+('.exe' if os.name=='nt' else '')
            shutil.copy2(target/filename,dest/filename)
            receipts.append({'file':filename,'sha256':hashlib.sha256((dest/filename).read_bytes()).hexdigest()})
    (dest/('build-'+args.engine+'.json')).write_text(json.dumps({'profile':profile,'source':'native','binaries':receipts},indent=2),encoding='utf-8')
if __name__=='__main__':main()
