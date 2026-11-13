# Changelog

## 1.1.3

- Preload the Statistics view asynchronously while Agents is open, keeping
  calendar creation out of its synchronous opening path.
- Show a loading message if Statistics is opened before the calendar is ready.

## 1.1.2

- Move Statistics into the Codex header as a text link and label its view Codex.
- Keep keyboard navigation and return focus within the Codex section.
- Match the preview's close control and frame to the native panel.

## 1.1.1

First public GitHub release.

- Add combined local Codex statistics and a rolling activity calendar to the
  native Agents panel, with automatic refresh and cached display.
- Keep native account controls, theme bindings, keyboard navigation, and
  return behavior.
- Rebuild damaged incremental caches and mirror the calendar in RTL layouts.
- Use Omarchy's Git-based install, update, and removal commands.
- Add portable CI, installed-Shell regression checks, and a synthetic preview.

## 1.1.0

Local prototype, shared as an archive before Git-based distribution.
