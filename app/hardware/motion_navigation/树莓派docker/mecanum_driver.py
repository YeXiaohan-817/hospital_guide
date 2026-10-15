#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
import tf2_ros
from gpiozero import PWMOutputDevice, OutputDevice


class MecanumDriver(Node):

  def __init__(self):
    super().__init__('mecanum_driver')

    # 🎯 1. 物理引脚初始化
    self.PWMA = PWMOutputDevice(12)
    self.AIN1 = OutputDevice(5)
    self.AIN2 = OutputDevice(6)

    self.PWMB = PWMOutputDevice(13)
    self.BIN1 = OutputDevice(19)
    self.BIN2 = OutputDevice(18)

    self.PWMC = PWMOutputDevice(16)
    self.CIN1 = OutputDevice(11)
    self.CIN2 = OutputDevice(8)

    self.PWMD = PWMOutputDevice(20)
    self.DIN1 = OutputDevice(26)
    self.DIN2 = OutputDevice(21)

    # 🏎️ 2. 状态变量（用于速度积分算法）
    self.x = 0.0
    self.y = 0.0
    self.th = 0.0

    self.vx = 0.0
    self.vth = 0.0
    self.last_time = self.get_clock().now()

    # 📻 3. ROS 2 订阅者与发布者
    self.subscription = self.create_subscription(
        Twist, '/cmd_vel', self.cmd_vel_callback, 10
    )

    self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
    self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

    # 📐 4. 静态 TF 广播器
    self.static_tf_broadcaster = tf2_ros.StaticTransformBroadcaster(self)
    self.publish_camera_static_tf()

    # ⏱️ 5. 定时器 20Hz 更新里程计
    self.timer = self.create_timer(0.05, self.update_odometry)

    self.get_logger().info(
        '🚀 【矢量叠加修复版】底盘驱动已运行（支持线速度+角速度合成运动）！'
    )

  def publish_camera_static_tf(self):
    t = TransformStamped()
    t.header.stamp = self.get_clock().now().to_msg()
    t.header.frame_id = 'base_link'
    t.child_frame_id = 'camera_link'
    t.transform.translation.x = 0.1
    t.transform.translation.y = 0.0
    t.transform.translation.z = 0.2
    t.transform.rotation.w = 1.0
    self.static_tf_broadcaster.sendTransform(t)

  def set_single_motor(
      self, pwm_dev, in1_dev, in2_dev, speed_val, is_inverted=False
  ):
    """单电机底层控制（带死区过滤与极性映射）"""
    abs_speed = abs(speed_val)

    # 过滤微小漂移死区 (< 0.02 m/s 视为静止)
    if abs_speed < 0.02:
      pwm_dev.value = 0.0
      in1_dev.value = 0
      in2_dev.value = 0
      return

    # 防卡死限幅：起步最小 PWM 0.15，最大上限 0.80
    target_pwm = max(0.15, min(0.80, abs_speed))
    pwm_dev.value = target_pwm

    # 根据速度正负与硬件接线极性决定转向
    if (speed_val > 0 and not is_inverted) or (
        speed_val < 0 and is_inverted
    ):
      in1_dev.value = 1
      in2_dev.value = 0
    else:
      in1_dev.value = 0
      in2_dev.value = 1

  def cmd_vel_callback(self, msg):
    # 提取速度并加入死区过滤
    raw_vx = msg.linear.x if abs(msg.linear.x) > 0.02 else 0.0
    raw_vth = msg.angular.z if abs(msg.angular.z) > 0.02 else 0.0

    self.vx = raw_vx
    self.vth = raw_vth

    if self.vx == 0.0 and self.vth == 0.0:
      self.stop_all()
      return

    # 🏎️ 速度叠加运动学计算 (vx 与 vth 线性叠加)
    speed_a = self.vx - self.vth * 0.4
    speed_b = self.vx - self.vth * 0.4
    speed_c = self.vx + self.vth * 0.4
    speed_d = self.vx + self.vth * 0.4

    # 分别驱动 4 个电机 (B 和 C 电机极性相反，is_inverted=True)
    self.set_single_motor(
        self.PWMA, self.AIN1, self.AIN2, speed_a, is_inverted=False
    )
    self.set_single_motor(
        self.PWMB, self.BIN1, self.BIN2, speed_b, is_inverted=True
    )
    self.set_single_motor(
        self.PWMC, self.CIN1, self.CIN2, speed_c, is_inverted=True
    )
    self.set_single_motor(
        self.PWMD, self.DIN1, self.DIN2, speed_d, is_inverted=False
    )

  def stop_all(self):
    self.PWMA.value = 0.0
    self.AIN1.value = 0
    self.AIN2.value = 0
    self.PWMB.value = 0.0
    self.BIN1.value = 0
    self.BIN2.value = 0
    self.PWMC.value = 0.0
    self.CIN1.value = 0
    self.CIN2.value = 0
    self.PWMD.value = 0.0
    self.DIN1.value = 0
    self.DIN2.value = 0

  def update_odometry(self):
    current_time = self.get_clock().now()
    dt = (current_time - self.last_time).nanoseconds / 1e9
    self.last_time = current_time

    delta_x = (self.vx * math.cos(self.th)) * dt
    delta_y = (self.vx * math.sin(self.th)) * dt
    delta_th = self.vth * dt

    self.x += delta_x
    self.y += delta_y
    self.th += delta_th

    cy = math.cos(self.th * 0.5)
    sy = math.sin(self.th * 0.5)

    t = TransformStamped()
    t.header.stamp = current_time.to_msg()
    t.header.frame_id = 'odom'
    t.child_frame_id = 'base_link'
    t.transform.translation.x = self.x
    t.transform.translation.y = self.y
    t.transform.rotation.z = sy
    t.transform.rotation.w = cy
    self.tf_broadcaster.sendTransform(t)

    odom = Odometry()
    odom.header.stamp = current_time.to_msg()
    odom.header.frame_id = 'odom'
    odom.child_frame_id = 'base_link'
    odom.pose.pose.position.x = self.x
    odom.pose.pose.position.y = self.y
    odom.pose.pose.orientation.z = sy
    odom.pose.pose.orientation.w = cy
    odom.twist.twist.linear.x = self.vx
    odom.twist.twist.angular.z = self.vth
    self.odom_pub.publish(odom)


def main(args=None):
  rclpy.init(args=args)
  node = MecanumDriver()
  try:
    rclpy.spin(node)
  except KeyboardInterrupt:
    node.stop_all()
  finally:
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
  main()