# tools/workflows/ — the two workflows the loop is forbidden to install

These two files belong at `.github/workflows/`. They are parked here because **no
scheduled run can ever put them there**, and that is a GitHub rule, not a bug to work
around.

## The measurement, so nobody re-derives it

Probed 2026-08-03 on a throwaway branch with nothing queued behind it:

```
! [remote rejected] probe/workflow-scope -> probe/workflow-scope
  (refusing to allow a Personal Access Token to create or update workflow
   `.github/workflows/_probe.yml` without `workflow` scope)
```

The rejection happens at GitHub, on the receiving side. It is not the sandbox proxy, not
`bin/push.sh`, and not something a different push path avoids. Also re-verified the same
day, so the PLAYBOOK's claims rest on evidence rather than memory:

| probe | result |
|---|---|
| `curl https://foundry.theshin-naidu.workers.dev/` | `403` — the sandbox still cannot reach `*.workers.dev` |
| `api.github.com/repos/theshin621/foundry` with the PAT | `403` — *"GitHub access to this repository is not enabled for this session"* |
| `api.github.com/repos/.../pulls` with the PAT | `403` — so **a run cannot open a PR**, with any credential |
| an `add_repo` tool (the 403 body suggests one) | **does not exist** in this session's tool set |

## Install them — 30 seconds, works from a phone

The dashboard (`tools/foundry-dashboard.html` → **Needs Theshin**) has a button for each
file that opens GitHub's editor **with the content already filled in**. Press Commit.
The same links, if you would rather not open the dashboard:

- [Install `ship-preview.yml`](https://github.com/theshin621/foundry/new/main?filename=.github%2Fworkflows%2Fship-preview.yml)
- [Install `health-check.yml`](https://github.com/theshin621/foundry/new/main?filename=.github%2Fworkflows%2Fhealth-check.yml)

(Those two are the filename-only versions — paste the file body from this folder. The
dashboard buttons carry the body in the URL, so they need no pasting.)

## The alternative, and why it is not the recommendation

Add **Workflows: Read and write** to the fine-grained PAT
(Settings → Developer settings → Personal access tokens → Fine-grained → the foundry
token → Repository permissions → Workflows). Then the loop installs and maintains these
itself, forever, with no further human step.

The cost is real: that token currently cannot touch CI. Granting it write access to
`.github/workflows/` means anything holding the token could rewrite what runs on every
push — which is the one place a leaked token turns into arbitrary execution. The runtime
secret surface was deliberately kept to one narrow PAT. Installing the files by hand once
keeps it that way. Your call; the loop will use the permission if it is ever granted.

## What each one buys

**`ship-preview.yml`** — opens one draft PR per `ship/**` branch. Cloudflare attaches a
preview deployment to the PR, so you look at the *real rendered page* before merging
rather than trusting a description of it. Merging the PR is the production deploy.

> If the job fails with *"GitHub Actions is not permitted to create or approve pull
> requests"*, switch it on at Settings → Actions → General → Workflow permissions.

**`health-check.yml`** — probes the hub and every `live` ship path after each deploy (and
daily at 05:17 UTC), then commits `public/health.json`. This is the **only** way a run can
learn whether the live site actually renders, since the sandbox cannot reach
`*.workers.dev`. It records HTTP status, byte count, and whether the analytics beacon is
present on each path.

Until it exists, the dashboard falls back to probing the live site **from your browser**
(an `<img>` load of `/up.svg`, which is not subject to CORS). That proves the deployment
is serving and nothing more — no HTTP status, no per-ship path, no beacon check, and no
signal at all inside a scheduled run. It is a fallback, not a replacement.
