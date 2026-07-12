# Task: Worker Poll Interval Finite Validation

## Brief task description

Reject non-finite worker polling interval configuration values before they reach the polling loop.

## Implementation summary

Used `math.isfinite` with the existing positive-value check in worker settings. `NaN`, positive
infinity, negative infinity, zero, and negative values now raise the unchanged configuration error.
