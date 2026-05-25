(* ================================================================== *)
(* TCU HEAT LOADER — Structured Text                                  *)
(* FP0-C14CRS                                                         *)
(* Functions:                                                         *)
(*   - PT100 CH0 reading → outletTempRaw (DT3)                       *)
(*   - RPi writes K value (0-4000) to DT100 via MEWTOCOL             *)
(*   - DT100 passed directly to WY4 (W5 SCR setpoint)                *)
(*   - Contactor Y0, Y1 LED indicator, W5 enable Y4                  *)
(*   - X5 safety interlock                                            *)
(* GT02 HMI removed — RPi touchscreen is now the operator interface  *)
(* ================================================================== *)

(* ------------------------------------------------------------------ *)
(* GLOBAL VARIABLES — declare in Global Variables table               *)
(*                                                                    *)
(* Class         Identifier          FP Addr  IEC Addr   Type        *)
(* VAR_EXTERNAL  rtdConvComplete1    X3F      %IX3.15    BOOL        *)
(* VAR_EXTERNAL  rtdConvComplete2    X3E      %IX3.14    BOOL        *)
(* VAR_EXTERNAL  rtdChannelSelect    X3D      %IX3.13    BOOL        *)
(* VAR_EXTERNAL  safetyTrip         X5       %IX0.5     BOOL        *)
(* VAR_EXTERNAL  rtdRawData         WX2      %IW2       INT         *)
(* VAR_EXTERNAL  rtdMaskedData      DT4      %MW4       WORD        *)
(* VAR_EXTERNAL  outletTempRaw      DT3      %MW3       INT         *)
(* VAR_EXTERNAL  rpiSetpoint        DT100    %MW100     INT         *)
(* VAR_EXTERNAL  w5Setpoint         WY4      %QW4       INT         *)
(* VAR_EXTERNAL  contactor          Y0       %QX0.0     BOOL        *)
(* VAR_EXTERNAL  contactorMirror    Y1       %QX0.1     BOOL        *)
(* VAR_EXTERNAL  w5Enable           Y4       %QX0.4     BOOL        *)
(* ------------------------------------------------------------------ *)

(* --- PT100 CH0 reading → outletTempRaw (DT3) --- *)
IF NOT rtdConvComplete1 AND NOT rtdConvComplete2 THEN
    outletTempRaw := rtdRawData;
    IF NOT rtdChannelSelect THEN
        rtdMaskedData := rtdMaskedData AND 16#FFFF;
    ELSE
        rtdMaskedData := rtdMaskedData OR 16#0000;
    END_IF;
END_IF;

(* --- X5 safety: zero setpoint and kill all outputs immediately --- *)
IF safetyTrip THEN
    w5Setpoint      := 0;
    contactor       := FALSE;
    contactorMirror := FALSE;
    w5Enable        := FALSE;
    RETURN;
END_IF;

(* --- Pass RPi setpoint (DT100) directly to W5 (WY4) --- *)
(* RPi writes K value 0-4000 to DT100 via MEWTOCOL        *)
(* K=0 means heater off — contactor stays on              *)
w5Setpoint := rpiSetpoint;

(* --- Contactor Y0: on when RPi has sent a non-zero setpoint --- *)
contactor := rpiSetpoint > 0;

(* --- Y1: mirrors contactor, blinks via sys_bPulse2s --- *)
contactorMirror := contactor AND sys_bPulse2s;

(* --- W5 enable Y4: same as contactor --- *)
w5Enable := rpiSetpoint > 0;
