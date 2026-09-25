# Offline LAN mode (server PC + cloud sync)

The lab keeps working when the internet is down. One **server PC** in the lab
runs this backend against its own MySQL database. Every desktop app (lab and
cashier) talks to that PC over the router's local network. Whenever the
internet is available, the server PC syncs with the cloud in the background.

```
  Desktop apps ──LAN──►  SERVER PC (this backend + local MySQL)
  (lab, cashier)              │  NODE_ROLE=lan
                              │  every 10 s, whenever the internet is up:
                              │    pull  ◄── portal bookings, payment proofs,
                              │              referrer activity, new users
                              │    push  ──► everything done in the lab
                              ▼
                        CLOUD (this backend + Aiven)
                        NODE_ROLE=cloud — public portal, referrer portal
```

The router doesn't need internet for the lab to work. It only has to keep
the local network (Wi-Fi or cable) up.

## What syncs, and who wins

- **Lab work (LAN → cloud):** patients, test requests, results, payments,
  referrals, blood bank, users, test types and templates, notifications and
  the audit log. Patients can then see released results on the online
  portal once the server PC syncs.
- **Online activity (cloud → LAN):** portal bookings and their items,
  payment proof images, referrer portal codes and photos, "book tests" from
  the referrer portal, and users created on the cloud admin page.
- **LAN-only authority:** numbering settings and counters, lab report
  counters and subscriptions. The cloud never overwrites these.
- **Not synced:** SSDO index and analytics (rebuilt from the data), and
  portal lock-out counters (kept per server).
- **Same record edited on both sides while offline:** the newer edit wins
  and ties go to the server PC. A record deleted on one side stays deleted.
- **Numbers:**
  - Real lab numbers are issued only by the server PC.
  - Referrer "book tests" on the cloud gets a temporary `WEB-XXXXXX` number.
    The server PC swaps in the next real lab number when it syncs, and the
    cloud gets the real number back.
  - Cloud portal bookings use the permanent code `SLB-WEB-0001`; bookings
    made in the lab keep `SLB-BKG-0001`. The two ranges never collide.

## Setup

### 1. Cloud: deploy this version and switch sync on (do this first)

In the Render dashboard, open the web service → **Environment**, add these variables and save (Render redeploys automatically):

```
NODE_ROLE=cloud
SYNC_ENABLED=true
SYNC_TOKEN=<long random secret, 32+ characters>
```

Generate the token once, for example with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`, and keep it
for step 3.

On startup, the cloud creates three new empty tables: `sync_outbox`,
`sync_map` and `sync_state`. Existing tables are not changed. If you use
Alembic instead, the migration is `0006_lan_sync_tables`.

Notes for Render:
- `SYNC_CLOUD_URL` in step 3 is the service's Render address, e.g.
  `https://<your-service>.onrender.com`.
- Render's disk is wiped on every deploy or restart, so payment proofs
  uploaded on the portal only live there until the next deploy. The server
  PC downloads each one within seconds of syncing, so the server PC becomes
  the safe copy.
- On Render's free plan the service sleeps when idle. The server PC's
  10-second sync keeps it awake. That uses about 730 of the free plan's
  750 hours a month, so it only fits if this is your only free service.

This step must come **before** step 2. From this moment the cloud records
every change it makes, so nothing done online is missed.

### 2. Server PC: install the software

1. Install **MySQL Server 8** (MySQL Installer for Windows). Then create the
   database and user:
   ```sql
   CREATE DATABASE solunex_lan CHARACTER SET utf8mb4;
   CREATE USER 'solunex'@'localhost' IDENTIFIED BY '<password>';
   GRANT ALL ON solunex_lan.* TO 'solunex'@'localhost';
   ```
2. Install **Python 3.11**, copy this project onto the PC, and set it up:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. On the router, give the server PC a **fixed IP**, for example
   `192.168.1.10`. Use a DHCP reservation, so the address never changes.
4. Allow the desktop apps in through the Windows firewall (PowerShell as
   administrator):
   ```
   New-NetFirewallRule -DisplayName "Solunex server" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
   ```

### 3. Server PC: configure it

Copy `.env.lan.example` to `.env` and fill it in:
- `JWT_SECRET`, `PORTAL_SECRET` and `ANTHROPIC_API_KEY` must match the
  cloud's values.
- `SYNC_TOKEN` must be the same secret as in step 1.
- `SYNC_CLOUD_URL` is the cloud's address.

### 4. Server PC: copy the cloud database

```
$env:AIVEN_DB_PASSWORD = "<aiven password>"
$env:LAN_DB_PASSWORD   = "<solunex password>"
.\scripts\lan\copy_cloud_to_lan.ps1
```

The script:
1. downloads the cloud database
2. loads it into local MySQL
3. runs `python -m app.sync.cli init-lan`, which clears the cloud's own
   sync queue from the copy
4. deletes the downloaded file, since it contains patient data

Do this **once**. Running it again later would throw away any lab work that
hasn't synced yet.

### 5. Start the server and point the desktop apps at it

- Run `scripts\lan\start_server.bat`, or install it as a Windows service
  with NSSM so it starts at boot: `nssm install SolunexServer`, pointing at
  that .bat file.
- In each desktop app, change the server address from the cloud URL to
  `http://192.168.1.10:8000` (the server PC's fixed IP).

## Checking on it

- `python -m app.sync.cli status`: how many changes are queued, whether the
  cloud is reachable, and the last success and last error.
- `python -m app.sync.cli run-once`: sync right now.
- `GET /api/sync/status` (any staff login) returns the same information as
  JSON. The desktop apps can show it as an "online / offline, N waiting"
  indicator.
- `POST /api/sync/run-now` (staff login) makes the server PC sync now
  instead of waiting for the next cycle.

While offline, `pending_changes` grows and `online` is `false`. Within about
10 seconds of the internet coming back, the queue drains to 0.

## Rules to keep it healthy

- **Only one server PC** runs with `NODE_ROLE=lan`.
- **Keep the server PC's clock correct** (Windows automatic time).
  "Newest edit wins" depends on it.
- **Run one worker** (`--workers 1`, as in `start_server.bat`).
- **Change data through the app.** Direct edits in MySQL Workbench or phpMyAdmin
  aren't recorded and won't sync.
- **Back up the server PC's database** regularly (e.g. nightly `mysqldump`
  to another disk). Until a change has synced, that PC holds the only copy.
