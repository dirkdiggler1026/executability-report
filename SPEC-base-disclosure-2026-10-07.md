# 规格:base-depth 的 DISCLOSURE.md 改为生成,拆出 HISTORY.md,并补 by_row

写给落地的一侧。判据 H 会**逐字节**比对,所以空格、破折号、结尾换行都算 —— 模板里的字面文本请原样抄,只替换 `{{…}}`。

本规格里每个 `{{…}}` 后面都注明了**来源文件与键路径**。规则:**凡不在产物里的值,一律不进文件。** 没有任何值来自时钟。

---

## 0. 为什么拆成两份

```
DISCLOSURE.md   生成 · 只写【当前这一跑是什么】· 进 GENERATED.json 的 outputs
HISTORY.md      手写 · 只写【过去说过什么、为什么改】· 不进 outputs
```

不拆的后果是具体的:H 要求 outputs 里的文件完全由生成器产出,而 History 是手写散文 —— 混在一份里,每次手改 History 都会让 H 变红,而那是误报。顺带,现在那两个重复的 `# Disclosure` H1 本来就是"两份文档被粘在一起"的症状,拆完自动消失。

---

## 1. `DISCLOSURE.md` 模板(生成)

```markdown
# Disclosure — Base exit-depth

**Canon `{{canon}}` at pinned block `{{block}}`**, block hash
`{{block_hash}}`, reads pinned by that hash with `requireCanonical`. No date appears in this
file on purpose: the hash is the time anchor, and anyone can resolve it with
`eth_getBlockByHash` rather than trusting a date copied in here. The endpoint read was
`{{endpoint}}`.

## What this run established

- **{{both_ok}} of {{row_set}} rows** read cleanly in both of two independent runs and were
  **identical across them**, with **0 disagreements**. Rows that were not identical in both
  runs are not published.
- **{{publishable}} rows are publishable** — Panel A {{panel_a}} (claim: the measured curve),
  Panel B {{panel_b}} (claim: the on-chain holdings bound). **{{sealed}} rows are sealed.**
- A failed read raises instead of returning a default, and every read failure is recorded per
  (pool, size, fee, spacing, leg, selector).

## What this run did not establish

- **{{errors}} rows have no figure.** Those rows issue the most reads and failed with
  HTTP 429 on `tickBitmap(int16)` in each run, and the two runs lost different rows. Their
  absence is a property of our read budget in that run, not of the pool. The rows:
{{errors_table}}
- **Two runs agreeing on the same block hash cannot exclude a deterministic degradation.** A
  fallback triggered by load would make both runs give the same answer. Excluding it needs a
  check that does not depend on the endpoint agreeing with itself — a storage proof anchored
  to the block hash — and that has not been done.
- **Multi-range accumulation is not replay-validated** (`multi_cross_validated`:
  `{{multi_cross_validated}}`), and **the round-trip composition is not replay-validated**
  (`roundtrip_composition_validated`: `{{roundtrip_composition_validated}}`). Each leg was
  checked separately against real swaps; their composition was not. Rows depending on either
  are sealed rather than published.
- Termination reasons (`exhausted` / `iteration_cap` / `sentinel`) are recorded per row. They
  are a boundary of the method, never a property of the asset.

## Provable window

`{{provable_chain}}`, about `{{provable_window_blocks}}` blocks, measured
`{{provable_measured}}` and marked derived. Verifying anything older than that window needs an
archival endpoint.

---

Earlier statements about this measurement, what was superseded and why, and one promise that
was made and not kept, are in [HISTORY.md](HISTORY.md). Nothing in this file is history: it
describes the current run only.
```

### 替换表

| 占位 | 来源 | 当前值 |
|---|---|---|
| `{{canon}}` | `base-ladder-Y.json` → `canon` | `basedepth-v3-1` |
| `{{block}}` | `base-depth-publishable-Y.json` → `block` | `52175000` |
| `{{block_hash}}` | 同上 → `block_hash` | `0xbdc05b98…cc13d` |
| `{{endpoint}}` | `base-ladder-Y.json` → `endpoint` | `https://mainnet.base.org` |
| `{{both_ok}}` | publishable → `both_ok` | `38` |
| `{{row_set}}` | `both_ok + errors` | `43` |
| `{{publishable}}` | publishable → `publishable` | `18` |
| `{{panel_a}}` | publishable → `panel_a` | `15` |
| `{{panel_b}}` | publishable → `panel_b` | `3` |
| `{{sealed}}` | publishable → `sealed` | `20` |
| `{{errors}}` | publishable → `errors` | `5` |
| `{{errors_table}}` | publishable → `errors_detail`(见下) | 5 行 |
| `{{multi_cross_validated}}` | `base-ladder-Y.json` → `multi_cross_validated` | `false` |
| `{{roundtrip_composition_validated}}` | 同上 | `false` |
| `{{provable_chain}}` | 同上 → `provable_until.chain` | `base-8453` |
| `{{provable_window_blocks}}` | 同上 → `provable_until.window_blocks` | `1283204` |
| `{{provable_measured}}` | 同上 → `provable_until.window_measured_utc` | `2026-10-01` |

🔴 `{{provable_measured}}` 是**唯一**的日期,而它是**可证明窗口的测量日**(产物里带 `derived: true`),不是这次测量的日期,也不是块的时间。所以它只出现在「Provable window」一节、且紧跟 "marked derived" —— **不要把它当成本次测量的日期用到别处。**

### `{{errors_table}}`

`errors_detail` 每项的键是 `pool` / `size` / `run1` / `run2`。渲染成:

```markdown
  | pool | size | run 1 | run 2 |
  |---|---|---|---|
  | `0x97f35d1e…` | 10000 | read_failed | read_failed |
```

两列分开列出,因为**两跑丢的行不同**正是"这 5 行是限流产物"的证据 —— 合成一列就把它藏掉了。

### 禁止出现在这份文件里的东西

```
任何由时钟得到的值(generated_utc / today / now)       ⇒ 嵌时钟的产物没人能复现,H 会判失败
任何 "provisional" / "under re-verification" 的措辞    ⇒ 当前这一跑不是暂定的;那些话属于 HISTORY
任何 "will be" / "to be added" 的承诺                  ⇒ 承诺写进 HISTORY,别写进当前状态
从别处抄来的日期                                       ⇒ 第二份事实会漂移
```

---

## 2. `HISTORY.md`(手写,不进 outputs)

每条**带日期前缀、时态不改**。至少四条:

```markdown
# History — Base exit-depth

Earlier statements kept readable next to the reason they changed. The current run is described
in [DISCLOSURE.md](DISCLOSURE.md) and nothing here describes it.

## 2026-10-04 — first table, at block 52,170,281
19 publishable rows (Panel A 15 / Panel B 4), 24 sealed, published before read validation
existed. Artifacts remain in this directory as `base-ladder.json` and
`base-ladder-gated.json`. **Superseded by the replacement of 2026-10-06.**

## 2026-10-06 — why that table was provisional
Four runs pinned to the same block hash at a later block (52,171,860) disagreed on 7 of 43
rows, and on the recovery figure itself in 3. The cause was in my reader, not the chain: a
failed `ticks()` returned 0 and a failed `tickBitmap` returned a sentinel, so a transport
failure read as "no liquidity change here". The largest disagreement was 3.49x on one row
(5.646941% vs 19.712807%) and the lower value was the corrupted one, so a majority vote across
runs would have selected the wrong number. **Superseded by the replacement record below.**

## 2026-10-06 — replacement
Replaced by the run at block 52,175,000 with read validation in effect. That run is the
subject of DISCLOSURE.md.

## 2026-10-04 — a promise made and not kept: `margin_to_next_tick`
The table published on 2026-10-04 said a per-row `margin_to_next_tick` would be added so the
width of Panel A's claim would be visible. The 2026-10-06 rewrite did not deliver it and
dropped the sentence without saying so. It is not delivered today. Delivering it means
recording, for each Panel A row, the distance from the absorption point to the next initialised
tick, which is a measurement rather than a reformatting of what exists.

## 2026-10-07 — my own wording about the larger tiers was wrong
A forum post of mine described the larger tiers as "measured but withheld pending one
validation". For 5 of 43 rows that is not what happened: the reads failed and those rows have
no figure at all. "Measured but withheld" is accurate for the sealed rows and not for those
five. The artifact always said they had no number; the post's wording did not.
```

最后一条是我的错,写进来是因为**它是一条已发出去的措辞**,而这个仓库的规矩是更正要发表,不管谁在依赖它。

---

## 3. `GENERATED.json`

落在 `measurements/base-depth/GENERATED.json`:

```json
{
  "generator": "code/base_depth_publish.py",
  "argv": ["--from", "base-ladder-Y.json", "--publishable", "base-depth-publishable-Y.json", "--out-dir", "{outdir}"],
  "outputs": ["README.md", "DISCLOSURE.md"],
  "inputs": ["base-ladder-Y.json", "base-depth-publishable-Y.json", "reads-Y1.json", "reads-Y2.json"]
}
```

```
generator  相对【仓库根】· 不许绝对路径 · 不许 ..
inputs     相对【测量目录】—— 生成器以该目录为 cwd 运行
argv       必须含 {outdir};H 把它替换成临时目录。没有占位 ⇒ H 直接判失败
outputs    相对测量目录,逐字节比对
```

自检(落地后跑一次,应为 exit 0):

```
python3 code/check_published.py        # 期望看到 "H  measurements/base-depth/README.md == regenerated"
```

若看到 `NOT EXERCISED`(退出码 3),那是**生成器跑不起来**,不是通过也不是失败 —— 查依赖与输入,别查被改动的文件。

---

## 4. `by_row` 规格 —— memoization 唯一干净的检验

现状:`reads-Y1.json` / `reads-Y2.json` 里 `by_row` 是空的 `{}`,而 `calls` 只有总数(2452 / 2456)。

**为什么总数不能用:** 一行在 429 上提前中断就少读很多次,两跑中断的行不同,所以 `calls` 的差被失败模式污染。拿它比较"memo 版 vs 非 memo 版"会把"memo 减少了读取"和"更多行提前中断"混在一起。

**要填什么。** 键 = 行标识(与 `errors_detail` 用同一套:`pool|label|size|fee|ts`),值:

```json
{
  "0xa079…|NVDAc/USDC|100|fee500|ts10": {
    "calls_total": 17,
    "by_selector": {"0x5339c296": 9, "0xf30dba93": 6, "0x3850c7bd": 1, "0x1a686502": 1},
    "cache_hits": 4,
    "failures": 0,
    "completed": true
  }
}
```

```
calls_total   该行实际发出的 eth_call 次数(不含缓存命中)
by_selector   按选择器分,因为"少读了哪一类"才是 memo 要证明的
cache_hits    被 memo 挡掉的次数 —— 它与 calls_total 的和应等于未 memo 版的 calls_total
failures      该行的失败次数
completed     该行是否跑到底(false ⇒ 这一行不进任何比较)
```

**检验的算法,写死在比较脚本里:**

```
1. 取两跑中 completed == true 且行值逐位一致的行集合 R(今天 R 就是那 38 行)
2. memo 版的读取量  = Σ_{r∈R} calls_total[r]
3. 非 memo 版的读取量 = Σ_{r∈R} (calls_total[r] + cache_hits[r])
4. 只比较这两个数。R 之外的行一律不进 —— 它们的读取量被中断截短了
```

🔴 第 3 步是关键:**基线不需要再跑一次**。`cache_hits` 让非 memo 版的读取量可以从同一跑里算出来,所以这个检验不需要网络、不需要第二次测量,只需要把字段填上。这是它比"重跑基线"便宜得多的原因 —— 也是为什么 `calls_total + cache_hits` 必须是精确的恒等式,而不是估计。

预注册一下,免得事后挑数:**若 R 上的 `Σ cache_hits` 为 0,结论是"memo 在这些行上没有生效",不是"memo 没用"** —— 两者不同,而且前者该去查 memo 的键。
