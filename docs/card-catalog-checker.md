# Local card catalog checker (Arch Linux)

The checker uses the official `/v1/cards` endpoint. It never commits, pushes,
publishes or changes `cards.json` in `--check` mode. That mode needs only Python 3
and its standard library. `--sync` additionally needs Git, OpenSSH, Node/npm,
Python venv/pip and Chromium runtime libraries for the project's Playwright tests.
The setup commands below are instructions for the owner;
adding these files to the repository does not install or start anything.

## Credential and IP allowlist

Create/manage the API key in the [official developer portal](https://developer.clashroyale.com/).
Allowlist the **public outgoing IP of this Arch machine/network**, not localhost
or its private LAN address. A VPN, different network or changed ISP address can
change that IP; update the allowlist/key when necessary. HTTP 401/403 means the
credential and allowlist need checking; the checker cannot distinguish every
authentication failure. It never prints the server's error body or the token.
HTTP redirects are refused so Authorization is not forwarded to another endpoint.

Keep the token outside the checkout, at `~/.config/crdr/api-token`, owned by your
user, with directory mode 700 and file mode 600. To create the file yourself,
this **Bash** snippet reads hidden input rather than putting a token in shell
history or command arguments. It refuses to overwrite an existing file:

```bash
install -d -m 700 "$HOME/.config/crdr"
(
    umask 077
    set -o noclobber
    IFS= read -r -s -p 'Clash Royale API token: ' crdr_token
    printf '\n' >&2
    printf '%s' "$crdr_token" > "$HOME/.config/crdr/api-token"
    unset crdr_token
)
chmod 600 "$HOME/.config/crdr/api-token"
```

Do not paste the token into a unit, command argument, issue, screenshot or Git
file. `LoadCredential` copies the file into the service's credential directory;
the script reads `$CREDENTIALS_DIRECTORY/crdr-api`. This isolates delivery, but
does not encrypt the source file on disk. See [systemd credentials](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html#Credentials).

For manual use only, `CLASH_ROYALE_API_TOKEN` remains supported. A configured
credential directory takes precedence; an unreadable/missing credential fails
closed rather than falling back to an environment token. To use the fallback
without putting the value in command history:

```bash
IFS= read -r -s -p 'Clash Royale API token: ' CLASH_ROYALE_API_TOKEN
printf '\n'
export CLASH_ROYALE_API_TOKEN
python3 scripts/update_cards.py --check
unset CLASH_ROYALE_API_TOKEN
```

## Install and verify the user units

From this repository, when you decide to activate the checker:

```bash
install -d "$HOME/.config/systemd/user"
cp deploy/systemd/crdr-cards.service deploy/systemd/crdr-cards.timer "$HOME/.config/systemd/user/"
```

The shipped `WorkingDirectory` and `ExecStart` point to
`%h/Projects/Python/ClashRoyaleDeckRandomizer`. If your checkout is elsewhere,
edit **both paths in the installed service**. Paths containing spaces must be
quoted using systemd unit syntax. No virtualenv is needed by the service.

```bash
systemd-analyze --user verify "$HOME/.config/systemd/user/crdr-cards.service" "$HOME/.config/systemd/user/crdr-cards.timer"
systemctl --user daemon-reload
systemctl --user start crdr-cards.service
systemctl --user status crdr-cards.service
journalctl --user -u crdr-cards.service -n 30 --no-pager
```

A successful check exits 0 both when unchanged and when changes are found.
Credential, HTTP/network, JSON/schema or local I/O failures exit 1. Neither case
publishes anything. Check status before enabling the daily schedule:

```bash
systemctl --user enable --now crdr-cards.timer
systemctl --user list-timers crdr-cards.timer
```

`OnCalendar=*-*-* 18:00:00` uses the machine's local timezone. `Persistent=true`
catches up a missed run when the timer becomes active again. A user timer runs
while its user manager is running; it does not by itself keep a powered-off
machine or a logged-out user session running. No sudo or linger setup is needed
for the normal logged-in workflow. See [systemd.timer](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).

To stop future runs: `systemctl --user disable --now crdr-cards.timer`.

## Reports and review

State is written to `$XDG_STATE_HOME/crdr-card-updater/`, or
`~/.local/state/crdr-card-updater/` when XDG_STATE_HOME is unset/empty. Relative
XDG_STATE_HOME values are ignored. Files contain card data, never credentials:

- `candidate.json`: validated API snapshot when differences exist.
- `diff.json`: machine-readable before/after data and changed field names.
- `diff.txt`: compact human-readable changes, IDs, costs, rarity, Evolution/Hero
  capability flags and artwork changes.
- `status.json`: UTC timestamp, changed flag and diff fingerprint of the latest
  **successful** check. It is written after the reports.
- `notified.json`: fingerprints already successfully notified.
- `.check.lock`: serializes report updates and notifications across processes.

Added/removed cards and changes to cost, rarity, capabilities or maxLevel are
classified as gameplay changes. Names and artwork are metadata. A card with both
kinds is classified as gameplay, while the report also flags its metadata change.
Tower/support cards are compared separately. List order is ignored. The checker
cannot infer gameplay type changes from IDs when the API does not supply a type.

The existing shared validator is used by check, preview and apply. Unexpected
fields, rarities, capabilities, malformed support cards, duplicate IDs or missing
required data stop the check for manual schema review. It does not guess how a
new API schema should map to application semantics.

On failure, previous successful reports remain intact and can be old: inspect
the journal and timestamp. An unchanged check updates status to `changed:false`
but retains earlier candidate/diff files as historical artifacts. **Do not treat
them as a pending update when status says unchanged.** Files are atomically
replaced individually; a failed/interrupted check is not an approval signal.

Review the diff and candidate, including removals and capability changes. Then
use the existing interactive apply workflow with a credential passed by systemd:

```bash
systemd-run --user --pty --wait --collect \
  --property="LoadCredential=crdr-api:$HOME/.config/crdr/api-token" \
  --working-directory="$PWD" \
  /usr/bin/python3 "$PWD/scripts/update_cards.py" --apply
```

This **fetches again** and prints a fresh preview. Review that exact diff before
typing `REPLACE cards.json`; decline if it differs from what you approved. Running
the script without `--check` or `--apply` still previews without applying.
After an explicit apply, inspect `git diff -- cards.json`, run regression tests,
and separately decide whether to commit/push. The scheduled service has no apply,
Git or publication command.

## Optional desktop notifications

Notifications are off in the supplied unit. If `notify-send` is available and
you want notifications, use `systemctl --user edit crdr-cards.service` to override:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 %h/Projects/Python/ClashRoyaleDeckRandomizer/scripts/update_cards.py --check --notify
```

Adjust the path if needed. No notification daemon/session or a failed notification
does not fail the check. Successful notifications are deduplicated by diff
fingerprint, including after restarts. Failed deliveries can be retried on the
next check; `notify-send` success means the desktop service accepted the request,
not that the user read it. Credential environment variables are not passed to the
notification subprocess. A crash between delivery and recording its fingerprint
can cause a repeated notification.

## Automatic synchronization: `--sync`

**Activation prerequisite:** R2 (Heal Spirit = Troop) must be deployed in both
`static/randomizer.js` and `card_model.py` on `origin/main`. R2 now fixes both local
models and updates the approved snapshot; it must still be reviewed and published
to main. The compatibility gate tests the models from the isolated remote clone
and rejects publication if either model still has the bug. Local R2 changes alone
do not activate synchronization or bypass the remote-model check.

The installed daily `--check` timer and its 18:00 schedule are unchanged. A separate
`deploy/systemd/crdr-cards-sync.service` is provided as a future service template,
with a 30-minute overall timeout; it is not installed automatically.

Synchronization performs the following under an exclusive `.sync.lock`:

1. Clone the latest `main` into a temporary directory inside the state directory.
2. Fetch and validate API data; compare against that clone, never the active
   user's possibly dirty/stale `cards.json`.
3. Record a candidate and diff in `crdr-card-updater/sync/`. Unchanged data exits
   without tests, commit or push.
4. Apply publication policy, write the candidate only in the temporary clone, and
   check JavaScript/Python type agreement and generator compatibility.
5. Create an isolated test venv, install locked npm dependencies with lifecycle
   scripts disabled, install Playwright Chromium and run Python, JS and browser
   tests **against that clone's candidate**. Commands have individual timeouts.
   Browser tests use an available local port and require their own server rather
   than reusing a user's running preview server.
6. Check candidate integrity, original HEAD, origin URL, index and tracked files.
   Fetch again; if `origin/main` advanced during testing, stop without merging or
   rebasing. A later scheduled run starts again from the new main.
7. Commit only `cards.json` as `chore(cards): sync official Clash Royale catalog`;
   push `HEAD:refs/heads/main` normally. Never force-push.
8. Record `sync/result.json` and optionally notify. The temporary clone is removed.

The compatibility test includes all 12 special-slot settings, 8 unique cards,
capabilities, Champions, locks, exact available pool, required/banned cards,
Spell/Building counts, average constraints and Mirror's average contribution of 1.
The Python model must classify all candidate IDs identically to JavaScript.
The existing test suite is also required; a timeout or missing dependency blocks
publication rather than skipping tests. Npm and Python installs need network
access; Chromium system libraries must already be installed by the owner.

The user's working tree is never reset, stashed, pulled, checked out or committed
by sync. After a remote update the active checkout can remain behind main until
the owner chooses to pull. This does not cause duplicate automatic commits,
because every run compares with a fresh remote clone.

### Publication policy and classification limits

Automatic publication accepts ordinary updates to existing cards' costs, rarity,
artwork, capabilities and metadata when the current model and tests support them.
Known supported capability bits are Evolution=1 and Hero=2, including dual-form=3.
Champions cannot simultaneously advertise those new forms under the current model.

Unseen IDs in `26000000..26999999` are provisionally admitted as Troops using the
existing namespace heuristic. This is **not independent confirmation of gameplay
type**. It cannot detect a future Supercell exception inside that namespace, nor
mechanic changes absent from API metadata. Automatic publication accepts this
limited risk for ordinary Troop additions; the report preserves the exact data.

New IDs in the Building/Spell namespaces require manual type review because
Furnace, Heal Spirit and Spirit Empress already demonstrate exceptions. After
reviewing/updating the model and deliberately adding such a card to the baseline,
its later compatible updates can be automatic. Unknown namespaces always block.
Tower/support IDs must remain in the known `159000000..159999999` namespace.

Every card removal blocks automatic publication, a stricter safeguard than just
mass removals. This prevents truncated catalogs and protects existing references.
Unknown schemas, unsupported capabilities, inconsistent artwork, duplicate IDs,
costs above 10, classification disagreement and failed tests also block. Artwork
must use HTTPS on the official `api-assets.clashroyale.com` host.

### GitHub authentication (owner configuration only)

Use a **dedicated write-enabled deploy key for this repository**, not a personal
key shared across projects or an API token embedded in a remote URL. Generate the
key yourself and add its public key to this repository's Settings → Deploy keys
with write access. A write deploy key is repository-scoped, but it is not limited
to `cards.json`; the application enforces that file restriction. See
[GitHub deploy keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys).

Keep the private key outside the checkout, e.g. `~/.ssh/crdr-catalog-deploy`, mode
600, with `~/.ssh` mode 700. Configure this alias yourself in `~/.ssh/config`:

```sshconfig
Host github.com-crdr-cards
    HostName github.com
    User git
    IdentityFile ~/.ssh/crdr-catalog-deploy
    IdentitiesOnly yes
    BatchMode yes
    StrictHostKeyChecking yes
```

Verify GitHub's host key against its
[published fingerprints](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)
and populate known_hosts yourself. Do not disable host-key checking. An encrypted
key needs an agent available to the user service; otherwise unattended operation
requires a dedicated key file that does not need interactive unlocking. Consider
the local file exposure before making that choice. No key is generated/read by
this implementation work.

The sync remote is fixed to
`git@github.com-crdr-cards:Franek2009/ClashRoyaleDeckRandomizer.git`; the active
checkout's remote is unchanged. Git commands ignore global/system Git config
(including URL rewrites), disable hooks/signing prompts and use noninteractive SSH.
API credential variables and GitHub token variables are removed from test/Git
subprocess environments. The Clash Royale credential remains separate from SSH.

Branch rules must permit this authorized actor's direct push for this design to
operate. Do not bypass a required-PR policy unintentionally; rejected pushes stop
the run. A deploy-key push produces a normal push event. Do not replace it with
the workflow `GITHUB_TOKEN`, whose own pushes normally do not start another
workflow. See [GitHub workflow triggering](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

### Safe manual trial and later activation (fish-compatible commands)

First deploy/review R2 and the synchronization code on main, configure the deploy
key and dependencies, then run a **dry run** yourself:

```fish
systemd-run --user --wait --collect \
  --property="LoadCredential=crdr-api:$HOME/.config/crdr/api-token" \
  --property=TimeoutStartSec=30min \
  --working-directory="$PWD" \
  /usr/bin/python3 "$PWD/scripts/update_cards.py" --sync --dry-run --notify
```

`--sync --dry-run` performs the same gates/tests and remote freshness check but
creates no commit and performs no push. `sync/result.json` says `validated`,
`unchanged` or `blocked`. Missing R2 deliberately returns `blocked`.
Without `--dry-run`, `--sync` may push: only run it when publication is intended.

**Only after the owner approves switching modes**, replace the installed service
using the provided template (adjust checkout paths first if necessary):

```fish
install -m 644 deploy/systemd/crdr-cards-sync.service "$HOME/.config/systemd/user/crdr-cards.service"
systemctl --user daemon-reload
systemctl --user cat crdr-cards.service
systemctl --user list-timers crdr-cards.timer
```

The timer continues to target `crdr-cards.service` daily at 18:00; its file is not
changed. `Persistent=true` catches up when the user manager/timer becomes active.
A powered-off machine cannot fetch data; no internet or a changed public IPv4
can cause fetch/authentication failure. HTTP 401/403 diagnostics are sanitized and
logged; check the allowlist, never publish an invalid/partial response. GitHub
failure blocks publication and the next day retries from a fresh clone. There is
no automatic retry loop within a run.

### Outcomes, notifications, deployment and rollback

Read `journalctl --user -u crdr-cards.service` and
`$XDG_STATE_HOME/crdr-card-updater/sync/result.json` (default state fallback above).
The result records status, reason, UTC time, base SHA, candidate hash and, when
created, the update commit SHA. Candidate/diff/status files are in that same
`sync/` directory. Report command failures by stage rather than printing arbitrary
Git/test stderr, which could contain sensitive output.

Successful push notification: `CRDR: catalog updated — … new cards, … new
evolutions, … new heroes.` Failure: `CRDR: catalog update requires attention.`
Identical outcomes are deduplicated across runs; notification failure does not
undo/fail a completed update. Successful push means remote main accepted the
commit, **not that Pages deployment has finished**. Pages tests and deploy both
explicitly check out the same immutable `github.sha`; deployment still depends
on its successful workflow. Inspect GitHub Actions for the result.

If a connection fails during push, acceptance can be ambiguous. Result
`remoteOutcome:unconfirmed` means check the recorded commit against GitHub before
assuming nothing was published. A repeated run compares latest remote data and
does not create a duplicate if that push actually succeeded. Never resolve this
with a force push. Failure to write a result after push is logged to the journal.

Disable automatic runs with `systemctl --user disable --now crdr-cards.timer`.
To revert to checking only, reinstall `deploy/systemd/crdr-cards.service` under
that same user-unit name and reload the manager; re-enable the timer only when
ready. No source-file change automatically modifies installed units.

For a bad published catalog, **stop the timer first**, inspect the recorded SHA,
and revert that cards-only commit in a clean checkout, e.g. `git revert <SHA>`.
Review/test and push the revert normally, then verify Pages. Do not reset/force
main. Fix the model/policy or source-data issue before resuming sync; otherwise
the official API data could simply be proposed again the next day.
