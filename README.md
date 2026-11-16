# Tankmate Signal

A World of Tanks mod for friend presence alerts in the hangar and during battle.

The current preview shows a sample notification and plays a chime once in each scene. Live friend presence events go to the game's log under `[TankmateSignal]`.

## Build and install

Close World of Tanks, then run this in PowerShell 7 from the project folder.

```powershell
.\Build-AndInstall.ps1 -GameRoot 'D:\Games\Wargaming.net\World_of_Tanks_EU'
```

The script builds `probe/tankmate-signal.wotmod` and installs it into the highest-numbered folder under the game's `mods` directory.
