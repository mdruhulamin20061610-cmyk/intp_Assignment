#!/usr/bin/env python3
"""
Task 1 — Voice-Controlled Quadrotor & Telemetry Dashboard.

IMPORTANT: the drone topic namespace is NOT hardcoded. It's a ROS2
parameter, because sjtu_drone forks differ (some use /simple_drone/...,
others /drone/...). Confirm the real namespace with `ros2 topic list`
after launching sjtu_drone_bringup, THEN set it via:

    ros2 run drone_voice_control drone_voice_control --ros-args -p drone_ns:=drone

(replace 'drone' with whatever prefix your `ros2 topic list` actually shows,
e.g. if you see /simple_drone/cmd_vel, use -p drone_ns:=simple_drone)

Architecture (3 workers):
  Worker A = ROS2      -> rclpy.spin() in a background thread
  Worker B = Microphone -> its own thread, writes to a lock-protected mailbox
  Worker C = PyQt5 GUI  -> owns the MAIN thread, updated via Qt signals
"""

import sys
import json
import math
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty

from tf_transformations import euler_from_quaternion

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
)

try:
    import vosk
    import sounddevice as sd
except ImportError:
    vosk = None
    sd = None


class Bridge(QObject):
    position_updated = pyqtSignal(float, float, float)
    orientation_updated = pyqtSignal(float, float, float)
    velocity_updated = pyqtSignal(float, float, float)
    status_updated = pyqtSignal(str)


class DroneVoiceControlNode(Node):
    def __init__(self):
        super().__init__("drone_voice_control")

        # --- Parameters (no hardcoded topic names) ---
        self.declare_parameter("drone_ns", "simple_drone")
        self.declare_parameter("vosk_model_path", "model")
        self.declare_parameter("start_mode", "manual")

        ns = self.get_parameter("drone_ns").value
        self.model_path_ = self.get_parameter("vosk_model_path").value

        cmd_vel_topic = f"/{ns}/cmd_vel"
        takeoff_topic = f"/{ns}/takeoff"
        odom_topic = f"/{ns}/odom"

        self.get_logger().info(
            f"Using topics: {cmd_vel_topic}, {takeoff_topic}, {odom_topic}"
        )

        # --- Worker A: publishers, subscriber, timer ---
        self.pub_ = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.takeoff_pub_ = self.create_publisher(Empty, takeoff_topic, 10)
        self.sub_ = self.create_subscription(
            Odometry, odom_topic, self.odom_callback, 10
        )
        self.timer_ = self.create_timer(0.1, self.check_mailbox)

        # --- Shared state (mailbox + switch) ---
        self.lock_ = threading.Lock()
        self.pending_command_ = None
        self.mode_ = self.get_parameter("start_mode").value

        # --- Qt bridge ---
        self.bridge_ = Bridge()

        # --- Auto takeoff, once, a few seconds after startup ---
        self.took_off_ = False
        self.takeoff_timer_ = self.create_timer(2.0, self.do_takeoff_once)

        self.get_logger().info(f"drone_voice_control started (mode={self.mode_})")

    def do_takeoff_once(self):
        if self.took_off_:
            return
        self.takeoff_pub_.publish(Empty())
        self.took_off_ = True
        self.bridge_.status_updated.emit("Airborne")
        self.get_logger().info("Takeoff command sent")
        self.takeoff_timer_.cancel()

    def set_mode(self, mode):
        with self.lock_:
            self.mode_ = mode
        self.bridge_.status_updated.emit(f"Mode: {mode}")
        self.get_logger().info(f"Switched to {mode} mode")

    def manual_command(self, cmd):
        if self.mode_ != "manual":
            return
        self.send_twist(cmd)

    def check_mailbox(self):
        with self.lock_:
            cmd = self.pending_command_
            self.pending_command_ = None
        if self.mode_ == "voice" and cmd:
            self.send_twist(cmd)

    def send_twist(self, cmd):
        msg = Twist()
        if cmd == "forward":
            msg.linear.x = 1.0
        elif cmd == "backward":
            msg.linear.x = -1.0
        elif cmd == "left":
            msg.angular.z = 1.0
        elif cmd == "right":
            msg.angular.z = -1.0
        elif cmd == "up":
            msg.linear.z = 1.0
        elif cmd == "down":
            msg.linear.z = -1.0
        elif cmd == "stop":
            pass
        else:
            self.get_logger().warn(f"Unknown command: {cmd}")
            return
        self.pub_.publish(msg)
        self.bridge_.status_updated.emit(f"Cmd: {cmd}")

    def odom_callback(self, msg):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        v = msg.twist.twist.linear

        roll, pitch, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])

        self.bridge_.position_updated.emit(p.x, p.y, p.z)
        self.bridge_.orientation_updated.emit(
            math.degrees(roll), math.degrees(pitch), math.degrees(yaw)
        )
        self.bridge_.velocity_updated.emit(v.x, v.y, v.z)

    def audio_loop(self):
        if vosk is None:
            self.get_logger().error("vosk/sounddevice not installed — voice control disabled")
            return

        model = vosk.Model(self.model_path_)
        recognizer = vosk.KaldiRecognizer(model, 16000)

        def callback(indata, frames, time_info, status):
            if recognizer.AcceptWaveform(bytes(indata)):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if not text:
                    return
                cmd = self.parse_command(text)
                if cmd:
                    with self.lock_:
                        self.pending_command_ = cmd

        with sd.RawInputStream(
            samplerate=16000, blocksize=8000, dtype="int16",
            channels=1, callback=callback
        ):
            self.get_logger().info("Listening for voice commands...")
            threading.Event().wait()

    @staticmethod
    def parse_command(text):
        text = text.lower()
        mapping = {
            "forward": "forward", "go forward": "forward",
            "backward": "backward", "back": "backward",
            "left": "left", "turn left": "left",
            "right": "right", "turn right": "right",
            "up": "up", "go up": "up",
            "down": "down", "go down": "down",
            "stop": "stop", "halt": "stop",
        }
        for phrase, cmd in mapping.items():
            if phrase in text:
                return cmd
        return None


class TelemetryWindow(QWidget):
    def __init__(self, node: DroneVoiceControlNode):
        super().__init__()
        self.node_ = node
        self.setWindowTitle("Drone Telemetry Dashboard")

        self.pos_label_ = QLabel("Position:  x=0.00  y=0.00  z=0.00")
        self.ori_label_ = QLabel("Orientation:  roll=0.0  pitch=0.0  yaw=0.0")
        self.vel_label_ = QLabel("Velocity:  vx=0.00  vy=0.00  vz=0.00")
        self.status_label_ = QLabel("Status: starting up")

        voice_btn = QPushButton("Voice Mode")
        manual_btn = QPushButton("Manual Mode")
        voice_btn.clicked.connect(lambda: node.set_mode("voice"))
        manual_btn.clicked.connect(lambda: node.set_mode("manual"))
        mode_row = QHBoxLayout()
        mode_row.addWidget(voice_btn)
        mode_row.addWidget(manual_btn)

        move_row = QHBoxLayout()
        for label, cmd in [
            ("Forward", "forward"), ("Backward", "backward"),
            ("Left", "left"), ("Right", "right"),
            ("Up", "up"), ("Down", "down"), ("Stop", "stop"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _checked, c=cmd: node.manual_command(c))
            move_row.addWidget(btn)

        layout = QVBoxLayout()
        layout.addWidget(self.pos_label_)
        layout.addWidget(self.ori_label_)
        layout.addWidget(self.vel_label_)
        layout.addWidget(self.status_label_)
        layout.addLayout(mode_row)
        layout.addLayout(move_row)
        self.setLayout(layout)

        node.bridge_.position_updated.connect(self.update_position)
        node.bridge_.orientation_updated.connect(self.update_orientation)
        node.bridge_.velocity_updated.connect(self.update_velocity)
        node.bridge_.status_updated.connect(self.update_status)

    def update_position(self, x, y, z):
        self.pos_label_.setText(f"Position:  x={x:.2f}  y={y:.2f}  z={z:.2f}")

    def update_orientation(self, roll, pitch, yaw):
        self.ori_label_.setText(
            f"Orientation:  roll={roll:.1f}  pitch={pitch:.1f}  yaw={yaw:.1f}"
        )

    def update_velocity(self, vx, vy, vz):
        self.vel_label_.setText(f"Velocity:  vx={vx:.2f}  vy={vy:.2f}  vz={vz:.2f}")

    def update_status(self, text):
        self.status_label_.setText(f"Status: {text}")


def main(args=None):
    rclpy.init(args=args)
    node = DroneVoiceControlNode()

    ros_thread = threading.Thread(target=lambda: rclpy.spin(node), daemon=True)
    ros_thread.start()

    audio_thread = threading.Thread(target=node.audio_loop, daemon=True)
    audio_thread.start()

    app = QApplication(sys.argv)
    window = TelemetryWindow(node)
    window.show()
    exit_code = app.exec_()

    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
