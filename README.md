# Course Predator

Course Predator is a real-time course-registration reaction race for two players. Each player controls a cursor, clicks useful course shapes, manages stamina and stress, and tries to finish with the highest score. The Python server is authoritative: clients send input, while the server owns scoring, timing, visibility, disconnect handling, and the final result.

The first public release is a desktop Pygame game. It supports the existing spectator and 3–4 player code paths, but the supported release scenario is an online 1v1 match.

## Features

- Authoritative TCP server with newline-delimited JSON messages.
- Pygame lobby, match renderer, spectator mode, and replay viewer.
- Normal, shield, ice, and illusion shapes with stamina/stress mechanics.
- Match replay files saved as JSON on the server.
- Optional shared room token for a private public listener.
- Linux systemd deployment template and journal logging.

There is no browser build, account system, matchmaking, or hosted public server included in this repository. The `assets/` directory contains the game artwork used by the client; no separate screenshot or GIF is currently maintained.

## Requirements

- Python 3.11 or newer.
- A desktop environment capable of running Pygame for each client.
- Network access to the server's TCP port for remote play.

## Installation

Clone the repository, create a virtual environment, and install the project:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

On a headless Linux VPS, install the server dependencies only and do not start the Pygame client there. The server does not require a display.

## Run a local match

Start the server in one terminal:

```bash
python run_server.py --host 127.0.0.1 --port 50007 --duration 60
```

Start two clients, either from the same machine or from two machines that can reach the server:

```bash
python run_client.py
```

In the lobby, enter the same host and port in both clients and choose **Join Game**. A match starts when the configured minimum number of players (two by default) has joined.

For a local host/client workflow, **Host Game** starts a local server process and connects the first client to `127.0.0.1`. This is convenient for development only.

## Connect to a remote server

1. The server owner starts the server on a VPS or reachable Linux computer.
2. Both players enter the server's public DNS name or public IP and the same TCP port in the lobby.
3. If the server owner configured a room token, both players enter the same token in their client configuration/environment.
4. Both players choose **Join Game**.

**Do not use `127.0.0.1` or `localhost` for remote play.** Those addresses always mean "this computer", so each player would connect to their own machine instead of the VPS. The default is intentionally local for safe development; replace it with the server's reachable hostname or address.

The default server port is `50007`. Choose a different port with `--port` and allow that exact TCP port through the VPS firewall.

## Optional room token

For a public listener, set a shared token on the server and clients without committing it:

```bash
export COURSE_PREDATOR_ROOM_TOKEN='replace-with-a-random-value'
python run_server.py --host 0.0.0.0 --port 50007
```

The client uses the same environment variable when it connects. A token is simple access gating, not authentication or an account system. Anyone who learns it can join, so use a long random value and rotate it between private sessions.

## VPS deployment

[`deploy/course-predator.service`](deploy/course-predator.service) is a template, not a provider-specific deployment. The owner must:

1. Create a dedicated non-root service user and application directory.
2. Copy the repository into that directory and install Python dependencies in a virtual environment.
3. Copy the unit to `/etc/systemd/system/`, replace the placeholder paths/user, and set the token through an environment file readable only by the service.
4. Open only the chosen TCP port in the VPS firewall, for example:

   ```bash
   sudo ufw allow 50007/tcp
   sudo ufw enable
   ```

5. Reload and start the service:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now course-predator
   sudo journalctl -u course-predator -f
   ```

The server deliberately exits cleanly after a finished room has saved its replay and all players have disconnected. The unit restarts it so the next room is available. This keeps room reset logic out of the game state, but it means the journal contains a normal stop/start boundary between rooms.

No VPS deployment or internet test is claimed by this repository. The owner must verify DNS, firewall rules, the token, systemd startup, and two real clients from separate networks.

## Troubleshooting

- **Connection refused:** confirm the server process is running, the host/port match, and the firewall allows TCP traffic on that port.
- **Both clients connect to different games:** check that neither client uses `127.0.0.1`/`localhost` for a remote server.
- **Waiting for players:** both clients must use **Join Game**, not **Host Game**, and must provide the same server address and token.
- **Token rejected:** compare `COURSE_PREDATOR_ROOM_TOKEN` exactly on the server and both clients, then restart the client.
- **A player leaves:** the match ends immediately and awards the remaining connected player; the server saves the replay after the room is empty.
- **No replay appears:** check the server's configured replay directory and journal for permission errors.
- **Client display problems on Linux:** run the client in a desktop session with the required SDL/Pygame display support; the server itself is headless.

## Development

```bash
python -m pytest
python -m ruff check .
python -m black --check .
```

The GitHub Actions workflow runs the same test and quality checks on pushes and pull requests.

## License

Course Predator is released under the [MIT License](LICENSE).
