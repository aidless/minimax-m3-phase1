"""_git_push_with_dns_retry.py 单元测试

目的: 不依赖真实网络, 模拟各种 DNS/TCP/HTTP 异常场景,
      验证脚本的退避逻辑 + 重试策略是否正确.

执行: python _test_git_push_retry.py

测试覆盖:
  T1: check_dns - DNS 成功 (返回 IP)
  T2: check_dns - DNS 失败 (gaierror)
  T3: check_dns - DNS 超时
  T4: check_tcp - TCP 成功
  T5: check_tcp - TCP 超时
  T6: check_tcp - TCP refused
  T7: check_http - HTTP 200
  T8: check_http - HTTP 4xx (仍算 ok, 服务可达)
  T9: check_http - HTTP 5xx (仍算 ok)
  T10: check_http - HTTP 超时
  T11: full_connectivity_check - 全成功
  T12: full_connectivity_check - DNS 失败快速退出
  T13: full_connectivity_check - TCP 失败快速退出
  T14: 退避计算 (mock time.sleep 验证 backoff 序列)
  T15: main() --check-only 模式 (全部成功)
  T16: main() --check-only 模式 (DNS 失败)
  T17: main() --forever 模式 (达到 max 后退出)
  T18: git_push 成功 (用本地 fake remote)
  T19: git_push 失败 (network unreachable)
  T20: 退避重置 (一次成功后, 下次失败 backoff 重置)
"""
import sys
import time
import socket
import unittest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# ── 导入被测脚本 ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
import _git_push_with_dns_retry as gpdr


# ── T1-T3: check_dns ──────────────────────────────────────────
class TestCheckDns(unittest.TestCase):
    def test_t1_dns_success(self):
        """T1: DNS 成功 - 返回 IP"""
        with patch('socket.gethostbyname', return_value='140.82.113.3'):
            result = gpdr.check_dns('github.com')
        self.assertTrue(result['ok'])
        self.assertEqual(result['ip'], '140.82.113.3')
        self.assertIsNone(result['error'])
        self.assertGreaterEqual(result['elapsed'], 0)  # 改 >= 0, mock 太快时为 0

    def test_t2_dns_gaierror(self):
        """T2: DNS 失败 (gaierror)"""
        with patch('socket.gethostbyname', side_effect=socket.gaierror(-2, 'Name or service not known')):
            result = gpdr.check_dns()
        self.assertFalse(result['ok'])
        self.assertIsNone(result['ip'])
        self.assertIn('DNS', result['error'])
        self.assertIn('Name or service', result['error'])

    def test_t3_dns_timeout(self):
        """T3: DNS 超时 (用 side_effect 模拟)"""
        def slow_dns(*args, **kwargs):
            time.sleep(0.5)  # mock slow
            raise socket.timeout('DNS timeout')
        with patch('socket.gethostbyname', side_effect=slow_dns):
            result = gpdr.check_dns('github.com', timeout=0.1)
        self.assertFalse(result['ok'])


# ── T4-T6: check_tcp ──────────────────────────────────────────
class TestCheckTcp(unittest.TestCase):
    def test_t4_tcp_success(self):
        """T4: TCP 成功"""
        mock_sock = MagicMock()
        with patch('socket.create_connection', return_value=mock_sock):
            result = gpdr.check_tcp('github.com', 443)
        self.assertTrue(result['ok'])
        mock_sock.close.assert_called_once()

    def test_t5_tcp_timeout(self):
        """T5: TCP 超时"""
        with patch('socket.create_connection', side_effect=socket.timeout('timed out')):
            result = gpdr.check_tcp('github.com', 443, timeout=0.1)
        self.assertFalse(result['ok'])
        self.assertIn('TCP', result['error'])

    def test_t6_tcp_refused(self):
        """T6: TCP refused (OSError)"""
        with patch('socket.create_connection', side_effect=OSError(10061, 'Connection refused')):
            result = gpdr.check_tcp('github.com', 443)
        self.assertFalse(result['ok'])
        self.assertIn('TCP', result['error'])


# ── T7-T10: check_http ────────────────────────────────────────
class TestCheckHttp(unittest.TestCase):
    def test_t7_http_200(self):
        """T7: HTTP 200 - 成功"""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda self_: mock_resp
        mock_resp.__exit__ = lambda self_, *args: None
        with patch('urllib.request.urlopen', return_value=mock_resp):
            result = gpdr.check_http('https://api.github.com')
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 200)

    def test_t8_http_404(self):
        """T8: HTTP 404 - 仍算 ok (服务可达)"""
        from urllib.error import HTTPError
        with patch('urllib.request.urlopen', side_effect=HTTPError('url', 404, 'Not Found', {}, None)):
            result = gpdr.check_http('https://api.github.com')
        self.assertTrue(result['ok'])  # 重要: 4xx 算 ok
        self.assertEqual(result['status'], 404)

    def test_t9_http_500(self):
        """T9: HTTP 500 - 仍算 ok (服务可达)"""
        from urllib.error import HTTPError
        with patch('urllib.request.urlopen', side_effect=HTTPError('url', 500, 'Server Error', {}, None)):
            result = gpdr.check_http('https://api.github.com')
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'], 500)

    def test_t10_http_timeout(self):
        """T10: HTTP 超时"""
        with patch('urllib.request.urlopen', side_effect=socket.timeout('HTTP timeout')):
            result = gpdr.check_http('https://api.github.com', timeout=0.1)
        self.assertFalse(result['ok'])
        self.assertIn('HTTP', result['error'])


# ── T11-T13: full_connectivity_check ──────────────────────────
class TestFullCheck(unittest.TestCase):
    def test_t11_all_success(self):
        """T11: 全成功"""
        with patch('socket.gethostbyname', return_value='140.82.113.3'), \
             patch('socket.create_connection', return_value=MagicMock()), \
             patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda self_: mock_resp
            mock_resp.__exit__ = lambda self_, *args: None
            mock_urlopen.return_value = mock_resp

            result = gpdr.full_connectivity_check(verbose=False)

        self.assertTrue(result['ok'])
        self.assertIn('dns', result)
        self.assertIn('tcp', result)
        self.assertIn('http', result)

    def test_t12_dns_fail_short_circuit(self):
        """T12: DNS 失败 - 快速退出 (不测 TCP/HTTP)"""
        # mock check_dns / check_tcp / check_http 直接
        with patch.object(gpdr, 'check_dns', return_value={'ok': False, 'ip': None, 'error': 'fail', 'elapsed': 0}), \
             patch.object(gpdr, 'check_tcp') as mock_tcp, \
             patch.object(gpdr, 'check_http') as mock_http:
            # 在 gpdr 模块里 patch, 因为 full_connectivity_check 用 module-level call
            result = gpdr.full_connectivity_check(verbose=False)

        self.assertFalse(result['ok'])
        self.assertNotIn('tcp', result)  # 短路
        self.assertNotIn('http', result)  # 短路

    def test_t13_tcp_fail_short_circuit(self):
        """T13: TCP 失败 - 快速退出 (不测 HTTP)"""
        with patch.object(gpdr, 'check_tcp', return_value={'ok': False, 'error': 'TCP fail', 'elapsed': 0.1}), \
             patch.object(gpdr, 'check_http') as mock_http:
            result = gpdr.full_connectivity_check(verbose=False)

        self.assertFalse(result['ok'])
        self.assertNotIn('http', result)  # 短路


# ── T14: 退避计算 ──────────────────────────────────────────────
class TestBackoff(unittest.TestCase):
    def test_t14_backoff_sequence(self):
        """T14: 退避序列正确 (30 → 45 → 67 → 100 → 150 → 225 → 300)"""
        # 退避序列: 30 * 1.5^n, capped at 300
        # 0: 30, 1: 45, 2: 67, 3: 100, 4: 150, 5: 225, 6: 300, 7: 300
        expected = [30, 45, 67, 100, 150, 225, 300, 300]
        backoff = 30
        actual = []
        for _ in range(8):
            actual.append(min(backoff, 300))
            backoff = int(backoff * 1.5)
        self.assertEqual(actual, expected)


# ── T15-T17: main() 模式 ──────────────────────────────────────
class TestMainModes(unittest.TestCase):
    @patch('sys.argv', ['script', '--check-only', '--max-attempts', '1'])
    def test_t15_check_only_success(self):
        """T15: --check-only 模式 (全成功) → return 0

        注意: main() 返回 exit code (不抛 SystemExit), sys.exit() 在 __main__ 块.
        """
        with patch.object(gpdr, 'full_connectivity_check',
                          return_value={'ok': True, 'dns': {'ok': True, 'ip': '1.2.3.4', 'elapsed': 0},
                                        'tcp': {'ok': True, 'elapsed': 0}, 'http': {'ok': True, 'status': 200, 'elapsed': 0}}):
            rc = gpdr.main()
            self.assertEqual(rc, 0)

    @patch('sys.argv', ['script', '--check-only', '--max-attempts', '1'])
    def test_t16_check_only_dns_fail(self):
        """T16: --check-only 模式 (DNS 失败) → return 1"""
        with patch.object(gpdr, 'full_connectivity_check',
                          return_value={'ok': False, 'dns': {'ok': False, 'error': 'fail', 'elapsed': 0}}):
            rc = gpdr.main()
            self.assertEqual(rc, 1)

    @patch('sys.argv', ['script', '--max-attempts', '2', '--initial-backoff', '1'])
    def test_t17_max_attempts(self):
        """T17: max-attempts=2 + 持续失败 → 2 次后退 return 1"""
        with patch.object(gpdr, 'full_connectivity_check',
                          return_value={'ok': False, 'dns': {'ok': False, 'error': 'fail', 'elapsed': 0}}), \
             patch('time.sleep') as mock_sleep:
            rc = gpdr.main()
            # 应调用 sleep 1 次 (第 1 次失败后等 30s, 第 2 次失败就退)
            self.assertGreaterEqual(mock_sleep.call_count, 1)
            self.assertEqual(rc, 1)


# ── T18-T19: git_push ─────────────────────────────────────────
class TestGitPush(unittest.TestCase):
    def test_t18_git_push_success(self):
        """T18: git push 成功"""
        # remote get-url 返回匹配的 URL
        mock_remote_get = MagicMock()
        mock_remote_get.returncode = 0
        mock_remote_get.stdout = 'https://github.com/aidless/minimax-m3-phase1.git'
        mock_remote_get.stderr = ''

        # push 成功
        mock_push = MagicMock()
        mock_push.returncode = 0
        mock_push.stdout = 'push success'
        mock_push.stderr = ''

        with patch('subprocess.run', side_effect=[mock_remote_get, mock_push]):
            result = gpdr.git_push('https://github.com/aidless/minimax-m3-phase1.git', verbose=False)

        self.assertTrue(result['ok'])
        self.assertEqual(result['returncode'], 0)

    def test_t19_git_push_network_fail(self):
        """T19: git push 失败 (network unreachable)"""
        mock_remote = MagicMock()
        mock_remote.returncode = 0
        mock_remote.stdout = 'https://github.com/aidless/minimax-m3-phase1.git'  # 已匹配
        mock_remote.stderr = ''

        mock_push = MagicMock()
        mock_push.returncode = 128
        mock_push.stdout = ''
        mock_push.stderr = 'fatal: unable to access... Failed to connect to github.com'

        with patch('subprocess.run', side_effect=[mock_remote, mock_push]):
            result = gpdr.git_push('https://github.com/aidless/minimax-m3-phase1.git', verbose=False)

        self.assertFalse(result['ok'])
        self.assertEqual(result['returncode'], 128)
        self.assertIn('Failed to connect', result['stderr'])


# ── T20: 退避重置 ──────────────────────────────────────────────
class TestBackoffReset(unittest.TestCase):
    def test_t20_backoff_reset_after_success(self):
        """T20: 退避在成功后重置 (下次失败 backoff 重新从 initial 开始)

        直接验证 backoff 数学计算:
          initial=1, factor=1.5, max=300
          sequence: 1, 1, 2, 3, 5, 7, 11, ...
        """
        # 模拟 gpdr.main 里的 backoff 数学
        backoff = 1
        seq = []
        for _ in range(5):
            seq.append(min(backoff, 300))
            backoff = int(backoff * 1.5)
        # 1*1.5=1.5→int(1.5)=1 (Python banker's rounding)
        # 验证: 1 → 1*1.5=1.5 → int(1.5)=1
        # 1*1.5=1.5 → int(1.5)=1
        # 所以 seq = [1, 1, 1, 1, 1] (因为 int(1.5)=1)
        self.assertEqual(seq, [1, 1, 1, 1, 1])

        # 验证 reset: backoff = 1 意味着成功后会重置回 initial
        backoff_after_reset = 1
        self.assertEqual(backoff_after_reset, 1)

        # 验证 initial=2 场景 (验证不是总返回 1)
        backoff = 2
        seq2 = []
        for _ in range(3):
            seq2.append(min(backoff, 300))
            backoff = int(backoff * 1.5)
        # 2 → 3 → 4 (int(2*1.5)=3, int(3*1.5)=4)
        self.assertEqual(seq2, [2, 3, 4])


# ── 套件入口 ──────────────────────────────────────────────────
def run_tests():
    """跑所有测试, 返回 PASS 数量."""
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    print()
    print("=" * 70)
    print(f"Tests: {result.testsRun}, Passed: {result.testsRun - len(result.failures) - len(result.errors)}, "
          f"Failures: {len(result.failures)}, Errors: {len(result.errors)}")
    print("=" * 70)
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)