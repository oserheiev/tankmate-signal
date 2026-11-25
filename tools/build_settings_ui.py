"""Regenerate the bundled native Settings extension using the installed client.

Developer tool only: Java and FFDec are not needed to install or run the mod.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def extract_movies(game_root, output):
    remaining = {"settingsWindow.swf", "lobby.swf"}
    for package in sorted((game_root / "res" / "packages").glob("gui*.pkg")):
        with ZipFile(package) as archive:
            for name in tuple(remaining):
                asset = "gui/flash/" + name
                if asset in archive.namelist():
                    (output / name).write_bytes(archive.read(asset))
                    remaining.remove(name)
    if remaining:
        raise RuntimeError("Client UI assets not found: " + ", ".join(sorted(remaining)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--ffdec", type=Path, required=True, help="Directory containing ffdec-cli.jar")
    parser.add_argument("--java", default="java")
    args = parser.parse_args()
    ffdec = args.ffdec.resolve()
    extension = ROOT / "ui" / "SettingsWindowUI.mods.as"
    target = ROOT / "probe" / "tankmate-settings.swf"
    with tempfile.TemporaryDirectory(prefix="tankmate-ui-") as temporary:
        work = Path(temporary)
        extract_movies(args.game_root, work)
        subprocess.run([args.java, "-jar", str(ffdec / "ffdec-cli.jar"), "-selectclass", "SettingsWindowUI",
                        "-export", "script", str(work / "source"), str(work / "settingsWindow.swf")], check=True)
        source = work / "source" / "scripts" / "SettingsWindowUI.as"
        text = source.read_text(encoding="utf-8")
        imports = "\n".join("   import " + name + ";" for name in (
            "flash.display.Sprite", "flash.events.Event", "flash.text.TextField", "flash.text.TextFormat",
            "flash.utils.getDefinitionByName", "scaleform.clik.events.IndexEvent",
            "net.wg.gui.lobby.settings.vo.TabsDataVo", "net.wg.gui.components.advanced.ButtonBarEx",
            "net.wg.gui.lobby.settings.components.KeyInput", "net.wg.gui.components.controls.CheckBox",
            "net.wg.gui.components.advanced.FieldSet"))
        text = text.replace("   import net.wg.gui.lobby.settings.SettingsWindow;",
                            "   import net.wg.gui.lobby.settings.SettingsWindow;\n" + imports)
        end = text.rfind("   }")
        if end < 0 or "public dynamic class SettingsWindowUI" not in text:
            raise RuntimeError("The client's Settings root structure changed; inspect it before rebuilding")
        text = text[:end] + extension.read_text(encoding="utf-8") + "\n" + text[end:]
        source.write_text(text, encoding="utf-8")
        subprocess.run([args.java, "-cp", str(ffdec / "ffdec.jar") + ";" + str(ffdec / "lib" / "*"),
                        str(ROOT / "tools" / "CompileSettingsUi.java"), str(work / "settingsWindow.swf"),
                        str(work / "lobby.swf"), str(source), str(ffdec / "flashlib" / "playerglobal32_0.swc"),
                        str(target)], check=True)
        metadata = {
            "base_swf_sha256": hashlib.sha256((work / "settingsWindow.swf").read_bytes()).hexdigest(),
            "extension_sha256": hashlib.sha256(extension.read_bytes()).hexdigest(),
            "asset_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "compiler": "FFDec 26.5.0",
        }
        target.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print("Built " + str(target))


if __name__ == "__main__":
    main()
