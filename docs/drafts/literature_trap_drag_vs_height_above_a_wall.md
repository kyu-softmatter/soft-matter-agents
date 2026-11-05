# Drag of a trapped sphere against its height above the coverslip: what the literature says

**What this page is.** A literature review written on 2026-11-04 at the
person's request. It supports planning one experiment: measure the drag
coefficient, and with it the trap stiffness, of a sphere held by the optical
tweezers, at a series of heights above the coverslip.

**What it is not.** It is not an ingest and not part of the store.
- It sits in `docs/drafts/` because a root session wrote it, and the root
  session may not write `librarian_agent/kb/`. Moving it into the store as
  distilled notes with source records is the librarian session's act.
- No source record and no entry was made from it.
- Every number below is either a paper's claim or a calculation shown with
  its formula. None of it is a value of this instrument.
- A number reaches a plan only through the librarian:
  - it is ingested one source at a time, through the four ingest steps;
  - a paper's number enters at E3 at best;
  - the store's entries stay the authority.

**How it was checked.**
- Every DOI below was resolved against Crossref on 2026-11-04, and its first
  author, year, title and journal matched.
- The three arXiv ids were resolved against arXiv.
- Each paper's **read level** is given in the bibliography:
  - *full*: the full text was read;
  - *abstract*: only the abstract or record was read;
  - *secondary*: the claim was seen only as another source quotes it.
- **Reasoning** marks the reviewer's own inference. It is not any paper's
  claim.

**Store names this bears on.** `optical_tweezers`, `piezo_stage`, `trapping`,
`trapped_particle_drag_offset`, `trap_stiffness`, `viscosity`, `temperature`.

---

## 1. What the store already says that bears on this

These are entries in the store; their grades are theirs.

- `tweez300_reports_nothing_back` (E3). The tweezers return no position,
  force or calibration over their interface.
  - So bead position must come from the camera.
  - Every calibration here is a **video** calibration.
- `tweez300_software_opens_the_red_arm_camera` (E5) and
  `tweez300_camera_is_released_so_it_shows_no_image` (E5): which camera body
  is involved.
- `objective_change_invalidates_trap_calibration` (E3). A calibration belongs
  to one objective. Changing objective silently voids it.
- `optical_tweezers_work_with_40x_60x_100x_person_statement` (E5) and
  `nosepiece_objective_assignment` (E3). The trapping objectives are:
  - a **40x water-immersion** objective (MRD77400);
  - **60x and 100x oil** objectives (MRD71670, MRD71970).

  This matters a great deal for focal shift; see section 4.
- `trap_laser_power_at_sample_1064nm_{40x,60x,100x}_80pct_rough` (E4). The
  trap delivers about 1 W at the sample at the 80% setting, as an
  order-of-magnitude estimate. With the heating rate in section 4, that is
  several kelvin.
- `trap_heating_detection_bound` (E5). The operator noticed no sample heating
  below roughly 20% on the dial.
- `trapped_particle_drag_offset` is a registered observable: the mean
  displacement under steady relative flow. It is the Stokes-drag method of
  section 3.

---

## 2. Theory: a sphere moving near one plane wall

**Notation.**
- R: the bead radius.
- ℓ: distance from the bead **centre** to the wall.
- Gap: g = ℓ − R.
- γ0 = 6πηR: the bulk Stokes drag.

Mixing centre distance and gap is the commonest transcription error here.
Each formula below names the one it uses.

**Parallel to the wall: Faxén's series, centre distance ℓ.**
This is how Tolić-Nørrelykke et al. 2006 write it (Eq. 40, *full*):

    γ∥/γ0 = 1 / [1 − (9/16)(R/ℓ) + (1/8)(R/ℓ)³ − (45/256)(R/ℓ)⁴ − (1/16)(R/ℓ)⁵]

- It is within 1% of the exact result for ℓ/R ≳ 1.4 (Tolić-Nørrelykke 2006,
  Appendix D).
- At contact it stays finite at about 3.1, while the exact drag diverges
  logarithmically (Goldman, Cox & Brenner 1967).
- So it underestimates the drag for gaps below about 0.4R.

**Normal to the wall.** Brenner 1961 is exact, in bipolar coordinates. Two
closed forms approximate it.
- **Bevan & Prieve 2000**, written with the gap z:

      γ⊥/γ0 = (6z² + 9az + 2a²) / (6z² + 2az),  a = R

  - Lavaud et al. 2021 say it is within 1% of Brenner (*full*).
  - Eloul & Compton 2016 say it agrees with experiment down to z/R ≈ 0.01.
  - The formula itself is *secondary*: the original paper was not opened.
- **Schäffer, Nørrelykke & Howard 2007**, written with ℓ:

      γ⊥/γ0 = 1 / [1 − (9/8)(R/ℓ) + (1/2)(R/ℓ)³ − (57/100)(R/ℓ)⁴ + (1/5)(R/ℓ)⁵ + (7/200)(R/ℓ)¹¹ − (1/25)(R/ℓ)¹²]

  - Said to be within 0.1% of Brenner for ℓ/R ≥ 1.1.
  - *Secondary*: read as the Lumicks Pylake documentation quotes it; the
    paper was not opened.

**Leading order only.** D∥/D0 ≈ 1 − 9R/(16ℓ) and D⊥/D0 ≈ 1 − 9R/(8ℓ)
(Dufresne et al. 2000, *full*).

**Frequency-dependent drag near the wall** (Tolić-Nørrelykke 2006 Eq. 41,
*full*).
- The bulk Stokes drag grows like √(f/f_ν), where f_ν = ν/(πR²) and ν is the
  kinematic viscosity.
- Near the wall, the Faxén term is modified by a factor that decays over the
  viscous penetration depth δ = R√(f_ν/f).
- The Pylake documentation applies it only for ℓ ≥ 1.5R (*secondary*).

**Values computed from the formulas above.** These are calculations, not
measurements.

| ℓ/R | gap/R | γ∥/γ0 (Faxén) | γ⊥/γ0 (Bevan–Prieve) | γ⊥/γ0 (Schäffer form) |
|---|---|---|---|---|
| 1.1 | 0.1 | 2.36 | 11.4 | 11.5 |
| 1.5 | 0.5 | 1.62 | 3.20 | 3.21 |
| 2 | 1 | 1.39 | 2.13 | 2.13 |
| 3 | 2 | 1.23 | 1.57 | 1.57 |
| 5 | 4 | 1.13 | 1.29 | 1.29 |
| 10 | 9 | 1.06 | 1.13 | 1.13 |
| 20 | 19 | 1.03 | 1.06 | 1.06 |
| 56 | 55 | 1.01 | 1.02 | 1.02 |

The two normal-direction forms agree to better than 1% from ℓ/R = 1.5 up.

**Reasoning: what the table means.**
- **The wall's effect reaches far.** The parallel drag is still 1% above bulk
  at ℓ ≈ 56R. For a 5 µm bead that is about 140 µm; for a 2 µm bead, about
  56 µm.
- A thin chamber has no "bulk" point at all, and the opposite wall adds its
  own correction. Lin, Yu & Rice 2000 found a superposition of the two
  single-wall drags adequate.
- So **the bulk drag is better taken as a fit parameter than as a measured
  point.**

---

## 3. Calibration methods, and which of them MEASURE the drag

The question at each height is whether a method yields γ(ℓ) or needs γ as an
input. Only the first kind can test the wall correction.

| method | gives γ? | source |
|---|---|---|
| Power spectrum, with absolute position calibration (nm per pixel) | **yes**: the fitted D gives γ = k_BT/D | Berg-Sørensen & Flyvbjerg 2004; Tolić-Nørrelykke 2006 |
| Active: stage (or trap) oscillated sinusoidally, spike in the spectrum | **yes**: γ, κ and the detector scale together, with only the temperature assumed | Tolić-Nørrelykke 2006 |
| Exposure-time sweep of the position variance (blur model) | **yes**: k and γ | Wong & Halvorsen 2006 |
| Bayesian or maximum-likelihood trajectory inference | **yes**: D and the potential | Richly et al. 2013; Pérez García et al. 2018; Lavaud et al. 2021 |
| Stokes drag: stage at constant velocity, mean displacement | only with κ from elsewhere (e.g. equipartition) | Neuman & Block 2004 (review) |
| Equipartition alone | no: κ only | Neuman & Block 2004 |

**The closest precedent is Tolić-Nørrelykke et al. 2006** (*full*).
- **Setup.**
  - 0.53 µm polystyrene beads, 100x/1.3 oil objective, quadrant photodiode.
  - 24 beads, each at 50 heights within 0–3 µm of the coverslip.
  - The stage was oscillated 150 nm at 32 Hz.
- **Result.**
  - Drag measured at each height and extrapolated to bulk with Faxén gave
    γ/γ0 = 1.007 ± 0.003.
  - The bead-to-bead spread was 1.5%, which the authors attribute to
    polydispersity.
  - The surface position was a free parameter of the Faxén fit, with the
    focal shift taken into account.
- **What they warn.**
  - With oil objectives, a calibration taken far from the surface and used
    near it can be badly wrong.
  - Use the full hydrodynamic theory if systematic errors below 10% are
    wanted.
  - AOD-moved traps work for the active method laterally. Axial calibration
    needs z motion of the sample.

**Other measured precedents.**
- **Schäffer et al. 2007** (*abstract*).
  - The same active method at many heights; drag against height was compared
    with exact Navier–Stokes solutions.
  - Near the surface, the detector sensitivity is modulated by a standing
    light wave between bead and surface.
  - Surface forces depended on salt and on the passivation layer.
- **Lavaud et al. 2021** (*full*).
  - A free polystyrene bead of 1.5 µm radius, tracked by holography with a
    60x/1.30 oil objective. The 3 ms exposure was chosen to avoid blur.
  - D∥(z) and D⊥(z) were inferred down to a 10 nm gap, and agree with Faxén
    and Bevan–Prieve.
  - **The wall position was itself a fit parameter, found to about 10 nm.**
- **Gillant et al. 2023** (*abstract*).
  - Bead height was read from interference rings in the back focal plane.
  - Step response, power spectrum, equipartition and Bayesian inference
    agreed on stiffness down to 2 µm above the surface.
- **Dufresne et al. 2000** (*full*).
  - Height was set by focusing alone, to ±0.5 µm.
  - **Two beads held in time-shared traps couple hydrodynamically, through
    the wall, over tens of radii.**
- **Video, tweezers and TIRF studies of hindered diffusion** agree with Faxén
  (parallel) and Brenner (normal). All *abstract*:
  - Faucheux & Libchaber 1994;
  - Lin, Yu & Rice 2000;
  - Carbajal-Tinoco et al. 2007;
  - Huang & Breuer 2007;
  - Choi et al. 2007, who found that electrostatic wall forces bias the
    normal direction first.
- **Leach et al. 2009** (*abstract*). Confirmed the translational Faxén
  correction with tweezers and measured the rotational one.
- **Pralle et al. 1998** (*abstract*). 0.5 and 1 µm beads, followed from 3 µm
  down to 0.2 µm. The drag followed Brenner.

---

## 4. Pitfalls specific to a height series, largest first

The ranking is reasoning; each item cites what it rests on.

**1. Not knowing the height: the h = 0 offset and the focal shift.**
- **Oil objectives** trap in water through an index mismatch.
  - The trap moves by about **0.8x the stage or objective displacement**:
    0.808 ± 0.005 at 100x/1.4 oil (Deufel & Wang 2006, *full*).
  - Neuman, Abbondanzieri & Block 2005 (*full*) give a method for measuring
    it.
  - Stiffness also falls with depth, by about 17% per µm in Deufel & Wang's
    conditions.
- **A water-immersion objective** showed no depth dependence of stiffness
  (Vermeulen et al. 2006, *Appl. Opt.*, *abstract*).
- **Reasoning, computed.**
  - At ℓ = 2R the sensitivity is d ln γ / d ln ℓ ≈ −0.40 (parallel) and
    ≈ −1.03 (normal).
  - So a 10% error in ℓ is about 4% in parallel drag and about 10% in normal
    drag, and worse closer in.
  - Ignoring a 0.8 focal-shift factor misplaces the bead by about 1 µm after
    5 µm of nominal travel.

**2. Camera blur and aliasing.**
- The measured variance is the true variance times
  S(α) = 2/α − (2/α²)(1 − e^(−α)), with α = exposure/τ and τ = γ/κ
  (Wong & Halvorsen 2006, *full*).
- In their test, naive equipartition at 1 ms exposure was off by about 50%.
- Spectra from a camera must also be corrected for aliasing and position
  noise (van der Horst & Forde 2010; Lansdorp & Saleh 2012; both
  *abstract*).
- **Reasoning, computed** for a 2 µm bead at 20 pN/µm:
  - τ ≈ 0.94 ms and f_c ≈ 170 Hz;
  - S ≈ 0.72 at 1 ms exposure, and S ≈ 0.97 at 0.1 ms;
  - near the wall γ is larger, so τ is longer and blur matters less.

**3. Temperature, through viscosity.**
- Heating at 1064 nm comes mainly from the water, about **8 K/W** (Peterman
  et al. 2003, *abstract*).
- In Jun et al. 2014 (*full*), heating moved passive calibrations by 30% or
  more until it was corrected for.
- **Reasoning.**
  - At the store's rough 1 W at 80% (E4), that is several kelvin.
  - Water viscosity falls about 2% per kelvin
    (`librarian_agent/kb/distilled/water_viscosity.md`).
  - So drag at full power can sit 10–20% below the room-temperature
    prediction.
  - The coverslip sinks heat, so the temperature itself may depend on height.
  - **Run the series at low power, or measure the temperature.**

**4. Bead radius.** The vendor's size spread goes straight into γ0.
Tolić-Nørrelykke saw 1.5% bead-to-bead. Fitting each bead's own bulk drag
absorbs it.

**5. Frequency-dependent drag.**
- **Reasoning, computed.** f_ν ≈ 1.3, 0.32 and 0.05 MHz for 1, 2 and 5 µm
  beads. At 1 kHz, the bulk correction √(f/f_ν) is then about 3%, 6% and
  14%.
- It matters for percent-level work with 5 µm beads.
- It fades near the wall (Mo, Simha & Raizen 2015, *abstract*).
- The hydrodynamic-memory resonance lies at tens of kHz, far above video
  rates (Franosch et al. 2011, *full*; Jannasch et al. 2011, *abstract*).

**6. Surface forces near contact.**
- Electrostatic and passivation-layer forces mainly affect the normal
  direction below a gap of about 0.5 µm (Schäffer 2007; Choi 2007).
- Use salt, and keep the smallest gaps out of the hydrodynamic fit.

**7. Instrument-specific effects.**
- AOD diffraction efficiency varies with deflection, so stiffness depends on
  where in the field the trap sits. Neuman & Block 2004, as quoted in search
  excerpts.
- Other beads in other time-shared traps couple hydrodynamically (Dufresne
  2000).
- **Reasoning.** The time-sharing cycle may beat with the camera exposure.

---

## 5. What follows for our plan

This section is reasoning, not any paper's claim.

**1. Primary measurement.** A video power spectrum, or a variance series, of
one trapped bead at each height.
- Use absolute nm per pixel. The store has per-objective pixel sizes; check
  them by stepping the piezo against its own sensor.
- Use a blur- and aliasing-corrected model (Wong & Halvorsen; van der Horst
  & Forde).
- This gives γ∥(ℓ) = k_BT/D directly.

**2. Independent check at each height.** Oscillate the piezo stage
sinusoidally and read the spike (Tolić-Nørrelykke 2006).
- It measures γ without assuming it, and tests the pixel scale and the blur
  correction.
- The registered observable `trapped_particle_drag_offset`, at constant stage
  velocity, is a cheaper third check once κ is known.

**3. Height from the data.** Fit Faxén to γ∥ against the nominal z position.
- Free parameters: the surface offset, the focal-shift factor, and the bulk
  drag (which absorbs radius and viscosity).
- Use only ℓ/R ≳ 1.4.
- Compare the normal direction with Bevan–Prieve if z can be tracked.
- Lavaud 2021 found the wall to about 10 nm this way.

**4. Objective.**
- The **40x water objective** should give a focal-shift factor near 1 and
  depth-independent stiffness. That makes it the cleanest first series.
- Repeating the series with the 60x and 100x oil objectives then measures the
  focal shift itself.
- Never carry a calibration across heights or across objectives.

**5. Isolation.** One bead at a time, with no other trap active. Either the
chamber is thick enough, or the fit model includes the far wall.

**What we must measure ourselves:**
- h = 0;
- the focal-shift factor, per objective;
- the pixel size;
- the true exposure time and frame timing;
- the temperature at the laser power used;
- each bead's bulk drag;
- the stiffness at every height.

**What we can take from theory:**
- the shape of the wall correction (Faxén parallel; Brenner, through
  Bevan–Prieve, normal);
- the frequency-dependent drag;
- the blur and aliasing transfer functions.

**Simulation side.**
- The same correction can go into Brownian dynamics as a position-dependent
  mobility. The simulation and the experiment then test one formula from
  both ends.
- Nørrelykke & Flyvbjerg 2011 give an exact simulation of time-lapse trap
  data, which is a test bench for the analysis code.

**Open choices for the person:**
- **Bead size.** 2 µm is a compromise. 5 µm settles fast and is easy to see,
  but its wall effect reaches about 140 µm.
- **Objective order.**
- **Laser power.**
- **Chamber thickness.**
- **Whether z is tracked as well as x–y.**

**No published closed-loop or autonomous routine for surface-referenced trap
calibration was found** (searched up to 2026).

---

## Bibliography

DOIs were resolved against Crossref on 2026-11-04. The read level is in
brackets.

**Theory**
- Brenner, H. (1961). Chem. Eng. Sci. 16, 242–251. doi:10.1016/0009-2509(61)80035-3 [abstract]
- Goldman, A. J., Cox, R. G. & Brenner, H. (1967). Chem. Eng. Sci. 22, 637–651. doi:10.1016/0009-2509(67)80047-2 [abstract]
- Cox, R. G. & Brenner, H. (1967). Chem. Eng. Sci. 22, 1753–1777. doi:10.1016/0009-2509(67)80208-2 [record]
- Bevan, M. A. & Prieve, D. C. (2000). J. Chem. Phys. 113, 1228–1236. doi:10.1063/1.481900 [abstract; formula secondary]
- Eloul, S. & Compton, R. G. (2016). J. Phys. Chem. Lett. 7, 4317–4321. doi:10.1021/acs.jpclett.6b02275 [passage]

**Measurements near a wall**
- Faucheux, L. P. & Libchaber, A. J. (1994). Phys. Rev. E 49, 5158. doi:10.1103/PhysRevE.49.5158 [abstract]
- Pralle, A. et al. (1998). Appl. Phys. A 66, S71–S73. doi:10.1007/s003390051102 [abstract]
- Pralle, A. et al. (1999). Microsc. Res. Tech. 44, 378–386. doi:10.1002/(SICI)1097-0029(19990301)44:5<378::AID-JEMT10>3.0.CO;2-Z [abstract; detection method]
- Lin, B., Yu, J. & Rice, S. A. (2000). Phys. Rev. E 62, 3909. doi:10.1103/PhysRevE.62.3909 [abstract]
- Dufresne, E. R., Squires, T. M., Brenner, M. P. & Grier, D. G. (2000). Phys. Rev. Lett. 85, 3317. doi:10.1103/PhysRevLett.85.3317 [full, arXiv]
- Schäffer, E., Nørrelykke, S. F. & Howard, J. (2007). Langmuir 23, 3654–3665. doi:10.1021/la0622368 [abstract]
- Carbajal-Tinoco, M. D. et al. (2007). Phys. Rev. Lett. 99, 138303. doi:10.1103/PhysRevLett.99.138303 [abstract]
- Huang, P. & Breuer, K. S. (2007). Phys. Rev. E 76, 046307. doi:10.1103/PhysRevE.76.046307 [abstract]
- Choi, C. K., Margraves, C. H. & Kihm, K. D. (2007). Phys. Fluids 19, 103305. doi:10.1063/1.2798811 [abstract]
- Leach, J. et al. (2009). Phys. Rev. E 79, 026301. doi:10.1103/PhysRevE.79.026301 [abstract]
- Mo, J., Simha, A. & Raizen, M. G. (2015). Phys. Rev. E 92, 062106. doi:10.1103/PhysRevE.92.062106 [abstract]
- Lavaud, M., Salez, T., Louyer, Y. & Amarouchene, Y. (2021). Phys. Rev. Research 3, L032011. doi:10.1103/PhysRevResearch.3.L032011 [full, arXiv 2012.05512]
- Gillant, F. et al. (2023). J. Eur. Opt. Soc.-Rapid Publ. 19, 28. doi:10.1051/jeos/2023026 [abstract]

**Calibration methods**
- Berg-Sørensen, K. & Flyvbjerg, H. (2004). Rev. Sci. Instrum. 75, 594–612. doi:10.1063/1.1645654 [abstract]
- Neuman, K. C. & Block, S. M. (2004). Rev. Sci. Instrum. 75, 2787–2809. doi:10.1063/1.1785844 [abstract]
- Berg-Sørensen, K. et al. (2006). Rev. Sci. Instrum. 77, 063106. doi:10.1063/1.2204589 [abstract; photodiode filtering]
- Tolić-Nørrelykke, S. F. et al. (2006). Rev. Sci. Instrum. 77, 103101. doi:10.1063/1.2356852 [full, arXiv]
- Vermeulen, K. C. et al. (2006). Rev. Sci. Instrum. 77, 013704. doi:10.1063/1.2165568 [abstract; AOD-based detector calibration]
- Richly, M. U. et al. (2013). Opt. Express 21, 31578. doi:10.1364/OE.21.031578 [abstract]
- Jun, Y. et al. (2014). Biophys. J. 107, 1474–1484. doi:10.1016/j.bpj.2014.07.033 [full]
- Pérez García, L. et al. (2018). Nat. Commun. 9, 5166. doi:10.1038/s41467-018-07437-x [abstract]
- Argun, A. et al. (2020). Appl. Phys. Rev. 7, 041404. doi:10.1063/5.0019105 [abstract]
- Gieseler, J. et al. (2021). Adv. Opt. Photon. 13, 74–241. doi:10.1364/AOP.394888 [abstract; tutorial with code]

**Focal shift, aberration, heating**
- Peterman, E. J. G., Gittes, F. & Schmidt, C. F. (2003). Biophys. J. 84, 1308–1316. doi:10.1016/S0006-3495(03)74946-7 [abstract]
- Neuman, K. C., Abbondanzieri, E. A. & Block, S. M. (2005). Opt. Lett. 30, 1318. doi:10.1364/OL.30.001318 [full]
- Deufel, C. & Wang, M. D. (2006). Biophys. J. 90, 657–667. doi:10.1529/biophysj.105.065458 [full]
- Vermeulen, K. C. et al. (2006). Appl. Opt. 45, 1812. doi:10.1364/AO.45.001812 [abstract]
- Reihani, S. N. S. & Oddershede, L. B. (2007). Opt. Lett. 32, 1998. doi:10.1364/OL.32.001998 [abstract]
- Viana, N. B. et al. (2007). Phys. Rev. E 75, 021914. doi:10.1103/PhysRevE.75.021914 [abstract]
- Dutra, R. S. et al. (2012). Appl. Phys. Lett. 100, 131115. doi:10.1063/1.3699273 [abstract]
- Dutra, R. S. et al. (2014). Phys. Rev. A 90, 013825. doi:10.1103/PhysRevA.90.013825 [record]

**Video tracking**
- Wong, W. P. & Halvorsen, K. (2006). Opt. Express 14, 12517. doi:10.1364/OE.14.012517 [full, arXiv]
- Gibson, G. M. et al. (2008). Opt. Express 16, 14561. doi:10.1364/OE.16.014561 [abstract]
- van der Horst, A. & Forde, N. R. (2010). Opt. Express 18, 7670. doi:10.1364/OE.18.007670 [abstract]
- Nørrelykke, S. F. & Flyvbjerg, H. (2011). Phys. Rev. E 83, 041103. doi:10.1103/PhysRevE.83.041103 [abstract]
- Lansdorp, B. M. & Saleh, O. A. (2012). Rev. Sci. Instrum. 83, 025115. doi:10.1063/1.3687431 [abstract; erratum RSI 85, 019901 (2014)]

**Inertia and hydrodynamic memory**
- Franosch, T. et al. (2011). Nature 478, 85–88. doi:10.1038/nature10498 [full, arXiv]
- Jannasch, A., Mahamdeh, M. & Schäffer, E. (2011). Phys. Rev. Lett. 107, 228301. doi:10.1103/PhysRevLett.107.228301 [abstract]
- Ferreira, Q. et al. (2026). arXiv:2606.09193. **Preprint, not peer reviewed** [full]

**Not confirmed.** These were cited from memory or from a secondary source
only. Do not cite them without checking:
- Faxén's original, usually given as Ark. Mat. Astron. Fys. 17(27), 1923, or
  his 1921 thesis;
- O'Neill 1964, Mathematika;
- Happel & Brenner, *Low Reynolds Number Hydrodynamics*, 1965;
- Brenner's normal series written out term by term;
- the Goldman–Cox–Brenner near-contact asymptote −(8/15) ln(g/R) + 0.9588;
- Neuman & Block's focal-shift values of 0.82 and 0.80, seen only as Deufel &
  Wang quote them.
