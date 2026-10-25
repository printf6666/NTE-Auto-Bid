# -*- coding: utf-8 -*-
"""场景流程：启动 → 竞拍回合 → 结算 → 循环下一局

阶段状态机（state.phase）：
  boot      脚本启动，等待 startup_wait 后点开始匹配（首局不购买道具）
  awaiting  等 OCR 识别到「竞拍第N回合」（超时重试点开始匹配，超过次数致命退出）
  playing   竞拍中：检测跳过（结算）与回合变化，回合变化触发当回合动作
  cooldown  结算完成，等待 cooldown_wait 后购买道具（第2局起）→ 开始匹配

结算时先 OCR 检查「出售」按钮（regions.sell_check）：识别不到=他人拍下，直接退出；
识别到=本局拍下，按最终估价决定是否点红键，再两下出售并退出。

worker 不为空时（GUI 运行）：除日志外还会上报阶段/回合/结算进度，并在动作前插入
可中断的暂停点。

mode：normal 普通模式 | giant 巨物模式（第2回合用特殊鉴定仪器再读一次估价，
>512万则本局切换高价公式）| supreme 至尊模式（第2回合用九格均价仪器，坐标同超级
鉴定仪器，用后等 avg_wait 秒在 regions.avg_check 读九格均价，严格>30万则本局切换
高价公式；第3回合用至尊鉴定仪器，坐标同特殊鉴定仪器）| avg2 存储盘模式（第1回合
大型鉴定仪器与第2回合二格均价仪器坐标均同超级鉴定仪器，第2回合读 avg_check 二格
均价，严格>30万切高价公式；其余与普通模式一致）。
"""
import logging
import random
import re
import time

import bid as bid_mod

log = logging.getLogger("yihuan")

_ROUND_RE = re.compile(r"第\s*([0-9])")
_ESTIMATE_RE = re.compile(r"[^0-9]")


def parse_round(text):
    """从「竞拍第N回合」提取回合数，容忍 OCR 断字/多字"""
    match = _ROUND_RE.search(text or "")
    return int(match.group(1)) if match else None


def parse_estimate(text):
    """估价区域文本 → 整数（去除千分位逗号等非数字字符）"""
    digits = _ESTIMATE_RE.sub("", text or "")
    if not digits or len(digits) > 9:
        return None
    return int(digits)


class Flow:
    def __init__(self, config, state, ocr, runner, capturer, control=None, worker=None,
                 mode="normal"):
        self.config = config
        self.state = state
        self.ocr = ocr
        self.runner = runner
        self.capturer = capturer
        self.control = control
        self.worker = worker
        self.mode = mode or "normal"
        self.regions = config["regions"]
        self.actions = config["actions"]
        self.loop = config["loop"]
        self.bid_config = config["bid"]

    # ---------- 暂停点与进度上报 ----------
    def checkpoint(self):
        if self.worker is not None:
            self.worker.check_interrupt()

    def report(self, method, *args):
        if self.worker is not None:
            getattr(self.worker, method)(*args)

    def notify_phase(self):
        if self.worker is not None:
            if self.control is not None:
                self.control.drain()  # 丢弃过期的停止/继续命令，避免误触发
            self.worker.on_phase(self.state.phase, self.state)

    # ---------- OCR 辅助 ----------
    def read_round(self):
        return self.ocr.read(self.capturer.grab_region(self.regions["round"]))

    def skip_appeared(self):
        return "跳过" in self.ocr.read(self.capturer.grab_region(self.regions["skip"]))

    def sell_appeared(self):
        """结算画面检查「出售」二字：识别到=本局拍下，识别不到=他人拍下

        默认只查 1 次（sell_check_times），点完跳过等 1 秒就读，没拍到马上退出；
        若出现把拍下误判成他人拍下的情况，把 config 里 sell_check_times 调大即可。
        """
        region = self.regions.get("sell_check")
        if not region:
            self.runner.fail("config.regions.sell_check 坐标缺失")
        times = int(self.loop.get("sell_check_times", 1))
        delay = float(self.loop.get("sell_check_delay", 1.0))
        for attempt in range(1, times + 1):
            self.checkpoint()
            text = self.ocr.read(self.capturer.grab_region(region))
            if "出售" in text:
                log.info("[结算] 识别到「出售」%r（第 %d/%d 次）→ 本局拍下", text, attempt, times)
                return True
            log.info("[结算] 未识别到「出售」%r（第 %d/%d 次）", text, attempt, times)
            if attempt < times:
                if self.runner.dry_run:
                    continue
                if self.worker is not None:
                    self.worker.sleep(delay)
                else:
                    time.sleep(delay)
        return False

    def read_number(self, region, label):
        """识别区域文本并解析为整数（带重试），label 用于日志"""
        times = int(self.loop.get("estimate_retry_times", 5))
        delay = float(self.loop.get("estimate_retry_delay", 1.0))
        for attempt in range(1, times + 1):
            self.checkpoint()
            image = self.capturer.grab_region(region)
            text = self.ocr.read(image)
            value = parse_estimate(text)
            if value is not None:
                log.info("[%s] 识别 %r → %d（第 %d/%d 次）", label, text, value, attempt, times)
                return value
            log.info("[%s] 识别失败 %r（第 %d/%d 次）", label, text, attempt, times)
            if attempt < times:
                if self.runner.dry_run:
                    continue
                if self.worker is not None:
                    self.worker.sleep(delay)
                else:
                    time.sleep(delay)
        return None

    def read_estimate(self):
        return self.read_number(self.regions["estimate"], "估价")

    # ---------- 主入口 ----------
    def tick(self):
        """每轮驱动一次状态机；各阶段按需截取所需识别框（冷却期零截图）"""
        phase = self.state.phase
        if phase == "boot":
            self.on_boot()
        elif phase == "awaiting":
            self.on_awaiting()
        elif phase == "playing":
            self.on_playing()
        elif phase == "cooldown":
            self.on_cooldown()

    # ---------- 启动 ----------
    def on_boot(self):
        wait = float(self.loop.get("startup_wait", 10.0))
        log.info("[启动] 等待 %.0f 秒后点开始匹配（首局不购买道具）", wait)
        self.runner.wait(wait, "启动")
        self.checkpoint()
        self.start_match()
        self.state.phase = "awaiting"
        self.state.match_started_at = time.time()
        self.notify_phase()

    def start_match(self):
        steps = self.actions.get("开始匹配")
        if not steps:
            self.runner.fail("config.actions.开始匹配 坐标缺失")
        self.runner.run("开始匹配", steps)

    # ---------- 等待进入竞拍 ----------
    def on_awaiting(self):
        state = self.state
        timeout = float(self.loop.get("auction_entry_timeout", 120.0))
        if state.match_started_at and time.time() - state.match_started_at > timeout:
            state.entry_failures += 1
            max_retries = int(self.loop.get("auction_entry_retries", 3))
            if state.entry_failures > max_retries:
                self.runner.fail(f"开始匹配后 {timeout:.0f} 秒未识别到竞拍回合，重试 {max_retries} 次仍失败")
            log.info("[等待竞拍] 超时，重试点开始匹配（%d/%d）", state.entry_failures, max_retries)
            self.checkpoint()
            self.start_match()
            state.match_started_at = time.time()
            return
        round_number = parse_round(self.read_round())
        if round_number is None:
            return
        state.phase = "playing"
        if round_number != 1:
            log.info("[竞拍] 未识别到第1回合，从第 %d 回合开始处理", round_number)
        self.notify_phase()
        self.handle_round(round_number)

    # ---------- 竞拍中 ----------
    def on_playing(self):
        state = self.state
        if state.current_round is not None and self.skip_appeared():
            self.settlement()
            return
        round_number = parse_round(self.read_round())
        if round_number is None:
            return
        current = state.current_round
        if current is None:
            self.handle_round(round_number)
            return
        if round_number == current:
            return
        if round_number < current:
            return  # 回合文本回退：忽略（疑似误识别）
        if round_number > current + 1:
            log.info("[竞拍] 回合跳变 %d → %d，中间回合已跳过", current, round_number)
        self.handle_round(round_number)

    # ---------- 回合动作 ----------
    def handle_round(self, round_number):
        state = self.state
        state.current_round = round_number
        self.report("on_round", round_number, state)
        wait = float(self.loop.get("round_wait", 10.0))
        log.info("[回合] 第 %d 回合开始，等待 %.0f 秒", round_number, wait)
        self.runner.wait(wait, f"第{round_number}回合")
        self.checkpoint()
        if self.skip_appeared():  # 等待期间有人秒掉
            self.settlement()
            return
        # 使用超级鉴定仪器（第一回合；若漏识别第1回合则在首个识别到的回合补用）
        if not state.instrument_used:
            steps = self.actions.get("使用仪器")
            if not steps:
                self.runner.fail("config.actions.使用仪器 坐标缺失")
            log.info("[回合] 使用超级鉴定仪器")
            self.runner.run("使用仪器", steps)
            state.instrument_used = True
            self.runner.wait(float(self.loop.get("item_wait", 10.0)), "使用仪器后")
            self.checkpoint()
            if self.skip_appeared():
                self.settlement()
                return
        # 模式专属回合动作（巨物/至尊的第2/3回合道具与检查）；返回 False 表示已进结算
        if not self.apply_mode_round(round_number):
            return
        # 第1/3/5回合读取当前估价
        if round_number in (1, 3, 5):
            value = self.read_estimate()
            if value is not None:
                state.estimate = value
                if value > bid_mod.HIGH_THRESHOLD and state.high_i is None:
                    state.high_i = round_number
                    log.info("[高价] 第 %d 回合估价 %d > %d，高价公式本局永久生效",
                             round_number, value, bid_mod.HIGH_THRESHOLD)
        self.checkpoint()
        bid_value = self.compute_bid(round_number)
        if bid_value is None:
            log.info("[出价] 第 %d 回合无有效估价，本回合不出价", round_number)
            return
        self.report("on_bid", round_number, bid_value, state)
        self.submit_bid(round_number, bid_value)

    # ---------- 模式专属回合动作 ----------
    def apply_mode_round(self, round_number):
        """模式专属回合动作；返回 False 表示本局已进结算"""
        if self.mode == "giant" and round_number == 2:
            return self._giant_round(round_number)
        if self.mode == "supreme" and round_number in (2, 3):
            return self._supreme_round(round_number)
        if self.mode == "avg2" and round_number == 2:
            return self._avg_price_round(round_number, "使用仪器",
                                         "存储盘模式：使用二格均价仪器", "二格均价")
        return True

    def _use_item(self, action_key, label, wait_key, wait_default):
        steps = self.actions.get(action_key)
        if not steps:
            self.runner.fail(f"config.actions.{action_key} 坐标缺失")
        log.info("[回合] %s", label)
        self.runner.run(label, steps)
        self.runner.wait(float(self.loop.get(wait_key, wait_default)), f"{label}后")
        self.checkpoint()

    def _skip_or_alive(self):
        """有人秒掉则进结算并返回 False"""
        if self.skip_appeared():
            self.settlement()
            return False
        return True

    def _giant_round(self, round_number):
        """巨物：第2回合用特殊鉴定仪器展示所占格数最多的藏品，再读一次估价"""
        self._use_item("使用特殊仪器", "巨物模式：使用特殊鉴定仪器", "item_wait", 10.0)
        if not self._skip_or_alive():
            return False
        state = self.state
        value = self.read_estimate()
        if value is not None:
            state.estimate = value
            if value > bid_mod.HIGH_THRESHOLD and state.high_i is None:
                state.high_i = round_number
                log.info("[高价] 第 %d 回合估价 %d > %d，高价公式本局永久生效",
                         round_number, value, bid_mod.HIGH_THRESHOLD)
        return True

    def _avg_price_round(self, round_number, action_key, label, price_label):
        """均价类仪器回合（坐标同超级鉴定仪器）：用后等 avg_wait 秒读 avg_check 均价，
        严格大于 avg_switch_threshold 则本局切换高价公式；均价不写入 state.estimate"""
        self._use_item(action_key, label, "avg_wait", 4.0)
        if not self._skip_or_alive():
            return False
        region = self.regions.get("avg_check")
        if not region:
            self.runner.fail("config.regions.avg_check 坐标缺失")
        value = self.read_number(region, price_label)
        if value is None:
            log.info("[%s] %s识别失败，保持常规公式", label, price_label)
            return True
        threshold = int(self.bid_config.get("avg_switch_threshold", 300000))
        if value > threshold and self.state.high_i is None:
            self.state.high_i = round_number
            log.info("[高价] 第 %d 回合%s %d > %d，高价公式本局永久生效",
                     round_number, price_label, value, threshold)
        else:
            log.info("[%s] %s %d ≤ %d，保持常规公式", label, price_label, value, threshold)
        return True

    def _supreme_round(self, round_number):
        """至尊：第2回合九格均价仪器（坐标同超级鉴定仪器），第3回合至尊鉴定仪器（坐标同特殊鉴定仪器）"""
        if round_number == 2:
            return self._avg_price_round(round_number, "使用仪器",
                                         "至尊模式：使用九格均价仪器", "九格均价")
        self._use_item("使用特殊仪器", "至尊模式：使用至尊鉴定仪器", "item_wait", 10.0)
        return self._skip_or_alive()

    def compute_bid(self, round_number):
        state = self.state
        if state.high_i is not None:
            # 高价公式：每回合随机加 high_step_min~max 万并累计，保证回合间涨幅恰在区间内；
            # 漏识别的回合按步数差额补抽（与旧固定步长的跳变行为一致）
            lo_wan = int(self.bid_config.get("high_step_min", 4620000)) // 10000
            hi_wan = max(lo_wan, int(self.bid_config.get("high_step_max", 4970000)) // 10000)
            steps = max(0, round_number - state.high_i - state.high_draws)
            step_wan = sum(random.randint(lo_wan, hi_wan) for _ in range(steps))
            state.high_draws += steps
            state.high_bonus += step_wan * 10000
            log.info("[高价] 第 %d 回合随机加价 %d 万，累计加价 %d 万（基准 %d 万）",
                     round_number, step_wan, state.high_bonus // 10000,
                     int(self.bid_config.get("high_base", 8890000)) // 10000)
            return bid_mod.compute_bid(round_number, None, state.high_i, self.bid_config,
                                       high_bonus=state.high_bonus)
        estimate = state.estimate
        if estimate is None:
            fake = int(self.bid_config.get("fake_estimate", 0) or 0)
            if fake > 0:
                log.info("[出价] 估价缺失，使用 fake_estimate=%d 验证公式", fake)
                estimate = fake
            else:
                return None
        # 估价≤500万：每轮加价随机 bonus_wan_min~max 万，累计入 bid_bonus（防止固定加价被看穿）
        lo = int(self.bid_config.get("bonus_wan_min", 1))
        hi = int(self.bid_config.get("bonus_wan_max", 5))
        increment = random.randint(lo, hi) * 10000
        state.bid_bonus += increment
        log.info("[出价] 本轮随机加价 %d 万，累计加价 %d（估价 %d）",
                 increment // 10000, state.bid_bonus // 10000, estimate)
        return bid_mod.compute_bid(round_number, estimate, None, self.bid_config,
                                   bonus=state.bid_bonus)

    def submit_bid(self, round_number, bid_value):
        digits = bid_mod.bid_digits(bid_value)
        log.info("[出价] 第 %d 回合 出价 %d → 输入 %s 万", round_number, bid_value, digits)
        steps = list(self.actions.get("出价") or [])
        if not steps:
            self.runner.fail("config.actions.出价 坐标缺失")
        for digit in digits:
            group = self.actions.get(f"数字{digit}")
            if not group:
                self.runner.fail(f"config.actions.数字{digit} 坐标缺失")
            steps.extend(group)
        if not self.actions.get("数字万"):
            self.runner.fail("config.actions.数字万 坐标缺失")
        steps.extend(self.actions["数字万"])
        if not self.actions.get("确认出价"):
            self.runner.fail("config.actions.确认出价 坐标缺失")
        steps.extend(self.actions["确认出价"])
        # 出价超过阈值（不含等于）时游戏弹「本次出价过高是否继续」二次确认
        threshold = bid_mod.CONFIRM_POPUP_THRESHOLD
        if bid_value > threshold:
            popup_steps = self.actions.get("出价过高继续")
            if not popup_steps:
                self.runner.fail("config.actions.出价过高继续 坐标缺失")
            log.info("[出价] %d > %d，弹二次确认，点继续", bid_value, threshold)
            steps.extend(popup_steps)
        self.runner.run(f"第{round_number}回合出价", steps)

    # ---------- 结算 ----------
    def settlement(self):
        state = self.state
        sell_wait = float(self.loop.get("sell_wait", 2.0))
        log.info("[结算] 竞拍结束（第 %d 局）", state.cycle)
        self.checkpoint()
        skip_steps = list(self.actions.get("跳过") or [])
        if not skip_steps:
            self.runner.fail("config.actions.跳过 坐标缺失")
        # 动作自带 1 秒等待：点完跳过等 1 秒即检查，没拍到马上退出
        self.runner.run("结算-跳过", skip_steps)
        self.checkpoint()
        # 结算画面检查「出售」按钮：识别到=本局拍下，识别不到=他人拍下
        won = self.sell_appeared()
        self.report("on_settle", won, state)
        if not won:
            # 他人拍下：本局没有可出售的藏品，直接退出
            log.info("[结算] 本局他人拍下，直接退出")
            exit_steps = self.actions.get("退出")
            if not exit_steps:
                self.runner.fail("config.actions.退出 坐标缺失")
            self.runner.run("结算-他人拍下", exit_steps)
            self._enter_cooldown()
            return
        # 本局拍下：结算画面读最终估价（文本框位置/格式与回合中相同）
        threshold = int(self.bid_config.get("sell_red_threshold", 5120000))
        final_estimate = self.read_estimate()
        if final_estimate is not None:
            over_threshold = final_estimate > threshold
            log.info("[结算] 最终估价 %d，红键阈值 %d → %s",
                     final_estimate, threshold, "不点红键" if over_threshold else "点红键")
        else:
            # OCR 失败回退：用本局最近一次估价判断
            fallback = state.estimate
            over_threshold = (fallback is not None and fallback > threshold) or state.high_i is not None
            log.info("[结算] 最终估价识别失败，回退估价=%s high_i=%s → %s",
                     fallback, state.high_i, "不点红键" if over_threshold else "点红键")
        steps = []
        if not over_threshold:
            # 最终估价≤红键阈值：出售前先点红色按键(2448,1156)
            red_steps = self.actions.get("出售红色按键")
            if not red_steps:
                self.runner.fail("config.actions.出售红色按键 坐标缺失")
            steps.extend(red_steps)
        # 两种情况都点两下出售：第一下触发出售，隔 sell_wait 第二下关闭出售后的「按任意键继续」弹窗
        sell_steps = self.actions.get("一键出售")
        if not sell_steps:
            self.runner.fail("config.actions.一键出售 坐标缺失")
        steps.extend(sell_steps)
        steps.append({"wait": sell_wait})
        sell_pos = [s for s in sell_steps if isinstance(s, list)]
        if not sell_pos:
            self.runner.fail("config.actions.一键出售 坐标缺失")
        steps.append(list(sell_pos[0]))
        steps.append({"wait": 0.5})
        exit_steps = self.actions.get("退出")
        if not exit_steps:
            self.runner.fail("config.actions.退出 坐标缺失")
        steps.extend(exit_steps)
        self.runner.run("结算-出售", steps)
        self._enter_cooldown()

    def _enter_cooldown(self):
        state = self.state
        state.reset_game()
        state.cycle += 1
        cooldown_wait = float(self.loop.get("cooldown_wait", 10.0))
        state.phase = "cooldown"
        state.cooldown_until = time.time() + cooldown_wait
        log.info("[结算] 完成，等待 %.0f 秒后进入下一局", cooldown_wait)
        self.notify_phase()

    def on_cooldown(self):
        if time.time() < self.state.cooldown_until:
            return
        self.checkpoint()
        # 第2局起每局先补道具（首局在 boot 阶段直接匹配）
        buy_steps = self.actions.get("购买道具")
        if not buy_steps:
            self.runner.fail("config.actions.购买道具 坐标缺失")
        log.info("[主界面] 购买道具")
        self.runner.run("购买道具", buy_steps)
        self.checkpoint()
        self.state.entry_failures = 0
        self.start_match()
        self.state.phase = "awaiting"
        self.state.match_started_at = time.time()
        self.notify_phase()
