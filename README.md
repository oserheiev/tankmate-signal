# Tankmate Signal

A World of Tanks mod for friend presence alerts in the hangar and during battle.

Tankmate Signal shows a plate and plays a chime when a friend comes online or goes offline. Status labels follow the game language. Online is green and offline is red. The initial friends list loads silently. Up to three plates appear at once, with later changes waiting for a slot. Diagnostic messages appear in the game log under `[TankmateSignal]`.

While the game is minimized, alerts pause and every friend status change is queued. The queued alerts appear in order when you restore the game and the hangar or battle HUD is visible.

## Build and install

Close World of Tanks, then run this in PowerShell 7 from the project folder.

```powershell
.\Build-AndInstall.ps1 -GameRoot 'D:\Games\Wargaming.net\World_of_Tanks_EU'
```

The script builds `probe/tankmate-signal.wotmod` and installs it into the highest-numbered folder under the game's `mods` directory.
