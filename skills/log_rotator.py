"""
错误日志轮转
功能：当日志文件超过大小/条数阈值时自动轮转（重命名归档），防止日志无限增长
轮转策略：
1. 按大小触发：超过 max_size_bytes 时轮转
2. 保留最近 N 个归档文件
输出：output/logs/system.log + system.log.1/2/3...
"""

import os
import time
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "output" / "logs"
LOG_FILE = LOG_DIR / "system.log"


class LogRotator:
    """日志轮转器"""

    def __init__(self, log_file=None, max_size_bytes=100_000, keep_backups=3):
        """
        max_size_bytes: 日志文件超过该大小触发轮转
        keep_backups: 保留的归档文件数量
        """
        self.log_file = Path(log_file) if log_file else LOG_FILE
        self.max_size_bytes = max_size_bytes
        self.keep_backups = keep_backups
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def should_rotate(self) -> bool:
        """检查是否需要轮转"""
        if not self.log_file.exists():
            return False
        return self.log_file.stat().st_size >= self.max_size_bytes

    def rotate(self) -> dict:
        """执行轮转：当前日志 → .1，依次后移，删除最旧"""
        if not self.log_file.exists():
            return {"rotated": False, "reason": "日志文件不存在"}

        # 后移归档（.2 → .3, .1 → .2）
        for i in range(self.keep_backups, 0, -1):
            src = Path(f"{self.log_file}.{i - 1}") if i > 1 else self.log_file
            dst = Path(f"{self.log_file}.{i}")
            if src.exists():
                if dst.exists():
                    dst.unlink()
                shutil.copy2(src, dst)

        # 清空当前日志
        self.log_file.write_text("", encoding="utf-8")

        return {
            "rotated": True,
            "reason": f"大小超过 {self.max_size_bytes} 字节",
            "backups": self.keep_backups,
        }

    def check_and_rotate(self) -> dict:
        """检查并在需要时轮转"""
        if self.should_rotate():
            return self.rotate()
        return {
            "rotated": False,
            "reason": f"日志大小 {self.log_file.stat().st_size if self.log_file.exists() else 0} 未超阈值",
        }

    def log(self, message: str, level: str = "INFO"):
        """写入日志（写前检查轮转）"""
        self.check_and_rotate()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{ts}|{level}|{message}\n")

    def list_backups(self) -> list:
        """列出归档文件"""
        backups = []
        for i in range(1, self.keep_backups + 1):
            p = Path(f"{self.log_file}.{i}")
            if p.exists():
                backups.append({"file": p.name, "size": p.stat().st_size})
        return backups


if __name__ == "__main__":
    print("=" * 60)
    print("  错误日志轮转 - 测试")
    print("=" * 60)

    # 测试配置：小阈值触发轮转
    rotator = LogRotator(max_size_bytes=500, keep_backups=3)

    # 1. 写入大量日志触发轮转
    print("\n=== 写入日志（触发轮转）===")
    for i in range(30):
        rotator.log(f"测试错误日志 #{i} " + "x" * 30, "ERROR")

    # 2. 检查归档
    print("\n=== 归档文件 ===")
    backups = rotator.list_backups()
    print(f"  归档数: {len(backups)}")
    for b in backups:
        print(f"    - {b['file']} ({b['size']} 字节)")

    # 3. 验证当前日志大小受控
    current_size = rotator.log_file.stat().st_size if rotator.log_file.exists() else 0
    print(f"\n当前日志大小: {current_size} 字节（阈值 {rotator.max_size_bytes}）")

    # 4. 验证轮转发生
    rotated = len(backups) > 0
    print(f"\n  {'✅ 通过标准达成：日志超限自动轮转' if rotated else '❌ 未轮转'}")
