## Agent skills

### Issue tracker

GitHub Issues — issues for this repo live in `mty2024/chemistry-engine`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage-role labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Multi-context layout — one `CONTEXT.md` per context, with a root `CONTEXT-MAP.md` pointing at them. See `docs/agents/domain.md`.

## Development

- Python 3.10+; the engine has no third-party runtime dependencies.
- Test suite: `python -m unittest discover -s tests -v`
- Run the CLI from the repo root: `python -m chemistry_engine ...` (or `chem ...` after `pip install -e .`).
- Refresh the periodic-table data from CIAAW: `python tools/update_periodic_table.py`
- Build and validate the documentation site: `python tools/build_site.py` then `python tools/check_site.py`; the site source is `site/` (plain HTML/CSS/JS) and deploys through `.github/workflows/pages.yml`.
- The in-browser playground (`site/playground.html`) installs the generated wheel into Pyodide; `tools/build_site.py` copies the wheel and `engine.json` into `site/assets/` for it.
- Package metadata and the `chem` console script live in `pyproject.toml` (entry point `chemistry_engine.cli:main`).
