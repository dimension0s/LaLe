"""
scheduler.py - 定时任务调度器

职责:
1. 启动时立即执行一次清理，用于回收站自动清理过期文件的监督
2. 每天定时清理过期文件（默认 17:00）
3. 独立进程运行

运行方式:
    python -m user_manager.scheduler
操作方法：
启动时立即执行一次，下一次执行时间显示为已经自定义好的时间，比如每天17:00，或者更复杂的定义（1号3点，5号6点等等）

"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime

# ============================================================
# 兼容直接运行：把项目根加入 sys.path
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    logger.error("未安装 apscheduler，请运行: pip install apscheduler")
    sys.exit(1)

from user_manager.recycle import cleanup_expired


# ============================================================
# 配置
# ============================================================
# 定时清理时间：每天 17:00
CLEANUP_HOUR = 17
CLEANUP_MINUTE = 0

# 是否在启动时立即执行一次
RUN_ON_STARTUP = True


# ============================================================
# 定时任务
# ============================================================
def job_cleanup_expired():
    """清理过期文件的任务"""
    logger.info("=" * 60)
    logger.info(f"定时任务触发: 清理过期文件")
    logger.info(f"时间: {datetime.now()}")
    logger.info("=" * 60)

    try:
        stats = cleanup_expired()
        logger.info(f"✅ 清理完成: {stats}")
    except Exception as e:
        logger.error(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()


# ============================================================
# 主函数
# ============================================================
def main():
    """启动调度器"""
    logger.info("=" * 60)
    logger.info("启动定时任务调度器")
    logger.info("=" * 60)
    logger.info(f"定时清理时间: 每天 {CLEANUP_HOUR:02d}:{CLEANUP_MINUTE:02d}")
    logger.info(f"启动时立即执行: {RUN_ON_STARTUP}")
    logger.info("=" * 60)

    # ============================================================
    # 1. 启动时立即执行一次
    # ============================================================
    if RUN_ON_STARTUP:
        logger.info("【启动任务】立即执行一次清理...")
        job_cleanup_expired()
    else:
        logger.info("【启动任务】跳过（RUN_ON_STARTUP=False）")

    # ============================================================
    # 2. 创建调度器
    # ============================================================
    scheduler = BackgroundScheduler()

    # 添加定时任务：每天 17:00 清理
    scheduler.add_job(
        job_cleanup_expired,
        trigger=CronTrigger(hour=CLEANUP_HOUR, minute=CLEANUP_MINUTE),
        id="cleanup_expired",
        name="清理过期文件",
        replace_existing=True,
        misfire_grace_time=3600,      # 错过执行后 1 小时内仍可触发
    )

    # ============================================================
    # 3. 启动调度器
    # ============================================================
    scheduler.start()

    logger.info("=" * 60)
    logger.info("✅ 调度器已启动")
    logger.info(f"下一次清理时间: {_next_run_time(scheduler)}")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 60)

    # ============================================================
    # 4. 优雅关闭
    # ============================================================
    def _shutdown(signum=None, frame=None):
        logger.info("")
        logger.info("收到停止信号，关闭调度器...")
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("✅ 调度器已关闭")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)     # Ctrl+C
    signal.signal(signal.SIGTERM, _shutdown)    # kill

    # ============================================================
    # 5. 保持进程运行
    # ============================================================
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        _shutdown()


def _next_run_time(scheduler) -> str:
    """获取下一次执行时间"""
    try:
        job = scheduler.get_job("cleanup_expired")
        if job and job.next_run_time:
            return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return "未知"


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    main()


# ctrl+c可以停止运行