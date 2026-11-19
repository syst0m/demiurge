"""Tests for the fail-closed pattern load in scan_security_and_pii.py.

Each test copies the scanner into a temporary directory, so the real
gitignored scripts/local_pii_patterns.py is never read or changed.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCANNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_security_and_pii.py")


def run_scanner(work_dir, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, os.path.join(work_dir, "scan_security_and_pii.py"), *args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        env=env,
    )


class ScannerPatternSourceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        shutil.copy(SCANNER, self.dir)
        self.sample = os.path.join(self.dir, "sample.txt")
        with open(self.sample, "w", encoding="utf-8") as f:
            f.write("nothing personal here\n")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_local_patterns(self, body):
        with open(os.path.join(self.dir, "local_pii_patterns.py"), "w", encoding="utf-8") as f:
            f.write(body)

    def test_strict_with_missing_pattern_source_exits_2(self):
        result = run_scanner(self.dir, "--strict", self.sample)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("pattern", result.stderr.lower())

    def test_strict_with_broken_pattern_source_exits_2(self):
        self.write_local_patterns("this is not python(\n")
        result = run_scanner(self.dir, "--strict", self.sample)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_default_with_missing_pattern_source_warns_and_exits_0(self):
        result = run_scanner(self.dir, self.sample)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING", result.stderr)

    def test_canary_with_pattern_source_is_caught(self):
        self.write_local_patterns(
            "import re\nPATTERNS = [(re.compile(r'\\bZZCANARY\\b'), 'canary')]\n"
        )
        with open(self.sample, "w", encoding="utf-8") as f:
            f.write("a line with ZZCANARY in it\n")
        result = run_scanner(self.dir, "--strict", self.sample)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("PERSONAL-LOCAL", result.stdout)


if __name__ == "__main__":
    unittest.main()
