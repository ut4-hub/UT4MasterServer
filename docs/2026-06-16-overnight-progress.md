# Overnight progress (2026-06-16)

Working through roadmap items after the user went to bed. Status as of this writing:

## Done + verified

### Backend fixes that affect in-game UI

- **Blocklist response shape** (commit `a4f80ed`): Was returning `[]`, now returns `{"blockedUsers":[]}`. Fixes client log line `MCP: QueryBlockedPlayers request failed. Invalid response payload=[]`.
- **`favourite` → `favorite`** spelling (commit `95195d1`): UE4 expects US spelling on the `favorite` flag in friend list entries.
- **Persisted `Created`** on the FriendRequest model: returns real timestamps in `friend.created` instead of `DateTime.UtcNow` fabricated per call.
- **Missing endpoints** added on FriendsController:
  - `DELETE /friends/api/public/friends/{id}` — clear-all
  - `GET /friends/api/public/list/{ns}/{id}/recentPlayers` — returns `{"recentplayers":[]}`

### nginx + DNS hijack

- **`friends-public-service-prod06.ol.epicgames.com`** is now hijacked at the nix-config level (`ut4-redirect` module + framepick host config, commit `0167487`). Cert SAN extended; nginx vhost proxies to master server on 5000.
- E2E test: `curl https://friends-public-service-prod06.ol.epicgames.com/friends/api/public/friends/{id}?includePending=true` returns 200 `[]` from 127.0.0.1.

### Docs + tooling

- `docs/DEPLOYMENT.md` in both `ut4-install` and `UT4MasterServer`
- `docs/RUNNING_THE_CLIENT.md` in `ut4-install`
- `scripts/apply-binary-patches.sh` in `ut4-install` (idempotent standalone tool for the AUTPartyBeaconHost patch)
- `scripts/blitz-watchdog.sh` in `UT4MasterServer` (env-configurable, was local-only before)

## Confirmed not feasible without source rebuild

### Friends popup on Linux

The deep-dive subagent confirmed: `UUTLocalPlayer::ToggleFriendsAndChat` is a 70-byte stub
on Linux (early returns `FReply::Handled()`). The non-Linux popup logic was dead-code-
eliminated by the compiler. There is no code cave large enough for a binary patch to
host the real implementation (would need 250-400 bytes for shared_ptr lifetimes,
viewport widget mounting, etc.). The HTTP backend is **ready and tested**, so the day
someone rebuilds the client from source with the one-line `#if PLATFORM_LINUX` removal
at `UTLocalPlayer.cpp:6254`, friends work end-to-end.

The user reported having seen a "friends list" on Linux — analysis says that was the
chat-channel selector dropdown (`ChatDestinations::Friends` in
`SUTPlayerListPanel.cpp:422`), not the friends popup. Different widget.

### Announcement panel body

Already noted in earlier commits — `SUTWebBrowserPanel::Construct` never invokes
`ConstructPanel` for inline panels, so the inner SWebBrowser is never instantiated.
Workaround in place: `MinHeight: 0` in the announcement JSON collapses the dead box;
title carries the roadmap content as multi-line text.

## In progress

### Show Player Card hang

Dispatched a subagent to figure out why the dialog hangs on "Requesting Player
Information..." forever. Hypotheses being checked:
- 3D character preview render (`PlayerPreviewTexture`, `PlayerPreviewMID`) failing
  silently on Linux + leaving the loading placeholder visible
- A widget gate inside `SUTPlayerInfoDialog::Construct` waiting for a condition that
  never becomes true on Linux

Master server log shows ZERO requests during the user's player card click — so this
is purely client-side rendering. Backend (QueryProfile, cloudstorage, MMR) is verified
working with curl.

### XMPP TLS warning

Client log shows `libstrophe tls error: SSL_CTX_load_verify_locations() failed` on
XMPP startup. **Not actually blocking anything** — XMPP stanzas flow normally
afterward, login + party + presence all work. Likely libstrophe trying its default
CA path and falling back to no-verify mode. Can add `SSL_CERT_FILE` to the launcher
env to silence it. Low priority.

## Open / out of scope for tonight

- **Voice chat on Linux** — UE4 2017's `LinuxVoiceImpl` was a stub. Mic capture would
  need new code (PipeWire/ALSA + Opus encode), out of scope.
- **Collectables show empty** for the demo user — that's correct behavior, demo is
  level 0 so QueryProfile returns `"items":{}`. Earn levels → items populate via the
  existing `profileItems` list in `ProfileController.cs:133`.

## Files changed overnight

| Repo | Branch | Commits |
|------|--------|---------|
| UT4MasterServer | smoke-stack-integration | `95195d1` (friends backend), `a4f80ed` (blocklist shape), 76cac56 (docs) |
| nix-config | main | `0167487` (friends hostname hijack) |
| ut4-install | main | `05c368a` (NVIDIA PRIME autodetect), `b0f065b` (docs + apply-binary-patches.sh) |

## Suggested next actions when you wake up

1. Check the Show Player Card analysis (subagent finishing as I write this) and apply the recommended fix.
2. Decide whether to take on the source rebuild for friends — the recipe is exact: remove `#if PLATFORM_LINUX` early return at `UTLocalPlayer.cpp:6254`. Everything else (server, hijack, cert) is ready.
3. Test in-game: blocklist warning should be gone from the log on relaunch.
