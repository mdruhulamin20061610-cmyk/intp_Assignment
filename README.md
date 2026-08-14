# Task 1 — Voice-Controlled Quadrotor & Telemetry Dashboard

## Overview
A ROS2 Humble node that controls a simulated quadrotor (`sjtu_drone`, ROS2
branch, chosen since the assignment did not mandate a specific package)
via either voice commands (offline speech recognition with Vosk) or a
PyQt5 GUI, with live telemetry (position, orientation, velocity) displayed
in the same window.

## Architecture
Three concurrent workers, communicating through thread-safe "mailboxes"
and Qt signals rather than direct function calls:
- **ROS2** — publishes `/simple_drone/cmd_vel`, `/simple_drone/takeoff`;
  subscribes to `/simple_drone/odom`
- **Microphone thread** — captures audio, runs it through Vosk, writes
  recognized commands into a lock-protected shared variable
- **PyQt5 GUI thread** — owns the main thread; receives updates via Qt
  signals emitted from the ROS2 odometry callback

## Requirements
- Docker + Docker Compose
- An X11 display (Linux desktop) for GUI passthrough
- A working microphone routed through PulseAudio (the Linux desktop default)

## Running with Docker

**One-time per session — allow the container to open windows on your screen:**
```bash
xhost +local:docker
```

**Build and start the container:**
```bash
cd ~/assignment1_ws
docker compose build
docker compose up -d
docker ps    # confirm task1_drone shows "Up"
```

**Terminal 1 — launch Gazebo + the drone** (leave this running for the
whole session, same as the native workflow):
```bash
docker exec -it task1_drone bash -c "source /opt/ros/humble/setup.bash && source /root/assignment1_ws/install/setup.bash && ros2 launch sjtu_drone_bringup sjtu_drone_bringup.launch.py"
```
Wait for this log line before continuing:
```
[INFO] [simple_drone.simple_drone]: The drone plugin finished loading!
```
(A long stream of `Unable to connect to model database` /
`Failed to find mesh file` warnings above that line is expected — those
are decorative background props in the world file failing to download
their meshes, since `GAZEBO_MODEL_DATABASE_URI=""` deliberately blocks
that lookup. Harmless.)

**Terminal 2 (new window) — voice control node + telemetry GUI:**
```bash
docker exec -it task1_drone bash -c "source /opt/ros/humble/setup.bash && source /root/assignment1_ws/install/setup.bash && ros2 run drone_voice_control drone_voice_control --ros-args -p vosk_model_path:=/root/assignment1_ws/src/drone_voice_control/models/model"
```

Both commands source ROS explicitly rather than relying on `~/.bashrc`,
because `docker exec ... bash -c "..."` runs a non-interactive shell,
which does not read `~/.bashrc` — even though the Dockerfile adds the
sourcing lines there.

**Shut down:**
```bash
docker compose down
```

## Parameters
| Parameter | Default | Purpose |
|---|---|---|
| `drone_ns` | `simple_drone` | Topic namespace prefix for the drone |
| `vosk_model_path` | `model` | Path to the Vosk speech model folder |
| `start_mode` | `manual` | Initial control mode (`manual` or `voice`) |

## Known notes
- Gazebo's online model database is disabled (`GAZEBO_MODEL_DATABASE_URI=""`)
  to avoid multi-minute startup stalls seen when that lookup times out.
- The bonus swarm/leader-follower feature was not implemented; effort was
  focused on the core 75-point requirements.
- If Terminal 2 crashes with `AttributeError: module 'numpy' has no
  attribute 'float'`, this is a NumPy version conflict with
  `tf_transformations`, isolated to this workspace via a venv — see
  **Step 8** in [SETUP_NATIVE.md](SETUP_NATIVE.md) for the fix (this only
  affects the native run; the Docker image pins a compatible NumPy at
  build time).

## Docker Note
Both the Gazebo simulation and the voice-control/GUI node run
successfully inside the container, including microphone access —
confirmed end-to-end. GUI windows render via X11 passthrough
(`xhost +local:docker` + an X11 socket mount); audio is routed through
the host's existing PulseAudio server (socket + cookie file shared into
the container) rather than raw ALSA hardware, since the host's
PulseAudio daemon normally holds that hardware exclusively and a
container requesting it directly gets "Device or resource busy."
Rendering uses Mesa's software rasterizer (`llvmpipe`) with no GPU
passthrough configured, so it is visibly slower to redraw than the
native run, but functionally correct.

**For evaluation:** see [SETUP_NATIVE.md](SETUP_NATIVE.md) for complete native installation instructions.
