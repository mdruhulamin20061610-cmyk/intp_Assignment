# Base image: Ubuntu 22.04 with ROS2 Humble already installed.
# Using the official ROS2 image instead of installing ROS2 ourselves from
# scratch avoids repeating the whole apt-key/repo dance inside the container.
FROM osrf/ros:humble-desktop

# Avoid apt prompting for timezone/locale input during build (would hang
# the build with no way to answer, since Docker builds are non-interactive).
ENV DEBIAN_FRONTEND=noninteractive

# --- System dependencies ---
# python3-pyqt5      : the GUI toolkit for the telemetry dashboard
# portaudio19-dev     : required for `sounddevice` (mic access) to build/run
# ros-humble-tf-transformations : quaternion -> Euler conversion
# git                 : needed to clone sjtu_drone during the build
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pyqt5 \
    python3-pip \
    portaudio19-dev \
    ros-humble-tf-transformations \
    git \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies not available via apt ---
RUN pip3 install --no-cache-dir vosk sounddevice

# --- Build the workspace ---
WORKDIR /root/assignment1_ws/src

# Bring in your own package code (built on the host, copied in here)
COPY src/drone_voice_control ./drone_voice_control

# Clone sjtu_drone at build time so the image is self-contained --
# anyone running this container gets the exact same simulator, no
# separate manual clone step required on their machine.
RUN git clone https://github.com/NovoG93/sjtu_drone.git -b ros2

WORKDIR /root/assignment1_ws

# Install any missing system deps declared by the cloned packages'
# package.xml files (mirrors the rosdep step we ran manually earlier).
RUN . /opt/ros/humble/setup.sh && \
    rosdep update && \
    rosdep install -r -y --from-paths src --ignore-src --rosdistro humble || true

# Build everything in the workspace.
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

# --- Vosk speech model ---
# Downloaded at build time so it's baked into the image -- no need for
# whoever runs this container to fetch it separately.
RUN mkdir -p /root/assignment1_ws/src/drone_voice_control/models && \
    cd /root/assignment1_ws/src/drone_voice_control/models && \
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip && \
    unzip -q vosk-model-small-en-us-0.15.zip && \
    mv vosk-model-small-en-us-0.15 model && \
    rm vosk-model-small-en-us-0.15.zip

# Skip the online Gazebo model database (same fix we applied manually --
# baking it in here means every future run of this container is fast,
# not just the first one).
ENV GAZEBO_MODEL_DATABASE_URI=""

# Auto-source ROS2 + the workspace for every shell opened in the container,
# same purpose as adding it to ~/.bashrc on a normal machine.
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /root/assignment1_ws/install/setup.bash" >> /root/.bashrc

CMD ["bash"]
