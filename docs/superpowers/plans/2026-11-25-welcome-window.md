# Welcome Window Implementation Plan

> **For agentic workers:** Execute inline using superpowers:executing-plans; verify each task before continuing.

**Goal:** Ship the approved compact welcome with the existing banner and explicit, persistent acknowledgement.

**Architecture:** Register a dedicated native SimpleDialog view using the client's IGuiLoader entities factory. Extend the stock dialog movie under a unique root class, retaining native window/input/button lifecycle. Build the inert banner from the exact notification textures already packaged by the mod.

**Tech Stack:** Python 2.7 runtime, Python 3 unittest/build tools, ActionScript 3, FFDec/Java, PowerShell packaging.

**Spec:** `docs/superpowers/specs/2026-11-25-welcome-design.md`

## Global constraints

No external settings providers. Acknowledgement is installation-wide and saved only by Got it. X/Esc is session-only. Preserve unrelated config values. Show only in the foreground Garage, never over another modal or during battle. Preview is inert and reuses existing textures.

## Review focus

Save failure must preserve previous config and leave the dialog open. Reconnect and repeated ticks must not duplicate the dialog. An existing modal/minimized client must defer it. Existing dialogs and Settings must retain their handlers. Localized text and a disabled or changed shortcut must fit the panel.

### Task 1: Persistence and session policy

- [x] Add failing tests in `tests/test_welcome.py` for absent/invalid acknowledgement, explicit successful acknowledgement, config preservation, failed saving, one display per session, and deferred loading.
- [x] Run the tests and observe the missing-interface failures.
- [x] Extend `probe/mod_tankmate_signal.py`: generic atomic config updates, `_welcome_read`, `_welcome_shown`, `_maybe_show_welcome(scene)`, `_acknowledge_welcome()`. Preserve existing settings behavior.
- [x] Run the full regression suite and check Python 2.7 compilation.

### Task 2: Native dialog and real banner

- [x] Add `ui/TankmateWelcomeUI.as` and `tools/build_welcome_ui.py`; extend `tools/CompileSettingsUi.java` to support a named, renamed root without changing existing Settings builds.
- [x] Inspect native methods before binding the dedicated SimpleDialog subclass, factory registration/removal, and dialog loading in `probe/mod_tankmate_signal.py`.
- [x] Add localized welcome copy in `probe/welcome-labels.json`; reuse the current shortcut and existing notification image assets in the inert preview.
- [x] Build the SWF/provenance, package it in `Build-AndInstall.ps1`, and extend `tools/verify_package.py` and meaningful package tests.

### Task 3: Verify and deliver

- [x] Run regression tests, Python 2.7 packaging, archive verification, and diff checks.
- [x] Install with the client closed. Check native layout/banner, Got it, X/Esc, modal deferral, and restart behavior in the game where automation permits. Record unverified cases explicitly.
- [x] Request a whole-change code review, address blocking findings, and update README and this ledger with results.

## Execution ledger

Approved image: compact option 5 with the existing angular banner. Native API inspection confirms `IGuiLoader.entitiesFactory.addSettings/removeSettings`, `AppEntry.loadView(SFViewLoadParams)`, and native SimpleDialog handlers. Working on `codex/welcome-window` in the current checkout to retain local reference assets; preserve unrelated AGENTS.md/release-assets files. No publication or merge is part of this implementation request.

Verified native eligibility contracts: `AppEntry.isModalViewShown()` is a method; current `WindowLayer.SUB_VIEW` uses `LOBBY_HANGAR` or `LEGACY_LOBBY_HANGAR` for both modern and legacy Garage. `Windowing.isWindowAccessible()` gates foreground focus. A regression covers store, unfocused Garage, existing modal and both Garage aliases. Initial live attempt caught and corrected method/property misuse before delivery. 57 behavioral/package tests pass; Python 2.7 compilation and stored-ZIP verification pass. Native visual and acknowledgement restart checks remain in progress.

Live checks additionally identified the required `DYNAMIC_SCOPE` registration and focused submit button, now matched to the native registration. Preview textures load correctly, including the localized message button and configured shortcut. The native wrapper reads the content width accessor; the custom root now exposes a fixed width while retaining native frame geometry. Final layout and restart validation are pending.

Observed on the installed Ukrainian client: centred native frame at the fixed content width, all three instruction columns inside it, existing localized banner/shortcut assets, native Got it and X. X closed the dialog, retained an unacknowledged config, and did not reopen during the session. Native Settings opened with both Mods/Tankmate Signal tab levels; Cancel returned normally. Final client session log contained welcome opened and no new matching UI errors. Restart-to-acknowledgement test remains in progress.

Final live verification passed: X-dismissed welcome returned on the next launch; Got it closed it and persisted `welcome_read: true` without changing Ctrl+T or Dev mode; the following focused Garage launch skipped the welcome. Closed the client and removed only the test acknowledgement to restore the original first-launch state for user review. Physical Esc, alternate shortcut rendering, non-Ukrainian layout, a forced write failure, and every pre-existing Settings input/apply combination were not rechecked live; relevant automated regressions pass. Final asset/source provenance matches. No PR, push, merge, or release requested.
