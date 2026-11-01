# Local card catalog checker (Arch Linux)

The checker uses the official `/v1/cards` endpoint. It never commits, pushes,
publishes or changes `cards.json` in `--check` mode. Only Python 3 and its standard
library are required.
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
