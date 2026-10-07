# Outreach metrics

How to tell whether a trace was seen. The unit is **not** how many posts were made; it is how many
people read a given post and how many followed a link out of it.

## Where the numbers come from

Every figure here is read from the platform's own JSON, never estimated:

- Aave: `https://governance.aave.com/t/<id>.json` - topic `views`, and per post `reads` /
  `readers_count`; per-link click counts are exposed on the post.
- Morpho: `https://forum.morpho.org/t/<id>.json` - same fields; `link_counts` is present.

Read them per post, not per user. A post with three readers is three readers whether or not anyone
replied.

## Why this replaced the old counting

Posting twice as often in a thread nobody reads doubles zero. The 2026-10-02 comment on 25722 got
one click on its GitHub link; the 2026-10-05 comment in the same thread got **0 clicks and 4
readers**. The thread had 392 views in total, against 1,332 for the Base thread and 7,845 for the
Ethereum one. So the fix was destination, not frequency.

## Thread selection (all three must hold)

1. It has an audience (views, and recent activity).
2. There is a live decision, or a review somebody has committed to.
3. We hold a measured fact relevant to it.

A large thread that fails (3) is not a target: posting where we have nothing to say spends the one
thing that cannot be replaced, which is having no stake in the outcome.

## The posts, with the reading at the time of posting

| platform | thread | our post | posted (UTC) | reply target | thread views then | reads / readers |
|---|---|---|---|---|---|---|
| Aave | 25427 Deploy Aave V4 on Base | #9 | 2026-10-06 13:19 | #5 LlamaRisk | 1,332 | 1 / 0 |
| Aave | 25722 Deploy Aave V4 on the Monad Network | #5 | 2026-10-06 14:28 | #3 trevorsc | 397 (392 before) | 1 / 0 |
| Morpho | 2301 Collateral Transparency Framework | #8 | 2026-10-07 11:51 | #7 SrAugust | 700 (697 before) | 2 / 1 |

Earlier, for comparison: 25722 #2 (2026-10-02) - link clicks 1; 25722 #4 (2026-10-05) - **link
clicks 0**, readers 4.

## The measurement to take

At least 24 hours after each post, record for every row above: `reads`, `readers_count`, the link
click count, and whether anyone replied. Add the observation as a new dated row rather than
overwriting, so the series stays readable.

## What is not yet measured

Inbound. Readers who arrive at the repository and open an artifact are the ones that matter, and the
proxy for that is repository traffic and referrers, not forum views. Until that is recorded, a post
with readers and no clicks is indistinguishable from a post with readers who read only the text.