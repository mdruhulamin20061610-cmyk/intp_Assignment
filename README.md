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
- A working microphone

## Running with Docker

```bash
# Allow the container to open windows on your display
xhost +local:docker

# Build the image (first time, or after code changes)
docker compose build

# Start the simulation + node
docker compose up
```

Inside the running container:
```bash
ros2 launch sjtu_drone_bringup sjtu_drone_bringup.launch.py
```
In a second shell into the same container (`docker exec -it task1_drone bash`):
```bash
ros2 run drone_voice_control drone_voice_control --ros-args \
  -p vosk_model_path:=/root/assignment1_ws/src/drone_voice_control/models/model
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

## Docker Note
The Docker image builds successfully and contains all dependencies. GUI/mesh rendering inside the container requires additional X11 and Gazebo model-path configuration; the demonstration video was recorded running natively on the host.
