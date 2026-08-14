# Task 1 — Full Recovery Runbook

If this laptop is lost, wiped, or replaced, this document alone rebuilds
Task 1 from a bare Ubuntu 22.04 install to a fully working system. Run
every command in order, top to bottom.

Assumes: Ubuntu 22.04, a working internet connection, and this repo
already cloned from GitHub (see the last section for the clone command).

---

## 1. Install ROS2 Humble

```bash
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8

sudo apt install software-properties-common
sudo add-apt-repository universe

sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
| sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt upgrade
sudo apt install ros-humble-desktop

echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

**Verify:** open a new terminal, run `ros2 topic list` — should run with no
"command not found" error.

---

## 2. Install Docker

```bash
sudo apt remove docker docker-engine docker.io containerd runc
sudo apt update
sudo apt install ca-certificates curl gnupg -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

sudo usermod -aG docker $USER
```

**Log out and back in** (required for the group change), then verify:
```bash
docker run hello-world
```

---

## 3. Clone this repo and set up the workspace

```bash
mkdir -p ~/assignment1_ws
cd ~/assignment1_ws
git clone <YOUR_GITHUB_REPO_URL> src_temp
mv src_temp/* src_temp/.git .
rmdir src_temp
```

*(Replace `<YOUR_GITHUB_REPO_URL>` with the actual repo URL once pushed —
see Section 8. This unpacks the repo directly into `~/assignment1_ws/`
rather than nesting it in a subfolder.)*

---

## 4. Get the sjtu_drone simulator

```bash
cd ~/assignment1_ws/src
git clone https://github.com/NovoG93/sjtu_drone.git -b ros2
cd ~/assignment1_ws
rosdep update
rosdep install -r -y --from-paths src --ignore-src --rosdistro humble
colcon build --symlink-install --packages-select-regex sjtu*
source install/setup.bash
```

---

## 5. Install Python dependencies

`tf_transformations` (installed below) depends on `transforms3d`, which
uses the now-removed `np.float` alias — it only works with NumPy <1.24.
To avoid clashing with any newer NumPy your system or `~/.local` may end
up with, install this project's Python packages into an isolated venv
scoped to this workspace, rather than system/user-wide.

```bash
sudo apt install ros-humble-tf-transformations python3-venv portaudio19-dev

cd ~/assignment1_ws
python3 -m venv --system-site-packages voice_env
source voice_env/bin/activate
export PYTHONNOUSERSITE=1
pip install "numpy<1.24" PyQt5 vosk sounddevice
```

**Why `--system-site-packages` + `PYTHONNOUSERSITE=1` together:** the venv
needs to see system-installed `rclpy` and `tf_transformations` (hence
`--system-site-packages`), but that flag has the side effect of also
exposing `~/.local`, which can shadow the NumPy just installed above.
`PYTHONNOUSERSITE=1` blocks that shadowing for the current terminal.

**Verify:**
```bash
python3 -c "import numpy; print(numpy.__version__)"           # 1.23.x
python3 -c "import PyQt5; print('PyQt5 OK')"
python3 -c "import vosk; print('vosk OK')"
python3 -c "import sounddevice; print('sounddevice OK')"
python3 -c "from tf_transformations import euler_from_quaternion; print('tf_transformations OK')"
```

You will need to re-run `source voice_env/bin/activate` and
`export PYTHONNOUSERSITE=1` in any new terminal before running the node
(see Section 9).

---

## 6. Download the Vosk speech model

```bash
mkdir -p ~/assignment1_ws/src/drone_voice_control/models
cd ~/assignment1_ws/src/drone_voice_control/models
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 model
rm vosk-model-small-en-us-0.15.zip
```

---

## 7. Build the drone_voice_control package

```bash
cd ~/assignment1_ws
colcon build --packages-select drone_voice_control
source install/setup.bash
```

**Verify:**
```bash
ros2 pkg executables drone_voice_control
```
Expected: `drone_voice_control drone_voice_control`

**Note:** `colcon` writes the generated executable's shebang line using
the *system* Python (`/usr/bin/python3`), even if `voice_env` is active
during the build. This means `ros2 run drone_voice_control ...` will
always launch under system Python, not the venv — see Section 9 for the
correct way to launch it.

---

## 8. Disable Gazebo's online model database

Prevents a multi-minute startup stall caused by an unreachable network
call — not needed since only a local model is spawned.

```bash
echo 'export GAZEBO_MODEL_DATABASE_URI=""' >> ~/.bashrc
source ~/.bashrc
```

---

## 9. Run everything

**Terminal 1 — start the simulation:**
```bash
source /opt/ros/humble/setup.bash
source ~/assignment1_ws/install/setup.bash
ros2 launch sjtu_drone_bringup sjtu_drone_bringup.launch.py
```
Wait for: `"The drone plugin finished loading!"`

**Terminal 2 — run the node:**
```bash
source ~/assignment1_ws/voice_env/bin/activate
export PYTHONNOUSERSITE=1
source /opt/ros/humble/setup.bash
source ~/assignment1_ws/install/setup.bash
python3 ~/assignment1_ws/install/drone_voice_control/lib/drone_voice_control/drone_voice_control \
  --ros-args -p vosk_model_path:=/home/$USER/assignment1_ws/src/drone_voice_control/models/model
```
Invoked via `python3 <path>` rather than `ros2 run` so it actually uses
`voice_env`'s Python (see the note at the end of Section 7).

A PyQt5 "Drone Telemetry Dashboard" window should appear; the drone
should auto-takeoff after ~2 seconds. Manual mode buttons and voice
commands ("forward", "backward", "left", "right", "up", "down", "stop")
both control the drone.

---

## 10. (Optional) Run everything via Docker instead

```bash
cd ~/assignment1_ws
xhost +local:docker
docker compose build
docker compose up -d
docker ps    # confirm task1_drone shows "Up"
```

**Terminal 1 — Gazebo:**
```bash
docker exec -it task1_drone bash -c "source /opt/ros/humble/setup.bash && source /root/assignment1_ws/install/setup.bash && ros2 launch sjtu_drone_bringup sjtu_drone_bringup.launch.py"
```

**Terminal 2 (new window) — voice control node:**
```bash
docker exec -it task1_drone bash -c "source /opt/ros/humble/setup.bash && source /root/assignment1_ws/install/setup.bash && ros2 run drone_voice_control drone_voice_control --ros-args -p vosk_model_path:=/root/assignment1_ws/src/drone_voice_control/models/model"
```

Both source ROS explicitly rather than relying on `~/.bashrc`, because
`docker exec ... bash -c "..."` opens a non-interactive shell, which
does not read `~/.bashrc` even though the Dockerfile appends the
sourcing lines there — that only benefits an interactive `bash` opened
with no `-c` argument.

**Shut down:**
```bash
docker compose down
```

---

## 11. Known issues and fixes encountered during development

| Symptom | Cause | Fix |
|---|---|---|
| Gazebo window frozen, "not responding" | Stalled trying to reach `models.gazebosim.org` | `export GAZEBO_MODEL_DATABASE_URI=""` (Section 8) |
| `/simple_drone/cmd_vel` missing from `ros2 topic list` | Drone plugin failed to finish loading due to the above stall | Same fix — re-launch after disabling model database |
| teleop's `t`/`l` work but `w`/`a`/`s`/`d` do nothing | `linear_velocity` starts at 0.0; only `q`/`e` change it | Press `q` several times to raise speed before pressing movement keys |
| `pip3 install ... --break-system-packages` → "no such option" | Older pip version (22.0.2) doesn't support that flag | Just omit the flag: `pip3 install vosk sounddevice` |
| Docker `COPY drone_voice_control` fails, path not found | Package actually lives under `src/`, not workspace root | Use `COPY src/drone_voice_control ./drone_voice_control` |
| `AttributeError: module 'numpy' has no attribute 'float'` | System/`.local` NumPy ≥1.24 breaks `transforms3d` | Section 5's isolated `voice_env` venv, pinned to `numpy<1.24` |
| Same numpy error persists even with `voice_env` active | `ros2 run` uses the executable's shebang, which `colcon` always writes as system Python | Launch with `python3 <path-to-executable>` instead (Section 9) |
| `[ERROR] vosk/sounddevice not installed` despite installing them | Installed outside `voice_env` (e.g. into `~/.local`) | Confirm `echo $VIRTUAL_ENV` shows `voice_env` before `pip install` |
| Docker: `ros2: command not found` when running `docker exec -it task1_drone bash -lc "..."` | `bash -lc` runs a non-interactive shell, which does not read `~/.bashrc` where the ROS sourcing lines live | Source explicitly in the command itself (Section 10) |
| Docker: `pactl: command not found` | Image was built before `pulseaudio-utils`/`libasound2-plugins` were added to the Dockerfile | `docker compose down && docker compose build && docker compose up -d` to rebuild with the current Dockerfile |
| Docker: `pactl list short sources` → `Connection failure: Access denied` | PulseAudio authenticates by cookie file, separate from the socket's file permissions; the container connects as `root`, a different user than the cookie's owner on the host | Mount `~/.config/pulse/cookie` into the container and set `PULSE_COOKIE` (see `docker-compose.yml`) |
| Docker: GUI windows never appear | `xhost +local:docker` not run on the host before `docker compose up` | Run it once per host login session before starting the container |

---

## How this repo was originally pushed to GitHub

```bash
cd ~/assignment1_ws
git init
git add .
git commit -m "Task 1: voice-controlled quadrotor + telemetry dashboard"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```
