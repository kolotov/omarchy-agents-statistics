# Upstream provenance

This is a user-owned clone of `omarchy.agents`, using the clone mechanism
documented in the [Omarchy plugin manual](https://omarchy.org/manual/shell-plugins/).
It is maintained independently and is not an official Omarchy release.

The initial source snapshot came from the installed Omarchy package
`4.0.0.r7840.gac6cb9c-1`, with Agents manifest version `1.0.0`.
Upstream source: [basecamp/omarchy](https://github.com/basecamp/omarchy).

## Inherited code and assets

- `AgentsPanel.qml`: the built-in Agents panel, with a Statistics link in the Codex header,
  view switching, and state reset when the panel closes.
- `HeroButton.qml`: the built-in Agents hero button, extracted for reuse
  by the panel and preview renderer.
- `Main.qml` and `Agent.qml`: the built-in usage-record display and watchers.
- `vendor/Reorder.js`: only the row-reordering functions used by Agents,
  extracted from the built-in Elsewhen model.
- `vendor/TailscaleIcon.qml`: the built-in Tailscale mark component.
- `assets/`: the provider marks shipped with the built-in Agents panel.

The original relative imports were made self-contained within this plugin.
Upstream license and attribution are retained in `LICENSE`.

## Plugin-specific code

- `StatisticsView.qml`, `Calendar.js`, and `i18n/en.json`: the combined
  activity view, built with Omarchy's shared components and theme tokens.
- `collect_statistics.py` and `rollouts.py`: an independent local history
  reader and aggregator, with no network or credential access.
- `tests/`: synthetic fixtures and regression checks.

The initial reader's per-day counters matched Omarchy's native reader on
376 unchanged local rollout files during development. This is a compatibility
check on those records, not a guarantee about every Codex version or transcript.

## Maintenance

Changes to the upstream Agents interface need an explicit compatibility review.
They are not pulled into this clone automatically. Review upstream changes to
shared UI components, plugin capabilities, account commands, quota collectors,
and rollout record formats before widening the tested-version statement.
