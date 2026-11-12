"""Run the unchanged retained-case recorder on final source; no production reads."""
import subprocess

from common import BASE, digest, docker_base, image_record, load_source, write_json

source = load_source()
assert not (BASE / "retained-history-feature.json").exists()
log = BASE / "retained-history-probe-original.log"
assert not log.exists()
script = BASE / "retained-history-probe.py"
image = image_record()
command = docker_base(source, readonly=True) + [image["Id"], "python", "/evidence/retained-history-probe.py"]
with log.open("xb") as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
write_json(BASE / "retained-history-probe-invocation.json", dict(candidate=source["candidate"], tree=source["tree"],
    command=command, image=image["Id"], script_sha256=digest(script), exit_code=result.returncode,
    scope="Final-source native retained-fixture replay; not a new production observation."))
assert result.returncode == 0
print("Recorded final-source retained cases.")

