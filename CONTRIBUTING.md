# Contributing to Agent Foundry

Thanks for contributing! We accept pull requests, bug reports, and feature requests.

## Workflow

1. Fork it.
2. Branch it (`git checkout -b feature/my-feature`).
3. Commit it (`git commit -am 'Add feature'`).
4. Push it (`git push origin feature/my-feature`).
5. Open a Pull Request.

## Pull Request Rules

- Run pre-commit hooks before submitting.
- Follow existing formatting.
- State exactly what changed and why in the PR description.

## Before opening a PR

Run the hooks, then run Vale across the whole repo:

```bash
pre-commit run --all-files
vale --no-wrap .
```

The `vale` pre-commit hook only sees the files you changed. CI runs `vale .` over everything,
so a pre-existing file can fail your PR for something you did not touch. That happened on the
first PR: a template's frontmatter read `name: {{AGENT_NAME}}`, and `{{` opens a flow mapping
in YAML, so the parse failed.

Workflows also need an explicit `permissions:` block. The default token in this repo cannot
list a PR's commits, and an action that tries gets `403 Resource not accessible by integration`
— which, from a secret scanner, reads as a leak and is not one.
