# Contributing

## Source and deployment

GitHub `kolotov/omarchy-agents-statistics`, branch `main`, is the canonical
source. Work in a separate development checkout. The copy under
`~/.config/omarchy/plugins/gkdev.agents/` is a clean runtime checkout managed
with `omarchy plugin add`, `update`, and `remove`.

Do not edit the installed checkout or packaged files under `/usr/share/omarchy`.
Do not commit history, account data, caches, diagnostic screenshots, or local
archives. Keep code, identifiers, comments, and documentation in English.

## Portable tests

Use Python 3.14 or later and Node.js 24:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_statistics.py -v
node tests/calendar.test.cjs
```

The tests use temporary synthetic histories. They do not inspect your accounts.
GitHub Actions runs the same commands; no package installation is required.

## Installed-Shell checks

On a supported Omarchy installation, run:

```sh
omarchy plugin validate .
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The UI check uses the actual installed Omarchy components and Quickshell's
offscreen platform. It verifies cached display, visible summary metrics,
keyboard navigation, return behavior, plain-text sinks, mirrored calendar
geometry, and live light/dark palette bindings. It does not change the desktop
theme or agent settings. Diagnostic outputs stay under ignored `backups/ui/`.

The portable CI job does not claim to validate the complete installed Shell.
Before publishing, also test native install, update, removal, preservation of
bar settings, restoration of the built-in Agents widget, and panel reopening.

## Preview

The UI test renders light and dark previews from synthetic activity:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_ui.py -v
cp backups/ui/statistics-light.png preview.png
```

Review the image before committing. Use demonstration data only.

## Publishing changes

1. Review the diff and run the applicable tests.
2. Update the manifest version for user-visible changes.
3. Commit and push the reviewed source to GitHub; wait for CI to pass.
4. Deploy locally with `omarchy plugin update gkdev.agents`.
5. Check that source, GitHub, and the installed checkout resolve to the same
   commit and that the installed checkout is clean.

Marketplace checks concern one exact public commit. Use the official
[submission requirements](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md)
and [security-baseline workflow](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SECURITY.md).
The listing category is `Developer Tools`; proposed tags are `ai`, `bar`, and
`quickshell`. The manifest's native bar-widget category is a separate field.

Do not open a marketplace submission or verification issue without the owner's
explicit approval of its completed title, body, and ownership checklist.
