# Lobby ATM: bank balance and cash in hand

**Branch:** `main`

## Goal
Split the one wallet into a bank balance and cash in hand. The top-left shows cash in hand. The modern lobby's ATM becomes something you walk up to and use (E, the prompt, or a click) to withdraw and deposit. The free Top up goes. The limits are admin settings (Settings › Bank).

Mockup: https://claude.ai/artifact/Y1pgFdZCarVzZtUv5LJc24 (source `docs/atm/mockup/`). Plan: `~/.claude/plans/update-to-player-bank-sparkling-frost.md`.

## Rules (defaults; all in admin Settings › Bank)
- New players: £1,000 bank, £0 in hand.
- Existing players: their current balance becomes cash in hand, and they get £1,000 bank.
- Withdraw only while cash in hand is under £500. The limit is £250 a withdrawal, or £500 when the bank is £2,000 or more. Going above £500 on hand is fine.
- The bank can go negative without limit. While it's negative, withdrawals are once every 30 minutes. The one that first takes it negative is allowed and starts the clock.
- Deposit any amount you're holding. Use the ATM on foot only.

## Files
- **Mockup:** `docs/atm/`.
- **Implementation (after sign-off):**
  - Server: `store.py`, a new `bank.py`, `casino.py`, `app.py`, `admin.py`, `plan_assets.py`, `admin_web/sections/settings.js`, `server/data/plan_assets/uploads.json`.
  - Client: `wallet_pill.gd`, `hud.gd`, `casino_floor.gd`, `furniture.gd`, a new `atm_panel.gd`, `net.gd`.
  - Docs: `protocol.md`, `architecture.md`, `README.md`.
  - Tests: `test_bank.py` (new), `test_ws.py`, `test_store_jackpot.py`.

## Mockup decisions (2026-10-23)
- **Style B, the cash machine.** It has a blue screen, side keys lined up with the labelled options, a keypad, and a cash slot that deals notes. Style A is dropped.
- **The ATM shows no cash-in-hand amount.** The top-left already shows it. The screens show the bank balance only.
- **The top-left pill shows just the amount,** with no "On hand" label.
- **Withdrawals are in £50 steps,** presets and Other amount alike, and the server checks it. Under "Most you can take", the Other amount screen says "£50 increments only". A wrong amount suggests the nearest one: "Can't pay £120. Try £100." Deposits can be any amount, to the penny: the keypad's "." (or the keyboard's) works on the deposit Other amount screen, with two decimal places.
- **The cash slot deals real £50 notes** (`docs/atm/mockup/img/note50.png`, 360×199), one per £50 up to a stack of 10. They come out over the slot's lit rim and hang down the fascia, each a little lower and askew.
- Undecided, so the mockup's defaults stand: the Recent screen (the last 4 ATM transactions) and the presets £50/£100/£250/£500.

## Done when
- [x] Mike signs off the mockup and picks a style (B)
- [x] The ATM works in the lobby, the top-left shows cash in hand, and Top up is gone
- [x] `tools/dev.sh test` passes

## Handoff
- **State:** done and live (2026-10-23). The live database was migrated: every player kept their balance as cash
  in hand and got £1,000 in the bank (a copy from before is `server/data/casino.pre-bank.sqlite`). The live
  `modern_atm` asset carries `"interact": "atm"`. Defaults: £1,000 bank and £0 in hand for new players; £250 limit,
  £2,000 once the bank is £2,500 or more; withdrawals while holding under £500; 30-minute overdrawn wait.
- **Checked:** `tools/dev.sh test` (922 passed). On a dev instance: the prompt, E opening the machine, a deposit,
  and a withdrawal dealing its notes.
- **Changed:** the files above, plus `hud.tscn` (the old grey InteractButton replaced by a bar-style prompt) and
  `client/assets/` (the note, and the VT323 screen font under the OFL).
- **Questions for Mike:** none open.
