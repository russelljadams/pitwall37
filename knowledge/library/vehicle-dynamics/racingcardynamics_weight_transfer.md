# Weight Transfer in Race Cars
**Source:** Racing Car Dynamics
**URL:** https://racingcardynamics.com/weight-transfer/

## Overview

Lateral weight transfer (or lateral load transfer) refers to the amount of change on the vertical loads of the tyres due to the lateral acceleration imposed on the centre of gravity of the vehicle. When a car corners, vertical load increases on the outer tires while decreasing on inner tires.

## Fundamental Equation

The total lateral load transfer is:

**dW = (W x Ay x h) / t**

Where:
- W = car weight
- Ay = lateral acceleration
- h = center of gravity height
- t = track width

## The Three Mechanisms of Lateral Load Transfer

### 1. Unsprung Mass Component

This involves the lateral acceleration acting on the center of gravity of the unsprung components. While straightforward to calculate, it is the least useful as a setup tool because modifications would negatively affect wheel hop characteristics and tire contact.

### 2. Kinematic (Direct Lateral Force) Component

This arises from lateral force acting on the sprung mass, transferred through roll centers. The equation involves roll center height and sprung weight distribution. Increasing roll centre height in one axle decreases the lateral weight transfer on the opposite axle.

### 3. Elastic (Roll Angle) Component

This component results from chassis roll during cornering, which compresses outer springs and extends inner ones. It is the most useful component as a setup tool, since it is the easiest to change when antiroll devices are present.

## Steady-State Pair Analysis

Engineers analyze tyre pairs (front or rear) rather than individual tires. The Fraction Load Transfer (FLT) represents the ratio of vertical load difference to axle weight. This analysis produces potential diagrams showing how tire pairs generate lateral force across different load transfer scenarios.

## Practical Setup Applications

**Roll Stiffness Distribution**: Adjusting front-to-rear roll stiffness ratio is the most practical method for tuning lateral load transfer. Lateral load transfer in one end of the car will change with the proportion of the roll stiffnesses on that axle, not the roll stiffnesses themselves.

**Antiroll Bar Adjustments**: Modern cars often feature adjustable antiroll bars that allow drivers to modify stiffness without replacing components.

**Roll Center Height**: Changing suspension geometry alters roll center positions, which affects both kinematic and elastic components in opposite directions.

## Important Limitation

These principles apply specifically to steady-state cornering. Transient lateral load transfer is an important aspect of vehicle setup but requires separate analysis involving damper characteristics.

## Practical Example

For a driver complaining about oversteer in slow corners, the recommended solution involves shifting roll rate distribution to the front, by either stiffening the front antiroll bar or softening the rear to reduce rear lateral load transfer relative to the front.

## Key Takeaway

Rather than changing total lateral load transfer (which requires altering track width or center of gravity height), engineers optimize how that transfer distributes between front and rear axles through suspension adjustments — primarily antiroll bar stiffness and roll center positioning.
