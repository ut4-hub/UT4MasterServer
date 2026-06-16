# Dev master server — pickup-and-go deploy

Spin up the full UT4 dev master server stack with every fix as of this
branch. Designed for a fresh machine: clone, run the commands, verify
with the smoke test. Disposable — branch can be deleted once you've
copied the bits you care about.

This branch (`deploy/dev-handoff-2026-06-16`) targets commit `5216d9b+`
on `smoke-stack-integration`. The handoff doc lives here so the receiving
machine only needs a single `git clone` + checkout.

## Map of related docs (READ THESE FIRST)

All paths relative to the matching repo root.

**In this repo (`ut4-hub/UT4MasterServer`):**
- `docs/DEPLOYMENT.md` — full architecture, controllers, login flow, Quick Play recipe, auto-inject/auto-promote logic
- `docs/2026-06-16-overnight-progress.md` — what changed in the last big session
- `docs/2026-06-16-source-rebuild-feasibility.md` — why we can't rebuild from source (CDN dead)
- `scripts/smoke-test-endpoints.sh` — 11-endpoint health check
- `scripts/blitz-watchdog.sh` — keeps the Blitz dedicated server in FlagRun mode

**In `ut4-hub/ut4-install`:**
- `docs/DEPLOYMENT.md` — client + dedicated-server side (binary patches, Engine.ini, two login paths)
- `docs/RUNNING_THE_CLIENT.md` — install-and-run walkthrough
- `docs/SOURCE_REBUILD_PLAN.md` — three-pronged rebuild plan (community ask / source / shim)
- `scripts/apply-binary-patches.sh` — idempotent AUTPartyBeaconHost patch
- `shims/ut4_friends_fix.cpp` — LD_PRELOAD shim source for the friends popup
- `pkgs/ut4-launcher.nix` — NixOS launcher with PRIME autodetect + SSL_CERT_FILE
- `pkgs/ut4-server-base.nix` — bakes the AUTPartyBeaconHost patch into the build

**In `itpick/nix-config` (public repo, main branch):**
- `modules/nixos/ut4-redirect/default.nix` — nginx + /etc/hosts hijack for Epic hostnames
- `hosts/framepick/configuration.nix` — example consumer of the redirect module
- `docs/superpowers/notes/2026-06-15-quickplay-handoff.md` — the working QuickPlay recipe

## Repo state pins (matching what's on the dev box right now)

| Repo | Branch | Head commit |
|------|--------|-------------|
| ut4-hub/UT4MasterServer | smoke-stack-integration | `5216d9b` (this handoff is on `deploy/dev-handoff-2026-06-16`) |
| ut4-hub/ut4-install | main | `bc2dfab` |
| itpick/nix-config | main | `0167487` |

## Prereqs on the target machine

- Docker (with compose plugin) — tested with 27.x
- ~6 GB free disk
- Ports `5000`, `5001`, `5222`, `5280`, `1025`, `8025`, `27017` free on `127.0.0.1`

## 1. Clone the repos

```bash
mkdir -p ~/code && cd ~/code

# Master server (this repo)
git clone -b smoke-stack-integration git@github.com:ut4-hub/UT4MasterServer.git

# Optional but useful: the client install flake
git clone git@github.com:ut4-hub/ut4-install.git
```

## 2. Build images + start the smoke stack

```bash
cd ~/code/UT4MasterServer

# Build the api image
docker build -t ut4-master-server-api:smoke -f UT4MasterServer/Dockerfile .

# Build the web (nginx) image
docker build -t ut4-master-server-web:smoke-v2 -f UT4MasterServer.Web/.docker/Dockerfile UT4MasterServer.Web

# Bring up the smoke compose stack (api, web, mongo, xmpp/ejabberd, mailpit)
# The compose file lives at /tmp/ut4ms-smoke on the original dev box.
# Copy or recreate it from the template below:
mkdir -p /tmp/ut4ms-smoke && cd /tmp/ut4ms-smoke
cat > docker-compose.yml <<'COMPOSE'
networks:
  ut4ms:
    driver: bridge

services:
  api:
    image: ut4-master-server-api:smoke
    container_name: ut4ms-smoke-api
    ports:
      - "127.0.0.1:5000:80"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      - ApplicationSettings__DatabaseConnectionString=mongodb://smoke:smokepass@mongo:27017/?authSource=admin
      - ApplicationSettings__DatabaseName=ut4master
      - ApplicationSettings__AllowPasswordGrantType=true
      - ApplicationSettings__WebsiteDomain=http://localhost:5001
      - ApplicationSettings__Mail__Host=mailpit
      - ApplicationSettings__Mail__Port=1025
      - ApplicationSettings__Mail__FromName=UT4 Master Server (dev)
      - ApplicationSettings__Mail__FromAddress=noreply@ut4-hub.local
      - ApplicationSettings__Mail__LogToConsole=true
      - Logging__LogLevel__Microsoft.AspNetCore=Information
    depends_on: [mongo, mailpit]
    networks: [ut4ms]

  web:
    image: ut4-master-server-web:smoke-v2
    container_name: ut4ms-smoke-web
    ports:
      - "127.0.0.1:5001:8080"
    networks: [ut4ms]

  mongo:
    image: mongo:7
    container_name: ut4ms-smoke-mongo
    environment:
      MONGO_INITDB_ROOT_USERNAME: smoke
      MONGO_INITDB_ROOT_PASSWORD: smokepass
      MONGO_INITDB_DATABASE: ut4ms
    volumes:
      - ./mongo-data:/data/db
    ports:
      - "127.0.0.1:27017:27017"
    networks: [ut4ms]

  xmpp:
    image: ut4ms-smoke-xmpp:local   # ejabberd built locally; see notes
    container_name: ut4ms-smoke-xmpp
    ports:
      - "127.0.0.1:5222:5222"
      - "127.0.0.1:5280:5280"
    networks: [ut4ms]

  mailpit:
    image: axllent/mailpit:latest
    container_name: ut4ms-smoke-mailpit
    ports:
      - "127.0.0.1:1025:1025"
      - "127.0.0.1:8025:8025"
    networks: [ut4ms]
COMPOSE

# Note: the ejabberd image (ut4ms-smoke-xmpp:local) needs to be built or
# pulled separately. On the original dev box it was built from a custom
# Dockerfile bundling extauth.py that calls /account/api/oauth/verify.
# If you skip ejabberd, in-game XMPP (chat, party, presence) won't work
# but everything else will.

docker compose up -d
```

## 3. Seed an account

```bash
# Replace credentials as you like
curl -s -X POST http://127.0.0.1:5000/account/api/create/account \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","email":"demo@ut4-hub.local","password":"demopass123"}'
```

## 4. Verify with smoke test

```bash
cd ~/code/UT4MasterServer
chmod +x scripts/smoke-test-endpoints.sh

# Need a live session in mongo first — log in via the game once, or
# manually create one via curl /account/api/oauth/token (password grant)
bash scripts/smoke-test-endpoints.sh
```

Expected: all 11 checks PASS.

## 5. (Optional) Run the Blitz dedicated server with the watchdog

If you need QuickPlay testing:

```bash
# Get the UT4 server zip from archive.org (~870 MB):
# https://archive.org/details/ut-4-windows-build.-7z (sibling Linux server)
# Extract to ~/Games/UT4-server/LinuxServer/

# Apply the AUTPartyBeaconHost IsValid bypass binary patch
bash ~/code/ut4-install/scripts/apply-binary-patches.sh ~/Games/UT4-server/LinuxServer

# Start the watchdog (relaunches into FlagRun on every empty-mode transition)
cp ~/code/UT4MasterServer/scripts/blitz-watchdog.sh ~/Games/UT4-server/
chmod +x ~/Games/UT4-server/blitz-watchdog.sh
nohup ~/Games/UT4-server/blitz-watchdog.sh > /tmp/blitz-watchdog.log 2>&1 &
```

## 6. (Optional) Hijack epicgames.com hostnames for the client

If you want the in-game client to actually reach this master server,
you need the NixOS module from `~/code/nix-config/modules/nixos/ut4-redirect/`
or an equivalent nginx + /etc/hosts setup. Required hostnames:

```
127.0.0.1  www.epicgames.com
127.0.0.1  accounts.epicgames.com
127.0.0.1  prod.ol.epicgames.com
127.0.0.1  friends-public-service-prod06.ol.epicgames.com
```

Plus an nginx cert covering all those hostnames in SAN, proxying:
- `:443` → `127.0.0.1:5000` for the friends host
- `:443` → `127.0.0.1:5001` for the master server web (or 302 redirects)
- `:5222` → ejabberd

## What's included in this branch

All commits up to `5216d9b` on `smoke-stack-integration`:

- Friends backend (`favorite` spelling, persisted `Created`, recentPlayers, clear-all, blocklist envelope)
- Auto-inject + auto-promote matchmaker logic (QuickPlay tile)
- Quick-Play endpoint family (`wait_times`, `matchMakingRequest`, etc.)
- ⓘ Info-icon / announcement system (cloudstorage + system files)
- Password reset (Mailpit + Resend support)
- `stats.json` and `oldplayercard` user-cloud stubs (player card unblock)
- Docs (this file + the full DEPLOYMENT.md + smoke-test-endpoints.sh)

## Mongo bootstrap state (seed if you skip the volume copy)

The compose file mounts `./mongo-data` as the mongo data dir. If you
copy the dev box's `mongo-data` over you inherit all state for free.
If you start clean, the api container's startup seeder will create the
`cloudstorage` system files from `UT4MasterServer/CloudStorageSystemFiles/*`
but **NOT** the oauth clients or trusted server.

Seed these by hand (replace mongo creds if you change them):

```bash
docker exec -i ut4ms-smoke-mongo mongosh \
  "mongodb://smoke:smokepass@127.0.0.1:27017/?authSource=admin" --quiet <<'EOF'
db = db.getSiblingDB("ut4master");

// OAuth clients the UT4 client expects to see
db.clients.insertMany([
  { _id: "34a02cf8f4414e29b15921876da36f9a", Secret: "daafbccc737745039dffe53d94fc76cf" },
  { _id: "1252412dc7704a9690f6ea4611bc81ee", Secret: "2ca0c925b4674852bff92b26f8322434" },
  { _id: "6ff43e743edc4d1dbac3594877b4bed9", Secret: "54619d6f84d443e195200b54ab649a53" },
  { _id: "6554d918c50ae96e093b29adb99b5673", Secret: "45c47dcf5bd38cc3bfb23a872526c31b" }
]);

// Trusted server entry — owner account 7c5bdd... must exist for the
// dedicated server's heartbeat to be accepted as a hub server
db.trustedservers.insertOne({
  _id: "6ff43e743edc4d1dbac3594877b4bed9",
  OwnerID: "7c5bddb0b837b75fb971c7e9faa297de"
});
EOF
```

Then create at least one human account:

```bash
curl -s -X POST http://127.0.0.1:5000/account/api/create/account \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","email":"demo@ut4-hub.local","password":"demopass123"}'
```

System cloudstorage files served (auto-seeded from `CloudStorageSystemFiles/`):
`UnrealTournamentOnlineSettings.json`, `UnrealTournmentMCPAnnouncement.json`,
`UnrealTournmentMCPGameRulesets.json`, `UnrealTournmentMCPStorage.json`,
`UTMCPPlaylists.json`.

## The UT4 client's Engine.ini override (for the receiving dev machine)

Without an `Engine.ini` override the UT4 client hits Epic's real prod
servers. Drop this at
`~/Documents/UnrealTournament/Saved/Config/LinuxNoEditor/Engine.ini`
**before first launch**. (`ut4-install`'s launcher seeds this
automatically; if you're not using that flake, do it manually.)

```ini
[OnlineSubsystemMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.OnlineEventsMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.OnlineIdentityMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.OnlinePartySystemMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.MatchmakingMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.UserCloudMcp]
Domain=127.0.0.1:5000

[OnlineSubsystemMcp.OnlineEntitlementsMcp]
Domain=127.0.0.1:5000

[/Script/UnrealTournament.UTGameEngine]
+IniVersions=(IniName="Engine",VersionString="$IniVersion-1")
```

Hostnames the binary HARDCODES (no Engine.ini override possible) —
these need the `ut4-redirect` module or an nginx hijack:
- `prod.ol.epicgames.com` (XMPP)
- `friends-public-service-prod06.ol.epicgames.com` (friends/blocklist/recentPlayers)

## Local launch.sh template (for the dev machine, outside Nix)

The dev box uses `~/Games/UT4/launch.sh`. Copy this to a fresh machine
if you don't want to use the `ut4-install` flake:

```bash
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAME_ROOT="${HERE}/LinuxNoEditor"
BIN="${GAME_ROOT}/Engine/Binaries/Linux/UE4-Linux-Shipping"

export NIXPKGS_ALLOW_UNFREE=1
NSS=$(nix-build '<nixpkgs>' --no-out-link -A nss)
NSPR=$(nix-build '<nixpkgs>' --no-out-link -A nspr)
GCONF=$(nix-build '<nixpkgs>' --no-out-link -A gnome2.GConf)
XSS=$(nix-build '<nixpkgs>' --no-out-link -A libxscrnsaver)
STEAMRUN="$(nix-build '<nixpkgs>' --no-out-link -A steam-run)/bin/steam-run"

cd "${GAME_ROOT}"

# Friends shim is OFF by default — re-enable when SOverlay wrap is fixed:
#   LD_PRELOAD=/path/to/libut4_friends_fix.so \
SDL_VIDEODRIVER=x11 \
SSL_CERT_FILE=/etc/ssl/certs/ca-bundle.crt \
__GL_SYNC_TO_VBLANK=1 \
__NV_PRIME_RENDER_OFFLOAD=1 \
__GLX_VENDOR_LIBRARY_NAME=nvidia \
__VK_LAYER_NV_optimus=NVIDIA_only \
vblank_mode=3 \
mesa_glthread=false \
LD_LIBRARY_PATH="${GAME_ROOT}/Engine/Binaries/Linux:${NSS}/lib:${NSPR}/lib:${GCONF}/lib:${XSS}/lib:${LD_LIBRARY_PATH:-}" \
exec "${STEAMRUN}" ./Engine/Binaries/Linux/UE4-Linux-Shipping \
  UnrealTournament -SaveToUserDir -opengl4 \
  -epicapp=UnrealTournamentDev -epicenv=Prod -EpicPortal "$@"
```

PRIME env vars are no-ops on non-NVIDIA systems; safe to leave. The
`-opengl4` flag matters — `-opengl3` falls back to a broken iGPU stack
on hybrid laptops.

## Verified working ✅ vs. known broken ❌

| Feature | State | Notes |
|---------|-------|-------|
| Login (username or email + password) | ✅ | Path A — stock client, no UT4UU |
| Forgot password / email reset | ✅ | Mailpit captures locally, Resend in prod |
| Quick-Play Blitz (FIRST cycle after server start) | ✅ | Lands in FlagRun |
| Quick-Play Blitz (subsequent cycles) | ⚠️ | Watchdog sometimes loses tail across log rotation; kill+restart watchdog to recover. See "Operational quirks" below |
| In-game chat (everyone + team) | ✅ | T / R keys |
| Announcement panel — title | ✅ | Multi-line ASCII; mixed font sizes need rich-text widget |
| Announcement panel — body box | ❌ | `SUTWebBrowserPanel::Construct` dead code on Linux; set `MinHeight: 0` to hide |
| Show Player Card | ⚠️ | Backend ready; client also needs the binary NOP at `0x15a3687` (6 bytes) — not in any flake yet |
| Show Player Stats | ⚠️ | Same gating as Player Card |
| Friends popup (main menu) | ❌ | `UUTLocalPlayer::ToggleFriendsAndChat` is a 70-byte stub on Linux. Backend works (verified). UI needs source rebuild or LD_PRELOAD shim (WIP — crashes ~15s after click) |
| Friends as chat target (in-match) | ✅ | Different widget; works |
| Voice chat (push-to-talk) | ❌ | Linux mic capture stubbed in UE4 4.15 |
| Collectable items | ⚠️ | Backend works; demo user is level 0 so `QueryProfile` returns empty items — earn levels to populate |
| QuickPlay tile + server browser shows servers | ✅ | Master returns the server; client lists it |
| "Hub" menu shows servers | ❌ | "Hub" specifically means `UTLobbyGameState` servers; we run game-instance servers, not lobbies |

## Operational quirks

### The watchdog can lose its tail across log rotation

`scripts/blitz-watchdog.sh` tails the server's `Saved/Logs/UnrealTournament.log`
for the `"Server switch level: ut-entry?game=empty"` line. When the
server backs up and recreates its log on restart, `tail -F` follows by
filename but sometimes misses the empty-mode transition for the second
match cycle onward.

**Symptom**: QuickPlay screen goes black on the second or third QuickPlay
click (lands in `UT-Entry` void instead of `FR-MeltDown`).

**Recovery**:
```bash
pkill -f blitz-watchdog.sh
pkill -f UE4Server-Linux-Shipping
sleep 2
nohup ~/Games/UT4-server/blitz-watchdog.sh > /tmp/blitz-watchdog.log 2>&1 &
```

A real fix would replace the `tail -F` watcher with a robust file-watcher
(inotify) or a polling loop that checks `lsof` on the server process.

### Master server's auto-promote logic

In `MatchmakingService.cs`, when a search criterion is `UT_PLAYLISTID_i`,
the matcher ALSO returns any server with `UT_RANKED_i=1` (via a Mongo
`$or` BsonDocument). This is what makes QuickPlay land on the Blitz
server even before the dedicated server has written a specific playlist
id. Important to preserve when porting fixes.

### Cloudstorage 'oldplayercard' stub

`CloudStorageController.GetFile` returns `{}` for `oldplayercard` when
the file is missing (similar to the stats.json stub). Without this stub,
the in-game Player Card dialog hangs forever on "Requesting Player
Information..." because the shipping client gates `UpdatePlayerCustomization`
on a successful `OnReadUserFileComplete`. Live test the stub with:

```bash
curl -s "http://127.0.0.1:5000/ut/api/cloudstorage/user/{accountId}/oldplayercard" \
  -H "Authorization: bearer {token}"   # should return 200 {}
```

### Mongo cleanup if the api refuses to start

If you see `MongoServerError: Command update requires authentication`
during seeding, the mongo container was created without the
`MONGO_INITDB_ROOT_*` env vars (re-create the container).

If the api logs `Bearer was not authenticated. Failure message: invalid token`
during normal operation, the api was recreated and in-memory session
state was flushed. Either log in again from the game, or fetch a fresh
session from mongo (see `smoke-test-endpoints.sh` for how).

## Known limitations (read before getting confused)

1. **Friends popup on Linux client**: compiled out in the shipping binary
   (`UTLocalPlayer.cpp:6254` `#if PLATFORM_LINUX return`). Backend is
   ready; UI needs a client rebuild or the LD_PRELOAD shim from
   `ut4-install/shims/`.
2. **Source rebuild**: blocked by dead Epic CDN. See
   `docs/2026-06-16-source-rebuild-feasibility.md` and
   `ut4-install/docs/SOURCE_REBUILD_PLAN.md`.
3. **Announcement panel body**: `SUTWebBrowserPanel::Construct` never
   invokes `ConstructPanel` — work around by setting `MinHeight: 0` in
   the announcement JSON.
4. **Player card "Requesting Player Information..."**: needs the
   `oldplayercard` stub (already in this branch) AND a client-side
   binary NOP at file offset `0x15a3687` (6 bytes `0f 84 5c 01 00 00`
   → `90 90 90 90 90 90`). The NOP is not in any nix flake yet.
5. **Toolchain stash**: `native-linux-v11_clang-5.0.0-centos7.tar.gz`
   (369 MB) was recovered from wayback. Lives at
   `~/Games/UT4-toolchain/` on the dev box. Won't help for the 4.15
   source rebuild without the missing engine binary deps but useful
   to keep around.

## Cleanup

```bash
docker compose -p ut4ms-smoke down -v
git checkout smoke-stack-integration
git branch -D deploy/dev-handoff-2026-06-16  # if you want to remove this branch locally
```

To delete the branch from the remote after the receiving machine has
picked it up:

```bash
git push origin --delete deploy/dev-handoff-2026-06-16
```
