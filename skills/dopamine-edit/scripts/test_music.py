#!/usr/bin/env python3
"""Run the focused music regressions from the shared offline suite."""
import unittest
from test_pipeline import PipelineTests

if __name__ == '__main__':
    names = [name for name in unittest.defaultTestLoader.getTestCaseNames(PipelineTests)
             if 'music' in name]
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PipelineTests(name) for name in names))
    raise SystemExit(0 if result.wasSuccessful() else 1)
