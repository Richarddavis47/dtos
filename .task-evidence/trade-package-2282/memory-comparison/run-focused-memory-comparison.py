"""Run matched tests serially in ordinary isolated 2 GiB admission."""
from pathlib import Path
import subprocess,sys
from common import BASE,docker_base,image_record,load_source,write_json
s=load_source()
reverse=sys.argv[1:]==['--reverse']
assert reverse or not sys.argv[1:]
root=BASE/('focused-memory-attribution-reverse' if reverse else 'focused-memory-attribution')
root.mkdir(exist_ok=False)
cases=[
    ('baseline', '/workspace/dtos-2282-memory-baseline',s['baseline'],s['baseline_tree']),
    ('candidate','/workspace/dtos-trade-package-2282',s['candidate'],s['tree']),
]
for label, checkout, head, tree in (reversed(cases) if reverse else cases):
    out=root/label
    out.mkdir()
    args=docker_base(s)
    args=[v.replace('/workspace/dtos-trade-package-2282:/app',checkout+':/app')
           .replace('DTOS_EXPECTED_HEAD='+s['candidate'],'DTOS_EXPECTED_HEAD='+head)
           .replace('DTOS_EXPECTED_TREE='+s['tree'],'DTOS_EXPECTED_TREE='+tree) for v in args]
    args+=['--name','dtos-2282-attribution-'+label,'-v',str(out)+':/output',
           '-e','PYTHONPATH=/app','-e','DTOS_REBUILD_SPACE_EVIDENCE=/output/space',
           image_record()['Id'],'python','/evidence/compare-focused-memory.py']
    write_json(out/'invocation.json',dict(command=args,head=head,tree=tree))
    with (out/'original-console.log').open('wb') as stream:
        proc=subprocess.run(args,stdout=stream,stderr=subprocess.STDOUT)
    (out/'original-exit.txt').write_text(str(proc.returncode)+'\n')
    print(label,proc.returncode,flush=True)
