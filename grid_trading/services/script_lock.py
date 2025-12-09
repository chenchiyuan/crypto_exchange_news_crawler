"""
脚本锁机制
Script Lock Mechanism

实现基于数据库的脚本互斥锁，避免定时任务并发执行
Feature: 001-price-alert-monitor
"""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from grid_trading.django_models import ScriptLock

logger = logging.getLogger("grid_trading")


def acquire_lock(lock_name: str, timeout_minutes: int = 10) -> bool:
    """
    获取脚本锁

    Args:
        lock_name: 锁名称，如'price_monitor_data_update'
        timeout_minutes: 锁超时时间(分钟)，默认10分钟

    Returns:
        True: 获取锁成功
        False: 锁已被占用

    Example:
        if acquire_lock('price_monitor_data_update'):
            try:
                # 执行数据更新逻辑
                update_klines()
            finally:
                release_lock('price_monitor_data_update')
        else:
            logger.error("脚本已在运行，跳过本次执行")
    """
    try:
        with transaction.atomic():
            # 尝试获取或创建锁
            lock, created = ScriptLock.objects.get_or_create(
                lock_name=lock_name,
                defaults={
                    'expires_at': timezone.now() + timedelta(minutes=timeout_minutes)
                }
            )

            if not created:
                # 锁已存在，检查是否过期
                if lock.expires_at < timezone.now():
                    # 锁已过期，更新过期时间并获取锁
                    lock.expires_at = timezone.now() + timedelta(minutes=timeout_minutes)
                    lock.save()
                    logger.info(f"✓ 获取锁成功(过期锁已更新): {lock_name}")
                    return True
                else:
                    # 锁未过期，无法获取
                    remaining_minutes = (lock.expires_at - timezone.now()).total_seconds() / 60
                    logger.warning(
                        f"✗ 锁被占用: {lock_name} "
                        f"(将于 {remaining_minutes:.1f} 分钟后过期)"
                    )
                    return False

            # 成功创建新锁
            logger.info(f"✓ 获取锁成功: {lock_name}")
            return True

    except Exception as e:
        logger.error(f"✗ 获取锁失败: {lock_name}, 错误: {e}")
        return False


def release_lock(lock_name: str) -> bool:
    """
    释放脚本锁

    Args:
        lock_name: 锁名称

    Returns:
        True: 释放成功
        False: 释放失败(锁不存在或异常)

    Example:
        release_lock('price_monitor_data_update')
    """
    try:
        deleted_count, _ = ScriptLock.objects.filter(lock_name=lock_name).delete()
        if deleted_count > 0:
            logger.info(f"✓ 释放锁成功: {lock_name}")
            return True
        else:
            logger.warning(f"⚠️ 锁不存在: {lock_name}")
            return False
    except Exception as e:
        logger.error(f"✗ 释放锁失败: {lock_name}, 错误: {e}")
        return False


def check_lock_status(lock_name: str) -> dict:
    """
    检查锁状态

    Args:
        lock_name: 锁名称

    Returns:
        dict: {
            'exists': bool,           # 锁是否存在
            'is_locked': bool,        # 锁是否有效(未过期)
            'acquired_at': datetime,  # 获取时间
            'expires_at': datetime,   # 过期时间
            'remaining_minutes': float # 剩余有效时间(分钟)
        }

    Example:
        status = check_lock_status('price_monitor_data_update')
        if status['is_locked']:
            print(f"锁有效，剩余 {status['remaining_minutes']:.1f} 分钟")
    """
    try:
        lock = ScriptLock.objects.get(lock_name=lock_name)
        now = timezone.now()
        is_locked = lock.expires_at > now
        remaining_seconds = (lock.expires_at - now).total_seconds()

        return {
            'exists': True,
            'is_locked': is_locked,
            'acquired_at': lock.acquired_at,
            'expires_at': lock.expires_at,
            'remaining_minutes': remaining_seconds / 60 if remaining_seconds > 0 else 0
        }
    except ScriptLock.DoesNotExist:
        return {
            'exists': False,
            'is_locked': False,
            'acquired_at': None,
            'expires_at': None,
            'remaining_minutes': 0
        }


def cleanup_expired_locks() -> int:
    """
    清理所有过期的锁

    Returns:
        int: 清理的锁数量

    Example:
        cleaned = cleanup_expired_locks()
        print(f"清理了 {cleaned} 个过期锁")
    """
    try:
        now = timezone.now()
        deleted_count, _ = ScriptLock.objects.filter(expires_at__lt=now).delete()
        if deleted_count > 0:
            logger.info(f"✓ 清理过期锁: {deleted_count} 个")
        return deleted_count
    except Exception as e:
        logger.error(f"✗ 清理过期锁失败: {e}")
        return 0
