(* ================================================================== *)
(* TCU HEAT LOADER — Autonomous K Sweep                               *)
(* FP0-C14CRS                                                         *)
(*                                                                    *)
(* Sweeps K500 → K4000 in K100 steps, 5 min per step, loops forever. *)
(* 36 steps × 5 min = 180 min per loop.                              *)
(*                                                                    *)
(* Uses TMY T0 (100ms resolution) for step dwell.                    *)
(* 5 min = 300 s = K3000 on TMY.                                     *)
(*                                                                    *)
(* POU Header — declare these local variables:                        *)
(*   VAR                                                              *)
(*     stepDone : BOOL;                                               *)
(*   END_VAR                                                          *)
(*                                                                    *)
(* Global Variables table — add these entries:                        *)
(*   Class         Identifier       FP Addr  IEC Addr   Type         *)
(*   VAR_EXTERNAL  rtdConvComplete1 X3F      %IX3.15    BOOL         *)
(*   VAR_EXTERNAL  rtdConvComplete2 X3E      %IX3.14    BOOL         *)
(*   VAR_EXTERNAL  rtdRawData       WX2      %IW2       INT          *)
(*   VAR_EXTERNAL  outletTempRaw    DT3      %MW3       INT          *)
(*   VAR_EXTERNAL  sweepStep        DT200    %MW200     INT          *)
(*   VAR_EXTERNAL  w5Setpoint       WY4      %QW4       INT          *)
(*   VAR_EXTERNAL  contactor        Y0       %QX0.0     BOOL         *)
(*   VAR_EXTERNAL  contactorMirror  Y1       %QX0.1     BOOL         *)
(*   VAR_EXTERNAL  w5Enable         Y4       %QX0.4     BOOL         *)
(*                                                                    *)
(* POU Header — declare these constants:                              *)
(*   VAR_CONSTANT                                                     *)
(*     K_START   : INT := 500;                                        *)
(*     K_STEP    : INT := 100;                                        *)
(*     K_MAX     : INT := 4000;                                       *)
(*     NUM_STEPS : INT := 36;                                         *)
(*     DWELL_TMY : INT := 3000;  (* 5 min = K3000 at 100ms *)        *)
(*   END_VAR                                                          *)
(* ================================================================== *)

(* ── PT100 CH0 reading → outletTempRaw (DT3) ───────────────────── *)
IF NOT rtdConvComplete1 AND NOT rtdConvComplete2 THEN
    outletTempRaw := rtdRawData;
END_IF;

(* ── Clamp sweepStep to valid range 0..NUM_STEPS-1 ──────────────── *)
IF sweepStep < 0 OR sweepStep >= NUM_STEPS THEN
    sweepStep := 0;
END_IF;

(* ── Compute current K value ─────────────────────────────────────── *)
w5Setpoint := K_START + (sweepStep * K_STEP);

(* ── Contactor and W5 always on during sweep ────────────────────── *)
contactor       := TRUE;
w5Enable        := TRUE;
contactorMirror := sys_bPulse2s;

(* ── Step dwell timer — TMY T0, 100ms resolution ───────────────── *)
(* Timer auto-resets each scan cycle until it expires (T0 goes TRUE) *)
TMY(T0, DWELL_TMY);

(* ── On timer expiry, advance to next step ──────────────────────── *)
stepDone := T0;
IF stepDone THEN
    IF sweepStep >= NUM_STEPS - 1 THEN
        sweepStep := 0;
    ELSE
        sweepStep := sweepStep + 1;
    END_IF;
END_IF;
