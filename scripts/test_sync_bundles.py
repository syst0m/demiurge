#!/usr/bin/env python3
"""
test_sync_bundles.py - functional and non-functional tests for scripts/sync_bundles.py.

Every test builds a throwaway library and project under a temp dir, so no real harness
directory and no real skill library is read or written.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sync_bundles.py"
BUNDLES = Path(__file__).resolve().parent.parent / "bundles"
if not BUNDLES.is_dir():
    for _c in [Path(__file__).resolve().parent.parent.parent / "agent-skills" / "bundles", Path.home() / "Documents" / "code" / "agent-skills" / "bundles"]:
        if _c.is_dir():
            BUNDLES = _c
            break


def run(args, **kw):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, **kw)

def make_library(root: Path, names) -> Path:
    lib = root / "lib"
    for name in names:
        d = lib / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n\n# {name}\n",
                                    encoding="utf-8")
    return lib


def make_bundles(root: Path, specs: dict) -> Path:
    """Write a temporary bundles/ tree and return it. The script reads BUNDLES_DIR at import."""
    bdir = root / "bundles"
    for name, skills in specs.items():
        d = bdir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "bundle.json").write_text(
            json.dumps({"name": name, "description": f"{name} bundle", "skills": skills}),
            encoding="utf-8")
    return bdir


class BundleHarness(unittest.TestCase):
    """Runs the script with a patched BUNDLES_DIR pointing at a temp tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bundles-test-"))
        self.library = make_library(self.tmp, ["alpha", "beta", "gamma", "delta"])
        self.bundles = make_bundles(self.tmp, {"b-one": ["alpha", "beta"],
                                              "b-broken": ["gamma", "absent-skill"]})
        self.project = self.tmp / "proj"
        self.project.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sync(self, *args):
        # Point LOCALAPPDATA at the temp tree so the Hermes user-scope target stays fake.
        env = dict(os.environ)
        env["LOCALAPPDATA"] = str(self.tmp)
        return run(["--bundles-dir", str(self.bundles), "--library", str(self.library),
                    "--project", str(self.project), *args], env=env)

    @property
    def hermes_home(self) -> Path:
        return self.tmp / "hermes"

    def add_gated_bundle(self):
        make_bundles(self.tmp, {"b-gated": ["alpha"]})
        (self.bundles / "b-gated" / "bundle.json").write_text(
            json.dumps({"name": "b-gated", "description": "gated", "skills": ["alpha"],
                        "hooks": True}), encoding="utf-8")


class TestManifests(unittest.TestCase):
    def test_repo_bundles_parse_and_are_unique(self):
        seen = {}
        for entry in sorted(BUNDLES.iterdir()):
            manifest = entry / "bundle.json"
            self.assertTrue(manifest.is_file(), f"{entry.name} has no bundle.json")
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], entry.name)
            self.assertTrue(data["skills"], f"{entry.name} lists no skills")
            self.assertTrue(data["description"])
            seen[data["name"]] = data
        self.assertGreaterEqual(len(seen), 5)

    def test_repo_bundle_skills_are_unique_within_a_bundle(self):
        for entry in sorted(BUNDLES.iterdir()):
            skills = json.loads((entry / "bundle.json").read_text(encoding="utf-8"))["skills"]
            self.assertEqual(len(skills), len(set(skills)), f"{entry.name} repeats a skill")


class TestFunctional(BundleHarness):
    def test_apply_then_check_is_clean(self):
        first = self.sync("--bundle", "b-one", "--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 0)

    def test_check_writes_nothing(self):
        before = sorted(p.relative_to(self.project).as_posix()
                        for p in self.project.rglob("*"))
        self.sync("--bundle", "b-one", "--check")
        after = sorted(p.relative_to(self.project).as_posix()
                       for p in self.project.rglob("*"))
        self.assertEqual(before, after)

    def test_apply_creates_every_harness_target(self):
        self.sync("--bundle", "b-one", "--apply")
        # Antigravity: a workspace plugin directory holding skill links.
        ag = self.project / ".agents" / "plugins" / "b-one"
        self.assertTrue((ag / "skills" / "alpha").is_symlink())
        self.assertTrue((ag / "plugin.json").is_file())
        # Claude Code: project skills, one link each. No bundle directory.
        self.assertTrue((self.project / ".claude" / "skills" / "alpha").is_symlink())
        self.assertFalse((self.project / ".claude" / "plugins" / "b-one").exists())
        # Hermes: the user plugin dir, because the gateway never loads ./.hermes/plugins.
        hz = self.hermes_home / "plugins" / "b-one"
        self.assertTrue((hz / "skills" / "alpha").is_symlink())
        self.assertTrue((hz / "plugin.yaml").is_file())
        self.assertFalse((self.project / ".hermes").exists())

    def test_apply_is_idempotent(self):
        self.sync("--bundle", "b-one", "--apply")
        second = self.sync("--bundle", "b-one", "--apply")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 0)

    def test_missing_link_is_reported_then_healed(self):
        self.sync("--bundle", "b-one", "--apply")
        (self.project / ".agents" / "plugins" / "b-one" / "skills" / "alpha").unlink()
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 1)
        self.assertEqual(self.sync("--bundle", "b-one", "--apply").returncode, 0)
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 0)

    def test_stale_copy_resyncs(self):
        self.sync("--bundle", "b-one", "--apply")
        dst = self.hermes_home / "plugins" / "b-one" / "skills" / "alpha"
        dst.unlink()
        dst.mkdir()
        (dst / "SKILL.md").write_text("stale\n", encoding="utf-8")
        self.assertEqual(self.sync("--bundle", "b-one", "--apply").returncode, 0)
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 0)

    def test_unknown_bundle_exits_2(self):
        self.assertEqual(self.sync("--bundle", "nope", "--check").returncode, 2)

    def test_unknown_harness_exits_2(self):
        self.assertEqual(self.sync("--harness", "nope", "--check").returncode, 2)

    def test_missing_skill_in_library_is_refused(self):
        out = self.sync("--bundle", "b-broken", "--apply")
        self.assertEqual(out.returncode, 1)
        self.assertIn("absent-skill", out.stdout)
        self.assertIn("not in any library", out.stdout)


    def test_gate_wiring_only_for_hook_bundles(self):
        self.sync("--bundle", "b-one", "--apply")
        self.assertFalse((self.project / ".agents" / "plugins" / "b-one" / "hooks.json").exists())
        self.assertFalse((self.hermes_home / "plugins" / "b-one" / "__init__.py").exists())

    def test_hook_bundle_registers_every_harness(self):
        self.add_gated_bundle()
        out = self.sync("--bundle", "b-gated", "--apply")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue((self.project / ".agents" / "plugins" / "b-gated" / "hooks.json").is_file())
        hooks = json.loads((self.project / ".agents" / "plugins" / "b-gated"
                            / "hooks.json").read_text(encoding="utf-8"))
        # Named hook group -> events -> flat handler list (agy plugin validate accepts this).
        self.assertIn("Stop", hooks["testing-matrix"])
        self.assertEqual(hooks["testing-matrix"]["Stop"][0]["type"], "command")
        self.assertIn("--hook-format antigravity",
                      hooks["testing-matrix"]["Stop"][0]["command"])
        hz = self.hermes_home / "plugins" / "b-gated"
        self.assertTrue((hz / "__init__.py").is_file())
        self.assertIn("pre_llm_call", (hz / "plugin.yaml").read_text(encoding="utf-8"))
        settings = json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Stop", settings["hooks"])
        self.assertEqual(self.sync("--bundle", "b-gated", "--check").returncode, 0)

    def test_hermes_plugin_is_enabled_in_config(self):
        self.add_gated_bundle()
        cfg = self.hermes_home / "config.yaml"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text("plugins:\n  enabled:\n    - already-there\n  disabled: []\n", encoding="utf-8")
        out = self.sync("--bundle", "b-gated", "--apply")
        self.assertEqual(out.returncode, 0, out.stderr)
        text = cfg.read_text(encoding="utf-8")
        self.assertIn("already-there", text)
        self.assertIn("b-gated", text)
        self.assertEqual(self.sync("--bundle", "b-gated", "--check").returncode, 0)

    def test_hermes_init_check_accepts_kwargs(self):
        """The pre_llm_call callback must accept **kwargs or Hermes rejects the hook registration."""
        self.add_gated_bundle()
        self.sync("--bundle", "b-gated", "--apply")
        init = self.hermes_home / "plugins" / "b-gated" / "__init__.py"
        self.assertTrue(init.is_file())
        text = init.read_text(encoding="utf-8").replace("\r\n", "\n")
        # event/payload are optional because Hermes passes hook data as kwargs
        self.assertIn("def _check(event=None, payload=None, **kwargs)", text)
        self.assertNotIn("def _check(event, payload):", text)

    def test_claude_settings_are_merged_not_replaced(self):
        self.add_gated_bundle()
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps({"theme": "dark", "hooks": {"Stop": [
            {"hooks": [{"type": "command", "command": "echo keep"}]}]}}), encoding="utf-8")
        self.sync("--bundle", "b-gated", "--apply")
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["theme"], "dark")
        commands = [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]]
        self.assertIn("echo keep", commands)
        self.assertTrue(any("testing_matrix_gate" in c for c in commands))


class TestClaudePlugins(BundleHarness):
    PLUGIN = "ponytail@ponytail"

    def setUp(self):
        super().setUp()
        make_bundles(self.tmp, {"b-plug": ["alpha"]})
        (self.bundles / "b-plug" / "bundle.json").write_text(
            json.dumps({"name": "b-plug", "description": "plug", "skills": ["alpha"],
                        "claude_plugins": [self.PLUGIN]}), encoding="utf-8")
        self.local = self.project / ".claude" / "settings.local.json"

    def test_apply_enables_plugin_in_local_settings(self):
        out = self.sync("--bundle", "b-plug", "--harness", "claude-code", "--apply")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("claude-code plugin ponytail@ponytail enabled", out.stdout)
        data = json.loads(self.local.read_text(encoding="utf-8"))
        self.assertIs(data["enabledPlugins"][self.PLUGIN], True)
        self.assertFalse((self.project / ".claude" / "settings.json").exists())

    def test_check_reports_drift_then_clean_after_apply(self):
        out = self.sync("--bundle", "b-plug", "--harness", "claude-code", "--check")
        self.assertEqual(out.returncode, 1)
        self.assertIn("DRIFT    claude-code plugin ponytail@ponytail not enabled", out.stdout)
        self.assertFalse(self.local.exists())
        self.sync("--bundle", "b-plug", "--harness", "claude-code", "--apply")
        self.assertEqual(
            self.sync("--bundle", "b-plug", "--harness", "claude-code", "--check").returncode, 0)

    def test_existing_keys_survive_merge(self):
        self.local.parent.mkdir(parents=True, exist_ok=True)
        self.local.write_text(json.dumps({
            "permissions": {"allow": ["Bash(ls)"]},
            "enabledPlugins": {"other@other": False}}), encoding="utf-8")
        out = self.sync("--bundle", "b-plug", "--harness", "claude-code", "--apply")
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(self.local.read_text(encoding="utf-8"))
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIs(data["enabledPlugins"]["other@other"], False)
        self.assertIs(data["enabledPlugins"][self.PLUGIN], True)

    def test_invalid_json_is_refused_and_untouched(self):
        self.local.parent.mkdir(parents=True, exist_ok=True)
        self.local.write_text("{not json", encoding="utf-8")
        out = self.sync("--bundle", "b-plug", "--harness", "claude-code", "--apply")
        self.assertEqual(out.returncode, 1)
        self.assertIn("REFUSE", out.stdout)
        self.assertEqual(self.local.read_text(encoding="utf-8"), "{not json")


class TestNonFunctional(BundleHarness):
    def test_real_file_is_never_clobbered(self):
        self.sync("--bundle", "b-one", "--apply")
        victim = self.project / ".claude" / "skills" / "alpha"
        victim.unlink()
        victim.write_text("user's own file\n", encoding="utf-8")
        out = self.sync("--bundle", "b-one", "--apply")
        self.assertEqual(out.returncode, 1)
        self.assertIn("REFUSE", out.stdout)
        self.assertEqual(victim.read_text(encoding="utf-8"), "user's own file\n")

    def test_dirty_project_still_syncs(self):
        """The guard is per-path, not project-wide: a repo with uncommitted work can still
        install a bundle, because the materializer only adds paths it owns."""
        subprocess.run(["git", "init", "-q", "."], cwd=self.project, check=True)
        (self.project / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
        out = self.sync("--bundle", "b-one", "--apply")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(self.sync("--bundle", "b-one", "--check").returncode, 0)

    def test_library_is_never_written_to(self):
        """The regression: the old sync-skills.sh wrote into another repo's working tree."""
        before = sorted(p.relative_to(self.library).as_posix()
                        for p in self.library.rglob("*"))
        self.sync("--bundle", "b-one", "--apply")
        after = sorted(p.relative_to(self.library).as_posix()
                       for p in self.library.rglob("*"))
        self.assertEqual(before, after)

    def test_no_copy_of_skill_bodies_into_the_project(self):
        """Links, not copies: the project must not grow a second copy of a skill."""
        self.sync("--bundle", "b-one", "--apply")
        link = self.project / ".agents" / "plugins" / "b-one" / "skills" / "alpha"
        self.assertTrue(link.is_symlink())
        self.assertNotEqual(link.resolve(), link)


if __name__ == "__main__":
    unittest.main(verbosity=2)
