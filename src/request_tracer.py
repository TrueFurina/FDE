"""
API 请求追踪
功能：追踪每次 API 请求的耗时/状态/路径，输出追踪报告
集成：FastAPI 中间件（自动记录）+ 独立查询接口
输出：output/request_trace.json
"""

import json
import time
import threading
from collections import defaultdict, deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TRACE_FILE = PROJECT_ROOT / "output" / "request_trace.json"


class RequestTracer:
    """API 请求追踪器"""

    def __init__(self, trace_file=None, max_traces=500):
        self.trace_file = Path(trace_file) if trace_file else TRACE_FILE
        self.max_traces = max_traces
        self._traces = deque(maxlen=max_traces)  # 内存中的最近追踪
        self._lock = threading.Lock()
        self.trace_file.parent.mkdir(exist_ok=True)

    def start(self) -> float:
        """开始追踪，返回开始时间戳"""
        return time.time()

    def end(self, start_time: float, method: str, path: str,
            status_code: int, duration_ms: float, extra: dict = None) -> dict:
        """结束追踪，记录一次请求"""
        trace = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 1),
            "success": status_code < 400,
            **(extra or {}),
        }
        with self._lock:
            self._traces.append(trace)
            self._persist()
        return trace

    def _persist(self):
        """持久化追踪记录（保存最近 max_traces 条）"""
        with open(self.trace_file, "w", encoding="utf-8") as f:
            json.dump(list(self._traces), f, ensure_ascii=False, indent=2)

    def query(self, path: str = None, method: str = None, limit: int = 20) -> list:
        """查询追踪记录"""
        traces = list(self._traces)
        if path:
            traces = [t for t in traces if path in t.get("path", "")]
        if method:
            traces = [t for t in traces if t.get("method") == method.upper()]
        return traces[-limit:]

    def stats(self) -> dict:
        """追踪统计：总请求/平均耗时/成功率/慢请求"""
        traces = list(self._traces)
        if not traces:
            return {"total": 0, "avg_duration_ms": 0, "success_rate": 0, "slow_requests": []}

        durations = [t["duration_ms"] for t in traces]
        success = sum(1 for t in traces if t["success"])
        slow = [t for t in traces if t["duration_ms"] > 3000]  # 慢请求 > 3s

        # 按路径统计
        by_path = defaultdict(lambda: {"count": 0, "total_ms": 0})
        for t in traces:
            by_path[t["path"]]["count"] += 1
            by_path[t["path"]]["total_ms"] += t["duration_ms"]

        return {
            "total": len(traces),
            "avg_duration_ms": round(sum(durations) / len(durations), 1),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "success_rate": round(success / len(traces), 3),
            "slow_count": len(slow),
            "slow_requests": [{"path": t["path"], "duration_ms": t["duration_ms"]} for t in slow[:5]],
            "by_path": {k: {"count": v["count"], "avg_ms": round(v["total_ms"] / v["count"], 1)} for k, v in by_path.items()},
        }


# 全局限流追踪器
tracer = RequestTracer()


class RequestTraceMiddleware:
    """FastAPI 请求追踪中间件"""

    def __init__(self, app, tracer_instance=None):
        self.app = app
        self.tracer = tracer_instance or tracer

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = self.tracer.start()
        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        # 包装 send 捕获状态码
        status_holder = {"status": 200}

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration_ms = (time.time() - start) * 1000
            self.tracer.end(start, method, path, status_holder["status"], duration_ms)


if __name__ == "__main__":
    print("=" * 60)
    print("  API 请求追踪 - 测试")
    print("=" * 60)

    tracer = RequestTracer()

    # 1. 模拟记录多次请求
    print("\n=== 记录请求 ===")
    test_requests = [
        ("GET", "/api/answer", 200, 1200.5),
        ("GET", "/api/answer", 200, 800.2),
        ("POST", "/api/answer", 200, 2500.0),
        ("POST", "/api/answer", 500, 3500.8),  # 失败+慢请求
        ("GET", "/health", 200, 5.1),
        ("POST", "/api/compliance", 200, 150.3),
    ]
    for method, path, status, dur in test_requests:
        tracer.end(time.time(), method, path, status, dur)
        print(f"  [{method:4s}] {path:20s} status={status} duration={dur}ms")

    # 2. 查询追踪
    print("\n=== 查询追踪（answer 路径）===")
    traces = tracer.query(path="/api/answer", limit=5)
    for t in traces:
        print(f"  [{t['method']}] {t['path']} → {t['status_code']} ({t['duration_ms']}ms) {'✅' if t['success'] else '❌'}")

    # 3. 统计
    print("\n=== 追踪统计 ===")
    stats = tracer.stats()
    print(f"  总请求: {stats['total']}")
    print(f"  平均耗时: {stats['avg_duration_ms']}ms")
    print(f"  成功率: {stats['success_rate']}")
    print(f"  慢请求(>3s): {stats['slow_count']}")
    print(f"  按路径: {json.dumps(stats['by_path'], ensure_ascii=False)}")

    ok = stats["total"] >= 5 and "avg_duration_ms" in stats
    print(f"\n  ✅ 通过标准达成：每次请求可追踪耗时状态" if ok else "  ❌ 未通过")
