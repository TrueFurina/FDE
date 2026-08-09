"""
系统日志系统
功能：记录操作日志（查询/反馈/系统事件），支持按级别/关键字查询
输出：output/system.log（结构化日志）
"""

import json
import logging
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = PROJECT_ROOT / "output" / "system.log"


class SystemLogger:
    """系统日志记录器"""

    def __init__(self, log_file=None):
        self.log_file = Path(log_file) if log_file else LOG_FILE
        self.log_file.parent.mkdir(exist_ok=True)
        # 配置 Python logging
        self._setup_logging()

    def _setup_logging(self):
        """配置 logging"""
        self.logger = logging.getLogger("beauty_kb")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s|%(levelname)s|%(message)s"))
            self.logger.addHandler(handler)

    # ===== 记录方法 =====
    def log_query(self, query: str, session_id: str = "", elapsed_ms: float = 0,
                  intent: str = "", result: str = ""):
        """记录查询日志"""
        entry = {
            "type": "query",
            "query": query[:100],
            "session_id": session_id or "-",
            "elapsed_ms": round(elapsed_ms, 1),
            "intent": intent,
            "result": result[:30],
        }
        self.logger.info(f"QUERY|{json.dumps(entry, ensure_ascii=False)}")
        return entry

    def log_feedback(self, query: str, feedback: str, session_id: str = ""):
        """记录反馈日志"""
        entry = {
            "type": "feedback",
            "query": query[:100],
            "feedback": feedback,
            "session_id": session_id or "-",
        }
        self.logger.info(f"FEEDBACK|{json.dumps(entry, ensure_ascii=False)}")
        return entry

    def log_event(self, event: str, level: str = "INFO", **kwargs):
        """记录系统事件"""
        entry = {"type": "event", "event": event, **kwargs}
        log_method = {
            "DEBUG": self.logger.debug,
            "INFO": self.logger.info,
            "WARN": self.logger.warning,
            "ERROR": self.logger.error,
        }.get(level.upper(), self.logger.info)
        log_method(f"{level.upper()}|{json.dumps(entry, ensure_ascii=False)}")
        return entry

    def log_error(self, component: str, error: str):
        """记录错误"""
        entry = {"type": "error", "component": component, "error": str(error)[:200]}
        self.logger.error(f"ERROR|{json.dumps(entry, ensure_ascii=False)}")
        return entry

    # ===== 查询方法 =====
    def query_logs(self, log_type: str = None, keyword: str = None,
                   level: str = None, limit: int = 50) -> list:
        """查询日志
        log_type: query/feedback/event/error
        keyword: 关键字过滤
        level: DEBUG/INFO/WARN/ERROR
        """
        if not self.log_file.exists():
            return []

        results = []
        for line in self.log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            ts, lvl, payload = parts

            # 级别过滤
            if level and lvl.upper() != level.upper():
                continue

            # 解析 payload（QUERY|... / ERROR|... 等）
            try:
                inner = payload.split("|", 1)
                if len(inner) >= 2:
                    entry_type = inner[0].lower()
                    data = json.loads(inner[1])
                else:
                    entry_type = payload.lower()
                    data = {"message": payload}
            except json.JSONDecodeError:
                entry_type = payload.lower()
                data = {"message": payload[:100]}

            # 类型过滤
            if log_type and entry_type != log_type.lower():
                continue

            # 关键字过滤
            if keyword and keyword.lower() not in json.dumps(data, ensure_ascii=False).lower():
                continue

            results.append({
                "timestamp": ts,
                "level": lvl,
                "type": entry_type,
                "data": data,
            })

            if len(results) >= limit:
                break

        return results

    def stats(self) -> dict:
        """日志统计"""
        if not self.log_file.exists():
            return {"total": 0, "by_level": {}, "by_type": {}}
        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        by_level = {}
        by_type = {}
        for line in lines:
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            lvl = parts[1].upper()
            by_level[lvl] = by_level.get(lvl, 0) + 1
            # 解析类型
            try:
                inner = parts[2].split("|", 1)
                t = inner[0].lower() if len(inner) >= 2 else "raw"
            except Exception:
                t = "raw"
            by_type[t] = by_type.get(t, 0) + 1
        return {"total": len(lines), "by_level": by_level, "by_type": by_type}


if __name__ == "__main__":
    print("=" * 60)
    print("  系统日志 - 测试")
    print("=" * 60)

    logger = SystemLogger()

    # 1. 记录各类日志
    logger.log_query("烟酰胺有什么功效？", session_id="s1", elapsed_ms=1200, intent="成分功效", result="ok")
    logger.log_query("这款面霜多少钱？", session_id="s2", elapsed_ms=800, intent="产品咨询", result="ok")
    logger.log_feedback("烟酰胺有什么功效？", "up", session_id="s1")
    logger.log_event("system_start", version="v2.1")
    logger.log_error("llm_api", "连接超时")

    # 2. 查询日志
    print("\n=== 全部日志 ===")
    logs = logger.query_logs(limit=10)
    for log in logs:
        print(f"  [{log['level']}] {log['type']}: {json.dumps(log['data'], ensure_ascii=False)[:60]}")

    print("\n=== 按类型查询（query）===")
    queries = logger.query_logs(log_type="query", limit=5)
    print(f"  查询日志数: {len(queries)}")

    print("\n=== 按关键字查询（烟酰胺）===")
    kw_logs = logger.query_logs(keyword="烟酰胺", limit=5)
    print(f"  含'烟酰胺'日志数: {len(kw_logs)}")

    print("\n=== 日志统计 ===")
    stats = logger.stats()
    print(f"  总日志: {stats['total']}")
    print(f"  按级别: {stats['by_level']}")
    print(f"  按类型: {stats['by_type']}")

    ok = stats["total"] >= 5 and len(queries) >= 2
    print(f"\n  {'✅ 通过标准达成：操作日志可记录可查询' if ok else '❌ 未通过'}")
