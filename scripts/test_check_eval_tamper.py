import unittest

from check_eval_tamper import check

EV = "skills/demo/evals/evals.json"


class TestEvalTamper(unittest.TestCase):
    def test_skill_and_its_evals_together_fail(self) -> None:
        errors, note = check([("M", EV), ("M", "skills/demo/SKILL.md")], "")
        self.assertEqual(len(errors), 1)
        self.assertIn("demo", errors[0])
        self.assertIsNone(note)

    def test_evals_only_passes(self) -> None:
        self.assertEqual(check([("M", EV)], "")[0], [])

    def test_skill_only_passes(self) -> None:
        self.assertEqual(check([("M", "skills/demo/SKILL.md")], "")[0], [])

    def test_new_skill_with_new_evals_passes(self) -> None:
        self.assertEqual(check([("A", EV), ("A", "skills/demo/SKILL.md")], "")[0], [])

    def test_other_skills_files_do_not_count(self) -> None:
        self.assertEqual(check([("M", EV), ("M", "skills/other/SKILL.md")], "")[0], [])

    def test_reviewed_line_skips_with_note(self) -> None:
        errors, note = check([("M", EV), ("M", "skills/demo/SKILL.md")],
                             "Tune demo\n\nEvals: reviewed\n")
        self.assertEqual(errors, [])
        self.assertIn("reviewed", note)


if __name__ == "__main__":
    unittest.main()
