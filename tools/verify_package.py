"""Check a built Tankmate Signal archive before installing or distributing it."""

import argparse
from pathlib import Path
import re
import struct
from xml.etree import ElementTree
from zipfile import BadZipFile, ZIP_STORED, ZipFile


MODULE = "res/scripts/client/gui/mods/mod_tankmate_signal.pyc"
TEXTURES = "res/gui/maps/icons/tankmate_signal/"
ASSETS = {
    MODULE: b"\x03\xf3\r\n",  # Python 2.7 bytecode magic
    TEXTURES + "tankmate-plate.dds": b"DDS ",
    TEXTURES + "tankmate-plate-offline.dds": b"DDS ",
    TEXTURES + "status-online.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "status-offline.png": b"\x89PNG\r\n\x1a\n",
}
MANIFEST = "meta.xml"


def verify_package(path):
    with Path(path).open("rb") as stream, ZipFile(stream) as archive:
        entries = archive.infolist()
        expected = {MANIFEST, *ASSETS}
        if len(entries) != len(expected) or set(archive.namelist()) != expected:
            raise ValueError("Archive entries differ from the expected package contents")

        for entry in entries:
            stream.seek(entry.header_offset)
            signature, _, flags, method = struct.unpack("<4sHHH", stream.read(10))
            if signature != b"PK\x03\x04" or flags or entry.flag_bits:
                raise ValueError("Unsupported ZIP header for " + entry.filename)
            if method != ZIP_STORED or entry.compress_type != ZIP_STORED:
                raise ValueError("WoT requires a stored ZIP entry for " + entry.filename)
            if not entry.file_size or entry.compress_size != entry.file_size:
                raise ValueError("Invalid stored ZIP size for " + entry.filename)

        invalid = archive.testzip()
        if invalid is not None:
            raise ValueError("CRC check failed for " + invalid)
        for name, magic in ASSETS.items():
            with archive.open(name) as asset:
                if asset.read(len(magic)) != magic:
                    raise ValueError("Unexpected file signature for " + name)

        manifest = ElementTree.fromstring(archive.read(MANIFEST))
        version = manifest.findtext("version", default="")
        if (manifest.tag != "root" or manifest.findtext("id") != "local.friendpresence.probe"
                or manifest.findtext("name") != "Tankmate Signal"
                or not re.fullmatch(r"\d+\.\d+\.\d+", version)):
            raise ValueError("Invalid Tankmate Signal manifest")
        return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    try:
        version = verify_package(args.package)
    except (OSError, ValueError, BadZipFile, ElementTree.ParseError, struct.error) as error:
        parser.exit(1, f"Package verification failed: {error}\n")
    print(f"Verified Tankmate Signal {version} ({args.package})")


if __name__ == "__main__":
    main()
