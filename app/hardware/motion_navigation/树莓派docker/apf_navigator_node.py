#!/usr/bin/env python3
import math
import time
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Point, Twist


class ApfNavigatorNode(Node):

    def __init__(self):
        super().__init__('apf_navigator_node')

        # 1. 订阅激光雷达与视觉矢量
        self.sub_scan = self.create_subscription(
            LaserScan, '/scan', self.scan_callback, 10
        )
        self.sub_yolo = self.create_subscription(
            Point, '/yolo_target_vector', self.yolo_callback, 10
        )

        # 2. 发布底盘控制指令
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # ⚙️ 驻停与解困参数
        self.stop_target_dist = 0.30  # 盲区内物理安全停车距离 (0.30m)
        self.in_view_stop_dist = 0.40  # 视野内可见大目标（如水杯）的到达判定距离 (0.40m)
        self.stop_reset_dist = 0.35  # 距离 > 0.35m 且无目标时解除驻停
        self.reverse_trigger_dist = 0.21  # < 0.21m 触发紧急倒车解困
        self.reverse_release_dist = 0.45  # >= 0.45m 退出普通倒车
        self.max_reverse_duration = 2.0  # 普通倒车最长 2.0 秒
        self.forced_reverse_duration = 2.0  # 低矮卡死基础倒车时间 2.0 秒

        # ⚙️ 避障与速度参数
        self.avoid_trigger_dist = 0.55  # 巡航阶段 < 0.55m 触发墙壁/障碍规避
        self.avoid_clear_dist = 0.65  # > 0.65m 恢复巡航

        self.max_linear_vel = 0.12  # 追踪/巡航最高线速度 (m/s)
        self.explore_linear_vel = 0.10  # 探寻线速度 (m/s)
        self.reverse_linear_vel = -0.10  # 倒车线速度 (m/s)

        # ⚙️ 转向角速度参数
        self.max_rotate_angular_vel = 0.35  # 原地对齐/寻找角速度上限 (0.35 rad/s)
        self.max_angular_vel = 0.22  # 普通行驶转向角速度上限 (0.22 rad/s)
        self.scan_angular_vel = 0.18  # 扫视角速度 (0.18 rad/s)
        self.rebound_angular_vel = 0.20  # 旋转寻找角速度 (0.20 rad/s)

        # ⚙️ 绿线对齐与防误触确认参数
        self.heading_tolerance = math.radians(12.0)  # 对齐 YOLO 绿线范围 (±12°)
        self.lock_confirm_duration = 1.0  # 红点在绿线内稳定 1.0 秒正式锁定
        self.recent_track_duration = 3.5  # 锁定后视觉丢失的盲进记忆时间 (3.5s)
        self.target_hold_duration = 0.80  # 视觉帧抖动短时缓存
        self.rebound_timeout = 3.0  # 旋转寻找超时时间 (3.0s)

        # ⚙️ 分离式卡死检测参数
        self.stuck_check_start_time = 0.0
        self.last_stuck_front_dist = 0.0
        self.last_stuck_target_angle = 0.0
        self.forward_stuck_threshold = 2.0  # 直行卡死时间门限 (2.0s)
        self.rotation_stuck_threshold = 2.5  # 旋转卡死时间门限 (2.5s)
        self.is_forced_reversing = False
        self.stuck_count = 0
        self.last_stuck_time = 0.0
        self.post_reverse_turn_duration = 1.8

        # 💡 倒车中后方受阻卡死检测变量
        self.reverse_stuck_check_start = 0.0
        self.last_reverse_rear_dist = 0.0
        self.reverse_stuck_duration_threshold = 1.0
        self.is_forward_escaping = False
        self.forward_escape_start_time = 0.0
        self.forward_escape_turn_dir = 1.0

        # ⚙️ APF 势场增益
        self.k_att = 1.2
        self.k_rep = 1.0
        self.k_tangent = 1.5
        self.d_zero = 0.60

        self.target_found = False
        self.target_angle = 0.0
        self.target_bbox_dist = 1.5
        self.last_target_bbox_dist = 1.5
        self.last_target_time = 0.0
        self.last_target_angle = 0.0
        self.vision_obstacle_near = False

        # 🎯 目标锁定与旋转寻找控制变量
        self.target_seen_start_time = 0.0
        self.is_target_locked = False
        self.is_rebound_searching = False
        self.rebound_start_time = 0.0
        self.rebound_dir = 1.0

        # 状态机变量
        self.is_reversing = False
        self.reverse_start_time = 0.0
        self.post_reverse_turn = False
        self.post_reverse_turn_start = 0.0

        self.is_arrived = False
        self.is_dynamic_avoiding = False
        self.avoid_turn_dir = 1.0
        self.avoid_start_dist = 0.0
        self.avoid_start_time = 0.0

        self.in_search_mode = False
        self.search_phase = 'SCAN'
        self.search_phase_start_time = 0.0

        # 控制平滑滤波
        self.prev_angular_z = 0.0
        self.prev_linear_x = 0.0
        self.alpha_angular = 0.70

        self.get_logger().info(
            '🚀 APF 导航节点升级：修复盲区到达未校验偏航角的漏洞，防止歪头面对非目标物时误判停车！'
        )

    def yolo_callback(self, msg: Point):
        """接收 YOLO 视觉节点坐标与连续时间判定"""
        current_time = time.time()

        if msg.z > 0.5:
            if self.is_rebound_searching:
                self.is_rebound_searching = False
                self.get_logger().info('🎯 [重新捕获] 旋转寻找成功！切入原地精准对齐。')

            self.target_angle = msg.x
            self.target_bbox_dist = msg.y
            self.last_target_bbox_dist = msg.y
            self.target_found = True
            self.last_target_time = current_time
            self.last_target_angle = msg.x
            self.vision_obstacle_near = msg.y < 0.45

            if abs(msg.x) <= self.heading_tolerance:
                if self.target_seen_start_time == 0.0:
                    self.target_seen_start_time = current_time

                seen_duration = current_time - self.target_seen_start_time
                if seen_duration >= self.lock_confirm_duration and not self.is_target_locked:
                    self.is_target_locked = True
                    self.get_logger().info(
                        f'🔒 [目标成功对齐并锁定] 红点稳定处于绿线内 {seen_duration:.1f}s，开始直线冲刺！'
                    )
            else:
                self.target_seen_start_time = 0.0
                self.is_target_locked = False
        else:
            self.target_found = False

            # 近距离因垂直盲区丢失时，绝对不准原地转圈寻找
            is_close_blind_spot = (
                self.is_target_locked and self.last_target_bbox_dist <= 0.60
            )

            has_recent_target = (self.last_target_time > 0.0) and ((current_time - self.last_target_time) < 3.5)

            if (
                self.is_target_locked or self.target_seen_start_time > 0.0 or has_recent_target
            ) and not self.is_rebound_searching and not is_close_blind_spot:
                self.is_rebound_searching = True
                self.rebound_start_time = current_time
                self.rebound_dir = 1.0 if self.last_target_angle >= 0 else -1.0
                self.get_logger().warn(
                    f'🔄 [目标丢失] 启动定向旋转寻找 (方向: {"左转" if self.rebound_dir > 0 else "右转"})，限时 {self.rebound_timeout}s...'
                )

            self.target_seen_start_time = 0.0
            self.is_target_locked = False

            if abs(msg.x) > 0.01:
                self.last_target_angle = msg.x
            self.vision_obstacle_near = msg.y < 0.45

    def scan_callback(self, msg: LaserScan):
        twist = Twist()
        current_time = time.time()

        if self.stuck_count > 0 and (current_time - self.last_stuck_time) > 10.0:
            self.stuck_count = 0
            self.get_logger().info('🧹 [状态重置] 远离死锁区域，连续卡死计数器已清零。')

        is_target_active = self.target_found or (
            (current_time - self.last_target_time) < self.target_hold_duration
        )

        recently_tracked = self.is_target_locked and (
            (current_time - self.last_target_time) < self.recent_track_duration
        )

        angle_min = msg.angle_min
        angle_increment = msg.angle_increment

        min_front_dist = 999.0
        min_left_dist = 999.0
        min_right_dist = 999.0
        min_rear_dist = 999.0

        for i, r in enumerate(msg.ranges):
            if math.isinf(r) or math.isnan(r) or r <= 0.01:
                continue

            angle = math.atan2(
                math.sin(angle_min + i * angle_increment),
                math.cos(angle_min + i * angle_increment),
            )

            if abs(angle) < math.radians(15.0):
                if r < min_front_dist:
                    min_front_dist = r
            elif math.radians(15.0) <= angle < math.radians(60.0):
                if r < min_left_dist:
                    min_left_dist = r
            elif -math.radians(60.0) < angle <= -math.radians(15.0):
                if r < min_right_dist:
                    min_right_dist = r
            elif abs(angle) > math.radians(135.0):
                if r < min_rear_dist:
                    min_rear_dist = r

        # ---------------- 0. 优先检测：紧急倒车触发（最高优先级）----------------
        if (
            min_front_dist < self.reverse_trigger_dist
            and not self.is_reversing
            and not self.is_forward_escaping
        ):
            if self.is_arrived:
                self.get_logger().warn(
                    f'🚨 [打破假到达] 检测到前方极近障碍物 ({min_front_dist:.3f}m < 0.21m)，取消驻停，立即触发紧急倒车避障！'
                )
                self.is_arrived = False

            self.is_reversing = True
            self.is_forced_reversing = False
            self.reverse_start_time = current_time
            self.reverse_stuck_check_start = current_time
            self.last_reverse_rear_dist = min_rear_dist
            self.get_logger().warn(
                f'🚨 距离过近 ({min_front_dist:.3f}m < 0.21m)！触发紧急倒车...'
            )

        # ---------------- 💡 核心对照：利用“视觉-雷达差值映射”识别中途垃圾桶遮挡 ----------------
        is_path_clear = True
        if self.target_found:
            if self.target_bbox_dist > 0.60:
                distance_gap = self.target_bbox_dist - min_front_dist
                if distance_gap > 0.45:
                    is_path_clear = False
        else:
            if self.last_target_bbox_dist > 0.60:
                distance_gap = self.last_target_bbox_dist - min_front_dist
                if distance_gap > 0.45:
                    is_path_clear = False

        # ---------------- 1. 前进 & 原地旋转分立卡死检测 ----------------
        is_turning = abs(self.prev_angular_z) > 0.08 and abs(self.prev_linear_x) < 0.03
        is_moving = abs(self.prev_linear_x) > 0.03

        is_in_final_approach = self.is_target_locked and (min_front_dist < 0.60) and is_path_clear

        if (is_turning or is_moving) and not self.is_arrived and not self.is_reversing and not self.is_forward_escaping and not is_in_final_approach:
            if self.stuck_check_start_time == 0.0:
                self.stuck_check_start_time = current_time
                self.last_stuck_front_dist = min_front_dist
                self.last_stuck_target_angle = self.target_angle
            else:
                stuck_elapsed = current_time - self.stuck_check_start_time
                dist_diff = abs(min_front_dist - self.last_stuck_front_dist)
                angle_diff = math.degrees(abs(self.target_angle - self.last_stuck_target_angle))

                is_forward_stuck = is_moving and (stuck_elapsed >= self.forward_stuck_threshold) and (dist_diff < 0.02)
                is_rotation_stuck = is_turning and (stuck_elapsed >= self.rotation_stuck_threshold) and (angle_diff < 1.0) and (dist_diff < 0.02)

                if is_forward_stuck or is_rotation_stuck:
                    self.stuck_count += 1
                    self.last_stuck_time = current_time
                    stuck_type = "原地旋转受阻" if is_rotation_stuck else "直行打滑卡死"
                    self.get_logger().error(
                        f'🚨 [卡死判定] 检测到【{stuck_type}】(持续 {stuck_elapsed:.1f}s)！第 {self.stuck_count} 次触发倒车规避程序...'
                    )

                    if self.is_rebound_searching or (is_target_active and abs(self.target_angle) > self.heading_tolerance):
                        self.get_logger().warn('🔀 [状态切换] 原地旋转卡死！退出旋转状态，强行切换至【避障倒车与循迹模式】！')

                    self.is_rebound_searching = False
                    self.is_reversing = True
                    self.is_forced_reversing = True
                    self.reverse_start_time = current_time
                    self.stuck_check_start_time = 0.0
                elif dist_diff >= 0.02 or angle_diff >= 1.0:
                    self.stuck_check_start_time = current_time
                    self.last_stuck_front_dist = min_front_dist
                    self.last_stuck_target_angle = self.target_angle
        else:
            self.stuck_check_start_time = 0.0

        # ---------------- 2. 驻停判定（严格加固：防止歪头面对非目标物误判停车）----------------
        is_visually_close = self.target_bbox_dist <= 0.45

        # 🎯 条件 A：目标在视野内可见（大目标，如水杯，0.40m 停车）
        target_in_view_arrival = (
            self.is_target_locked
            and is_target_active
            and self.target_found
            and min_front_dist <= self.in_view_stop_dist  # 0.40m
            and is_path_clear
        )

        # 🎯 条件 B：目标因过近进入垂直盲区消失（小目标/盲进，0.30m 停车）
        # 💡 核心加固：必须确保最后一次记录的目标偏航角严格在 ±15 度正前方以内，绝不允许歪头盲进停车！
        is_last_heading_straight = abs(self.last_target_angle) <= math.radians(15.0)

        blind_close_arrival = (
            self.is_target_locked
            and recently_tracked
            and not self.target_found
            and min_front_dist <= self.stop_target_dist  # 0.30m
            and self.last_target_bbox_dist <= 0.60
            and is_last_heading_straight  # 💡 增加偏航防错校验
            and is_path_clear
        )

        if (target_in_view_arrival or blind_close_arrival) and min_front_dist >= self.reverse_trigger_dist:
            self.is_arrived = True

        if self.is_arrived:
            if min_front_dist > self.stop_reset_dist and not is_target_active:
                self.is_arrived = False
                self.is_target_locked = False
                self.target_seen_start_time = 0.0
                self.in_search_mode = False
                self.get_logger().info(
                    f'🔄 目标已移除 (前距: {min_front_dist:.2f}m > {self.stop_reset_dist}m)，解除驻停！'
                )
            else:
                self.is_arrived = True
                self.in_search_mode = False
                self.is_dynamic_avoiding = False
                twist.linear.x = 0.0
                twist.angular.z = 0.0
                self.prev_linear_x = 0.0
                self.prev_angular_z = 0.0
                self.cmd_pub.publish(twist)
                self.get_logger().info(
                    f'🛑 [精确驻停] 目标抵达！雷达测距: {min_front_dist:.2f}m | 已停止前行！',
                    throttle_duration_sec=1.0,
                )
                return

        # ---------------- 3. 倒车解困与后退受阻逻辑 ----------------
        if self.is_reversing:
            current_reverse_elapsed = current_time - self.reverse_stuck_check_start
            rear_dist_diff = abs(min_rear_dist - self.last_reverse_rear_dist)

            is_rear_blocked = (current_reverse_elapsed >= self.reverse_stuck_duration_threshold) and (rear_dist_diff < 0.02)

            if is_rear_blocked:
                self.get_logger().warn(
                    f'🚨 [倒车动作卡死] 电机后退但雷达后方无变化！转为【向前突围逃逸】！'
                )
                self.is_reversing = False
                self.prev_linear_x = 0.0
                self.is_forward_escaping = True
                self.forward_escape_start_time = current_time
                self.forward_escape_turn_dir = 1.0 if min_left_dist >= min_right_dist else -1.0
            else:
                if current_reverse_elapsed >= 0.5:
                    self.reverse_stuck_check_start = current_time
                    self.last_reverse_rear_dist = min_rear_dist

                reverse_elapsed = current_time - self.reverse_start_time
                target_reverse_duration = 2.8 if self.stuck_count >= 3 else self.forced_reverse_duration

                should_release = (
                    reverse_elapsed >= target_reverse_duration
                    if self.is_forced_reversing
                    else (min_front_dist >= self.reverse_release_dist or reverse_elapsed >= self.max_reverse_duration)
                )

                if should_release:
                    self.is_reversing = False
                    self.is_forced_reversing = False
                    self.prev_linear_x = 0.0
                    self.post_reverse_turn = True
                    self.post_reverse_turn_start = current_time

                    self.is_target_locked = False
                    self.target_seen_start_time = 0.0
                    self.last_target_time = 0.0

                    spatial_best_dir = 1.0 if min_left_dist >= min_right_dist else -1.0
                    self.avoid_turn_dir = spatial_best_dir
                    self.post_reverse_turn_duration = 1.8
                    self.get_logger().info(
                        f'✅ 避障倒车完成！向{"左" if self.avoid_turn_dir > 0 else "右"}旋转规避盲区...'
                    )

        # ---------------- 4. 核心运动控制状态机 ----------------
        raw_v = 0.0
        raw_w = 0.0

        # 🔴 状态 A：紧急倒车
        if self.is_reversing:
            self.in_search_mode = False
            self.is_dynamic_avoiding = False
            raw_v = self.reverse_linear_vel
            raw_w = 0.10 if min_left_dist >= min_right_dist else -1.0 * 0.10

        # 🚀 状态 A1：倒车时后方受阻，向前突围
        elif self.is_forward_escaping:
            self.in_search_mode = False
            self.is_dynamic_avoiding = False
            escape_elapsed = current_time - self.forward_escape_start_time
            raw_v = 0.10
            raw_w = self.forward_escape_turn_dir * self.max_rotate_angular_vel
            if escape_elapsed >= 1.5 or min_front_dist > 0.6:
                self.is_forward_escaping = False

        # 🟠 状态 A2：倒车出困后强转规避
        elif self.post_reverse_turn:
            self.in_search_mode = False
            self.is_dynamic_avoiding = False
            raw_v = 0.0
            raw_w = self.avoid_turn_dir * self.max_rotate_angular_vel
            if (current_time - self.post_reverse_turn_start) > self.post_reverse_turn_duration:
                self.post_reverse_turn = False

        # 🟡 状态 B：目标在画面中（根据视觉偏差精确对齐或中途避障绕行）
        elif is_target_active and self.target_found:
            self.in_search_mode = False
            self.is_rebound_searching = False

            if not is_path_clear and min_front_dist < 0.85:
                if not self.is_dynamic_avoiding:
                    self.is_dynamic_avoiding = True
                    self.avoid_turn_dir = 1.0 if min_left_dist >= min_right_dist else -1.0
                    self.get_logger().warn(
                        f'🚧 [中途障碍拦截] 发现垃圾桶等中间阻碍！启动动态绕行（选择向{"左" if self.avoid_turn_dir > 0 else "右"}绕开）...'
                    )

            if min_front_dist > self.avoid_clear_dist:
                self.is_dynamic_avoiding = False

            if self.is_dynamic_avoiding:
                raw_v = 0.04
                raw_w = self.avoid_turn_dir * self.max_rotate_angular_vel
            else:
                target_deg = math.degrees(self.target_angle)
                is_aligned_in_green_lines = abs(self.target_angle) <= self.heading_tolerance

                # 💡 优化：当距离目标很近（< 0.6m）时，主动降低旋转角速度上限，防止因为 YOLO 延迟导致过冲
                current_max_rot_vel = 0.20 if min_front_dist < 0.6 else self.max_rotate_angular_vel

                if not is_aligned_in_green_lines:
                    raw_v = 0.0
                    self.prev_linear_x = 0.0
                    raw_w = float(
                        np.clip(
                            1.5 * self.target_angle,
                            -current_max_rot_vel,
                            current_max_rot_vel,
                        )
                    )
                    self.get_logger().info(
                        f'🎯 [原地精准旋转] 偏航: {target_deg:.1f}°，拉入绿线内...',
                        throttle_duration_sec=0.5,
                    )
                else:
                    raw_v = self.max_linear_vel
                    raw_w = float(
                        np.clip(
                            0.15 * self.target_angle,
                            -0.08,
                            0.08,
                        )
                    )
                    self.get_logger().info(
                        f'🟢 [绿线内直行] 偏航: {target_deg:.1f}° | 正对目标中心前进 (前距: {min_front_dist:.2f}m)...',
                        throttle_duration_sec=0.8,
                    )

        # 🟣 状态 C：丢失目标后的旋转寻找
        elif self.is_rebound_searching:
            rebound_elapsed = current_time - self.rebound_start_time

            if rebound_elapsed > self.rebound_timeout:
                self.is_rebound_searching = False
                self.target_seen_start_time = 0.0

                was_close_to_target = (self.last_target_bbox_dist < 0.9)

                if was_close_to_target:
                    self.in_search_mode = False
                    raw_v = 0.0
                    self.prev_linear_x = 0.0
                    raw_w = self.rebound_dir * self.scan_angular_vel
                    self.get_logger().warn('⚠️ [近距离目标搜寻超时] 目标就在附近！继续原地轻柔寻找，拒绝切换至巡航避障！')
                else:
                    self.in_search_mode = True
                    self.search_phase = 'EXPLORE'
                    self.search_phase_start_time = current_time
                    self.get_logger().warn('🔀 [状态切换] 旋转寻找超时，切换至巡航模式 (EXPLORE)！')
            else:
                raw_v = 0.0
                self.prev_linear_x = 0.0
                raw_w = self.rebound_dir * self.rebound_angular_vel
                self.get_logger().info(
                    f'↺ [旋转寻找中] 正在旋转找目标 ({rebound_elapsed:.1f}s/{self.rebound_timeout}s)...',
                    throttle_duration_sec=0.4,
                )

        # 🟣 状态 D：已锁定且贴近目标时的垂直盲区盲进冲刺停靠
        elif recently_tracked:
            self.in_search_mode = False
            self.is_dynamic_avoiding = False

            time_since_lost = current_time - self.last_target_time

            if is_path_clear and ((min_front_dist <= self.stop_target_dist and is_last_heading_straight) or (self.last_target_bbox_dist <= 0.60 and time_since_lost >= 1.0 and is_last_heading_straight)):
                self.is_arrived = True
                self.get_logger().info(
                    f'🛑 [安全盲进到达] 垂直盲区内无遮挡且正对，雷达前距 {min_front_dist:.2f}m，确认到达停靠！'
                )
            else:
                if not is_path_clear:
                    self.get_logger().warn(
                        f'⚠️ [冲刺受阻] 盲进前方检测到突发障碍，暂停盲进...',
                        throttle_duration_sec=0.5,
                    )
                    raw_v = 0.0
                    raw_w = 0.0
                else:
                    raw_v = 0.10  # 保持平稳前冲线速度
                    raw_w = 0.0   # 保持直行
                    self.get_logger().warn(
                        f'🙈 [最后冲刺·盲进中] 目标进入垂直盲区 | 前距: {min_front_dist:.2f}m...',
                        throttle_duration_sec=0.6,
                    )

        # 🔵 状态 E：原循迹巡航模式 (SEARCH / EXPLORE)
        else:
            if not self.in_search_mode:
                self.in_search_mode = True
                self.search_phase = 'SCAN'
                self.search_phase_start_time = current_time
                self.current_explore_duration = 8.0

            phase_elapsed = current_time - self.search_phase_start_time

            if self.search_phase == 'SCAN':
                if min_front_dist < 0.35:
                    raw_v = 0.02
                    raw_w = 0.18 if min_left_dist > min_right_dist else -0.18
                else:
                    raw_v = 0.0
                    search_dir = 1.0 if self.last_target_angle >= 0 else -1.0
                    raw_w = search_dir * self.scan_angular_vel

                if phase_elapsed >= 2.0:
                    self.search_phase = 'EXPLORE'
                    self.search_phase_start_time = current_time

            elif self.search_phase == 'EXPLORE':
                should_avoid = (
                    min_front_dist < self.avoid_trigger_dist
                ) or self.vision_obstacle_near

                if should_avoid and not self.is_dynamic_avoiding:
                    self.is_dynamic_avoiding = True
                    self.avoid_start_dist = min_front_dist
                    self.avoid_start_time = current_time
                    self.avoid_turn_dir = (
                        1.0 if min_left_dist >= min_right_dist else -1.0
                    )
                    self.get_logger().warn(
                        f'🚧 [巡航障碍规避] 触发避障！雷达前距: {min_front_dist:.2f}m | 视觉近距标志: {self.vision_obstacle_near} | 向{"左" if self.avoid_turn_dir > 0 else "右"}绕行...'
                    )

                elif min_front_dist > self.avoid_clear_dist:
                    self.is_dynamic_avoiding = False

                if self.is_dynamic_avoiding:
                    raw_v = 0.03
                    raw_w = self.avoid_turn_dir * self.max_rotate_angular_vel
                else:
                    raw_v = self.explore_linear_vel
                    wall_diff = min_left_dist - min_right_dist
                    raw_w = float(np.clip(0.25 * wall_diff, -0.12, 0.12))

                if phase_elapsed >= self.current_explore_duration:
                    self.search_phase = 'SCAN'
                    self.search_phase_start_time = current_time
                    self.is_dynamic_avoiding = False

        # ---------------- 5. 动力平滑输出 ----------------
        is_aligning = is_target_active and self.target_found and (abs(self.target_angle) > self.heading_tolerance)
        current_alpha = 0.90 if is_aligning else self.alpha_angular

        twist.angular.z = (
            current_alpha * raw_w
            + (1.0 - current_alpha) * self.prev_angular_z
        )
        twist.linear.x = 0.5 * raw_v + 0.5 * self.prev_linear_x

        self.prev_angular_z = twist.angular.z
        self.prev_linear_x = twist.linear.x

        self.cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = ApfNavigatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()