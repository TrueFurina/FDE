"""
错误告警通知
功能：监控系统错误，达到阈值时触发告警记录（日志+告警文件）
支持：错误计数、阈值触发、告警记录查询、静默期控制
输出：output/alerts.json（告警记录）
"""

import json
import time
from collections import deque
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ALERTS_FILE = PROJECT_ROOT / "output" / "alerts.json"


class AlertManager:
    """错误告警管理器"""

    def __init__(self, alert_file=None, threshold=3, window=300, cooldown=60):
        """
        threshold: 窗口内错误数达到该值触发告警
        window: 统计窗口（秒）
        cooldown: 同类告警冷却时间（秒）
        """
        self.alert_file = Path(alert_file) if alert_file else ALERTS_FILE
        self.threshold = threshold
        self.window = window
        self.cooldown = cooldown
        self._errors = deque()      # [(timestamp, component, error)]
        self._last_alert = {}       # component -> last alert time
        self.alert_file.parent.mkdir(exist_ok=True)

    def report_error(self, component: str, error: str, level: str = "ERROR") -> dict:
        """上报错误，达到阈值触发告警
        返回: {"alerted": bool, "error_count": int, "reason": str}
        """
        now = time.time()
        # 记录错误
        self._errors.append((now, component, str(error)[:200]))
        # 清理窗口外错误
        while self._errors and now - self._errors[0][0] > self.window:
            self._errors.popleft()

        # 统计该组件在窗口内的错误数
        component_errors = [e for e in self._errors if e[1] == component]
        count = len(component_errors)

        # 检查是否触发告警
        if count >= self.threshold:
            # 冷却检查
            last = self._last_alert.get(component, 0)
            if now - last < self.cooldown:
                return {"alerted": False, "error_count": count, "reason": "冷却期内不重复告警"}

            self._last_alert[component] = now
            alert = self._record_alert(component, count, component_errors)
            return {"alerted": True, "error_count": count, "reason": f"窗口内错误数达到阈值", "alert": alert}

        return {"alerted": False, "error_count": count, "reason": f"未达阈值 ({count}/{self.threshold})"}

    def _record_alert(self, component: str, count: int, errors: list) -> dict:
        """记录告警到文件"""
        alert = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "component": component,
            "error_count": count,
            "window_seconds": self.window,
            "recent_errors": [e[2] for e in errors[-3:]],  # 最近3条错误
            "level": "ALERT",
        }
        # 追加到告警文件
        alerts = self._load_alerts()
        alerts.append(alert)
        with open(self.alert_file, "w", encoding="utf-8") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
        return alert

    def _load_alerts(self) -> list:
        if not self.alert_file.exists():
            return []
        try:
            return json.load(open(self.alert_file, encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def query_alerts(self, component: str = None, limit: int = 10) -> list:
        """查询告警记录"""
        alerts = self._load_alerts()
        if component:
            alerts = [a for a in alerts if a["component"] == component]
        return alerts[-limit:]

    def stats(self) -> dict:
        """告警统计"""
        alerts = self._load_alerts()
        by_component = {}
        for a in alerts:
            by_component[a["component"]] = by_component.get(a["component"], 0) + 1
        return {
            "total_alerts": len(alerts),
            "by_component": by_component,
        }

    def reset(self):
        """重置错误计数"""
        self._errors.clear()
        self._last_alert.clear()


if __name__ == "__main__":
    print("=" * 60)
    print("  错误告警通知 - 测试")
    print("=" * 60)

    # 测试配置：窗口60s，3次错误触发，冷却30s
    mgr = AlertManager(threshold=3, window=60, cooldown=30)

    # 1. 前2次错误不触发（未达阈值）
    print("\n=== 上报错误（未达阈值）===")
    for i in range(2):
        r = mgr.report_error("llm_api", f"连接超时 #{i+1}")
        print(f"  错误{i+1}: alerted={r['alerted']} count={r['error_count']} ({r['reason']})")

    # 2. 第3次错误触发告警
    print("\n=== 第3次错误（应触发告警）===")
    r3 = mgr.report_error("llm_api", "连接超时 #3")
    print(f"  错误3: alerted={r3['alerted']} count={r3['error_count']}")
    print(f"  {'✅ 告警已触发' if r3['alerted'] else '❌ 未触发'}")

    # 3. 冷却期内重复不告警
    print("\n=== 冷却期内重复（不重复告警）===")
    r4 = mgr.report_error("llm_api", "连接超时 #4")
    print(f"  错误4: alerted={r4['alerted']} count={r4['error_count']} ({r4['reason']})")

    # 4. 查询告警记录
    print("\n=== 告警记录 ===")
    alerts = mgr.query_alerts("llm_api")
    for a in alerts:
        print(f"  [{a['timestamp']}] {a['component']}: {a['error_count']}个错误")

    # 5. 统计
    stats = mgr.stats()
    print(f"\n=== 告警统计 ===")
    print(f"  总告警: {stats['total_alerts']} | 按组件: {stats['by_component']}")

    ok = r3["alerted"] and not r4["alerted"] and stats["total_alerts"] >= 1
    print(f"\n  {'✅ 通过标准达成：错误时可触发告警记录' if ok else '❌ 未通过'}")
