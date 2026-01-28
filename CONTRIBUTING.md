# Contributing

Thanks for helping improve the Catalog Intelligence Pipeline!

## Quickstart
1. Fork the repository and create a feature branch.
2. Install dependencies: `python -m pip install -e .[dev]`.
3. Run the quality gates locally:
   - `make lint`
   - `make test`
4. Update docs/README when behavior changes.
5. Open a pull request that describes the motivation, testing, and any follow-up work.

## Commit / PR Checklist
- Tests cover new code paths.
- Lint/type checks pass locally.
- Config changes document the new environment variables.
- Any schema/API change includes version notes in `CHANGELOG.md`.

We follow conventional review etiquette: be respectful, provide context, and keep PRs focused when possible.
