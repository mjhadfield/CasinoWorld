// Settings: how the floor runs (NPCs on or off, the population, cooldowns, dealer shifts), the Default seating style, and
// the Bank (the lobby ATM's rules and what new players start with), and this browser's admin preferences, side by side.
import { ZOOM_STEP } from "/admin-ui/plan/plan.js";
let H;

export function init(h) {
  H = h;
  h.view.innerHTML = `
  <div class="wb" style="grid-template-columns: minmax(0, 560px) minmax(0, 560px) minmax(0, 560px) minmax(0, 1fr)">
    <form class="panel" id="settings-form">
      <div class="ph">Floor <span class="grow"></span><button type="submit" class="primary">Save</button></div>
      <div class="pb padded">
        <label class="controls" style="margin-bottom:12px"><input type="checkbox" id="s-npcs-on"> NPCs in the casino</label>
        <div class="grid2">
          <label class="field"><span>Punters on the floor</span><input type="number" id="s-population" min="0" max="30" step="1"></label>
          <label class="field"><span>Regulars' cooldown (× normal)</span><input type="number" id="s-regular" min="0.05" max="1" step="0.05"></label>
          <label class="field"><span>Cooldown after a visit (min)</span><span class="controls"><input type="number" id="s-cool-lo" min="0" step="1" style="width:6em"> to <input type="number" id="s-cool-hi" min="0" step="1" style="width:6em"></span></label>
          <label class="field"><span>Cooldown after going bust (min)</span><span class="controls"><input type="number" id="s-bust-lo" min="0" step="1" style="width:6em"> to <input type="number" id="s-bust-hi" min="0" step="1" style="width:6em"></span></label>
          <label class="field"><span>Dealer shift (min)</span><input type="number" id="s-shift" min="0.5" max="240" step="0.5"></label>
          <label class="field"><span>Between tables' reliefs (min)</span><input type="number" id="s-stagger" min="0.5" max="240" step="0.5"></label>
        </div>
        <p class="hint">Changes apply straight away; cooldowns from the next visit that ends. Switching NPCs off (no Save needed) sends them home: anyone at a table finishes the round they're in first. Back on, they arrive one at a time.</p>
      </div>
    </form>
    <form class="panel" id="seating-form">
      <div class="ph">Seating · Default style <span class="grow"></span><button type="submit" class="primary">Save</button></div>
      <div class="pb padded">
        <div class="grid2">
          <label class="field"><span>Chair</span><select id="st-chair"><option value="stool">Low-back stool</option><option value="lounge">Lounge chair</option></select></label>
          <label class="field"><span>Upholstery</span><input type="color" id="st-upholstery"></label>
          <label class="field"><span>Frame</span><select id="st-frame"><option value="brass">Brass</option><option value="gold">Gold</option><option value="chrome">Chrome</option><option value="gunmetal">Gunmetal</option><option value="copper">Copper</option><option value="black">Black</option></select></label>
          <label class="field"><span>Back height (×)</span><input type="number" id="st-back" min="0.6" max="1.4" step="0.05"></label>
          <label class="field"><span>Size (×)</span><input type="number" id="st-size" min="0.85" max="1.15" step="0.05"></label>
          <label class="field"><span>Sitting down</span><select id="st-sit"><option value="swivel">Swivel</option><option value="pull">Pull out</option><option value="glide">Glide (no chair animation)</option></select></label>
          <label class="field"><span>Sit speed (×)</span><input type="number" id="st-sit_speed" min="0.5" max="1.5" step="0.1"></label>
          <label class="field"><span>Slot screen opens</span><select id="st-slot_screen"><option value="after_sit">After the sit</option><option value="at_once">At once</option></select></label>
          <label class="field"><span>Craps standing spot</span><select id="st-craps_spot"><option value="footprints">Footprints</option><option value="spotlight">Spotlight</option><option value="medallion">Medallion</option><option value="ring">Ring</option></select></label>
        </div>
        <p class="hint">Every table and slot cabinet uses this style; saving updates the floor straight away. The card tables and Roulette take their chairs' frame and upholstery from their table style (Tables tab); these colour the slot stools.</p>
      </div>
    </form>
    <form class="panel" id="bank-form">
      <div class="ph">Bank <span class="grow"></span><button type="submit" class="primary">Save</button></div>
      <div class="pb padded">
        <div class="grid2">
          <label class="field"><span>New characters' bank, Easy (£)</span><input type="number" id="b-start_bank_easy" step="1"></label>
          <label class="field"><span>New characters' bank, Normal (£)</span><input type="number" id="b-start_bank" step="1"></label>
          <label class="field"><span>New characters' bank, Hard (£)</span><input type="number" id="b-start_bank_hard" step="1"></label>
          <label class="field"><span>New characters' cash in hand (£)</span><input type="number" id="b-start_hand" min="0" step="1"></label>
          <label class="field"><span>Withdraw only while holding under (£)</span><input type="number" id="b-hand_under" min="0" step="1"></label>
          <label class="field"><span>Overdrawn: wait between withdrawals (min)</span><input type="number" id="b-cooldown_min" min="0" step="1"></label>
          <label class="field"><span>Withdrawal limit (£)</span><input type="number" id="b-low_cap" min="50" step="50"></label>
          <label class="field"><span>Bigger withdrawals from a bank of (£)</span><input type="number" id="b-threshold" min="0" step="50"></label>
          <label class="field"><span>Bigger: wait between them (min)</span><input type="number" id="b-big_wait_min" min="0" step="1"></label>
          <label class="field"><span>Bigger: half the bank, rounded down to (£)</span><input type="number" id="b-big_step" min="50" step="50"></label>
        </div>
        <p class="hint">The lobby's ATM moves money between a player's bank and the cash they play with. Withdrawals come in £50 notes, so the limit and rounding are multiples of £50. With a bank at the threshold or more, one withdrawal per wait may be up to half the bank, rounded down (£2,000 → £1,000, £6,700 → £3,000); between them the usual limit applies. The bank can go overdrawn without limit; the wait applies only while it is. A new character's bank depends on the difficulty picked for it; the ATM's rules are the same for every difficulty. Changes apply to the next use of the ATM, and the starting amounts to characters made from now on.</p>
      </div>
    </form>
    <div class="panel">
      <div class="ph">This browser</div>
      <div class="pb padded">
        <label class="field"><span>Floor plan scroll zoom: <b id="p-zoom-out"></b> per wheel notch</span>
          <input type="range" id="p-zoom" min="${ZOOM_STEP.min}" max="${ZOOM_STEP.max}" step="1"></label>
        <p class="hint">Saved as you move it (no Save needed) and kept in this browser only. Lower zooms more gently; ${ZOOM_STEP.default}% is the default (it used to be 15%).</p>
      </div>
    </div>
  </div>`;
  const $ = s => h.view.querySelector(s);
  const zoom = $("#p-zoom"), saved = +H.remember.get("zoom_step");
  const showZoom = () => { $("#p-zoom-out").textContent = zoom.value + "%"; };
  zoom.value = saved >= ZOOM_STEP.min && saved <= ZOOM_STEP.max ? saved : ZOOM_STEP.default; showZoom();
  zoom.addEventListener("input", () => { H.remember.set("zoom_step", zoom.value); showZoom(); });
  $("#s-npcs-on").addEventListener("change", async e => {
    const on = e.target.checked;
    try {
      await H.api("PUT", "/api/npc-settings", {npcs_on: on});
      H.status(on ? "NPCs switched on: they'll come in one at a time." : "NPCs switched off: they'll finish their round and leave.", "ok");
    } catch (err) { e.target.checked = !on; H.status(err.message, "warn"); }
  });
  $("#settings-form").addEventListener("submit", async e => {
    e.preventDefault();
    try {
      await H.api("PUT", "/api/npc-settings", {population: +$("#s-population").value, regular_cooldown: +$("#s-regular").value,
        cooldown_min: [+$("#s-cool-lo").value, +$("#s-cool-hi").value], bust_cooldown_min: [+$("#s-bust-lo").value, +$("#s-bust-hi").value],
        dealer_shift_min: +$("#s-shift").value, dealer_stagger_min: +$("#s-stagger").value});
      H.status("Settings saved.", "ok");
    } catch (err) { H.status(err.message, "warn"); }
  });
  $("#bank-form").addEventListener("submit", async e => {
    e.preventDefault();
    const body = {};
    for (const k of BANK) body[k] = +$("#b-" + k).value;
    try {
      await H.api("PUT", "/api/bank-settings", body);
      H.status("Bank settings saved.", "ok");
    } catch (err) { H.status(err.message, "warn"); }
  });
  $("#seating-form").addEventListener("submit", async e => {
    e.preventDefault();
    const body = {};
    for (const k of SEATING) body[k] = NUMBERS.includes(k) ? +$("#st-" + k).value : $("#st-" + k).value;
    try {
      await H.api("PUT", "/api/seating/styles/default", body);
      H.status("Seating saved.", "ok");
    } catch (err) { H.status(err.message, "warn"); }
  });
}

const BANK = ["start_bank_easy", "start_bank", "start_bank_hard", "start_hand", "hand_under", "cooldown_min", "low_cap", "threshold", "big_wait_min", "big_step"];
const SEATING = ["chair", "upholstery", "frame", "back", "size", "sit", "sit_speed", "slot_screen", "craps_spot"];
const NUMBERS = ["back", "size", "sit_speed"];

export async function load() {
  const $ = s => H.view.querySelector(s);
  try {
    const s = await H.api("GET", "/api/npc-settings");
    $("#s-npcs-on").checked = s.npcs_on;
    $("#s-population").value = s.population; $("#s-regular").value = s.regular_cooldown;
    $("#s-cool-lo").value = s.cooldown_min[0]; $("#s-cool-hi").value = s.cooldown_min[1];
    $("#s-bust-lo").value = s.bust_cooldown_min[0]; $("#s-bust-hi").value = s.bust_cooldown_min[1];
    $("#s-shift").value = s.dealer_shift_min; $("#s-stagger").value = s.dealer_stagger_min;
    const st = (await H.api("GET", "/api/seating")).styles.default;
    for (const k of SEATING) $("#st-" + k).value = st[k];
    const b = await H.api("GET", "/api/bank-settings");
    for (const k of BANK) $("#b-" + k).value = b[k];
    H.status("Settings loaded.");
  } catch (e) { H.status("Couldn't load settings: " + e.message, "warn"); }
}
