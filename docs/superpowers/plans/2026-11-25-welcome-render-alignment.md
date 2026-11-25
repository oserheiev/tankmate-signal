# Match the approved welcome render

User correction: the existing approved render is the target; the generic smaller native dialog and removal of badges drifted from it.

Reference: C:/Users/oserh/.codex/generated_images/01a20ef1-1b47-7d62-b150-2915b8ecf5e7/exec-82bbd2aa-2a3e-4e3f-805d-acd473c51241.png

Match the render's roughly 70% viewport width and 52% viewport height, dominant warm title with the existing client metal emblem, larger real banner, three numbered bronze badges, fine dividers, and a substantial native acknowledgement button. Native dialog lifecycle and saved properties remain unchanged. Use the installed client logo and existing banner assets; no generated raster UI.

- [x] Rebuild the UI and matching provenance.
- [x] Run regressions and package validation.
- [x] Inspect the installed result against the render, correcting clipping and proportions.
- [x] Commit only the requested source, generated assets and validation record.

User rejected the 70% viewport size as too large. Reduce to a medium 1360-unit width (roughly 54% of the observed viewport), preserving render composition and proportional content scaling. Use a normally sized native button with an explicit large native-font label, and restore the inline shortcut keycap from the render.

User requested sizing based on the native UI rather than another visual estimate. Inspected installed DefaultDialog.css: DefaultDialogTemplate_center width720rem, title36rem, content16rem, DialogTemplateButton min-width160rem, CButton medium min-height32rem/font15rem. Native Settings content is802x523. Use720 content width, roughly400 content height plus the native frame, with effective36/18/16 title/heading/body sizes and a native160x32 button. Preserve the render composition and badges while allowing localized instructions sufficient height. The prior1360 width and percentage-based sizing are superseded.

Sizing evidence: installed gui/gameface/_dist/production/dialogs/DefaultDialog/DefaultDialog.css, DefaultDialogTemplate_center width720rem, DefaultDialogTemplate_title font36rem, DefaultDialogTemplate_content font16rem, DialogTemplateButton min-width160rem, CButton medium min-height32rem and font15rem. Wulf CSS and Scaleform use separate renderers; these are a logical-size reference, not a claim of exact cross-renderer screen pixels. The native Scaleform wrapper still controls final padding/positioning.

Latest build: Python 2.7 packaging,57 existing regression tests, archive verification, source/SWF checksum checks and diff checks pass. Live verification is currently awaiting sign-in; client opens to empty login fields, so no final-rendering claim is made yet. Earlier oversized previews were inspected and rejected by the user; their size is superseded.

The final screenshot feedback supersedes the emblem and inline keycap in the render. The title and subtitle now align left, the preview grows by 15% within the live plate's 412 by 84 reference size, and the message shortcut wraps with the sentence. The native button sits in the center of the footer with vertically centered text. The welcome recalculates its fit from the available Scaleform stage and native padding when the stage changes, up to the standard 720 by 400 layout.

Observed in the installed Ukrainian Garage at the current resolution: enlarged banner, left-aligned title and subtitle, complete instructions and centered button label and placement. Alt+Enter with the welcome open did not change display mode, so a second resolution was not verified live. All 57 regression tests, package validation and provenance checks passed. The final dialog was left open for review.
