# Tankmate Signal

A World of Tanks mod for friend presence alerts in the hangar and during battle.

Tankmate Signal shows a plate and plays a chime when a friend comes online or goes offline. Status labels follow the game language. Online is green and offline is red. The initial friends list loads silently. Up to three plates appear at once, with later changes waiting for a slot. Diagnostic messages appear in the game log under `[TankmateSignal]`.

While the game is minimized, alerts pause and every friend status change is queued. The queued alerts appear in order when you restore the game and the hangar or battle HUD is visible.

## Build and install

Close World of Tanks. Open 64-bit Windows PowerShell 5.1 or PowerShell 7 in the project folder and pass the folder containing the game's `win64` and `mods` directories.

```powershell
$gameRoot = 'C:\Games\World_of_Tanks_EU'
.\Build-AndInstall.ps1 -GameRoot $gameRoot
```

The script uses the installed client's Python runtime. It builds `probe/tankmate-signal.wotmod` and installs it into the highest-numbered folder under the game's `mods` directory. Rerun it after updating the client. The package includes its own translations from `probe/status-labels.json` and uses the current game language when available, with an English fallback.

To uninstall, close WoT and remove `tankmate-signal.wotmod` from the corresponding game version's `mods` directory.

## Test the notification

Set `_SHOW_TEST_NOTIFICATION = True` near the top of `probe/mod_tankmate_signal.py`, then rebuild, install, and launch the game. One sample alert appears when the hangar or battle HUD is visible. Set it back to `False` and rebuild to disable the sample.

If the sample is missing, search the game's `game.log` for `tankmate-signal.wotmod` to check whether WoT accepted the package, then for `[TankmateSignal]` to check mod initialization and alerts. A `compression not supported` error means the package should be rebuilt with this installer. WoT Safe Mode disables mods.

## Development checks

The regression tests use Python 3 and mock the WoT client API. GitHub Actions runs them on pushes and pull requests.

```powershell
python -B -m unittest discover -s tests -v
.\Build-AndInstall.ps1 -GameRoot $gameRoot -PackageOnly
python tools/verify_package.py probe/tankmate-signal.wotmod
```

`-PackageOnly` builds the archive without writing to the game's mods folder. The verifier checks the manifest, assets, ZIP headers, and checksums. Before distributing a build, try the sample alert in the hangar and in a battle replay, including the countdown, and check a real friend status change while minimized and after restoring the window. Rebuild with the sample flag disabled before sharing the package.

## Release from main

In GitHub, open **Actions → Release main → Run workflow** and select `main`. Choose `patch`, `minor`, or `major` to increase the version, or `none` to keep the version in `VERSION`. Leave **Publish a GitHub Release** unchecked to build a test artifact without changing `main`.

A publish run verifies the package, commits the new version to `main`, and tags the release commit. Each release includes the multilingual `.wotmod` and its SHA-256 checksum. Copy the mod into the active version folder under the game's `mods` directory while WoT is closed.
