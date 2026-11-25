# Built-in settings implementation plan

**Goal:** Move the message shortcut editor into World of Tanks Settings → Controls without external mods.

**Design:** Add a Tankmate Signal group to the built-in keyboard settings data, alongside Movement and Cruise Control. Use the stock group and key-input renderers; remove the separate GUI overlay and texture. Keep the native row's stored key unbound so it cannot participate in the game's single-key conflict handling. Capture mod shortcut combinations before native key dispatch, display the combination in the native key field, and keep mod edits separate from stock command mappings. Apply/OK persists JSON and activates the shortcut; closing discards unapplied edits. Backspace/Delete clears a captured binding, and the built-in Default button resets it.

**Approaches:** The user selected a native keyboard group over a separate Settings tab. Stock keyboard data supports additional groups and rows. The mod retains control of combination capture because native single-key conflict handling would otherwise clear game bindings. No replacement Flash assets or external settings providers are needed.

**Constraints:** Python 2.7 compatibility; no runtime dependencies beyond the game; do not change stock game key mappings; retain Ctrl+T and test shortcut reservations.

- [x] Add tests for native lifecycle, Apply/Cancel, save failure, capture, reset/clear, layout and visibility.
- [x] Implement the native section, config persistence, lifecycle hooks and cleanup.
- [x] Update documentation and run regression tests, build and package verification.

**Review correction:** A failed shortcut save must still delegate the original native apply callback. The Flash screen confirms its own changes after the callback regardless of its return value; blocking stock apply would lose unrelated pending settings. The mod reports its own save failure and retains its previous shortcut.

**Validation limit:** Mocked client tests and package checks cannot establish actual client input routing and renderer behavior. A live Settings screen check is required before release.
