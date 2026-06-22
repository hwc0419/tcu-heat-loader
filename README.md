# System Overview
This page explains what changed in the system architecture this session, what the current setup actually is, and why the original 2kW heater circuit is still worth documenting even though the AMAT0 Stress Test no longer uses it directly.

## What changed from the original diagram
<img width="960" height="720" alt="System_Overview" src="https://github.com/user-attachments/assets/f082b309-741d-4016-b565-228bd8e0c11d" />
Two changes were made to the architecture diagram above, relative to the version that predates the AMAT0 pivot:

**A new `:AMAT0` block was added, separate from the existing `:Heater` block.** These are two distinct pieces of hardware, not a relabeling of one into the other. The original `:Heater` block — the 2kW resistive heater driven by the `:Power Regulator` (W5SP/W5SZ), fed by NFB/MC, and controlled via the PLC's DC I/O current loop — is still physically present and wired exactly as before. AMAT0 is a separate pre-heated tank, heated externally by its own dedicated 2kW heater before each test run, then disconnected from that heater and connected to the TCU's water circuit for the burst-and-decay test itself. AMAT0 is not part of the W5/NFB/MC control chain at all — see [AMAT0 Test](AMAT0‐Test) for the full procedure.

**The Power Meter's connection was corrected to match reality.** The diagram now shows the PZEM-004T connecting via direct RPi GPIO UART, with no USB or RS485 adapter in the path, matching [Hardware and Wiring](Hardware-and-Wiring)'s existing description. An earlier version of this diagram showed an RS485-to-USB adapter (a cp2102) routing the Power Meter through a USB-A port — that adapter is real hardware, but it's currently disconnected: the PZEM's CT resistor overheated during a previous installation attempt, and the cp2102 link was never reconnected afterward. The diagram now carries an explicit note to this effect so it doesn't silently imply a working connection that isn't there.

## Current setup, in short

The TCU's own water circuit and 2kW heater remain wired exactly as they were before this session's pivot — nothing about that physical circuit was touched. What changed is purely on the test-methodology side: the TCU++ app no longer runs a sustained heat-load test against that heater (the old stepped 0–2000W test), because sustained heat load on the TCU could no longer be guaranteed in the test rig. Instead, the AMAT0 tank — heated separately, then connected only for the duration of a burst-and-decay measurement — is now the primary test fixture, with its own dedicated tab and growing reference dataset.

The AMAT0 test's own methodology has since been substantially redesigned too: the original z-score/statistical-distribution approach (and its adaptive "log until the dataset's historical max" stopping rule) was replaced with a much simpler range-based design after reviewing real test data, and the test now runs for a fixed, operator-configured duration. The tab itself was renamed "AMAT0 Stress Test" → "AMAT0 Test" and split into two sub-tabs — Main (the gated, scored test) and Reference (for building the comparison dataset). See [AMAT0 Test](AMAT0‐Test) for the current methodology in full.

The 2kW heater circuit itself, the PLC's continuous K-based control of it, and the whole RPi↔PLC MEWTOCOL link are all still fully functional and untouched by this pivot. They're simply not what the current test exercises by default.

## The 2kW heater can still be used — it just needs repiping

Because AMAT0 and the 2kW heater's circuit both connect to the same point on the TCU's water loop, only one can be connected at a time. Using the 2kW heater again after AMAT0 has been in use means physically disconnecting AMAT0 and re-plumbing the water lines back to the heater circuit — there's no software switch for this, it's a manual piping change on the rig itself.

This matters beyond just restoring the old test: the 2kW heater, the W5SP/W5SZ phase-angle power regulator, and the PLC's continuous 0–4000 K-value control loop over MEWTOCOL are a general-purpose heat-load simulation capability, not something specific to the TCU project. The same control chain — RPi writes a K value to PLC DT100 over MEWTOCOL, the PLC drives the W5 via its FP0-A21 analogue output, the W5 phase-fires the heater — could drive a 2kW resistive load for a different heat-load simulation project entirely, with no changes to the PLC program itself.

Because of that reuse potential, the documentation explaining how to program the PLC for this kind of heater control is worth keeping accurate and discoverable even while this specific project's day-to-day testing has moved to AMAT0. The relevant pages are:

- [Hardware and Wiring](Hardware-and-Wiring) — the W5 terminal connections, the PLC I/O summary (Y0 contactor, Y4 run enable, WY4/FP0-A21 analogue output, the MEWTOCOL COM port settings), and the original fixed three-stage scheme this replaced.
- [PLC Ladder Logic Analysis](PLC-Ladder-Logic-Analysis) — the original 1325-step ladder program's structure, including why it can no longer be recompiled or reflashed (FPWIN Pro 7 strips the HMI stage-select registers on recompile), for anyone who needs to understand the PLC's prior logic before extending it.
- [MEWTOCOL Debugging](MEWTOCOL‐Debugging) — the current RPi↔PLC communication link, the signal integrity issue that was found there, and how it was fixed.
- [K↔Watts Conversion](K‐Watts‐Conversion) — the empirical K-to-watts mapping for this specific heater/W5 pairing. A different heat-load project reusing this control chain with a different heater would need its own sweep table, since this one is specific to the Reach Electrical 262627 2kW element used here, but the same piecewise-linear-interpolation approach (and the reasoning for why a closed-form model isn't used) would carry over directly.

## Outstanding project items

For reference, the broader list of work still remaining on this project beyond the test-methodology pivot:

- PZEM-004T power meter is non-functional (CT resistor overheated) — needs a replacement power meter installed.
- SD card approval from Ronald is still pending.
- TCU↔PLC serial link has a high failure rate — the MEWTOCOL signal integrity issue is diagnosed (see [MEWTOCOL Debugging](MEWTOCOL‐Debugging)) but the planned fix (a self-powered USB-RS232 adapter in place of the current setup) hasn't been installed yet.
- The 15.6" touchscreen still needs to be mounted on the control panel.
- An inline PT100 temperature sensor near the TCU inlet pipe still needs to be installed.
