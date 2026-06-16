# Dev master server — pickup-and-go deploy

Spin up the full UT4 dev master server stack with every fix as of this
branch. Designed for a fresh machine: clone, run the commands, verify
with the smoke test. Disposable — branch can be deleted once you've
copied the bits you care about.

This branch (`deploy/dev-handoff-2026-06-16`) targets commit `5216d9b+`
on `smoke-stack-integration`. The handoff doc lives here so the receiving
machine only needs a single `git clone` + checkout.

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
