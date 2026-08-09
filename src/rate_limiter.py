"""
API 限流保护
功能：限制单位时间内的请求次数，超限请求被拒绝（返回 429）
策略：滑动窗口 + 每 IP/客户端 限流
集成：FastAPI 中间件
"""

import time
import threading
from collections import defaultdict
from pathlib import Path

# 引入配置热加载
import sys
sys.path.insert(0, str(Path(__file__).parent))
from hot_config import HotConfig

CONFIG = HotConfig()


class RateLimiter:
    """API 限流器（滑动窗口）"""

    def __init__(self, max_requests=None, window_seconds=None):
        # 默认：每 60 秒最多 30 次请求
        self.max_requests = max_requests or int(CONFIG.get("rate_limit", "max_requests", 30))
        self.window_seconds = window_seconds or int(CONFIG.get("rate_limit", "window_seconds", 60))
        self._requests = defaultdict(list)  # key -> [timestamp, ...]
        self._lock = threading.Lock()

    def allow(self, key: str = "default") -> dict:
        """检查是否允许请求
        返回: {"allowed": bool, "remaining": int, "retry_after": int}
        """
        now = time.time()
        with self._lock:
            # 清理过期记录
            timestamps = self._requests[key]
            self._requests[key] = [t for t in timestamps if now - t < self.window_seconds]

            # 检查是否超限
            if len(self._requests[key]) >= self.max_requests:
                # 计算还需等待多久
                oldest = min(self._requests[key])
                retry_after = int(self.window_seconds - (now - oldest)) + 1
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after": retry_after,
                    "max_requests": self.max_requests,
                    "window_seconds": self.window_seconds,
                }

            # 记录本次请求
            self._requests[key].append(now)
            remaining = self.max_requests - len(self._requests[key])
            return {
                "allowed": True,
                "remaining": remaining,
                "retry_after": 0,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
            }

    def reset(self, key: str = None):
        """重置限流（key 为空则全部重置）"""
        with self._lock:
            if key:
                self._requests.pop(key, None)
            else:
                self._requests.clear()


# 全局限流器实例
limiter = RateLimiter()


class RateLimitMiddleware:
    """FastAPI 限流中间件"""

    def __init__(self, app, limiter_instance=None):
        self.app = app
        self.limiter = limiter_instance or limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 提取客户端标识（IP）
        headers = dict(scope.get("headers", []))
        client_ip = b""
        for k, v in headers.items():
            if k == b"x-forwarded-for":
                client_ip = v.split(b",")[0]
                break
        if not client_ip:
            client = scope.get("client")
            client_ip = str(client[0]).encode() if client else b"unknown"

        key = client_ip.decode(errors="ignore")

        # 限流检查
        result = self.limiter.allow(key)
        if not result["allowed"]:
            # 返回 429
            body = f'{{"detail": "请求过于频繁，请 {result["retry_after"]} 秒后重试", "retry_after": {result["retry_after"]}}}'.encode()
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", str(result["retry_after"]).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


if __name__ == "__main__":
    print("=" * 60)
    print("  API 限流保护 - 测试")
    print("=" * 60)

    # 用小的窗口做测试
    rl = RateLimiter(max_requests=5, window_seconds=60)
    print(f"限流配置: 每 {rl.window_seconds}s 最多 {rl.max_requests} 次")

    # 1. 前 5 次请求应全部允许
    print("\n=== 前5次请求（应全部允许）===")
    for i in range(5):
        r = rl.allow("test_client")
        print(f"  第{i+1}次: allowed={r['allowed']} remaining={r['remaining']}")

    # 2. 第 6 次请求应被拒绝（超限）
    print("\n=== 第6次请求（应被拒绝）===")
    r6 = rl.allow("test_client")
    print(f"  第6次: allowed={r6['allowed']} retry_after={r6['retry_after']}s")
    print(f"  {'✅ 超限请求被拒绝' if not r6['allowed'] else '❌ 未被拒绝'}")

    # 3. 不同客户端不受影响
    print("\n=== 不同客户端（应允许）===")
    r_other = rl.allow("other_client")
    print(f"  other_client: allowed={r_other['allowed']} remaining={r_other['remaining']}")

    # 4. 重置后恢复
    print("\n=== 重置后（应恢复允许）===")
    rl.reset("test_client")
    r_reset = rl.allow("test_client")
    print(f"  重置后: allowed={r_reset['allowed']} remaining={r_reset['remaining']}")

    ok = not r6["allowed"] and r_other["allowed"] and r_reset["allowed"]
    print(f"\n  {'✅ 通过标准达成：超限请求被拒绝' if ok else '❌ 未通过'}")
