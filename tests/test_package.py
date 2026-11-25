from pathlib import Path
import tempfile
import unittest
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from tools.verify_package import ASSETS, MANIFEST, SETTINGS_UI, verify_package


class PackageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.package = Path(directory.name) / "tankmate-signal.wotmod"

    def write_package(self, compression=ZIP_STORED, missing=None):
        with ZipFile(self.package, "w", compression=compression, compresslevel=0) as archive:
            archive.writestr(MANIFEST, "<root><id>local.friendpresence.probe</id>"
                             "<name>Tankmate Signal</name><version>1.2.3</version></root>")
            for name, signature in ASSETS.items():
                if name != missing:
                    content = (Path(__file__).resolve().parents[1] / "probe" / "tankmate-settings.swf").read_bytes() if name == SETTINGS_UI else signature
                    archive.writestr(name, content)

    def test_accepts_expected_stored_package(self):
        self.write_package()
        self.assertEqual(verify_package(self.package), "1.2.3")

    def test_rejects_compression_even_when_deflate_level_is_zero(self):
        self.write_package(compression=ZIP_DEFLATED)
        with self.assertRaisesRegex(ValueError, "stored ZIP entry"):
            verify_package(self.package)

    def test_rejects_missing_assets(self):
        self.write_package(missing=next(iter(ASSETS)))
        with self.assertRaisesRegex(ValueError, "Archive entries"):
            verify_package(self.package)

    def test_rejects_inconsistent_local_compression_header(self):
        self.write_package()
        with self.package.open("r+b") as stream:
            stream.seek(8)
            stream.write(b"\x08\x00")
        with self.assertRaisesRegex(ValueError, "stored ZIP entry"):
            verify_package(self.package)
