# Approved compact welcome

Use the selected compact, three-column native welcome layout. The header contains Tankmate Signal, a short value statement, and a preview assembled from the existing notification textures: silhouette and online dot, nickname/clan, green status rule, status label, and slanted message area with the configured shortcut. The preview is inert and must not contact another player.

Explain presence alerts in the Garage/battle, messaging from an online alert (including holding Ctrl to click in battle), and Settings → Mods → Tankmate Signal. Use the game's native modal window, typography, and acknowledgement button. English and Ukrainian copy are provided, with English fallback for other locales.

Show only in the foreground Garage when no other modal is active. Got it atomically saves `welcome_read: true` in the existing installation-wide config, preserving other settings. X/Esc closes for this client session without saving acknowledgement. A failed save keeps the dialog open and reports the failure. Do not re-show on reconnect or every update tick. No external menu dependencies, generated screenshot assets, or automatic test messages.

Implementation choice: register a dedicated native SimpleDialog subclass and a uniquely named SWF root. This preserves existing dialogs and their callbacks. Keep the generated SWF and provenance alongside the Settings asset. Existing Python 2.7 compatibility and stored-ZIP packaging requirements apply.
