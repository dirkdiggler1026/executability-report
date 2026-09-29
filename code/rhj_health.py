#!/usr/bin/env python3
"""守着发行方接口的三件事,其中一件是【正信号】。

    python3 rhj_health.py            # 正常:该响就响
    RHJ_DRILL=1 python3 rhj_health.py   # 演练:只打印,不发,不写去重戳

🔴 为什么要正信号告警(2026-09-29 定)。已经寄出的信里写了一句
   "I have started snapshotting the endpoint every two hours, so the sequence
   will answer this either way"。那句话把这条序列的存活变成了【对第三方的承诺】。
   OnFailure 只在单元【失败】时响;它不管 timer 被关掉、不管跑通了但内容没人看。
   而 195 个 pendingMultiplier 现在全空 ⇒ **第一个非空值本身就是答案**。
   等事后分析才发现,等于白守一次窗口 —— 窗口不会重开。

三件:
  ① pendingMultiplier 任一非空        ⇒ 立刻推(这是答案,不是故障)
  ② 任一跟踪资产 currentMultiplier 变了 ⇒ 立刻推(若此前 ① 从未响过,这本身是否定的答案)
  ③ 最新快照超过 STALE_H 小时          ⇒ 推(序列断了,而信里承诺它在跑)

去重 6 小时,同其它几条;但 ① 和 ② 各自独立去重,免得一条压住另一条。
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time

ROOT = os.environ.get("RHJ_DATA", "/root/predict-data/dexfeed_data/rhj_assets")
STATE = os.path.join(ROOT, "_health_state.json")
REPEAT_S = int(os.environ.get("RHJ_ALERT_REPEAT_S", "21600"))
STALE_H = float(os.environ.get("RHJ_STALE_H", "6"))
DRILL = os.environ.get("RHJ_DRILL", "0") == "1"


def snapshots():
    return sorted(glob.glob(os.path.join(ROOT, "20??-??-??", "rhj-*.json")))


def send(text: str) -> None:
    print(text)
    if DRILL:
        print("  (RHJ_DRILL=1 ⇒ 不发送、不写去重戳)")
        return
    sys.path.insert(0, "/root/predict-data/tools")
    try:
        import notify
        if notify.configured():
            print("  TG 推送", "成功" if notify.send(text) else "失败")
        else:
            print("  TG 未配置")
    except Exception as e:
        print(f"  TG 异常 {e!r}", file=sys.stderr)


def main() -> int:
    files = snapshots()
    if not files:
        send("🔴 rhj-feed:一个快照都没有")
        return 2
    cur = json.load(open(files[-1]))
    age_h = (time.time() - time.mktime(time.strptime(
        cur["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ"))) / 3600.0

    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    now = int(time.time())

    def fire(key: str, text: str) -> None:
        if now - int(st.get(key, 0)) < REPEAT_S:
            print(f"  ({key} 在去重窗口内,不重复发)")
            return
        send(text)
        if not DRILL:
            st[key] = now

    s = cur.get("summary") or {}
    alerted = False

    # ① 正信号
    pend = s.get("pending_multiplier_nonempty") or []
    if pend:
        alerted = True
        rows = (cur["endpoints"]["assets"].get("body") or {}).get("assets") or []
        by = {r["tokenSymbol"]: r for r in rows}
        detail = "\n".join(f"  {t}  current={by.get(t,{}).get('currentMultiplier')}  "
                           f"pending={by.get(t,{}).get('pendingMultiplier')}" for t in pend)
        fire("pending", "🟢 rhj-feed:pendingMultiplier 出现非空 —— 这是那个问题的答案\n"
                        f"{detail}\n快照 {cur['fetched_utc']}\n{files[-1]}")
    else:
        print(f"  ① pendingMultiplier 仍然全空 (assets={s.get('assets_total')})")

    # ② 跟踪资产的 currentMultiplier 变了
    prev_tracked = st.get("tracked") or {}
    tracked = {k: v.get("current") for k, v in (s.get("tracked") or {}).items()}
    moved = {k: (prev_tracked.get(k), v) for k, v in tracked.items()
             if k in prev_tracked and prev_tracked[k] != v}
    if moved:
        alerted = True
        det = "\n".join(f"  {k}  {a} → {b}" for k, (a, b) in sorted(moved.items()))
        ever = "是" if st.get("pending_ever") else "否"
        fire("moved", "🟢 rhj-feed:currentMultiplier 变了\n" + det +
                      f"\n此前 pendingMultiplier 曾经非空过吗:{ever}\n快照 {cur['fetched_utc']}")
    if pend:
        st["pending_ever"] = True
    if not DRILL:
        st["tracked"] = tracked

    # ③ 序列自己断了 —— 信里承诺它在跑
    if age_h > STALE_H:
        alerted = True
        fire("stale", f"🔴 rhj-feed:最新快照已 {age_h:.1f} 小时前 "
                      f"({cur['fetched_utc']}) —— 信里承诺这条序列在跑")
    else:
        print(f"  ③ 最新快照 {age_h:.1f}h 前 ✓")

    if not DRILL:
        json.dump(st, open(STATE, "w"), indent=1)
    if not alerted:
        print("  ✅ 无需告警")
    return 0


if __name__ == "__main__":
    sys.exit(main())
