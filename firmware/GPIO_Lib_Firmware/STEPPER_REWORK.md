

# Stepper and Encoder Feature Plan

## Primary goals
- Support independent and coordinated (uniform) motion for multiple steppers.
- Keep user-facing units in mm and revolutions while preserving precise step-domain control internally.
- Make microstepping an explicit multiplier of base resolution (base = full-step units).
- Support optional feedback devices for position correction and closed-loop hold.
- Add command queueing with look-ahead blending near deceleration points.
- Keep host API simple while firmware remains robust and deterministic.

## Scope and non-goals
- In scope: Stepper motion core, homing, queueing, synchronization, feedback mapping, PID hold.
- In scope: Host API consistency and command-range definition.
- Out of scope for v1: full trajectory planner (G-code style jerk-limited path engine).
- Out of scope for v1: dynamic re-parenting of one stepper to multiple sync groups.

## Core model

### 1) Stepper runtime entities
- `StepperUnit`: one motor driver instance (enable/step/dir + optional microstep pins).
- `MotionProfile`: configured limits in mm domain and rev domain.
- `MoveQueue`: bounded FIFO of target moves with per-command overrides.
- `SyncGroup`: optional group for uniform coordinated start and shared completion time.
- `FeedbackDevice`: optional position source (encoder, potentiometer, etc.) with unit mapping.

### 2) Unit conventions
- Internal truth: steps (fixed-point accumulator).
- User-facing reads/writes: mm and rev.
- `steps_per_mm` and `steps_per_rev` are specified in full steps.
- Effective resolution:
  - `effective_steps_per_mm = steps_per_mm * microstep_divisor`
  - `effective_steps_per_rev = steps_per_rev * microstep_divisor`
- Position APIs always return values derived from effective resolution.

### 3) Motion behavior contract
- `move_to_*` is absolute-position by default.
- Each command can override speed/accel for that move only.
- If no override is provided, configured defaults are used.
- `stop()` performs controlled deceleration, not hard immediate pulse cut.
- Queue look-ahead rule: when current segment enters decel window, scheduler checks next command and blends if legal under accel/velocity constraints.

## Uniform motion mode

### Concept
If multiple steppers have uniform mode enabled and are triggered together, they finish their queued front command at the same time, even if distances differ.

### Rules
- Sync is opt-in per stepper (`set_uniform_mode(True)`).
- A stepper can only be in one sync group at a time.
- Group launch happens only when all participating steppers are in a launchable state.
- Per-axis limits are still enforced; if one axis saturates, group speed is reduced to the highest common feasible profile.
- If uniform mode is disabled, the stepper executes independently as soon as command arrives.

## Feedback and closed-loop behavior

### Feedback mapping
- Feedback is attached per stepper.
- Mapping supports both domains:
  - `mm_per_unit`
  - `rev_per_unit`
- Firmware can expose both raw feedback units and mapped values.

### Closed-loop modes
- Open-loop: pulse engine only; feedback is informational.
- Assist mode: feedback can periodically rebase software position.
- Hold mode: PID position hold when motor is idle or at target.

### Safety constraints
- Closed-loop never violates configured max speed/acceleration constraints.
- If feedback invalid/stale, controller drops to open-loop and reports warning/error state.

## Homing model
- Homing config is optional and persistent per stepper instance.
- Supports one-switch, two-switch or absolute value (e.g., encoder) workflows.
- Homing completes by setting both step-domain and unit-domain positions.
- Bounds protection:
  - stop and error if configured max travel is exceeded without switch trigger.
- `is_homed()` reflects successful completion of latest homing cycle.

## Host API

### Base Stepper lifecycle (0x0320-0x032F)
- `stepper = gpio.Stepper(gpio, <pins>)`
- `stepper = gpio.Stepper.<SubClassStepper>(...)`
- `stepper.setup()`
- `stepper.invert_direction(False/True)`
- `stepper.set_uniform_mode(False/True)`
- `stepper.set_microstepping(GPIO_Lib.Stepper.MICROSTEPS.X1_64)`
- `stepper.config_homing(...)`
- `stepper.home()`
- `stepper.is_homed()`
- `stepper.stop()`
- `stepper.get_position_mm()`
- `stepper.get_position_rev()`
- `stepper.get_status()`

### MM motion domain (0x0330-0x033F)
- `stepper.configure_motion_mm(steps_per_mm, max_speed_mm_s, acceleration_mm_s2, max_length_mm=None)`
- `stepper.move_to_mm(target_mm, speed_mm_s=None, acceleration_mm_s2=None, move=True)`
- `stepper.set_position_mm(current_mm)`
- `stepper.set_speed_mm_s(speed_mm_s)`
- `stepper.set_acceleration_mm_s2(acceleration_mm_s2)`

### REV motion domain (0x0340-0x034F)
- `stepper.configure_motion_rev(steps_per_rev, max_speed_rpm, acceleration_rpm_s, max_revs=None)`
- `stepper.move_to_rev(target_rev, speed_rpm=None, acceleration_rpm_s=None, move=True)`
- `stepper.set_position_rev(current_rev)`
- `stepper.set_speed_rpm(speed_rpm)`
- `stepper.set_acceleration_rpm_s(acceleration_rpm_s)`

### Feedback domain (0x0350-0x035F)
- `stepper.attach_feedback_device(feedback_device, pin_or_config)`
- `stepper.set_mapping_value_mm_per_unit(feedback_units, mm)`
- `stepper.set_mapping_value_rev_per_unit(feedback_units, rev)`
- `stepper.detach_feedback_device()`
- `stepper.get_feedback_position_mm()`
- `stepper.get_feedback_position_rev()`
- `stepper.set_position_from_feedback()`
- `stepper.enable_closed_loop_control(False/True)`
- `stepper.set_closed_loop_parameters(kp, ki, kd)`

## Firmware architecture (RTOS model)
- `StepperTask` owns stepper state and queue processing.
- `EncoderTask` or shared feedback polling task updates feedback snapshots.
- `DispatchTask` parses and routes commands only; no direct pulse generation.
- All responses go via TX queue path.
- Use bounded queues and report overflow with explicit error codes.

## Command policy
- Define command IDs around the v2 feature model.
- Keep command ranges aligned with host-side APIs and examples.
- Version-gate behavior as v2 in firmware and host package releases.

## State machine
- `UNCONFIGURED` -> `IDLE` -> `MOVING` -> `IDLE`
- `IDLE` -> `HOMING` -> `IDLE`
- Any state -> `ERROR` on fault
- `ERROR` -> `IDLE` only after explicit clear/reset command

## Error model
- Include explicit fault reasons in status:
  - queue overflow
  - homing timeout / travel limit exceeded
  - invalid feedback mapping
  - closed-loop instability / feedback timeout
  - illegal command in current state

## Implementation plan

### Phase A: API and command contract
- Freeze v2 API signatures and command IDs.
- Add/verify `get_status()` with position, speed, queue depth, state, fault code.
- Align firmware handlers and host wrappers to the finalized API.

### Phase B: Motion core
- Finalize trapezoidal planner in step-domain fixed-point.
- Implement queue look-ahead blend at decel boundary.
- Add strict per-axis limit enforcement.

### Phase C: Uniform group coordinator
- Implement sync-group object and launch barrier.
- Add common-time solver with per-axis saturation handling.
- Add coordinated queue launch behavior for mm and rev commands.

### Phase D: Feedback and closed-loop
- Standardize feedback device interface.
- Implement mapping validation and stale-signal detection.
- Implement PID hold mode and safe fallback to open-loop.

### Phase E: Homing and safety
- Implement one-switch and two-switch homing workflows.
- Enforce travel bounds and homing timeout protections.
- Add deterministic recovery and clear-fault behavior.

### Phase F: Validation and documentation
- Host-side integration tests (single axis, multi-axis sync, queue blend, homing, feedback).
- Long-run stress tests for queue pressure and command throughput.
- Update examples and docs for v2 API usage.

## Acceptance criteria
- Two or more steppers in uniform mode reach targets simultaneously within configured tolerance.
- Motion in mm and rev remains consistent with microstepping changes.
- Queue blending reduces stop-and-go transitions without overshoot faults.
- Homing is repeatable and bounded by configured safety limits.
- Closed-loop hold maintains position under expected disturbance limits.
- Status command always reports actionable state/fault information.

## Open decisions to finalize
- Decide fixed-point format for internal step-domain math.
- Decide default queue depth and overflow strategy (reject newest vs drop oldest).
- Decide whether `move=True` should trigger group launch immediately or only arm until explicit sync trigger.
- Decide minimum supported feedback update rate for stable closed-loop hold.
