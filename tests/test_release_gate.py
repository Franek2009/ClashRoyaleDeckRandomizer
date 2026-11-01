"""Exercise the release SHA gate with fake gh responses; never publish anything."""
import os
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify_release.sh"
SHA = "1" * 40


def run_gate(tmp_path, **overrides):
    fake = tmp_path / "gh"
    fake.write_text("""#!/usr/bin/python3
import os,sys
if sys.argv[1] != 'api':
    raise SystemExit('Only read-only api calls are allowed')
if os.environ.get('FAKE_HTTP_ERROR'):
    raise SystemExit('Mock HTTP failure')
endpoint=sys.argv[2]
if endpoint.endswith('/commits/main'):
    print(os.environ['FAKE_MAIN'])
elif '/deployments?' in endpoint:
    print(os.environ['FAKE_DEPLOYMENT'])
elif '/statuses?' in endpoint:
    print(os.environ['FAKE_STATUS'])
else:
    raise SystemExit('Unexpected API endpoint')
""")
    fake.chmod(0o700)
    env = {"PATH":str(tmp_path) + os.pathsep + os.defpath,
           "GITHUB_REPOSITORY":"example/crdr", "RELEASE_SHA":SHA,
           "FAKE_MAIN":SHA, "FAKE_DEPLOYMENT":"7\t" + SHA, "FAKE_STATUS":"success",
           **overrides}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=5)


def test_release_requires_matching_successful_live_deployment(tmp_path):
    result = run_gate(tmp_path)
    assert result.returncode == 0
    assert SHA in result.stdout


@pytest.mark.parametrize("overrides,message", [
    ({"FAKE_MAIN":"2" * 40}, "main"),
    ({"FAKE_DEPLOYMENT":"7\t" + "2" * 40}, "Pages deployment"),
    ({"FAKE_DEPLOYMENT":""}, "Pages deployment"),
    ({"FAKE_STATUS":"pending"}, "not successful"),
    ({"FAKE_STATUS":"failure"}, "not successful"),
    ({"FAKE_STATUS":"inactive"}, "not successful"),
    ({"FAKE_HTTP_ERROR":"1"}, "Mock HTTP failure"),
    ({"RELEASE_SHA":"v1.1.0"}, "Invalid release commit SHA"),
])
def test_mismatched_or_unverified_release_is_blocked(tmp_path, overrides, message):
    result = run_gate(tmp_path, **overrides)
    assert result.returncode != 0
    assert message in result.stderr
