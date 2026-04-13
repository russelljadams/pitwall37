# Ride Height & Bottoming Out — Race Engineering Knowledge Base

> Compiled from professional race engineering sources, SAE research, OptimumG methodology,
> F1 technical analysis, and motorsport engineering education materials.
> Last updated: 2026-04-11

---

## 1. THE FUNDAMENTALS: WHY RIDE HEIGHT MATTERS

### The Core Trade-Off
Every race engineer faces the same fundamental tension: **lower ride height = more performance, but also more risk**. The benefits of running low are:

1. **Lower center of gravity** — reduces lateral weight transfer, increases cornering grip
2. **Enhanced ground effect** — air accelerates through the narrowing gap between floor and ground, creating low pressure (Venturi effect), generating downforce without drag penalty
3. **Better aero efficiency** — the underbody is the most aerodynamically efficient downforce-generating surface on the car
4. **Lower roll centers** — reduces body roll tendency

The risks:
1. **Bottoming out** — chassis/floor contacts track surface
2. **Aero stall** — flow separation under the floor when ride height drops below critical threshold
3. **Porpoising** — oscillatory cycle of aero stall and recovery
4. **Plank/skid block wear** — regulatory disqualification risk (F1: plank must retain 9mm of original 10mm)
5. **Insufficient suspension travel** — shock bottoming, loss of tire contact

### Static vs. Dynamic Ride Height
- **Static ride height**: What you set in the garage. Measured with car at rest, no driver, no fuel load adjustments.
- **Dynamic ride height**: The actual ground clearance at any moment on track. This is what matters.
- Dynamic ride height changes due to: downforce compression, braking pitch, cornering roll, bump/kerb impacts, fuel load, tire wear.

**Key insight**: A car set to 30mm static front ride height might run at 15-20mm at speed on straights due to aero loading compressing the springs.

---

## 2. BOTTOMING OUT — TYPES AND DISTINCTIONS

### Three Distinct Phenomena (Critical to Distinguish)

**a) Mechanical Bottoming**
- Suspension reaches end of travel (shock bottoms out)
- Caused by: insufficient spring rate, insufficient bump stop engagement, ride height too low for available travel
- Telemetry signature: suspension position abruptly reaches extreme value, suspension velocity drops to near zero (~8mm/s or less indicates bottoming)
- Consequence: momentary loss of tire contact patch, jarring impact, potential structural damage

**b) Aerodynamic Bottoming (Plank/Floor Contact)**
- The floor or plank physically contacts the track surface
- Does NOT necessarily mean aero stall — the car can scrape and still generate downforce
- This is what produces sparks (titanium skid blocks in F1)
- Some plank contact is expected and acceptable at professional level
- Consequence: plank wear, potential floor damage, but downforce may still be present

**c) Aerodynamic Stall / Porpoising**
- The most dangerous form — ride height drops below critical threshold where underbody airflow separates/stalls
- Downforce suddenly drops, car springs upward, airflow reattaches, car gets sucked back down — cycle repeats
- Frequency typically 1-7 Hz in F1 cars (6-7 Hz is dangerous for driver health)
- This is a purely aerodynamic phenomenon — you can have aero stall without physical contact
- Telemetry signature: oscillating ride height, oscillating downforce, characteristic pitch frequency

**The critical distinction for our engineering**:
- Occasional plank scrape on bumps/kerbs = NORMAL, possibly even desired (running at the limit)
- Sustained aero stall oscillation = DANGEROUS and slow
- Mechanical shock bottoming = setup error, needs fixing

---

## 3. ACCEPTABLE BOTTOMING LEVELS — WHAT THE PROS SAY

### The Honest Answer: There Is No Universal Percentage

Professional race engineering does not work with a single "acceptable bottoming percentage." The answer depends on:
- **Where** on track it occurs (kerb strike vs. mid-corner vs. straight)
- **Duration** of contact (transient bump vs. sustained scrape)
- **Frequency** (once per lap vs. every corner)
- **Consequence** (does it cause aero stall? does it unload tires?)
- **Speed** at which it occurs (low-speed bottoming is less consequential than high-speed)

### General Engineering Guidelines (Synthesized from Multiple Sources)

**Transient bottoming on kerbs/bumps:**
- Expected and acceptable in professional racing
- 1-3 brief contacts per lap over known bumps = NORMAL for a well-set-up car
- The car should recover immediately (no sustained oscillation)
- If the driver reports no handling disturbance, it's fine

**Sustained bottoming (floor scraping for extended distance):**
- NOT acceptable — causes plank wear, floor damage, inconsistent aero
- Even 0.5 seconds of sustained contact at 250 km/h = significant plank wear
- Target: zero sustained bottoming events

**Aero stall events:**
- Target: ZERO. Any aero stall oscillation means the setup needs changing.
- Even one porpoising cycle per lap is too many — it means the car is operating in the force-reduction region of the aero map

**Practical heuristic used by engineers:**
- If ride height at speed (minimum value on fastest straight) stays above the aero stall threshold → acceptable
- If minimum ride height occasionally touches the stall region on bumps but recovers within <100ms → marginal but possibly fast
- If the car enters sustained oscillation at any point → raise ride height or stiffen springs

### The "Fast Car Bottoms" Paradox
There IS a correlation between some bottoming and fast lap times:
- A car running RIGHT at the limit of acceptable ride height will occasionally scrape
- The fastest setup is often the one that JUST avoids aero stall while running as low as possible
- If a car never bottoms at all, it's probably running too high and leaving downforce on the table
- **The target is "barely not bottoming" rather than "never bottoming"**

---

## 4. METRICS PROFESSIONAL ENGINEERS TRACK

### Ride Height Channels (from telemetry/data acquisition)
1. **Front Ride Height Average** = (LF Ride Height + RF Ride Height) / 2
2. **Rear Ride Height Average** = (LR Ride Height + RR Ride Height) / 2
3. **Minimum Ride Height per Lap** — the absolute lowest point reached
4. **Ride Height at Speed** — ride height correlated with speed channel, shows aero compression
5. **Ride Height Variance (Standard Deviation)** — measures aero platform stability
6. **Rake Angle** — difference between front and rear ride height, critical for aero balance

### Bottoming Detection Metrics
1. **Suspension velocity near zero** — when suspension velocity drops below ~8 mm/s, the shock is at or near its physical limit (bottoming)
2. **Suspension position at extreme** — position channel hitting min/max value
3. **Vertical acceleration spikes** — sudden g-force spikes indicate floor/plank contact
4. **Plank wear measurement** — post-session physical measurement (F1: must retain 9mm of 10mm)

### Aero Platform Stability Metrics
1. **Ride height vs. speed scatter plot** — should show smooth, predictable relationship
2. **Pitch angle variation** — how much the car's nose-tail attitude changes through a lap
3. **Roll angle at speed** — lateral ride height difference in corners
4. **Aero balance shift** — how front/rear downforce balance changes with ride height (~5% balance shift per significant ride height change is typical)

### Frequency Domain Analysis
1. **Suspension natural frequency** — typical targets:
   - Low downforce cars: 2.0-2.5 Hz
   - High downforce formula cars: 3.0-5.0+ Hz
2. **Porpoising frequency** — if detected, typically 1-7 Hz
3. **Body vertical frequency** — should NOT show resonance peaks in the 1-7 Hz danger zone

---

## 5. GROUND EFFECT AND THE AERO MAP

### How Ground Effect Changes the Equation

Ground effect cars (like the F324) are fundamentally different from non-ground-effect cars:

**The Aero Map Concept:**
An aero map is a 3D visualization of downforce (and drag) as a function of front and rear ride height. It reveals:
- **Force enhancement region**: as ride height decreases, downforce increases (desirable operating range)
- **Peak downforce point**: the ride height that produces maximum downforce
- **Force reduction region**: below peak, further ride height decrease causes downforce LOSS (aero stall region)

**Critical insight**: The aero map is NOT symmetric. The transition from enhancement to reduction can be sudden ("switch-like" behavior), especially in cars with aggressive underbody tunnels.

### Static vs. Transient Aero Maps
Traditional aero maps show steady-state downforce at fixed ride heights. But real cars are vibrating:
- The car's underbody operates in a **transient** regime — the ride height is oscillating constantly
- A car might have its static ride height set in the enhancement region but transiently pass through the stall region on bumps
- **Transient aero maps** (frequency and amplitude dependent) are more accurate but harder to obtain
- Methods: CFD simulation with vibration inputs, wind tunnel with moving ground, track testing with accelerometers

### The Seal and the Stall
Ground effect works by "sealing" the edges of the floor/tunnels to prevent high-pressure air from leaking in:
- **Good seal** = strong pressure differential = high downforce
- **Broken seal** (ride height too high, or floor damaged) = pressure leak = reduced downforce
- **Stalled flow** (ride height too low) = flow separation in diffuser = sudden downforce loss

The F324's Venturi tunnels and diffuser are particularly sensitive to this because:
- The tunnels have specific design ride height ranges
- Floor edge vortices help maintain the seal — these are sensitive to ride height and yaw angle
- The diffuser adverse pressure gradient can cause flow detachment at very low ride heights

---

## 6. ENGINEERING SOLUTIONS — HOW PROS MANAGE IT

### Spring Rate Selection for Aero Cars
- Adding aero to a car requires **20-60% stiffer springs** vs. non-aero baseline
- Stiffer springs = less ride height variation = more consistent aero platform
- But too stiff = loss of mechanical grip, tire wear, poor drivability
- **Target**: spring rate that limits aero-induced ride height change to a controlled range while still allowing tire compliance

### Bump Stops / Packers
The primary tool for managing bottoming in formula cars:

**Function**: Progressive-rate secondary springs that engage near end of travel
- Start soft (~100 lb/in) and ramp up progressively
- Prevent shock from reaching physical limit
- Create a "two-stage" spring system: soft at low speed, stiff under aero load

**For aero cars specifically**:
- At low speed, main springs do the work (soft, compliant)
- At high speed, bump stops engage under aero load, providing platform support
- This lets you run lower static ride height while protecting against bottoming

**Packers vs. bump springs**:
- **Bump stops (rubber)**: high hysteresis (stiffer in compression than extension), progressive rate
- **Linear bump springs**: cleaner rate progression, easier to model, preferred for high-aero applications
- **Packers (parallel springs)**: rates ADD together when engaged (progressive gain vs. sudden switch)

### Third Spring / Heave Spring
Used in F1 and high-level formula cars:
- Controls heave (vertical) motion independently from roll
- T-bar linkage design: when both wheels compress equally (aero load), all springs work together = stiff platform
- When one wheel moves (cornering), T-bar rotates, only single wheel's damper engaged = compliant
- **This is the key innovation** that lets F1 cars be stiff in heave (aero platform) but soft in roll (mechanical grip)

### Ride Height Adjustment Strategy
1. Start with ride height in the middle of the aero map's force enhancement region
2. Lower progressively while monitoring:
   - Minimum ride height at speed on fastest straight
   - Ride height over worst bumps/kerbs
   - Plank contact indicators
   - Aero balance consistency
3. Stop lowering when you reach the first sign of:
   - Aero stall oscillation
   - Sustained plank contact
   - Aero balance becoming unpredictable
4. Raise 1-2mm from that point for margin

---

## 7. F1 PLANK REGULATIONS (Reference)

- Plank material: Jabroc (engineered wood) with titanium skid blocks
- Original thickness: 10mm
- Maximum allowable wear: 1mm (must retain 9mm minimum post-race)
- Wear measured at specific points along the plank
- Skid blocks create sparks when contacting track — this is by design
- Excessive wear = disqualification (famously: Verstappen, Spa 2024 sprint qualifying)

**For the F324 in iRacing**: The sim models ride height inspection. If FrontRhAtSpeed or RearRhAtSpeed approaches 0mm, the car fails inspection. This is the sim's equivalent of the plank rule.

---

## 8. PRACTICAL APPLICATION — F324 DALLARA SUPER FORMULA LIGHTS

### Car-Specific Characteristics
- Double wishbone pushrod suspension with inboard springs and dampers
- Adjustable ride heights and third springs
- Significant ground effect from Venturi tunnels
- Aero platform stability is critical for consistent lap times

### Setup Philosophy
1. **Softer springs** = better mechanical grip but less stable aero platform, more ride height variation
2. **Stiffer springs** = worse mechanical grip but consistent aero behavior, predictable car
3. **The sweet spot** is where you have enough stiffness to control the aero platform while retaining enough compliance for tire grip
4. Third spring tuning is critical for managing heave without sacrificing roll compliance

### Bottoming Management for F324
- Monitor FrontRhAtSpeed and RearRhAtSpeed channels
- These values approaching 0mm = failing inspection / excessive bottoming
- Target: maintain minimum 2-3mm clearance at speed at all points on track
- Use bump stops to prevent final mm of travel
- Adjust spring perch offset to set static ride height
- Stiffer third spring = less heave under aero load = more consistent platform

---

## 9. RECOMMENDED RESOURCES

### Essential Textbooks
- **"Race Car Vehicle Dynamics" by Milliken & Milliken** (SAE R-146) — the definitive reference, covers everything from tire mechanics to aero integration. ISBN: 978-1560915263. Available from SAE: https://www.sae.org/publications/books/content/r-146/
- **"The Dynamics of the Race Car" by ChassisSim** — practical race car dynamics. https://www.chassissim.com/the-dynamics-of-the-race-car-new-hard-cover-book-available/
- **"Vehicle Dynamics: Theory and Application" by Jazar** — full textbook, PDF available: https://geumotorsports.wordpress.com/wp-content/uploads/2016/08/vehicle-dynamics-theory-and-applications.pdf

### Courses and Seminars

**OptimumG — Applied Vehicle Dynamics Seminar (Claude Rouelle)**
- 4-day intensive seminar, 8AM-8PM daily
- 1000+ slide binder provided to participants
- Covers: aero maps, ride height, suspension design, springs, dampers, data acquisition
- 400+ seminars delivered, 14,000+ engineers trained across 34 countries
- Taught by Claude Rouelle (45 years experience)
- Syllabus PDF: https://optimumg.com/wp-content/uploads/2022/04/OptimumG-Applied-Vehicle-Dynamics-to-Race-Car-Design-and-Development-Seminar-Content.pdf
- Upcoming seminars: https://optimumg.com/our-seminars/
- Online lecture available: https://optimumg-s-school.thinkific.com/courses/vehicle-dynamics-lecture

**DRIVER61 — Motorsport Engineering Courses**
- F1 Aerodynamics Course with Willem Toet (19+ hours)
- Vehicle Dynamics course
- https://driver61.com/education/
- Aerodynamics Unlocked: https://courses.driver61.com/aerodynamics-unlocked/

**High Performance Academy (HPA)**
- Suspension Tuning & Optimization course
- Aerodynamics Fundamentals course
- Free alignment & suspension 101 lesson
- https://www.hpacademy.com/courses/suspension-and-car-setup/
- https://www.hpacademy.com/courses/aerodynamics-fundamentals/

**Virtual Racing School (VRS)**
- Free ride height and setup guides for sim racing
- https://virtualracingschool.com/academy/iracing-career-guide/setups/ride-heights/

### Research Papers

**"Ground Effect Aerodynamics of Race Cars"** — Southampton University
- Comprehensive review of ground effect principles, ride height sensitivity
- PDF: https://eprints.soton.ac.uk/42969/1/GetPDFServlet.pdf

**SAE 2023-01-5064**: "Aerodynamic Analysis of the Ride Height Dependency of a High-Performance Vehicle Equipped with a Multichannel Diffuser in Ground Effect"
- RANS vs DDES comparison at various ride heights
- Shows unsteady flow dominates at low ride heights
- https://saemobilus.sae.org/papers/aerodynamic-analysis-ride-height-dependency-a-high-performance-vehicle-equipped-a-multichannel-diffuser-ground-effect-2023-01-5064

**"Analyzing Porpoising on High Downforce Race Cars"** — MDPI Energies
- Causes and setup adjustments to avoid porpoising
- https://www.mdpi.com/1996-1073/15/18/6677

**University of Michigan — Formula SAE Aero Sensitivity**
- Sensitivity of vehicle aerodynamics to roll and pitch
- PDF: https://deptapps.engin.umich.edu/open/rise/getreport?file=MacKethan_ME490_FinalPaper.pdf

**Stanford Dynamic Design Lab — Race Car Data Analysis**
- Open data from race car drivers
- PDF: https://ddl.stanford.edu/sites/g/files/sbiybj25996/files/media/file/kegelman_harbott_gerdes_2017_0.pdf

### Technical References (Free)
- F1 Technical — Ride Height: https://www.f1technical.net/features/10682
- Formula 1 Dictionary — Ride Height: https://www.formula1-dictionary.net/ride_height.html
- Formula 1 Dictionary — Ground Effect: https://www.formula1-dictionary.net/ground_effect.html
- Formula 1 Dictionary — Aero Mapping: https://www.formula1-dictionary.net/map_aero.html
- Zebulon Motorsport — Aero Tuning Guide: https://zebulonmsc.com/blogs/motorsport-blog/aerodynamics-tuning-how-to-tune-your-car-for-and-with-aero
- Racecomp Engineering — Bump Stops 101: https://www.racecompengineering.com/blogs/the-apex-files/bump-stops-101
- AMB Aero — Porpoising Solutions: https://amb-aero.com/aerodynamics-solutions-to-porpoising-in-2022-formula-1-cars/

### Recommended Reading List (Motorsport Engineering)
From motorsportengineer.net's top 10 list:
- https://motorsportengineer.net/10-books-every-aspiring-motorsport-engineer-should-read-part-1/
- Also recommended: yourdatadriven.com's 19 motorsports books list: https://www.yourdatadriven.com/good-motorsports-books/

---

## 10. KEY TAKEAWAYS FOR PITWALL37

1. **There is no magic "acceptable bottoming percentage"** — it depends on type (mechanical vs. aero vs. plank), location, duration, and consequence
2. **Some bottoming = running at the limit = potentially fast**; the goal is "barely not bottoming" not "never bottoming"
3. **Aero stall is the line you must never cross** — any sustained oscillation means you've gone too low
4. **Monitor FrontRhAtSpeed and RearRhAtSpeed** as primary indicators in iRacing telemetry
5. **Bump stops are the engineer's primary tool** for managing the bottom end of suspension travel
6. **Third spring tuning** controls heave independently from roll — critical for aero platform
7. **Aero maps are non-linear** — small ride height changes can cause large downforce changes near the stall boundary
8. **Spring rate increases of 20-60%** are typical when adding significant aero to a car
9. **Transient aero behavior** (vibration-dependent) differs from static — real-world bottoming effects are frequency and amplitude dependent
10. **The fastest setup** lives on the knife edge between maximum aero performance and the onset of stall
