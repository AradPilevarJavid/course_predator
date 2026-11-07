# Roadmap

## First public 1v1 release

- Two desktop Pygame clients can join one authoritative Python TCP server.
- A match starts with two players, synchronizes authoritative state, accepts validated input, and delivers the final result.
- Ordinary disconnects end or cleanly stop a room without leaving the server permanently stuck.
- Replays are saved, and the server can be restarted by the supplied systemd unit for another room.
- Optional shared room-token access, tests, CI, installation instructions, and VPS setup documentation are included.
- Existing spectator and 3–4 player paths remain available but are not expanded in this release.

## Future improvements

- In-process room reset and multiple consecutive rooms without a service restart.
- Stronger identity/authentication and administrative controls if the game ever needs public matchmaking.
- Better reconnect/resume behavior for transient network failures.
- More automated end-to-end testing across real network boundaries.
- Additional game modes, balancing, and UI polish.

The future list is intentionally outside the first public release scope: no browser port, accounts, matchmaking, mobile client, or four-player feature expansion is planned here.
