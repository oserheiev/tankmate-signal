"""Build the dedicated welcome dialog from the installed client's native movie."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path, required=True)
    parser.add_argument('--ffdec', type=Path, required=True)
    parser.add_argument('--java', default='java')
    args = parser.parse_args()
    ffdec = args.ffdec.resolve()
    extension = ROOT / 'ui' / 'TankmateWelcomeUI.as'
    target = ROOT / 'probe' / 'tankmate-welcome.swf'
    with tempfile.TemporaryDirectory(prefix='tankmate-welcome-') as directory:
        work = Path(directory)
        remaining = {'simpleDialog.swf', 'lobby.swf'}
        for package in sorted((args.game_root / 'res' / 'packages').glob('gui*.pkg')):
            with ZipFile(package) as archive:
                for name in tuple(remaining):
                    path = 'gui/flash/' + name
                    if path in archive.namelist():
                        (work / name).write_bytes(archive.read(path))
                        remaining.remove(name)
        if remaining:
            raise RuntimeError('Native movies not found: ' + ', '.join(sorted(remaining)))
        subprocess.run([args.java, '-jar', str(ffdec / 'ffdec-cli.jar'), '-selectclass', 'SimpleDialogUI',
                        '-export', 'script', str(work / 'source'), str(work / 'simpleDialog.swf')], check=True)
        source = work / 'source' / 'scripts' / 'SimpleDialogUI.as'
        text = source.read_text(encoding='utf-8')
        imports = '\n'.join('   import ' + name + ';' for name in (
            'flash.display.Sprite', 'flash.events.Event', 'flash.text.TextField', 'flash.text.TextFormat',
            'flash.geom.ColorTransform',
            'net.wg.gui.components.controls.Image'))
        text = text.replace('   import net.wg.gui.dialogs.SimpleDialog;',
                            '   import net.wg.gui.dialogs.SimpleDialog;\n' + imports)
        end = text.rfind('   }')
        if end < 0 or 'public dynamic class SimpleDialogUI' not in text:
            raise RuntimeError('Native dialog structure changed; inspect before rebuilding')
        source.write_text(text[:end] + extension.read_text(encoding='utf-8') + '\n' + text[end:], encoding='utf-8')
        subprocess.run([args.java, '-cp', str(ffdec / 'ffdec.jar') + ';' + str(ffdec / 'lib' / '*'),
                        str(ROOT / 'tools' / 'CompileSettingsUi.java'), str(work / 'simpleDialog.swf'),
                        str(work / 'lobby.swf'), str(source), str(ffdec / 'flashlib' / 'playerglobal32_0.swc'),
                        str(target), 'SimpleDialogUI', 'TankmateWelcomeUI'], check=True)
        metadata = {'base_swf_sha256': hashlib.sha256((work / 'simpleDialog.swf').read_bytes()).hexdigest(),
                    # Normalize checkout line endings, as the compiler input does.
                    'extension_sha256': hashlib.sha256(extension.read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
                    'asset_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'compiler': 'FFDec 26.5.0'}
        target.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print('Built ' + str(target))


if __name__ == '__main__':
    main()
