# Welcome appearance refinement

**Goal:** Polish the existing approved three-column welcome, preserving native styling, the real banner and acknowledgement behavior.

**Design calls:** Keep the 1040-unit width and native frame/button. Increase content height to 350, use 32-unit outer margins and consistent column baselines. Use the native $TitleFont for headings (30/22) and $TextFont for body (16) and supporting text (14/18). Ivory #EEEDE9 and body #D1CBBC sit over the stock dark panel; dividers use the existing muted #B2AA98 at reduced opacity; the existing banner supplies the bronze #92713E and green #9CC280. Drop decorative step numbers because the three groups explain independent capabilities. Use a plain sample nickname supported by the embedded title font and a clearer, wider shortcut label.

[Title and value statement]             [Existing real banner]
------------------------------------------------------------
Alerts                    Message                    Settings
Body aligned consistently across all three groups.
                          Battle hint
                                                     [Got it]

This refines the selected compact layout; no new controls or runtime behavior. The banner remains the focal element; other decoration stays quiet.

- [x] Update UI typography, spacing and preview alignment.
- [x] Rebuild SWF and provenance, run existing regressions, package and verify.
- [x] Install with the client closed and inspect rendering in the game; check close and acknowledgement controls as needed.
- [x] Commit source and rebuilt assets, recording actual observed checks.

First live check: larger Ukrainian headings/body, aligned columns, visible full banner and wider Ctrl+T keycap all rendered inside the centred native frame; X dismissed normally. Adjusted the settings breadcrumb to an explicit second line to keep Tankmate Signal together. 57 regression tests, Python 2.7 packaging, package verification and source/asset checksum checks pass. No new implementation-detail tests were added for this visual-only change.

Final installed-client check passed: the complete Ukrainian layout and deliberate two-line settings path render inside the native frame; no clipping was observed, and the window is left open for review. Final session log shows welcome opened and no matching new UI errors. X was checked on the first refined build. Acknowledgement/restart behavior, keyboard input and other locales were not rechecked live because their runtime code is unchanged; the existing behavioral regressions pass. Rebuilt SWF and companion provenance are committed together.
