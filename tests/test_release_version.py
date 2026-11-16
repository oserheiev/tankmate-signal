import unittest

from tools.release_version import next_version


class ReleaseVersionTests(unittest.TestCase):
    def test_bump_types(self):
        for bump, version in (
            ("none", "1.2.3"),
            ("patch", "1.2.4"),
            ("minor", "1.3.0"),
            ("major", "2.0.0"),
        ):
            with self.subTest(bump=bump):
                self.assertEqual(next_version("1.2.3", bump), version)

    def test_invalid_version(self):
        for version in ("1.2", "1.2.3-rc1", "01.2.3"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                next_version(version, "patch")
