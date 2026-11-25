"""Check a built Tankmate Signal archive before installing or distributing it."""

import argparse
import json
from pathlib import Path
import re
import struct
from xml.etree import ElementTree
from zipfile import BadZipFile, ZIP_STORED, ZipFile
import zlib


MODULE = "res/scripts/client/gui/mods/mod_tankmate_signal.pyc"
SETTINGS_UI = "res/gui/flash/tankmateSettings.swf"
WELCOME_UI = "res/gui/flash/tankmateWelcome.swf"
TEXTURES = "res/gui/maps/icons/tankmate_signal/"
ASSETS = {
    MODULE: b"\x03\xf3\r\n",  # Python 2.7 bytecode magic
    SETTINGS_UI: b"CWS",
    WELCOME_UI: b"CWS",
    TEXTURES + "welcome-labels.json": b"{",
    TEXTURES + "plate.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "profile-online.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "profile-offline.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "shortcut-keycap.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "status-rule.png": b"\x89PNG\r\n\x1a\n",
    TEXTURES + "whisper-labels.json": b"{",
}
LABELS = Path(__file__).resolve().parents[1] / "probe" / "status-labels.json"
for _locale in json.loads(LABELS.read_text(encoding="utf-8")):
    for _state in ("online", "offline"):
        ASSETS[f"{TEXTURES}status-{_locale}-{_state}.png"] = b"\x89PNG\r\n\x1a\n"
    for _state in ("ready", "ready-hover", "sent", "retry", "retry-hover", "pending", "unavailable"):
        ASSETS[f"{TEXTURES}whisper-{_locale}-{_state}.png"] = b"\x89PNG\r\n\x1a\n"
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
        settings_ui = archive.read(SETTINGS_UI)
        try:
            body = zlib.decompress(settings_ui[8:])
            size = struct.unpack("<I", settings_ui[4:8])[0]
        except (zlib.error, struct.error):
            raise ValueError("Invalid Settings UI SWF")
        if len(body) + 8 != size or not all(name in body for name in (
                b"as_setTankmateSettings", b"tankmate.signal", b"tankmateMods")):
            raise ValueError("Settings UI does not provide the mod settings bridge")
        welcome = archive.read(WELCOME_UI)
        try:
            body = zlib.decompress(welcome[8:])
            size = struct.unpack("<I", welcome[4:8])[0]
        except (zlib.error, struct.error):
            raise ValueError("Invalid welcome UI SWF")
        if len(body) + 8 != size or not all(name in body for name in (
                b"TankmateWelcomeUI", b"as_setTankmateWelcome", b"plate.png", b"shortcut-keycap.png")):
            raise ValueError("Welcome UI does not provide the native welcome bridge")

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
