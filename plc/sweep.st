(* --- Initialise on first scan --- *)
IF NOT bInitDone THEN
    iCurrentK      := 500;
    iStepCount     := 0;
    bSweepActive   := TRUE;
    bSweepComplete := FALSE;
    bStepDone      := FALSE;
    bInitDone      := TRUE;
END_IF;

(* --- X5 safety trip: kill sweep immediately --- *)
IF gSafetyTrip THEN
    bSweepActive    := FALSE;
    bSweepComplete  := FALSE;
    gContactor      := FALSE;
    gW5Enable       := FALSE;
    gW5Setpoint     := 0;
    RETURN;
END_IF;

(* --- Step timer: IN goes FALSE when step done to auto-reset --- *)
tStepTimer(IN := bSweepActive AND NOT bSweepComplete AND NOT bStepDone AND NOT tStepTimer.Q,
           PT := T#30S);

(* --- Detect timer expiry --- *)
IF tStepTimer.Q THEN
    bStepDone := TRUE;
END_IF;

(* --- Main sweep logic --- *)
IF bSweepActive AND NOT bSweepComplete THEN

    (* Energise contactor and W5 enable *)
    gContactor  := TRUE;
    gW5Enable   := TRUE;

    (* Write current K value to W5 analogue input *)
    gW5Setpoint := iCurrentK;

    (* Process step completion *)
    IF bStepDone THEN
        bStepDone := FALSE;

        IF iStepCount >= 70 THEN
            (* Sweep complete *)
            bSweepComplete  := TRUE;
            bSweepActive    := FALSE;
            gContactor      := FALSE;
            gW5Enable       := FALSE;
            gW5Setpoint     := 0;

        ELSE
            (* Advance to next step *)
            iCurrentK  := iCurrentK + 50;
            iStepCount := iStepCount + 1;

        END_IF;

    END_IF;

ELSIF bSweepComplete THEN

    (* Keep outputs off, zero setpoint *)
    gContactor  := FALSE;
    gW5Enable   := FALSE;
    gW5Setpoint := 0;

END_IF;

