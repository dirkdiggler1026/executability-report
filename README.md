# 可成交性实测 — 数据与复核

对链上聚合器、Robinhood Chain 代币化股票与预测市场的独立可执行深度测量。

## 目录

```
index.html    报告全文（单文件，直接用浏览器打开）
data/         原始测量数据
  2026-09-03/  2026-09-04/
    quotes.jsonl.gz   每次报价一行
    rounds.jsonl      每轮的规范化哈希
code/         采集与复核脚本
```

## 可复核基线

**起点：2026-09-03 17:09 UTC，区块 53,579,264。**

该时刻之前（12:44–14:07 的 6 轮）的数据存在采集缺陷——整轮的报价调用
未钉定在同一区块高度，导致记录的区块号与数据实际状态不符。那批数据
已隔离在 `2026-09-03.pre-pinned-block/`（不含在本包内），**不可复核，
不计入任何结论**。

## 本次快照

报告中的全部数字对应 **17 轮 / 截至区块 53,861,286**（2026-09-03 17:09 →
09-04 UTC）。采集持续进行，本仓库的数据文件会随之增长；届时轮数会多于
报告所述，但已有轮次的记录不会改变。

完整性校验：

```bash
cd data/2026-09-03 && sha256sum -c MANIFEST.sha256
cd data/2026-09-04 && sha256sum -c MANIFEST.sha256
```

## 自己验一遍

报告里代币化股票的每个数字都可独立复算。需要一个 Robinhood Chain
的归档节点（在历史区块上 eth_call；公共端点只保留最近约 128 块）：

```bash
export RHCHAIN_RPC="https://robinhood-mainnet.g.alchemy.com/v2/<你自己的 key>"
python3 code/verify.py 53579264      # 基线首轮
python3 code/verify.py --latest
```

脚本会在那个区块高度重放全部 324 次报价调用，重算哈希，与
`rounds.jsonl` 里记录的比对。一致即证明该轮数据未被修改。

## 哈希原像规范 `rhdepth-v1`

只有**在同一区块能被第三方精确复现**的字段参与哈希：

```
每行: block|sym|side|size_usd|poolId|amount_in_raw|amount_out_raw|status
整数一律十进制字符串（uint256 超出 JS 安全整数范围）
行按字典序排序，\n 连接，前置 "rhdepth-v1" 一行，取 keccak256
```

排除时间戳、网络延迟与一切派生浮点——它们跨语言/跨运行不可复现，
放进原像会让「任何人都能重算核对」这句话静默失效。

## 依赖

无。`code/evm.py` 是零依赖实现（keccak-f[1600] + 静态 ABI 编码 + eth_call），
只需要 Python 3 和 curl。

## 边界

- 报价来自 Quoter 模拟调用，不是实际成交；真实执行受 MEV/滑点保护影响，通常更差
- 代币化股票仅统计 USDG 计价的池子
- 基线自 2026-09-03 17:09 UTC 起，时间尺度短，不可外推到跨周末与财报窗口
