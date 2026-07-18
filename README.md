# Course Predator

A real-time 1v1 multiplayer reaction game about stressful university course registration. It uses Python, TCP sockets, object-oriented game models, server-side authoritative validation, and multithreading.

## Features

- Authoritative server with separate client handler threads and a locked game state.
- Modular Pygame desktop client with separated lobby, game, replay, renderer, mouse, widget, and network modules.
- Lobby flow: host locally, join by IP/port, or spectate an active match.
- Server-generated normal, shield, ice, and stress-only illusion shapes.
- Stamina, stress, shields, freezing, hidden shapes, darkening, cursor slowdown, cursor jumps, and cursor trails.
- Race-safe click validation: the first validated click removes the shape on the server.
- Real-time score/status broadcasts to both players and spectators.
- JSON replay recording saved after each match and replay playback from the lobby.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate`.

You can also install the package locally:

```bash
pip install -e .
```

## Run

### Easy Lobby

```bash
python run_client.py
```

Use **Host Game** to start a local server and join as Player 1. On the second computer/client, enter the host IP and port, then click **Join Game**. Extra clients can use **Spectate**.

### Manual Server

```bash
python run_server.py --host 0.0.0.0 --port 50007 --duration 60
```

Then start clients:

```bash
python run_client.py --host 127.0.0.1 --port 50007 --name Alice
python run_client.py --host 127.0.0.1 --port 50007 --name Bob
python run_client.py --host 127.0.0.1 --port 50007 --spectator
```

## Controls

- Move the mouse to move the in-game virtual cursor.
- Left click to send a click to the authoritative server.
- Press `Esc` to leave a match or replay.

The client intentionally uses a virtual cursor. At match start it samples a baseline between raw relative movement and visible movement, then applies stress slowdown to that original baseline.

## Replay

Every completed match writes a JSON recording to `replays/match_<timestamp>.json`.

From the lobby, click **Watch Replay** to play the newest replay, or run:

```bash
python run_client.py --replay replays/match_123456.json
```

## Configuration

Runtime defaults come from `course_predator/constants.py`, optional `config.json`, and environment variables. Useful variables:

- `COURSE_PREDATOR_HOST`
- `COURSE_PREDATOR_PORT`
- `COURSE_PREDATOR_DURATION`
- `COURSE_PREDATOR_REPLAY_DIR`
- `COURSE_PREDATOR_SERVER_TICK_RATE`
- `COURSE_PREDATOR_STATE_BROADCAST_RATE`
- `COURSE_PREDATOR_REPLAY_RECORD_RATE`
- `COURSE_PREDATOR_LOG_LEVEL`

## Main Classes

- `course_predator.server.Server`: accepts clients, broadcasts state, and owns the game loop.
- `course_predator.client.NetworkClient`: socket listener/sender thread for the client.
- `course_predator.client.GameApp`: Pygame rendering and input loop.
- `course_predator.client.GameClient`: small state/input facade decoupled from Pygame rendering.
- `course_predator.game.Game`: authoritative rules, timers, scoring, stamina, and stress.
- `course_predator.models.Player`: score, stamina, stress, shield, freeze, and mouse state.
- `course_predator.models.Shape`: base class for normal, shield, ice, and illusion shapes.

## Developer Commands

```bash
make test
make lint
make format
make run-server
make run-client
```


## Project Statistics
- Files: 25
- Directories: 4
- Total lines: 2,436
- Total size: 86.4 KB (88,434 bytes)
- Estimated tokens: 183

## Project Structure

```
course_predator/
├── Makefile
├── README.md
├── course_predator/
│   ├── __init__.py
│   ├── client/
│   │   ├── __init__.py
│   │   ├── game.py
│   │   ├── lobby.py
│   │   ├── mouse.py
│   │   ├── network.py
│   │   ├── renderer.py
│   │   ├── replay.py
│   │   └── widgets.py
│   ├── config.py
│   ├── constants.py
│   ├── game.py
│   ├── models.py
│   ├── protocol.py
│   ├── replay.py
│   ├── server.py
│   └── types.py
├── pyproject.toml
├── replays/
├── requirements.txt
├── run_client.py
├── run_server.py
└── tests/
    ├── test_game.py
    └── test_protocol.py
```


