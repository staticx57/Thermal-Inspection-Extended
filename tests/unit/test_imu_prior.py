"""IMU prior math + effect on tracking (synthetic scene with known motion)."""
import numpy as np
import pytest

from thermal_inspection.processing import imu_prior as ip


def _yaw(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


class TestMath:
    def test_rotvec_matches_known_rotation(self):
        R = ip.rotation_from_rotvec(np.array([0, np.radians(30), 0]))
        assert np.allclose(R, _yaw(30), atol=1e-9)
        assert np.allclose(ip.rotation_from_rotvec(np.zeros(3)), np.eye(3))

    def test_gyro_integration_constant_rate(self):
        rate = np.radians(60)                                    # 60 deg/s about y for 0.5 s -> 30 deg
        samples = [(i * 0.01, 0, rate, 0) for i in range(100)]
        R = ip.integrate_gyro(samples, 0.1, 0.6)
        assert np.allclose(R, _yaw(30), atol=1e-6)

    def test_gyro_integration_empty_or_reversed_window(self):
        assert np.allclose(ip.integrate_gyro([], 0, 1), np.eye(3))
        assert np.allclose(ip.integrate_gyro([(0, 0, 1, 0)], 1, 0.5), np.eye(3))

    def test_windows_compose_in_order(self):
        a, b = ip.ImuSample(_yaw(10), np.array([0, -9.8, 0])), ip.ImuSample(_yaw(20), None)
        c = a.then(b)
        assert np.allclose(c.delta_R, _yaw(30)) and np.allclose(c.gravity_cam, [0, -9.8, 0])   # keeps last reading

    def test_odometry_prior_is_inverse_of_camera_rotation(self):
        # camera turned by +20 deg yaw: a fixed point's camera-frame coordinates rotate by the inverse
        T = ip.rotation_prior_transform(_yaw(20))
        p = np.array([0.0, 0.0, 2.0])
        assert np.allclose(T[:3, :3] @ p, _yaw(-20) @ p)

    def test_gravity_check(self):
        up_cam = np.array([0.0, -9.81, 0.0])                      # upright camera: accel reads up along -y (y is down)
        g_world = ip.gravity_world_from_pose(np.eye(4), up_cam)
        assert ip.gravity_error_deg(np.eye(4), up_cam, g_world) == pytest.approx(0, abs=1e-6)
        tilted = np.eye(4)
        tilted[:3, :3] = np.array([[1, 0, 0], [0, np.cos(0.3), -np.sin(0.3)], [0, np.sin(0.3), np.cos(0.3)]])
        assert ip.gravity_error_deg(tilted, up_cam, g_world) == pytest.approx(np.degrees(0.3), abs=0.01)
        assert ip.gravity_error_deg(tilted, np.array([0, -20.0, 0]), g_world) == 0      # being shaken: no veto
        assert ip.gravity_error_deg(tilted, None, g_world) == 0 and ip.gravity_error_deg(tilted, up_cam, None) == 0


pytest.importorskip("open3d")
from tests.unit import mapping_synth as ms  # noqa: E402


def _imu_between(pose_a, pose_b):
    """Perfect gyro: the camera-frame rotation increment between two poses, plus a gravity reading that matches the
    synthetic world's up (-y of the world frame in these tests, expressed in the later camera)."""
    delta = pose_a[:3, :3].T @ pose_b[:3, :3]
    g_cam = pose_b[:3, :3].T @ np.array([0.0, -9.81, 0.0])
    return ip.ImuSample(delta, g_cam)


def _scan(trajectory, use_imu):
    from thermal_inspection.processing.world_mapper import WorldMapper
    wm = WorldMapper(voxel_size=0.02)
    wm.start_scan(ms.W, ms.H, ms.FX, ms.FY, ms.CX, ms.CY)
    errs = []
    for i, p in enumerate(trajectory):
        color, depth = ms.render(p, noise=0.002, seed=i)
        imu = _imu_between(trajectory[i - 1], p) if (use_imu and i > 0) else (
            ip.ImuSample(np.eye(3), _imu_between(p, p).gravity_cam) if use_imu else None)
        wm.track_and_texture(color, depth, imu=imu)
        errs.append(ms.pose_error(wm._pose, p))
    return wm, errs


FAST_PAN = [ms.pose(tx=0.04 * i, yaw_deg=9.0 * i) for i in range(6)]       # 9 deg per frame, a fast hand pan


class TestTrackingWithImu:
    def test_imu_never_hurts_a_gentle_scan(self):
        _, errs = _scan(ms.TRAJECTORY, use_imu=True)
        assert max(e[0] for e in errs) < 0.06 and max(e[1] for e in errs) < 2.0

    def test_imu_helps_a_fast_pan(self):
        _, without = _scan(FAST_PAN, use_imu=False)
        _, with_imu = _scan(FAST_PAN, use_imu=True)
        end_without, end_with = without[-1], with_imu[-1]
        # Without the gyro this pan silently ends ~14 deg off (odometry's capture range is exceeded and it settles on
        # a wrong answer without reporting lost); with a perfect gyro it tracks to well under a degree.
        assert end_without[1] > 5.0
        assert end_with[0] < 0.05 and end_with[1] < 1.0

    def test_gravity_veto_rejects_a_tilted_pose(self):
        wm, _ = _scan(ms.TRAJECTORY[:3], use_imu=True)
        before = wm._pose.copy()
        lost_before = wm._scan_lost_frames
        # a frame whose accelerometer says the camera is rolled 40 deg from where tracking believes it is
        color, depth = ms.render(ms.TRAJECTORY[3], noise=0.002, seed=9)
        roll = np.radians(40)
        Rz = np.array([[np.cos(roll), -np.sin(roll), 0], [np.sin(roll), np.cos(roll), 0], [0, 0, 1]])
        bad_gravity = Rz @ _imu_between(ms.TRAJECTORY[2], ms.TRAJECTORY[3]).gravity_cam
        wm.track_and_texture(color, depth, imu=ip.ImuSample(_imu_between(ms.TRAJECTORY[2], ms.TRAJECTORY[3]).delta_R,
                                                          bad_gravity))
        assert wm._scan_lost_frames == lost_before + 1          # vetoed, not integrated
        assert np.allclose(wm._pose, before)

    def test_submit_frame_merges_dropped_imu_windows(self):
        from thermal_inspection.processing.world_mapper import WorldMapper
        wm = WorldMapper()
        wm._worker = type("W", (), {"is_alive": lambda self: True})()      # pretend a busy worker: slot stays pending
        f = np.zeros((4, 4, 3), np.uint8)
        d = np.ones((4, 4), np.float32)
        wm.submit_frame(f, d, imu=ip.ImuSample(_yaw(10), None))
        wm.submit_frame(f, d, imu=ip.ImuSample(_yaw(20), None))
        assert np.allclose(wm._slot[4].delta_R, _yaw(30))
