# Native Setup Guide (No Docker)

Complete instructions to run this project natively on Ubuntu 22.04.
Follow every step in order. Estimated time: 20–30 minutes, mostly downloads.

**Tested environment:** Ubuntu 22.04 LTS, ROS 2 Humble, Gazebo Classic 11.10.2

---

## Step 1 — Install ROS 2 Humble

Skip this section if `ros2 topic list` already works on your machine.

```bash
# Locale (ROS2 requires UTF-8)
sudo apt update && sudo apt install locales -y
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

# Enable Ubuntu Universe repository
sudo apt install software-properties-common -y
sudo add-apt-repository universe -y

# Add the ROS2 GPG key
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

# Add the ROS2 apt repository
echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
| sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

# Install ROS2 Humble Desktop (includes RViz, Gazebo tooling, demos)
sudo apt update && sudo apt upgrade -y
sudo apt install ros-humble-desktop -y

# Auto-source ROS2 in every new terminal
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

**Verify:** open a new terminal and run `ros2 topic list`. It should run
without a "command not found" error.

---

## Step 2 — Install ROS 2 package dependencies

These are required by the `sjtu_drone` simulator and by this project's node.

```bash
sudo apt install -y \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-gazebo-plugins \
  ros-humble-gazebo-dev \
  ros-humble-xacro \
  ros-humble-rviz2 \
  ros-humble-joint-state-publisher \
  ros-humble-joint-state-publisher-gui \
  ros-humble-robot-state-publisher \
  ros-humble-imu-tools \
  ros-humble-teleop-twist-keyboard \
  ros-humble-joy \
  ros-humble-tf-transformations \
  python3-colcon-common-extensions \
  python3-rosdep \
  xterm
```

| Package | Why it's needed |
|---|---|
| `gazebo-ros-pkgs`, `gazebo-plugins`, `gazebo-dev` | Gazebo ↔ ROS2 bridge; required to build `sjtu_drone_description` |
| `xacro` | Processes the drone's URDF macro file at launch |
| `rviz2` | 3D visualization, launched by the bringup file |
| `joint-state-publisher`, `robot-state-publisher` | Publish the robot's joint/link transforms |
| `imu-tools` | IMU message filters used by the drone description |
| `teleop-twist-keyboard`, `joy` | Manual teleoperation support |
| `tf-transformations` | Quaternion → Euler conversion for the telemetry dashboard |
| `xterm` | The bringup launch file opens a teleop window in xterm |
| `colcon-common-extensions`, `rosdep` | Build tooling |

---

## Step 3 — Install Python dependencies

```bash
sudo apt install -y python3-pyqt5 python3-pip portaudio19-dev
pip3 install vosk sounddevice
```

| Package | Why it's needed |
|---|---|
| `python3-pyqt5` | The telemetry dashboard GUI |
| `portaudio19-dev` | System audio library required by `sounddevice` |
| `vosk` | Offline speech recognition engine |
| `sounddevice` | Captures microphone audio |

**Note:** if `pip3 install` reports an "externally-managed-environment"
error, add `--break-system-packages` to the command. Older pip versions
(≤22.x) do not recognize that flag and do not need it.

**Verify all four:**
```bash
python3 -c "import PyQt5; print('PyQt5 OK')"
python3 -c "import vosk; print('vosk OK')"
python3 -c "import sounddevice; print('sounddevice OK')"
python3 -c "from tf_transformations import euler_from_quaternion; print('tf_transformations OK')"
```

---

## Step 4 — Create the workspace and clone this repository

```bash
mkdir -p ~/assignment1_ws
cd ~/assignment1_ws
git clone https://github.com/mdruhulamin20061610-cmyk/intp_Assignment.git .
```

The trailing `.` clones directly into `assignment1_ws` rather than into a
nested subfolder.

---

## Step 5 — Clone the drone simulator

This project uses `sjtu_drone` (ROS2 branch), an open-source quadrotor
simulator. It is **not** included in this repository — it is cloned
separately so this repo stays small and the simulator stays at its
upstream version.

```bash
cd ~/assignment1_ws/src
git clone https://github.com/NovoG93/sjtu_drone.git -b ros2
```

---

## Step 6 — Download the Vosk speech model

Also not included in this repository (~40 MB binary).

```bash
mkdir -p ~/assignment1_ws/src/drone_voice_control/models
cd ~/assignment1_ws/src/drone_voice_control/models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 model
rm vosk-model-small-en-us-0.15.zip
```

**Verify:** `ls ~/assignment1_ws/src/drone_voice_control/models/model`
should show: `am  conf  graph  ivector  README`

---

## Step 7 — Build the workspace

```bash
cd ~/assignment1_ws
sudo rosdep init 2>/dev/null || true
rosdep update
rosdep install -r -y --from-paths src --ignore-src --rosdistro humble
colcon build --symlink-install
source install/setup.bash
```

**Verify:**
```bash
ros2 pkg executables drone_voice_control
```
Expected output: `drone_voice_control drone_voice_control`

---

## Step 8 — Disable Gazebo's online model database

Without this, Gazebo stalls for several minutes on startup attempting to
reach `models.gazebosim.org`, and the drone plugin fails to load in time.
This project only spawns local models, so the lookup is unnecessary.

```bash
echo 'export GAZEBO_MODEL_DATABASE_URI=""' >> ~/.bashrc
source ~/.bashrc
```

---

## Step 9 — Run

**Terminal 1 — start the simulation:**
```bash
source /opt/ros/humble/setup.bash
source ~/assignment1_ws/install/setup.bash
ros2 launch sjtu_drone_bringup sjtu_drone_bringup.launch.py
```

Wait until this line appears before continuing:
```
[INFO] [simple_drone.simple_drone]: The drone plugin finished loading!
```

**Terminal 2 — start the voice control node and dashboard:**
```bash
source /opt/ros/humble/setup.bash
source ~/assignment1_ws/install/setup.bash
ros2 run drone_voice_control drone_voice_control --ros-args \
  -p vosk_model_path:=$HOME/assignment1_ws/src/drone_voice_control/models/model
```

### What should happen
1. A PyQt5 window titled **"Drone Telemetry Dashboard"** appears
2. After ~2 seconds the drone automatically takes off in Gazebo
3. Position, orientation, and velocity update live in the dashboard
4. **Manual Mode** (default): the movement buttons control the drone
5. **Voice Mode**: click "Voice Mode", then speak any of:
   `forward`, `backward`, `left`, `right`, `up`, `down`, `stop`

---

## Node parameters

| Parameter | Default | Purpose |
|---|---|---|
| `drone_ns` | `simple_drone` | Topic namespace prefix. Change if your `ros2 topic list` shows a different prefix. |
| `vosk_model_path` | `model` | Absolute path to the Vosk model folder |
| `start_mode` | `manual` | Initial control mode: `manual` or `voice` |

Override any of them at launch, e.g.:
```bash
ros2 run drone_voice_control drone_voice_control --ros-args -p start_mode:=voice
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Gazebo window frozen / "not responding" | Stalled reaching the online model database | Confirm Step 8 was applied: `echo $GAZEBO_MODEL_DATABASE_URI` should print an empty line |
| `/simple_drone/cmd_vel` missing from `ros2 topic list` | Drone plugin never finished loading | Same as above; relaunch after applying Step 8 |
| `package not found` when running `ros2 run` | Workspace not sourced in this terminal | `source ~/assignment1_ws/install/setup.bash` |
| Dashboard opens but numbers never change | Simulation not running, or wrong namespace | Check `ros2 topic list` for the real prefix, then pass `-p drone_ns:=<prefix>` |
| Voice commands do nothing | Wrong model path, or no microphone detected | Verify Step 6, and check the terminal for `Listening for voice commands...` |
| `colcon build` fails on `sjtu_drone_description` | Missing `gazebo_ros` | Re-run Step 2 |

---

## Alternative: Docker

A `Dockerfile` and `docker-compose.yml` are included and the image builds
successfully with all dependencies:

```bash
xhost +local:docker
docker compose build
docker compose up -d
docker exec -it task1_drone bash
```

Note that GUI rendering inside the container requires additional X11 and
Gazebo model-path configuration beyond what is provided. **Native
installation (Steps 1–9 above) is the recommended path for evaluation.**
