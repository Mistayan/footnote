# Versioning

Decided 22 November 2026 (#507). One version for the whole product: the engine, the launcher and the Windows installer
always carry the same number, and CI checks it (`python scripts/next-version.py --check`).

## The number

`MAJOR.MINOR.PATCH`, following [Semantic Versioning 2.0](https://semver.org), and nothing else: `0.2.0`, never
`0.2.0-alpha.1`, `0.2.0-rc.1` or a stage name. The app has shown it works; the number alone says how far it has come.

- **Before 1.0** a MINOR release can still break things; the changelog says how to move.
- **1.0** is the first **stable** release, the maintainer's call once all of these hold:
  1. the command line's JSON output and the MCP tools' names and input schemas are documented, covered by contract tests, and
     change only after a deprecation period;
  2. state and database formats move forward by themselves, and `footnote rollback` still opens them;
  3. the installer and the in-app update are signed and verified (#500);
  4. one release has gone through a full in-app update on Windows.

## What triggers a bump

Count every commit merged since the last release tag; the highest row wins. The commit types are the ones CI already
checks (Conventional Commits, `scripts/check-commits.py`).

| The release contains | Before 1.0 | From 1.0 |
|---|---|---|
| a **breaking change** (a `!` after the type, or a `BREAKING CHANGE:` line in the body) | MINOR | MAJOR |
| a **new capability** (`feat`) | MINOR | MINOR |
| anything else: `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `style`, `revert` | PATCH | PATCH |

A **breaking change** is anything that can make an existing setup, script or agent stop working after the update:

- a command, flag or argument removed or renamed, or its meaning changed;
- a field of a command's JSON output removed, renamed, or given another type;
- an MCP tool removed or renamed, or its input schema changed so that old calls fail;
- what the hooks return to an agent changed in a way the agent configuration must follow;
- a configuration key removed or renamed, or a default changed so that behaviour changes for people who never set it;
- a state or database format the previous version can no longer read (no rollback);
- a platform, agent or requirement dropped.

A **new capability** is something a user or an agent can do that they could not before: a command or flag, an MCP tool, a
configuration option, a launcher screen or action, an installer step, a supported agent, a product.

Nothing else moves the number: not the size of a change, not the time since the last release, not a milestone.

## Releases

- Release when `main` holds something users should have; there is no fixed cadence. A security fix ships as a PATCH as soon as
  it is merged.
- The tag is `v<version>` (`v0.2.0`). Its CHANGELOG.md section is the release notes; the in-app update shows its top-level
  bullets as "what's new".
- No pre-release tags: a build to try before releasing is the CI artifact of its pull request, not a GitHub release. (A tag
  with a suffix would also be marked a pre-release, which GitHub's latest release, and so the in-app update, skips.)
- Versions before this rule keep their names: `0.1.0-alpha.1` to `0.1.0-alpha.3`. The first release under it is `0.2.0`.

## Cutting a release

```bash
python scripts/next-version.py              # the next version, and the commits that decide it
python scripts/next-version.py --set 0.2.0  # write it into every manifest and lock file
python scripts/next-version.py --check      # every manifest carries the same version (CI runs this)
```

Then update CHANGELOG.md (`python scripts/changelog.py <git-cliff>`; `git cliff --bumped-version` gives the same answer as
the script, see `[bump]` in `cliff.toml`), merge, and push the tag.
