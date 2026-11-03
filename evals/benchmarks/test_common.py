#!/usr/bin/env python3
"""Tests for the pricing and cost helpers shared by the benchmark runners."""

import unittest

from common import compute_cost, cost_change_percent, format_percent


class CommonTests(unittest.TestCase):
    def test_unpriced_model_raises(self):
        with self.assertRaises(ValueError):
            compute_cost("claude-opus-5-5", 1000, 100)

    def test_known_model_cost(self):
        # 1M uncached input at $3 plus 1M output at $15.
        self.assertEqual(compute_cost("claude-3-5-sonnet-20241022", 1_000_000, 1_000_000), 18.0)

    def test_arm_with_no_resolved_task_has_no_cost_change(self):
        self.assertIsNone(cost_change_percent(0.5, 2, 0.0, 0))
        self.assertIsNone(cost_change_percent(0.0, 0, 0.5, 2))
        self.assertEqual(format_percent(None), "n/a")

    def test_cost_change(self):
        self.assertEqual(cost_change_percent(2.0, 1, 1.0, 1), -50.0)
        self.assertEqual(format_percent(-50.0), "-50.00%")


if __name__ == "__main__":
    unittest.main()
