# PitWall37 Anti-BS Engineering Plan

## North Star

Use the LLM as a race-engineering interface, not a race-engineering authority.

PitWall37 should do five jobs:

1. Store everything.
2. Surface patterns fast.
3. Generate testable hypotheses.
4. Force disciplined experiments.
5. Measure what actually made the driver faster.

If the system goes beyond that and starts freewheeling, it becomes noise.

## Output Contract

Every meaningful recommendation must include:

- `Observation`: exact evidence from telemetry, lap times, setup values, or prior sessions.
- `Inference`: what the evidence probably means.
- `Confidence`: `high`, `medium`, or `low`.
- `Action`: one concrete change only.
- `Validation`: what metric must improve next run.

Every recommendation must also declare source tags:

- `DATA`: historical DB, lap telemetry, or live bridge state.
- `MODEL`: deterministic setup rules and constraints from `setup_model.py`.
- `HYPOTHESIS`: plausible but not yet validated.
- `REFERENCE`: outside docs, guides, or published engineering references.

If a reply cannot produce both `Observation` and `Validation`, it should not give advice.

## Hard Rules

- No generic coaching language without evidence.
- No multi-variable setup changes unless the user explicitly asks for a broad swing.
- No pretending that a mechanical explanation is validated just because it sounds coherent.
- Setup and driving advice stay separate unless the data proves they are interacting.

## Build Plan

### 1. Recommendation Scorecard

Persist every material recommendation with:

- source
- session and track context
- category and focus area
- observation, inference, confidence
- single action
- validation plan
- later grade: improved / no change / worse / mixed

Goal: make the engineer auditable.

### 2. Experiment Log

Track every serious test as an experiment:

- driver or setup
- exact change
- baseline metric
- expected metric
- actual metric
- result
- confidence before and after

Goal: turn improvement into a chain of validated experiments instead of vibes.

### 3. Split Coaching Roles

Keep two different mental models:

- `Driving Coach`: braking, release, minimum speed, throttle timing, confidence, consistency.
- `Setup Engineer`: platform, aero balance, ride height, diff, damping, pressures.

Goal: stop the system from smearing driver errors and car balance issues into one blob.

### 4. Weakness Taxonomy

Classify time loss and development themes into:

- high-speed aero
- medium-speed rotation
- slow-speed traction
- chicane direction change
- brake stability
- brake release rotation
- exit commitment
- consistency
- setup platform
- setup aero balance
- setup diff
- setup damping
- setup tire pressure
- setup ride height

Goal: build a transferable driver model across tracks instead of a pile of lap notes.

### 5. Driver Model

Generate a rolling driver model from validated history only.

Examples:

- "Brake stability changes improved 4 of the last 5 times."
- "Exit commitment remains a global weakness across Road Atlanta and Mugello."
- "Rear platform changes helped only when front RH at speed stayed above the safety floor."

Goal: extract real truths from the driver's own data.

## Training Loop

1. Run a baseline.
2. Diagnose the single biggest time loss.
3. Test one variable.
4. Validate the outcome.
5. Capture the result permanently.

That is the loop.

## Product Principle

The repo is successful only if it makes the driver faster.

If the AI generates words but does not improve adaptation speed, repeatability, technical correctness, or honesty, it is failing the mission.
