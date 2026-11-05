# Sorting four kinds of colloid by size and colour: what the literature says

**What this page is.** A literature review written on 2026-11-04 at the
person's request, for planning one experiment.
- Four kinds of particle, for example two diameters times two fluorescent
  colours, are mixed in one chamber and sorted so each kind ends in its own
  region.
- The lab's main tool is the AOD-steered optical tweezers.
- The longer aim is a closed loop: an agent detects particles in images,
  decides, and moves them.

**What it is not.** It is not an ingest and not part of the store.
- It sits in `docs/drafts/` because a root session wrote it, and the root
  session may not write `librarian_agent/kb/`. Moving it into the store as
  distilled notes with source records is the librarian session's act.
- No source record and no entry was made from it.
- Every number below is either a paper's claim or a calculation shown with
  its formula. None is a value of this instrument.
- A number reaches a plan only through the librarian, one source at a time; a
  paper's number enters at E3 at best.

**How it was checked.**
- Every DOI below was resolved against Crossref on 2026-11-04, and its first
  author, year, title and journal matched. One arXiv id was resolved against
  arXiv.
- Each paper's read level is given in the bibliography:
  - *full* means the full text was read;
  - *abstract* means only the abstract or record was read;
  - *excerpt* means the number was seen only in a search-engine excerpt of
    the full text. **Confirm an excerpt number in the paper before quoting
    it.**
- **Reasoning** marks the reviewer's own inference. It is not any paper's
  claim.

**Store names this bears on.** `optical_tweezers`, `trapping`,
`particle_suspension_a`, `particle_suspension_b`, `confocal_csuw1`,
`camera_red`, `filter_wheel_em1`, `filter_wheel_em2`.

---

## 1. What the store already says that bears on this

These are entries in the store; their grades are theirs.

**The tweezers act open-loop.**
- `tweez300_reports_nothing_back` (E3): the tweezers report no trap
  positions back. Every "did the bead go where I sent it" must be read off
  the camera.
- `trapped_bead_is_the_one_that_does_not_translate` (E3): in a crowded field
  the trapped bead is the one that does not move when the stage moves.

**Commanding the traps.**
- `tweez300_position_origin_is_image_centre` (E3) and
  `tweez300_positive_x_is_right_on_screen` (E3) fix the trap frame against
  the image. Image-to-trap mapping is the first calibration a sorting loop
  needs.
- `tweez300_host_streamed_positions_move_smoothly` (E3): positions streamed
  at 10 Hz move a trap smoothly.
- `tweez300_back_to_back_sends_come_back_busy` (E3): commands need a gap.
- `tweez300_new_trap_starts_at_strength_zero` (E3): a new trap delivers
  nothing until a strength is set.
- `objective_change_invalidates_trap_calibration` (E3): the image-to-trap
  mapping belongs to one objective.

**The beads the store lists.** All of them are red-emitting.

| bead | size | excitation / emission | entries |
|---|---|---|---|
| Abvigen AFR-0500-COOH (`particle_suspension_a`) | 5 µm | 620 / 680 nm | `tracer_excitation_peak`, `tracer_emission_peak`, `tracer_diameter_measured` |
| Bangs FSFR004 and FSFR005, Flash Red | 1 and 2 µm nominal | 660 / 690 nm | `bangs_flash_red_excitation_peak`, `bangs_flash_red_emission_peak` |
| Invitrogen F8801 (`particle_suspension_b`) | 0.1 µm | 580 / 605 nm | `f8801_excitation_peak`, `f8801_emission_peak` |

- All peaks are supplier figures at E3.
- `abvigen_published_data_is_unreliable` (E3) warns about that supplier's
  sheet.
- **Reasoning.** The 5 µm Abvigen and the Flash Red beads overlap almost
  completely in both excitation and emission, so they are one colour channel,
  not two. **A second colour has to be bought.**

---

## 2. The landscape in one paragraph

**Passive optical sorting selects on polarizability.** Polarizability is set
by size and refractive-index contrast, and these methods never select on
colour.
- The methods are optical lattices, optical fractionation, optical
  chromatography, line traps, and blinking or moving trap arrays.
- Nearly all of them need the fluid to move relative to the light pattern.
- The exception is a moving standing wave (Čižmár et al. 2006), which needs
  an interference setup.

**Colour therefore needs active sorting.** Image each particle, classify it
from fluorescence, then move it with a steerable trap.
- That is the scheme of Chapin, Germain & Dufresne 2006.
- It suits a static chamber and an AOD multi-trap system.

---

## 3. Active, image-based sorting: the precedents

**Chapin, Germain & Dufresne 2006** (*abstract*; numbers from *excerpts*).
This is the closest precedent.
- Real-time feature finding in bright-field images, at 100x/1.4 oil, locates
  the particles.
- Holographic traps catch them before they diffuse away, and a planner moves
  them to targets with no human in the loop.
- *Excerpt numbers:*
  - 1.0 µm silica was separated from 1.9 µm silica, classified by integrated
    image intensity.
  - About 94% were correct on the first pass. The software found the
    misplaced particle and re-sorted to 100%.
  - Path planning took about 16 s.

**Selin et al. 2026, "SmartTrap"** (*full*). An autonomous tweezers system.
- **Detection.** A YOLOv5 detector, trained mostly on synthetic images plus
  about 1,000 annotated frames.
- **Speed.** The decision loop ran at about 20 Hz on a consumer GPU, near the
  camera rate. Trap feedback ran at about 7 kHz.
- **Run.** From a mixture of small (r = 1.0–1.5 µm) and large (r = 2.12 µm)
  beads, it trapped 938 particles and characterised 159 large ones in 4.5 h.
- **Failure mode they detect.** Two particles in one trap, recognised from a
  focal-position offset.
- **Hardware.** The traps are steered by piezo fibre "wigglers", not AODs.

**Wang Y. et al. 2025** (*full*). Fluorescence-activated sorting in flow.
- **Setup.** 10 µm green and orange polystyrene, a 1064 nm trap at about
  250 mW gated by a shutter for 80 ms.
- **Classifier.** "Colour" was mean grey value in one channel, with a
  threshold.
- **Results.**
  - Purity: 94.4% (orange) and 77.3% (green).
  - Yield: 70.2% and 95.0%.
  - Throughput: 0.83 particles per minute.
- Pluronic F-127 was used against aggregation.
- **Lesson:** a single-channel brightness threshold is a weak colour
  classifier.

**Wang M. M. et al. 2005** (*abstract*). Fluorescence detection triggers a
laser switch that reroutes cells at a microfluidic junction in 2–4 ms. This
is the flow-based paradigm.

**Landenberger et al. 2012** (*abstract*). Steerable tweezers with optimised
path and velocity profiles. Objects from 2 to 30 µm were moved; yeast was
sorted by shape and by fluorescence.

**Vossen et al. 2004** (*abstract*).
- AOD trap arrays held several hundred µm-sized particles, combined with
  confocal imaging. This is close to the hardware here.
- In an index-matched solvent, only the tracers felt the traps. The
  refractive index can make a trap selective.

**Milne et al. 2007** (*abstract*). An **AOD-generated** periodic landscape
sorted four particle sizes at once into separate streams, under flow.

**Xie, Chen & Li 2005** (*abstract*). Raman-activated sorting with tweezers.
It is label-free and slow, and only marginal here.

---

## 4. Passive sorting by size or index (for comparison)

| method | selects on | demonstrated | needs | source |
|---|---|---|---|---|
| 3D optical lattice | polarizability (size, index) | about 2x size discrimination; ≥96% purity | flow | MacDonald, Spalding & Dholakia 2003 (*abstract*) |
| Optical fractionation (tilted trap array) | size, at a lock-in threshold | 0.79 vs 0.5 µm silica, about 40% purification per pass | flow | Ladavac, Kasza & Grier 2004 (*full*, preprint) |
| Kinetic lock-in | size vs array spacing | lock-in hierarchy | flow | Korda, Taylor & Grier 2002; Roichman, Wong & Grier 2007 (*abstract*) |
| Multidimensional fractionation | radius and index together | holographic verification of each sphere | flow | Xiao & Grier 2010 (*abstract*) |
| Optical chromatography | size and index | equal sizes split by index (PS, PMMA, silica) | counter-flow | Imasaka et al. 1995; Hart & Terray 2003 (*abstract*) |
| Blinking traps | diffusion during the off period | 1 vs 2 µm silica | flow | Dasgupta, Verma & Gupta 2012 (*abstract*) |
| Moving trap array | size, index | 2, 3 and 5 µm silica; about 30 particles/s | flow | Dasgupta, Ahlawat & Gupta 2012 (*abstract*) |
| Line trap ("travelator") | size | 1.1 vs 3.2 µm, over 90% (*excerpt*) | electrophoretic drive | Cheong et al. 2006 |
| Moving standing wave | size (fringe hopping) | sub-µm particles | interference optics, no flow | Čižmár et al. 2006 (*abstract*) |

**Reasoning.** The blinking-trap result matters twice for an AOD system:
- Time-sharing *is* blinking, so small beads can be lost between visits.
- The same effect is a size filter that costs no hardware.

---

## 5. Colour: classification and its pitfalls

**A 1064 nm trap bleaches dyes by two-photon absorption.**
- **Lu & Chemla 2023** (*abstract*; dye details from *excerpts*):
  - emission near the focus fell by about 90% within about 1 minute under
    typical conditions;
  - Cy3, AF546 and AF647 bleached;
  - **blue-absorbing AF488 showed no detectable effect even at 210 mW**,
    because two 1064 nm photons do not reach its excited state.
- **van Dijk et al. 2004** (*abstract*): with visible excitation and the
  trap on together, the bleaching rate rose linearly with both intensities.
- **Zhang et al. 1998** (*abstract*): even yellow-green BODIPY beads
  fluoresced under a CW 1064 nm trap.

**Heating does not separate colours.** At 1064 nm the heat comes mainly from
the water, about 8 K/W (Peterman, Gittes & Schmidt 2003, *abstract*).
- **Reasoning.** A visible dye in the bead adds no usable colour-dependent
  force at 1064 nm.

**Overlapping dyes.** Spectral imaging with linear unmixing separates
strongly overlapping emissions (Zimmermann, Rietdorf & Pepperkok 2003,
*abstract*).

**Reasoning: what this means here.**
- The camera is monochrome, so colour means which excitation and emission
  channel a bead shows up in.
- **Classify colour once, before trapping.** Keep track of identity in bright
  field afterwards, and do not excite fluorescence while a bead is trapped.
- **The red beads in the store are the susceptible kind.**
  - A blue-excited, green-emitting dye is the natural second colour: well
    separated from Flash Red and Abvigen, and resistant to 1064 nm
    two-photon bleaching.
  - A dye loaded densely into a bead may bleach more slowly than single
    molecules do. **Measure it before relying on it.**
- **Classify on a ratio of two channels under sequential excitation**, not
  on one channel's brightness.
  - Measure the bleed-through matrix on single-kind samples first.
  - The one-channel threshold in Wang Y. 2025 gave 77% purity for one class.

---

## 6. Moving many particles: automation and control

**Path planning and collision avoidance.**
- **Banerjee, Chowdhury, Losert & Gupta 2012** (*abstract*). Real-time
  coordinated transport of several particles with collision avoidance.
- **Banerjee, Chowdhury & Gupta 2014** (*abstract*). An overview of
  autonomous optical manipulation.

**Cross-field analogue: Barredo et al. 2016** (*abstract*; details from
*excerpts* of the preprint). Image, assign, then move, with about 50 atoms
rearranged in a trap array under real-time control.
- Moves ran along lattice links.
- A blocked move was split in two.
- The assignment and collision logic transfers to colloids.

**Detection.**
- **Crocker & Grier 1996** (*abstract*). The standard centroid-and-link
  tracking, about 10 nm in plane.
- **Helgadottir, Argun & Volpe 2019** (*abstract*). DeepTrack, a learned
  tracker robust to noise and uneven light.
- **SmartTrap** (section 3) used YOLO.

**Learned control.**
- **Praeger et al. 2021** (*abstract*). A reinforcement-learning policy,
  trained in simulation, steered a real trapped bead to a target past free
  beads.
- **Zhang, Werner & Banerjee 2024** (*abstract*; **preprint or conference
  paper**). Detection, tracking and planning added to a commercial
  holographic system, with 5 µm polystyrene.

**Reviews.**
- **Ciarlo et al. 2024** (*abstract*). Deep learning across tweezers design,
  calibration, control and analysis.
- **Yang et al. 2025** (*abstract*). Optical sorting divided into active and
  passive, with AI-driven sorting and a comparison with other fields.

**Holograms are not needed here.** **Bianchi & Di Leonardo 2010**
(*abstract*) compute holograms at video rate for spatial-light-modulator
tweezers. With AODs the pattern is set by the drive signal instead.

---

## 7. Time-shared AOD traps: what limits them

**Multi-trap systems in the literature.**
- **Visscher, Gross & Block 1996** (*abstract*). Compares split-beam and
  time-shared multiple traps.
- **Mio et al. 2000** (*abstract*). One beam scanned at up to 1.2 kHz held
  several 1 µm colloids.
- **Guilford et al. 2004** (*abstract*). Four to six time-shared traps, each
  visited about 10,000 times a second.
- **Vossen et al. 2004** (*abstract*). Several hundred particles in AOD
  arrays.

**Trapping small particles.**
- **Ashkin et al. 1986** (*abstract*). A single dedicated beam trapped
  particles down to about 25 nm.
- **Rohrbach 2005** (*abstract*). Stiffness is greatest for spheres near the
  wavelength in diameter.
- **Bendix et al. 2014** (*record*). A review of nanoparticle trapping.

**Not found.** No verified model linking trap count, revisit time and
particle relaxation time to effective stiffness. **Reasoning:** measure
stiffness against trap count on this instrument.

**Transport numbers, computed** with D = k_BT/(6πηa) and
v = (2/9)Δρ g a²/η. Inputs: water at about 20 °C, η = 1.0 mPa·s, polystyrene
1.05 g/cm³, so Δρ = 50 kg/m³. These are calculations, not measurements.

| diameter | D (µm²/s) | settling speed (µm/s) | gravitational height |
|---|---|---|---|
| 0.1 µm | 4.3 | 0.0003 | about 1.6 cm |
| 1 µm | 0.43 | 0.027 | about 16 µm |
| 2 µm | 0.21 | 0.11 | about 2 µm |
| 5 µm | 0.086 | 0.68 | about 0.13 µm |

**Reasoning.**
- **The 1–5 µm beads settle into a near-2D layer** on the bottom coverslip,
  within minutes to about an hour. That is convenient for 2D detection.
  - The risk is sticking to the glass, so passivate or use a surfactant.
- **The 0.1 µm beads are a different experiment.**
  - They stay suspended in 3D and are below the imaging resolution.
  - They diffuse ten times faster than 1 µm beads, so they escape during a
    time-sharing off period.
  - In the Rayleigh regime the gradient force falls with particle volume.
  - Leave them out of the four kinds, or test them with one dedicated trap.

---

## 8. Non-optical alternatives, briefly

| method | selects on | where it beats tweezers | source |
|---|---|---|---|
| Deterministic lateral displacement | size: 0.8, 0.9 and 1.0 µm split, about 10 nm resolution | resolution, throughput | Huang et al. 2004 (*abstract*) |
| Free-flow acoustophoresis | size, density, compressibility: 2, 5, 8 and 10 µm split into four outlets | throughput for µm sizes | Petersson et al. 2007 (*abstract*) |
| Dielectrophoresis | dielectric properties | label-free; needs electrodes | Pethig 2010 (review, *abstract*) |
| Optoelectronic tweezers | dielectrophoresis from a projected image; 15,000 traps | parallelism; needs a special chamber | Chiou, Ohta & Wu 2005 (*abstract*) |
| Pinched flow fractionation | size | simple passive device | Yamada, Nakashima & Seki 2004 |
| Field-flow fractionation | mass, size, density | 1 nm to over 100 µm | Giddings 1993 |
| Inertial microfluidics | size, shape | very high throughput | Di Carlo 2009 |

**Reasoning.** None of these sees colour. Tweezers win where the chamber is
static, the sample small, every particle placed individually, and colour
combined with size.

---

## 9. What follows for our experiment

This section is reasoning, not any paper's claim.

**1. The method.** Active, image-based sorting in a static chamber.
- The loop: detect, classify (size from bright field, colour from two
  fluorescence channels), assign each particle to a region, plan
  collision-free paths, move, re-image, correct.
- Chapin 2006 is the template, and its re-check pass is what took accuracy
  from about 94% to 100%.

**2. Calibrations before any sorting.**
- The image-to-trap mapping, per objective.
- Stiffness against trap count and against position in the field.
- Bleaching of each dye under the trap.
- The channel bleed-through matrix.

**3. Throughput to expect.**
- A first target of a few hundred beads per hour with tens of traps is
  plausible from the precedents: SmartTrap at over 200 per hour with one
  trap; Vossen with hundreds of particles held.
- The limits are trap force against Stokes drag (5 µm beads move slowest at
  a given force), and per-trap stiffness falling as traps are added.

**4. Risks.**
- Two beads in one trap.
- Collisions and hydrodynamic coupling between moving beads.
- Misdetection in crowds.
- Drift between the camera and trap coordinates.
- Uneven AOD efficiency across the field.
- Beads sticking to the glass.
- The trap bleaching the very colour being sorted on.

**5. How it feeds the closed loop.**
- Sorting is a natural closed-loop task. The image is the state, the trap
  moves are the actions, and purity and time are the score.
- The same loop can be run in simulation first: Brownian dynamics with
  traps as moving harmonic wells, plus the wall-corrected mobility from
  `literature_trap_drag_vs_height_above_a_wall.md`.

**Open choices for the person.**
1. **The four kinds.**
   - Sizes: 2 and 5 µm is the most robust pair; 1 and 2 µm is harder and
     settles slower.
   - The second colour: blue-excited, green-emitting is favoured above.
   - Whether the 0.1 µm beads are out.
2. **The chamber.** Height, passivation or surfactant, concentration, and
   whether a flow cell comes later. Flow would open the passive and
   fluorescence-switch methods.
3. **The target regions.** Four regions in one field of view, or across
   stage moves; size and spacing; whether held by "fence" traps or by
   settled beads.
4. **The success metric.** Purity and yield per region, misclassification
   rate, beads lost, beads per hour, and stability over time.
5. **The detector and loop rate.** Centroid tracking or a learned detector;
   when to re-image.

---

## Bibliography

DOIs were resolved against Crossref on 2026-11-04. The read level is in
brackets.

**Passive optical sorting**
- Imasaka, T. et al. (1995). Anal. Chem. 67, 1763–1765. doi:10.1021/ac00107a003 [record; described via Neves 2021]
- Korda, P. T., Taylor, M. B. & Grier, D. G. (2002). Phys. Rev. Lett. 89, 128301. doi:10.1103/PhysRevLett.89.128301 [abstract]
- MacDonald, M. P., Spalding, G. C. & Dholakia, K. (2003). Nature 426, 421–424. doi:10.1038/nature02144 [abstract; size figure from excerpt]
- Hart, S. J. & Terray, A. V. (2003). Appl. Phys. Lett. 83, 5316–5318. doi:10.1063/1.1635984 [abstract]
- Ladavac, K., Kasza, K. & Grier, D. G. (2004). Phys. Rev. E 70, 010901(R). doi:10.1103/PhysRevE.70.010901 [full, preprint cond-mat/0310396]
- Čižmár, T. et al. (2006). Phys. Rev. B 74, 035105. doi:10.1103/PhysRevB.74.035105 [abstract]
- Cheong, F. C. et al. (2006). Appl. Phys. B 83, 121–125. doi:10.1007/s00340-006-2139-8 [record; numbers from excerpt]
- Roichman, Y., Wong, V. & Grier, D. G. (2007). Phys. Rev. E 75, 011407. doi:10.1103/PhysRevE.75.011407 [abstract]
- Milne, G. et al. (2007). Opt. Lett. 32, 1144. doi:10.1364/OL.32.001144 [abstract]
- Xiao, K. & Grier, D. G. (2010). Phys. Rev. Lett. 104, 028302. doi:10.1103/PhysRevLett.104.028302 [abstract]
- Dasgupta, R., Verma, R. S. & Gupta, P. K. (2012). Opt. Lett. 37, 1739. doi:10.1364/OL.37.001739 [abstract]
- Dasgupta, R., Ahlawat, S. & Gupta, P. K. (2012). Appl. Opt. 51, 4377. doi:10.1364/AO.51.004377 [abstract]
- Juniper, M. P. N. et al. (2012). Opt. Express 20, 28707. doi:10.1364/OE.20.028707 [abstract; mapping AOD landscapes under flow]

**Reviews**
- Grier, D. G. (2003). Nature 424, 810–816. doi:10.1038/nature01935 [abstract]
- Dholakia, K., MacDonald, M. P., Zemánek, P. & Čižmár, T. (2007). Methods Cell Biol. 82, 467–495. doi:10.1016/S0091-679X(06)82017-0 [abstract]
- Dholakia, K., Reece, P. & Gu, M. (2008). Chem. Soc. Rev. 37, 42–55. doi:10.1039/b512471a [abstract]
- Jonáš, A. & Zemánek, P. (2008). Electrophoresis 29, 4813–4851. doi:10.1002/elps.200800484 [abstract]
- Neves, A. A. R. et al. (2021). Front. Phys. 8, 603641. doi:10.3389/fphy.2020.603641 [full]
- Yang, M. et al. (2025). Light Sci. Appl. 14, 103. doi:10.1038/s41377-024-01734-5 [abstract]

**Active, image-based sorting**
- Wang, M. M. et al. (2005). Nat. Biotechnol. 23, 83–87. doi:10.1038/nbt1050 [abstract]
- Xie, C., Chen, D. & Li, Y. (2005). Opt. Lett. 30, 1800. doi:10.1364/OL.30.001800 [abstract]
- Chapin, S. C., Germain, V. & Dufresne, E. R. (2006). Opt. Express 14, 13095. doi:10.1364/OE.14.013095 [abstract; numbers from excerpts]
- Landenberger, B. et al. (2012). Lab Chip 12, 3177. doi:10.1039/c2lc21099a [abstract]
- Wang, Y. et al. (2025). Biosensors 15, 541. doi:10.3390/bios15080541 [full]
- Selin, M. et al. (2026). Nat. Methods 23, 1368–1378. doi:10.1038/s41592-026-03129-3 [full]

**Colour, bleaching, heating**
- Zhang, Y. et al. (1998). Appl. Opt. 37, 2766. doi:10.1364/AO.37.002766 [abstract]
- Peterman, E. J. G., Gittes, F. & Schmidt, C. F. (2003). Biophys. J. 84, 1308–1316. doi:10.1016/S0006-3495(03)74946-7 [abstract]
- Zimmermann, T., Rietdorf, J. & Pepperkok, R. (2003). FEBS Lett. 546, 87–92. doi:10.1016/S0014-5793(03)00521-0 [abstract]
- van Dijk, M. A. et al. (2004). J. Phys. Chem. B 108, 6479–6484. doi:10.1021/jp049805+ [abstract]
- Lu, J. & Chemla, Y. R. (2023). Biophys. J. 122, 4316–4325. doi:10.1016/j.bpj.2023.10.006 [abstract; dye ranking from excerpts]

**Automation, tracking, control**
- Crocker, J. C. & Grier, D. G. (1996). J. Colloid Interface Sci. 179, 298–310. doi:10.1006/jcis.1996.0217 [abstract]
- Bianchi, S. & Di Leonardo, R. (2010). Comput. Phys. Commun. 181, 1444–1448. doi:10.1016/j.cpc.2010.04.012 [abstract]
- Banerjee, A. G., Chowdhury, S., Losert, W. & Gupta, S. K. (2012). IEEE Trans. Autom. Sci. Eng. 9, 669–678. doi:10.1109/TASE.2012.2200102 [abstract]
- Banerjee, A. G., Chowdhury, S. & Gupta, S. K. (2014). IEEE Robot. Autom. Mag. 21, 81–88. doi:10.1109/MRA.2014.2332407 [abstract]
- Barredo, D. et al. (2016). Science 354, 1021–1023. doi:10.1126/science.aah3778 [abstract]
- Helgadottir, S., Argun, A. & Volpe, G. (2019). Optica 6, 506. doi:10.1364/OPTICA.6.000506 [abstract]
- Praeger, M. et al. (2021). Mach. Learn.: Sci. Technol. 2, 035024. doi:10.1088/2632-2153/abf0f6 [abstract]
- Ciarlo, A. et al. (2024). Nanophotonics 13, 3017–3035. doi:10.1515/nanoph-2024-0013 [abstract]
- Zhang, T., Werner, N. & Banerjee, A. G. (2024). arXiv:2404.17045. **Preprint or conference paper** [abstract]

**Multi-trap systems and small particles**
- Ashkin, A. et al. (1986). Opt. Lett. 11, 288. doi:10.1364/OL.11.000288 [abstract]
- Visscher, K., Gross, S. P. & Block, S. M. (1996). IEEE J. Sel. Top. Quantum Electron. 2, 1066–1076. doi:10.1109/2944.577338 [abstract]
- Mio, C. et al. (2000). Rev. Sci. Instrum. 71, 2196–2200. doi:10.1063/1.1150605 [abstract]
- Guilford, W. H. et al. (2004). Anal. Biochem. 326, 153–166. doi:10.1016/j.ab.2003.11.025 [abstract]
- Vossen, D. L. J. et al. (2004). Rev. Sci. Instrum. 75, 2960–2970. doi:10.1063/1.1784559 [abstract]
- Rohrbach, A. (2005). Phys. Rev. Lett. 95, 168102. doi:10.1103/PhysRevLett.95.168102 [abstract]
- Bendix, P. M., Jauffred, L., Nørregaard, K. & Oddershede, L. B. (2014). IEEE J. Sel. Top. Quantum Electron. 20(3), 15–26. doi:10.1109/JSTQE.2013.2287094 [record; the survey's report gave article number 4800112, and Crossref gives these pages]

**Non-optical alternatives**
- Giddings, J. C. (1993). Science 260, 1456–1465. doi:10.1126/science.8502990
- Huang, L. R., Cox, E. C., Austin, R. H. & Sturm, J. C. (2004). Science 304, 987–990. doi:10.1126/science.1094567 [abstract]
- Yamada, M., Nakashima, M. & Seki, M. (2004). Anal. Chem. 76, 5465–5471. doi:10.1021/ac049863r
- Chiou, P. Y., Ohta, A. T. & Wu, M. C. (2005). Nature 436, 370–372. doi:10.1038/nature03831 [abstract]
- Petersson, F. et al. (2007). Anal. Chem. 79, 5117–5123. doi:10.1021/ac070444e [abstract]
- Di Carlo, D. (2009). Lab Chip 9, 3038. doi:10.1039/b912547g
- Pethig, R. (2010). Biomicrofluidics 4, 022811. doi:10.1063/1.3456626 [abstract]

**Not confirmed.** These were seen only as partial listings. Do not cite them
without checking:
- Perroud et al. 2008, Anal. Chem. (optical-force cell sorting);
- Liu et al. 1995, Opt. Lett. 20, 2246 (two-photon fluorescence in a CW IR
  trap);
- Kachynski et al. 2003, Opt. Lett. 28, 2288;
- Martínez & Petrov 2012, Appl. Opt. 51, 5522 (AOD time-sharing force
  mapping);
- Kaneta et al. 1997, Anal. Chem. 69, 2701 (optical chromatography theory);
- Malagnino et al. 2002, Opt. Commun. 214, 15;
- Simmons et al. 1996, Biophys. J. 70, 1813;
- Lee et al. 2005, Phys. Rev. Lett. 94, 110601;
- a Monte Carlo study of time-shared trap stiffness (Chinese Optics Letters,
  about 2010).
