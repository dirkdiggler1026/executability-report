# Addendum 2 to PREREG-rtr-recovery-shape-2026-09-22

**Attestation, signed 2026-09-23 UTC.**

## Why this is a separate file

§11 of the registration is published in an explicitly unattested state, and says so in the
document. Its closing paragraph states the mechanism for closing that state:

> Per this document's own rule the attestation is appended as an addendum rather than
> inserted here, which is why the registration does not wait on it.

That mechanism was written down on 2026-09-22, before the outcome of anything it covers was
known. **The registration itself is not edited.** Its "Fixing this document" section ends
*This file is never edited*, and the value of that sentence is that it stays true — the file
a reader hashes today is the file that was published, and this addendum is additional
material rather than a revision of it.

## The four things no tool reaches

§11 names them. They are the whole content of this addendum, because everything a tool can
check was checked and recorded in §11 itself:

1. whether the operator holds these tokenized stocks at an address other than the two
   declared ones;
2. whether the operator holds them on another chain;
3. whether the operator has provided liquidity by a route that bypasses `PositionManager`
   and is therefore invisible to the `balanceOf` checks;
4. whether the operator trades on the venues characterised here.

The first three are questions about holdings. The fourth is a question about conduct.
**A balance is readable; conduct is not.** That asymmetry is why this addendum exists at
all, and it is also why the wording below is narrower than an earlier draft of it.

## The attestation

**I hold no position in any tokenized stock measured on this page, at any address I
control, on any chain. I have not traded, and do not trade, on the venues characterised
here, and I have not provided liquidity to any pool measured here, by any route.**

This is a statement about a moment and about my own conduct. The balance checks in §11
establish part of it; the rest is mine to state and cannot be established by a tool.

## Why the wording is what it is

An earlier draft said *these two addresses are all my addresses*. That was withdrawn, and
the reason is not stylistic.

- *"These two addresses are all my addresses"* is a claim about **the completeness of my own
  records**. No person can verify that about themselves — an old wallet, a wallet made for
  one purchase and forgotten, an address derived once and never written down, all defeat it.
  If it were later falsified, what would be damaged is not that sentence but the whole
  registration that carried it.
- *"At any address I control"* is a claim about **a fact I know**. It does not require
  enumerating anything, and it is answerable by the person making it.

The two sentences differ in what they ask the reader to accept, and only the second is
something a declarant is in a position to assert.

## What this establishes, and what it does not

It is a statement by the operator about the operator's own holdings and activity. A position
in a measured tokenized stock held at a controlled address, on any chain, would contradict
it; so would a trade on a measured venue. **It is falsifiable in that direction, and that is
the direction that matters.**

It is **not** a proof that no other address exists, and no such proof is possible. It is
also not a claim about assets this project does not measure: it says nothing about holdings
in WETH, SOL or any other asset outside the tokenized stocks measured here.

## How it is signed

There is no notarisation and none is needed. The signature is the commit: a dated entry in a
public repository, which is the same mechanism every other statement in this document relies
on. A reader does not have to trust the declarant; the declarant has made a statement that a
later observation can break, and has made it where it cannot be quietly withdrawn.

## Status of the measurement

This addendum makes no claim about any measurement, and it does not change §7's
falsification conditions, the boundaries, the cell set or any definition. It answers §11
and nothing else.
