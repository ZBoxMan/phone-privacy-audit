"""计分：最强信号 + 0.6 × 其余信号之和，再乘来源系数；分数只用来分档，报告里不显示。"""

from .vocab import TRUSTED_INSTALLERS


def trust_factor(installer, has_icon, is_system):
    if is_system:
        return 0.75
    if has_icon and installer in TRUSTED_INSTALLERS:
        return 0.62
    if has_icon:
        return 0.85
    return 1.0


def ios_trust_factor(is_store: bool) -> float:
    """过了苹果审核的降权。商店里的软件要权限，多半有正当理由。"""
    return 0.55 if is_store else 1.0


def combine(signals, factor=1.0):
    ws = sorted((s["score"] for s in signals), reverse=True)
    return max(1, min(100, round((ws[0] + 0.6 * sum(ws[1:])) * factor)))


def level_of(score: int) -> str:
    if score >= 65:
        return "high"
    if score >= 32:
        return "check"
    if score >= 15:
        return "watch"
    return "low"
