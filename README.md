# Tankmate Signal

A World of Tanks mod for friend presence alerts in the hangar and during battle.

Tankmate Signal shows a plate and plays a chime when a friend comes online or goes offline. Status labels follow the game language. Online is green and offline is red. The initial friends list loads silently. Up to three plates appear at once, with later changes waiting for a slot. Diagnostic messages appear in the game log under `[TankmateSignal]`.

While the game is minimized, alerts pause and every friend status change is queued. The queued alerts appear in order when you restore the game and the hangar or battle HUD is visible.

Online alerts include a message button in the Garage and battle. Hold Ctrl to use the mouse during battle, or press **Ctrl+T** while the alert is visible to message the player on the most recently displayed alert. Holding the shortcut sends once. The button shows when the message has been submitted, when you can retry, or when the recipient lookup is unavailable. Hovering over the button keeps the alert visible while you use it.

Notifications use an angular panel with a profile silhouette, colored status indicator, and a bronze message area. Clan tags appear beside the nickname when available from the game's contact data.

The button and message follow the current game language, with English as a fallback. The message asks to play in a Platoon and mentions that you are in battle when sent during battle.

Open **Settings → Mods → Tankmate Signal**. Click **Message hotkey**, then press a key combination. Press **Backspace** or **Delete** while capturing to disable the shortcut, or **Esc** to cancel capture. Click the game's **Apply** or **OK** button to save and activate changes. Closing the window without applying discards your edits.

The **Dev mode** checkbox unlocks test notifications: **Ctrl+F9** for Sauzer_'s online notification and **Ctrl+F10** for offline, regardless of their actual status. Enabling it does not show a notification automatically. Dev mode defaults off and its saved value persists across launches. These combinations remain reserved for testing.

**No settings-menu dependencies are needed.** The mod includes its Settings UI extension and uses the game's native tab, key-field, and checkbox components. Aslain Mod Menu and OpenWG are not required. The Controls tab has no Tankmate Signal section.

Both values are saved in `mods/configs/tankmate_signal.json`, for example `{ "whisper_hotkey": "CTRL+T", "dev_mode": false }`. You can also edit this file while the game is closed. If it is missing, the mod uses **Ctrl+T** with Dev mode off. Old config files containing only the shortcut remain valid. The mod does not read Aslain/Mod Menu settings.

## Build and install

Close World of Tanks. Open 64-bit Windows PowerShell 5.1 or PowerShell 7 in the project folder and pass the folder containing the game's `win64` and `mods` directories.

```powershell
$gameRoot = 'C:\Games\World_of_Tanks_EU'
.\Build-AndInstall.ps1 -GameRoot $gameRoot
```

The script uses the installed client's Python runtime. It builds `probe/tankmate-signal.wotmod` and installs it into the highest-numbered folder under the game's `mods` directory. Rerun it after updating the client. The package includes its own translations from `probe/status-labels.json` and uses the current game language when available, with an English fallback.

To uninstall, close WoT and remove `tankmate-signal.wotmod` from the corresponding game version's `mods` directory.

## Test the notification

Enable **Dev mode** in **Settings → Mods → Tankmate Signal**, click **Apply**, and use **Ctrl+F9 / Ctrl+F10** in the hangar or a battle replay. Turn Dev mode off and apply to disable those shortcuts again.

If the sample is missing, search the game's `game.log` for `tankmate-signal.wotmod` to check whether WoT accepted the package, then for `[TankmateSignal]` to check mod initialization and alerts. A `compression not supported` error means the package should be rebuilt with this installer. WoT Safe Mode disables mods.

## Development checks

The regression tests use Python 3 and mock the WoT client API. GitHub Actions runs them on pushes and pull requests.

```powershell
python -B -m unittest discover -s tests -v
.\Build-AndInstall.ps1 -GameRoot $gameRoot -PackageOnly
python tools/verify_package.py probe/tankmate-signal.wotmod
```

`-PackageOnly` builds the archive without writing to the game's mods folder. The verifier checks the manifest, assets, ZIP headers, and checksums. Before distributing a build, try the sample alert in the hangar and in a battle replay, including the countdown, and check a real friend status change while minimized and after restoring the window. Rebuild with the sample flag disabled before sharing the package.

Also check **Settings → Mods → Tankmate Signal** in the client: confirm both tab levels, key capture, checkbox description, Apply/OK, Cancel, and the persisted Dev mode value after a restart. Verify that the original Settings tabs still work. The automated UI tests use mocked game APIs and do not verify actual rendering or client input routing.

The bundled `probe/tankmate-settings.swf` is built from the stock Settings UI and `ui/SettingsWindowUI.mods.as`. Regenerate it when the client's Settings UI changes, using Java 17+ and the portable FFDec 26.5.0 distribution:

```powershell
python tools/build_settings_ui.py --game-root $gameRoot --ffdec 'C:\Tools\ffdec'
```

The companion JSON records the stock SWF, extension source, and generated asset checksums. Normal packaging and installation use the checked-in SWF and require neither Java nor FFDec.

## Release from main

In GitHub, open **Actions → Release main → Run workflow** and select `main`. Choose `patch`, `minor`, or `major` to increase the version, or `none` to keep the version in `VERSION`. Leave **Publish a GitHub Release** unchecked to build a test artifact without changing `main`.

A publish run verifies the package, commits the new version to `main`, and tags the release commit. Each release includes the multilingual `.wotmod` and its SHA-256 checksum. Copy the mod into the active version folder under the game's `mods` directory while WoT is closed.
