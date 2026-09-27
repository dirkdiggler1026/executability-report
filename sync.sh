#!/usr/bin/env bash
#
# publish.sh in all but name: this is the only thing that decides what reaches this
# repository. It runs once a day at 06:01 UTC from a systemd timer, and it is the last
# gate before a measurement becomes public.
#
# It is published for the same reason every round carries a checksum: a gate that cannot
# be read is a gate you are asked to trust. Nothing here is a policy statement — every
# guard below was added after a specific failure, and the comment at each one names the
# failure it exists for. If a guard looks paranoid, the incident is written next to it.
#
# The guards, in the order they appear:
#
#   refuse to run on a dirty tree      a hand commit made on this machine was destroyed
#                                      by the `reset --hard` that used to be on line 28
#   only whole days are published      a partial day's MANIFEST is wrong the moment it
#                                      is written, and a wrong checksum is worse than none
#   strict YYYY-MM-DD names only       withdrawn data lives in suffixed directories; a
#                                      whitelist of good names beats a list of bad suffixes,
#                                      because a missed suffix publishes withdrawn data
#   enumerations ship with the rounds  a round names the venue list it used; if that list
#                                      is not published the reference cannot be resolved
#   explanatory records ship too       a refusal record written by a defective collector
#                                      is kept unchanged as evidence, but the note saying
#                                      which of its fields are mislabelled must travel with it
#   publication gate on the venue list every enumerated_at_block must resolve to a file, or
#                                      to an explicit record that it cannot. Neither ⇒ refuse
#   now.html is built before the commit so the page cannot be older than the data beside it;
#                                      not by discipline, but because they cannot be committed apart
#   head check must exist and pass     tags hand-added to a generated file were about to be
#                                      silently deleted by the generator the next morning
#   a missing check is a failure       a check that skips when absent is the same thing as
#                                      no check
#   two counts, not one                "rounds" once meant "every record in the tree",
#                                      quarantined copies included — 605 against 562
#
# What this script deliberately does NOT do: touch index.html, README.md or code/. Those are
# hand-published. An automated job that can overwrite prose will one day overwrite it at 06:01
# and nobody will notice that morning.
#
# ⚠️ Now that this file is tracked, editing it without committing will make the 06:01 run
#    refuse to start — the dirty-tree guard above applies to this file too. That is the
#    intended behaviour, and it is stated here because it is a new one.
#
# 把采集数据同步到公开仓库。
#
# 🔴 **只碰 data/。** index.html / README.md / code/ 是人工发版的产物,
#    自动任务绝不能覆盖它们 —— 否则某天凌晨的定时任务会把人写的
#    文案冲掉,而且没人会立刻发现。
#
# 🔴 只推【已完成的日期目录】。当天的目录还在增长,推上去的快照
#    和 MANIFEST 立刻就过期;而一份对不上的校验和比没有校验和更糟。
set -uo pipefail

SRC=/root/predict-data/dexfeed_data/uniswap_v4_rh
REPO=/opt/rh-report
TODAY=$(date -u +%F)
log() { echo "$(date -u '+%F %T') | $*"; }

cd "$REPO" || { log "FAIL: 仓库不存在"; exit 1; }

# 拉一次,避免人工发版后本地落后导致 push 冲突
#
# 🔴 **这一行每天 06:03 会静默销毁 /opt/rh-report 里任何未推送的本地改动。**
#    `reset --hard` 不是 merge —— 它把工作区和索引都扔回 origin/main。
#    未跟踪文件不受影响(本脚本自己就是未跟踪的,所以它活得下来),
#    但对【已跟踪文件】的任何本地编辑,只要没在 06:03 前推上去,就没了,而且不报错。
#    ⇒ 在这台机器上改 code/ 或 index.html:**改完立刻推**,不要过夜。
#    这条写在这里而不是写在某个规范文档里,因为要读到它的人,
#    正是将来打算动这一行的那个人。
git fetch -q origin main || { log "FAIL: fetch"; exit 1; }

#    上面那段警告瞄错了读者：它写给「将来要改这一行的人」，而会被咬的是
#    「在这台机器上做过一次手工提交的人」—— 那个人没有理由读 sync.sh。
#    所以改成让机器去读:有未推的提交、或已跟踪文件有未提交改动 ⇒
#    先把现状存成分支(信息零丢失)，再拒绝运行(systemd 看得见失败)。
#    -uno:未跟踪文件 reset 不动，不该拿它们报警(本脚本自己就是未跟踪的)。
if [ -n "$(git log origin/main..HEAD --oneline)" ] || [ -n "$(git status --porcelain -uno)" ]; then
  save="sync-save-$(date -u +%Y%m%dT%H%M%SZ)"
  git stash -q -u >/dev/null 2>&1 && stashed=1 || stashed=0
  git branch "$save" HEAD 2>/dev/null
  [ "$stashed" = 1 ] && git stash pop -q >/dev/null 2>&1
  log "FAIL: 本地有未推提交或未提交改动,已存为分支 $save;拒绝 reset --hard"
  git log origin/main..HEAD --oneline | while read -r l; do log "  未推: $l"; done
  git status --porcelain -uno | while read -r l; do log "  未提交: $l"; done
  exit 1
fi
git reset -q --hard origin/main || { log "FAIL: reset"; exit 1; }

n=0
for d in "$SRC"/*/; do
  day=$(basename "$d")
  # 只认严格的 YYYY-MM-DD。隔离目录一律带后缀(.pre-pinned-block /
  # .rhdepth-vN-defective /以后还会有别的),白名单比逐个列后缀稳:
  # 漏掉一种后缀 = 把已撤回的数据静默推成公开数据。
  case "$day" in
    [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
    *) log "跳过非日期目录: $day"; continue;;
  esac
  # 跳过当天(未完成)的目录
  [ "$day" = "$TODAY" ] && continue
  [ -f "$d/rounds.jsonl" ] || continue
  mkdir -p "data/$day"
  cp "$d/quotes.jsonl.gz" "$d/rounds.jsonl" "data/$day/" || continue
  ( cd "data/$day" && sha256sum quotes.jsonl.gz rounds.jsonl > MANIFEST.sha256 )
  n=$((n+1))
done

# ── ③a2 第二条序列 canon rhdepth-oneside-v1 → data-oneside/ ──────────
# 🔴 为什么必须连 enumerations/ 一起发:addendum 2 §2a 注册的是
#    「A round records enumerated_at_block, and that number has to point at a file
#     that still exists」。只发轮次不发枚举 ⇒ 第三方拿到一个解不开的块号,
#    而那正是那条注册要防的东西。清单档案不可变,所以只增不改。
# 🔴 refusals.jsonl 是【拒绝落盘的理由】,不是轮次。它和轮次同目录、不同文件名,
#    每行第一个字段是 record="refusal"。没有它,一条作废了 212 行的规则
#    在外面看就只是「那一小时没数据」。
SRC2=/root/predict-data/dexfeed_data/oneside_depth
n2=0
if [ -d "$SRC2" ]; then
  for d in "$SRC2"/*/; do
    day=$(basename "$d")
    case "$day" in
      [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
      *) continue;;                      # enumerations/ 和隔离目录都走这里
    esac
    [ "$day" = "$TODAY" ] && continue    # 当天还在长,同 data/
    [ -f "$d/rounds.jsonl" ] || continue
    mkdir -p "data-oneside/$day"
    cp "$d/quotes.jsonl.gz" "$d/rounds.jsonl" "data-oneside/$day/" || continue
    [ -f "$d/refusals.jsonl" ] && cp "$d/refusals.jsonl" "data-oneside/$day/"
    # 🔴 说明性记录也必须跟着走。2026-09-27:01:01 那条拒绝记录是【修复前】的
    #    采集器写的,字段 revert_selector 里放的不是 selector 而是 stateRoot 的前四字节。
    #    记录本身不改 —— 它是那个缺陷存在过的一手物证 —— 但旁边那条
    #    FIELD-ARTIFACT-*.json 说明它错在哪。**只发记录不发说明,等于把错字段当成事实发出去。**
    #    白名单会漏掉将来新增的说明文件,所以这里按前缀收,不按文件名。
    for note in "$d"/FIELD-ARTIFACT-*.json "$d"/QUARANTINED*.json "$d"/MISSING-*.json; do
      [ -f "$note" ] && cp "$note" "data-oneside/$day/"
    done
    ( cd "data-oneside/$day" && sha256sum $(ls quotes.jsonl.gz rounds.jsonl \
        refusals.jsonl FIELD-ARTIFACT-*.json QUARANTINED*.json MISSING-*.json \
        2>/dev/null) > MANIFEST.sha256 )
    n2=$((n2+1))
  done
  # 枚举档案:只增不改,所以整目录拷过去;MISSING-*.json 也在这里(缺档的显式记录)
  if ls "$SRC2"/enumerations/*.json >/dev/null 2>&1; then
    mkdir -p data-oneside/enumerations
    cp "$SRC2"/enumerations/*.json data-oneside/enumerations/
    ( cd data-oneside/enumerations && sha256sum *.json > MANIFEST.sha256 )
  fi
  # 🔴 发布闸门:每个 enumerated_at_block 都要指得到东西。指不到 ⇒ 必须有一条
  #    显式的 MISSING-<block>.json。两者都没有 = 静默的断链,拒绝发布。
  if [ -d data-oneside ]; then
    python3 - <<'PYEOF' || { log "FAIL: data-oneside 枚举链断,拒绝发布"; exit 1; }
import json, glob, os, sys
have = set()
for p in glob.glob("data-oneside/enumerations/pools-*.json"):
    have.add(int(os.path.basename(p).split("-")[1].split(".")[0]))
noted = set()
for p in glob.glob("data-oneside/enumerations/MISSING-*.json"):
    noted.add(int(os.path.basename(p).split("-")[1].split(".")[0]))
bad = {}
for p in glob.glob("data-oneside/*/rounds.jsonl"):
    for line in open(p):
        if not line.strip():
            continue
        eb = (json.loads(line).get("pools_source") or {}).get("enumerated_at_block")
        if eb is not None and eb not in have and eb not in noted:
            bad.setdefault(eb, 0)
            bad[eb] += 1
for eb, n in sorted(bad.items()):
    print(f"enumerated_at_block {eb} 无存档且无 MISSING 记录（{n} 轮）", file=sys.stderr)
sys.exit(1 if bad else 0)
PYEOF
  fi
  git add data-oneside/ >/dev/null 2>&1
fi

# ── ③b 连续性指标:首页那行数字的【唯一来源】────────────────────
# 🔴 它必须随 data/ 一起进仓库,否则本地发版侧的核对闸门看不到它,
#    "单源"就不成立 —— 人又回去手打两遍,而那正是 2026-09-05 在
#    release/ 抓到的 EN 12 轮 / ZH 17 轮漂移的成因。
#    仍然只碰 data/,不触 index/README/code(文案归人工发版)。
if python3 /root/predict-data/tools/continuity.py >/dev/null 2>&1; then
  cp /root/predict-data/dexfeed_data/continuity.json data/ 2>/dev/null
  cp /root/predict-data/dexfeed_data/continuity_anchor.json data/ 2>/dev/null
else
  log "WARN: continuity 生成失败,本轮沿用仓库里的旧值"
fi

git add data/ >/dev/null 2>&1

# 🔴 **跳过判据要排除 generated_utc**:continuity.json 每轮都带新时间戳,
#    直接比会「永远有变化」⇒ 天天产生一个内容等价的空 commit,
#    把「无变化,跳过」这条日志变成永远不会出现的死分支。
#    判据:剥掉 generated_utc 后内容未变 **且** 没有新的日期数据 ⇒ 才算无变化。
only_ts=$(python3 - <<'PYEOF'
import json, subprocess, sys
def strip(b):
    try:
        d = json.loads(b)
    except Exception:
        return None
    d.pop("generated_utc", None)
    return json.dumps(d, sort_keys=True, ensure_ascii=False)
names = subprocess.run(["git","diff","--cached","--name-only"],
                       capture_output=True, text=True).stdout.split()
# 有日期目录的数据变动 ⇒ 一定要提交
if any(n != "data/continuity.json" and n != "data/continuity_anchor.json" for n in names):
    print("no"); sys.exit()
if "data/continuity.json" not in names:
    print("no"); sys.exit()
new = strip(open("data/continuity.json","rb").read())
old = strip(subprocess.run(["git","show","HEAD:data/continuity.json"],
                           capture_output=True).stdout)
print("yes" if (old is not None and new == old) else "no")
PYEOF
)
if [ "$only_ts" = "yes" ]; then
  git restore --staged data/continuity.json data/continuity_anchor.json 2>/dev/null
  git checkout -- data/continuity.json data/continuity_anchor.json 2>/dev/null
fi

if git diff --cached --quiet; then
  log "无变化,跳过 ($n 个日期目录已是最新)"
  exit 0
fi

# ── now.html:必须在数据落盘【之后】、提交【之前】生成 ────────────────
# 🔴 位置本身就是那条保证。页面和它旁边的数据进【同一个 commit】
#    ⇒ 页面不可能比数据旧,而这不是靠纪律,是靠它们无法分开提交。
#    2026-09-20 实测过反例:页面在 06:03 同步【之前】生成,一出生就落后一天,
#    而它自称 "regenerated daily"。
#
# 🔴 生成失败就整个失败,不要"先把数据推出去,页面下次再说"。
#    那会得到:新数据 + 旧页面 + 页面上写着每日重生成 —— 静默的假话。
#    数据没丢(下一轮从 dexfeed_data 重新拷),而坏掉的构建必须是响的。
#    同一条理由本文件开头已经写过:一份对不上的校验和比没有校验和更糟。
# 🔴 stderr 要进日志。make_now.py 的账本地址守卫分两级:地址抄错 = 致命(页面会印错合约),
#    deployments.jsonl 多出一条链 = 警告(页面只是不完整,不是假的)—— 后者【继续发布】,
#    但那句 WARN 必须有人看得见,否则"警告"和"没检查"是同一个东西。
if [ -f make_now.py ]; then
  mn_err="$(python3 make_now.py 2>&1 >/dev/null)" || {
    log "FAIL: make_now.py 生成 now.html 失败: ${mn_err}"; exit 1; }
  # if 而不是 `[ -n .. ] && log ..`:后者在 mn_err 为空时整句返回 1。
  # 本文件现在是 `set -uo pipefail`(没有 -e)所以无害 —— 但它会在有人加上 -e 的那天变成炸弹。
  if [ -n "$mn_err" ]; then log "make_now: ${mn_err}"; fi
  git add now.html >/dev/null 2>&1
fi

# ── head 闸门:生成器不许再静默删标签 ─────────────────────────────
# 🔴 2026-09-26 的实事:og / favicon 标签是手工加进 now.html 的,而 now.html
#    自己第一行就写着「Generated by make_now.py … Do not hand-edit」。
#    生成器没同步 ⇒ 第二天 06:01 这里跑 make_now.py,标签消失,而提交信息叫
#    "data: sync through ...",日志那行也看不出来。本地已把标签搬进模板(ac44c87),
#    这一句是那件事的【机器判据】——约定靠人记,判据不靠。
# 🔴 文件不在 = 失败,不是跳过。它是被跟踪文件,而上面刚 reset --hard origin/main,
#    所以它必然在;它不在就说明仓库状态不对,那时候「静默跳过检查」和
#    「没有检查」是同一个东西 —— 本文件开头对 WARN 写过同一句话。
if [ ! -f code/check_heads.py ]; then
  log "FAIL: code/check_heads.py 不存在 —— head 闸门无法执行,拒绝发布"
  exit 1
fi
ch_out="$(python3 code/check_heads.py 2>&1)" || {
  log "FAIL: check_heads.py 不过 —— 三个页面的 head 不一致,拒绝发布"
  printf '%s\n' "$ch_out" | while IFS= read -r l; do log "  $l"; done
  exit 1
}
[ -n "$ch_out" ] && printf '%s\n' "$ch_out" | while IFS= read -r l; do log "check_heads: $l"; done

# 🔴 两个数,不是一个。
#    records = 树里每一条 rounds.jsonl 记录,含【已作废的 v1 隔离目录】和
#      snapshot 的重复拷贝;rounds = 严格日期目录里 canon=rhdepth-v2 的轮次。
#    2026-09-16 之前这里只报前者、却叫它 "rounds" —— 605 vs 562,
#    差 43(隔离 31 + snapshot 12)。量的名字不得比它建立的东西承诺更多,
#    而这一次犯规的是我们自己的提交信息。
records=$(cat data/*/rounds.jsonl 2>/dev/null | wc -l)
rounds=$(python3 - <<'PYEOF'
import json,glob,re
pat=re.compile(r'^\d{4}-\d{2}-\d{2}$')
n=0
for f in glob.glob("data/*/rounds.jsonl"):
    if not pat.match(f.split("/")[1]): continue
    for l in open(f):
        if l.strip() and json.loads(l).get("canon")=="rhdepth-v2": n+=1
print(n)
PYEOF
)
# 🔴 提交信息要说出【这次动了哪几条序列】。
#    09-26 学到的:一条改动如果提交信息里看不见,日志行里也看不见,它就是静默的
#    —— 那天差一点被 "data: sync through ..." 盖掉的是 now.html 的整组 head 标签。
#    第二条序列第一次上线时,提交信息不该长得和例行同步一样。
rounds2=$(python3 - <<'PYEOF'
import json, glob, re
pat = re.compile(r'^\d{4}-\d{2}-\d{2}$')
n = 0
for f in glob.glob("data-oneside/*/rounds.jsonl"):
    if not pat.match(f.split("/")[1]):
        continue
    for l in open(f):
        if l.strip() and json.loads(l).get("canon") == "rhdepth-oneside-v1":
            n += 1
print(n)
PYEOF
)
# 🔴 不要写成 `grep -c . || echo 0`。grep 对空输入【既打印 0 又返回 1】
#    ⇒ `|| echo 0` 也触发 ⇒ 变量成了两行 "0\n0"，2026-09-27 06:01 的提交信息
#    就印成了 "oneside 16 rounds, 0 0 refused"。已推的历史改不了，这里改往后。
ref2=$(cat data-oneside/*/refusals.jsonl 2>/dev/null | grep -c . ); ref2=${ref2:-0}
msg="data: sync through $(date -u -d yesterday +%F) (${rounds} rounds, ${records} records)"
if [ "${rounds2:-0}" -gt 0 ] 2>/dev/null; then
  msg="${msg}; oneside ${rounds2} rounds, ${ref2} refusal records"
fi
git commit -q -m "$msg" || { log "FAIL: commit"; exit 1; }
git push -q origin main || { log "FAIL: push"; exit 1; }
log "已推送 | 日期目录 $n | v2 轮次 $rounds | 记录 $records | oneside 日期目录 ${n2:-0} · 轮次 ${rounds2:-0} · 拒绝 ${ref2:-0}"
