"""Run unchanged Windows worker controls inside a measured 2 GiB Job object."""

import json
import sys
import unittest
from src.platform.windows_job_memory import create_validation_job


def main():
    handle, measured = create_validation_job(2 * 1024**3)
    assert handle
    print("ENFORCED_WINDOWS_JOB " + json.dumps(measured), flush=True)
    unittest.main(module=None, argv=[sys.argv[0], *sys.argv[1:]])


if __name__ == "__main__":
    main()
