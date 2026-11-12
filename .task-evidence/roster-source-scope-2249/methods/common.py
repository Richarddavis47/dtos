"""Small source-bound controller for existing native resource controls."""
import hashlib,json,os,subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parent
SOURCE_CHECKOUT=Path('/workspace/dtos-sleeper-relevance-2249')
IMAGE='dtos-canonical314:2245'
IMAGE_ID='sha256:f70a0c6402700dfb954c99d8163d4164926f74435c34d2e7e462407151663ae6'
os.environ.pop('DOCKER_CONTEXT',None)
os.environ['DOCKER_HOST']='unix:///var/run/docker.sock'
def load_source(): return json.loads((BASE/'source.json').read_text())
def write_json(path,row): path.write_text(json.dumps(row,indent=2)+'\n')
def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def command(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def assert_checkout(source, checkout=SOURCE_CHECKOUT):
    assert command("git", "rev-parse", "HEAD", cwd=checkout) == source["candidate"]
    assert command("git", "rev-parse", "HEAD^{tree}", cwd=checkout) == source["tree"]
    assert not command("git", "status", "--porcelain", cwd=checkout), "Source checkout must be clean"


def image_record():
    record = json.loads(command("docker", "image", "inspect", IMAGE))[0]
    assert record["Id"] == IMAGE_ID, "Existing pinned validation runtime changed"
    return record


def git_common_dir(checkout):
    value = Path(command("git", "rev-parse", "--git-common-dir", cwd=checkout))
    return (checkout / value).resolve() if not value.is_absolute() else value.resolve()


def docker_base(source, readonly=True):
    assert_checkout(source)
    image_record()
    common = git_common_dir(SOURCE_CHECKOUT)
    return [
        "docker", "run", "--rm", "--init", "--user", "1000:1000",
        "--memory=2g", "--memory-swap=2g", "--cpus=2", "--network=none",
        "--env", "HOME=/tmp", "--env", "NODE_OPTIONS=--max-old-space-size=256",
        "--env", "DTOS_EXPECTED_HEAD=" + source["candidate"],
        "--env", "DTOS_EXPECTED_TREE=" + source["tree"],
        "--env", "GIT_CONFIG_COUNT=1", "--env", "GIT_CONFIG_KEY_0=safe.directory",
        "--env", "GIT_CONFIG_VALUE_0=/app",
        "--volume", str(SOURCE_CHECKOUT) + ":/app" + (":ro" if readonly else ""),
        "--volume", str(common) + ":" + str(common) + ":ro",
        "--volume", str(BASE) + ":/evidence", "--workdir", "/app",
    ]

