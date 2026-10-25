# -*- coding: utf-8 -*-
"""出价计算：常规公式 / 高价公式 / 向上取整到万"""
import random

# 估价超过该值即视为「大红」，本局改用高价公式。
# 所有大红最低为 512 万（超级存储盘），故取 512 万为分界，不可配置。
HIGH_THRESHOLD = 5120000

# 出价超过该值时游戏会弹出「本次出价过高是否继续」，固定 200 万，不可配置。
CONFIRM_POPUP_THRESHOLD = 2000000


def ceil_to_wan(value):
    return -(-value // 10000) * 10000


def compute_bid(round_number, estimate, high_i, bid_config, bonus=None, high_bonus=None):
    """计算回合出价（已向上取整到万）。

    high_i 非空（本局任一回合估价>500万后永久生效）:
        high_base + high_bonus（scenes 每回合随机加 high_step_min~max 万累计传入，
        保证回合间涨幅恰为一次抽样；high_bonus=None 时按每步 randint 回退，min=max 即固定步长）
    否则:
        估价 * 1.3 + bonus
    bonus=None 时回退 base_per_round * 回合数（自测/兼容）；
    正常流程由 scenes 传入本局累计随机加价 bonus_wan_min~max 万/轮。
    """
    if high_i is not None:
        if high_bonus is None:
            steps = max(0, round_number - high_i)
            step_lo = int(bid_config.get("high_step_min", 4620000))
            step_hi = max(step_lo, int(bid_config.get("high_step_max", 4970000)))
            high_bonus = sum(random.randint(step_lo, step_hi) for _ in range(steps))
        raw = int(bid_config["high_base"]) + int(high_bonus)
    else:
        multiplier = float(bid_config.get("multiplier", 1.5))
        if bonus is None:
            bonus = int(bid_config.get("base_per_round", 30997)) * round_number
        raw = int(estimate * multiplier) + int(bonus)
    return int(ceil_to_wan(raw))


def bid_digits(bid_value):
    """取整到万后的输入序列，如 1540000 → '154'（配合数字万键）"""
    return str(bid_value // 10000)


if __name__ == "__main__":
    # min=max 让高价随机步长变成固定 335 万，便于断言精确值
    cfg = {"multiplier": 1.3, "base_per_round": 30997,
           "high_base": 8888888, "high_step_min": 3350000, "high_step_max": 3350000}
    checks = [
        ((1, 1000000, None), 1340000, "134"),
        ((2, 1500000, None), 2020000, "202"),
        ((3, 4000000, None), 5300000, "530"),
        ((1, None, 1), 8890000, "889"),
        ((2, None, 1), 12240000, "1224"),
        ((5, None, 1), 22290000, "2229"),
        ((3, None, 3), 8890000, "889"),
    ]
    for (r, est, hi), expected, digits in checks:
        got = compute_bid(r, est, hi, cfg)
        assert got == expected, f"round={r} est={est} high_i={hi}: got {got}, want {expected}"
        if digits:
            assert bid_digits(got) == digits, f"digits {bid_digits(got)} != {digits}"
    # 含0的输入序列: high_i=1 第2回合 12238888 → 12240000 → '1224'
    assert bid_digits(compute_bid(2, None, 1, cfg)) == "1224"
    # 随机步长边界：n 步累加后必须落在 [base + n*min, base + n*max]
    rand_cfg = {"high_base": 8890000, "high_step_min": 4620000, "high_step_max": 4970000}
    for r, hi in ((2, 1), (5, 1)):
        value = compute_bid(r, None, hi, rand_cfg)
        assert 8890000 + (r - hi) * 4620000 <= value <= 8890000 + (r - hi) * 4970000, \
            f"random step out of range: round={r} got {value}"
    print("bid self-test OK")
