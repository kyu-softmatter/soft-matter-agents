# Quantity: temperature

Every entry in the store about the quantity temperature.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> Thermodynamic temperature. Where it was read is a property of the number and belongs in `at`, not in the name.

- unit: `K`
- kind: physical

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| ambient_temperature | 293 | K | from a document, a reading off the instrument, or another project's record; the person read it off the instrument | E3 · operator_read:kyuhwan_20260917 | none stated | none | quantity ambient_temperature, quantity temperature | [lab_ambient_temperature](../entries/lab_ambient_temperature.json) |
| temperature_stability | 1 | K | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260923 | none stated | none | quantity temperature_stability, quantity ambient_temperature, quantity temperature | [room_temperature_hold_band](../entries/room_temperature_hold_band.json) |
| temperature_resolution | 1 | K | recalled or assumed; the person's recollection | E5 · operator_recall:kyuhwan_20260923 | none stated | none | quantity temperature_resolution, quantity ambient_temperature, quantity temperature | [room_thermometer_reads_in_one_kelvin_steps](../entries/room_thermometer_reads_in_one_kelvin_steps.json) |

## Claims

### [no_thermometer_at_the_sample](../entries/no_thermometer_at_the_sample.json)

There is no thermometer beside the sample. The only thermometer in the laboratory reads the room, so any temperature attributed to the sample is a room reading applied to it.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260919).

Conditions, verbatim:

> This laboratory as of 2026-09-19, read by the operator. It REPLACES an inference: lab_ambient_temperature reasoned that its value could only be the room's, from the fact that nothing actuates the sample. The same conclusion is now stated, which is a stronger claim than a consequence of an absence, and it is why the sample-adjacent reading stops being an open question. What it does NOT say is how far the room thermometer is from the sample or how well the two track -- neither is known, and an unknown distance is not a small one. Falsified by putting a thermometer at the sample, which is also what would close the two questions it leaves open.

### [room_temperature_is_controlled](../entries/room_temperature_is_controlled.json)

The room is held continuously by air conditioning. There is a setpoint on this instrument's environment -- it is the room's, not the sample's.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; the person read it off the instrument (E3 · operator_read:kyuhwan_20260919).

Conditions, verbatim:

> This laboratory as of 2026-09-19, read by the operator. It runs opposite to how it sounds, and that is the reason it is worth an entry: holding the room does not shrink the sample question, it ISOLATES it. With the room held, whatever still moves at the sample is local -- illumination, a contacting objective, the stage, the trapping laser -- and each of those has its own gap. Do not read 'the room is controlled' as 'temperature is handled'. It also corrected a sentence in this store: lab_ambient_temperature argued that 20 C could not be a setpoint because nothing actuates the temperature, which collapsed 'nothing actuates the SAMPLE' into 'nothing actuates'. That grade never rested on the argument and did not move; the reasoning did. What this entry does NOT say: what the setpoint is, how tightly the room holds it, and how well the sample follows the room. The third is the one that matters and all three are open -- a controlled room is not a controlled sample, and the distance between them is still unmeasured.

### [declared_versus_inferred_temperature](../entries/declared_versus_inferred_temperature.json)

Temperature enters the two sides differently, and the difference is not symmetric. In the `bd_overdamped` simulation the declared temperature is realised by construction -- it is a parameter of the noise amplitude and there is no mechanism that could fail to realise it -- so citing a temperature there records WHY the number was chosen and is not evidence about the model's temperature. In the experiment nothing actuates the sample and the only thermometer reads the room, so a temperature used there is INFERRED, and citing the same entry is a claim about the sample. The uncertainty therefore sits entirely on the experiment side.

Identifiers: none

How it is known: computed; computed from other values (E4 · computed:temperature_asymmetry).

Conditions, verbatim:

> Holds while both halves hold, and each is separately falsifiable. The experiment half rests on sample_temperature_not_actuated and on lab_ambient_temperature being a reading of the room: connect the temperature stage, or record where the thermometer sits relative to the sample, and it changes. The simulation half rested on a premise this store does not hold -- and it was ANSWERED on 2026-09-20, in a better form than it was asked. There is no thermostat in `bd_overdamped`: the integrator is a position-only Wiener increment, positions + normal(0, sqrt(2*D*dt)) with D = k_B*T/(3*pi*eta*d), so no velocity is represented, there is no kinetic energy, and there is nothing to thermostat. Temperature is a parameter of the noise amplitude. So the premise is true CONSTITUTIVELY rather than empirically, and the confirmation this entry asked for is one that configuration cannot supply -- asking for it was the error, not leaving it open. E4 rather than E3 because a consequence is never better than the derivation that produced it, whatever the grade of its inputs. What this entry does NOT say is how large the experiment-side uncertainty is; that needs the thermometer's distance from the sample and how well the two track, and neither is known. WHAT THIS ENTRY RESTS ON, NAMED, BECAUSE CHECK 62 FOUND IT HAD NO `inputs` AND THE PROSE IS WHERE THEY WERE. Three supports. (1) sample_temperature_not_actuated, E3 -- nothing drives the sample temperature. (2) no_thermometer_at_the_sample, E3 -- the only reading is the room's, which is what makes the experiment side INFERRED rather than measured. (3) the declared temperature being realised in `bd_overdamped`, which this store does NOT hold and should not. It is settled and the settlement lives outside this store, in contracts/capabilities/simulation.json's `temperature_realisation` field, marked `kind: constitutive` and measured from the integrator's code by simulation-2 rather than read off a label (976522e). It is recorded in a field a check can read rather than in prose, which is why this entry can point at it. IT HOLDS FOR BOTH BUILDS OF THIS CONFIGURATION, AND THE SENTENCE THAT SAID OTHERWISE WAS WRONG TWICE OVER. This read `the HOOMD backend is unconfirmed, and hoomd_backend.py exists at 456 lines without being installed`. HOOMD 7.2.0 has been installed since the morning of 2026-09-22 -- verified here by importing it rather than by being told: version 7.2.0, gpu_enabled False, mpi_enabled False. And the exception it drew was unnecessary: hoomd.md.methods.Brownian does not evolve velocities either. Its documentation says particle velocities are completely decoupled from positions and that a fresh velocity distribution is drawn at the set temperature every step, while the position update carries no velocity term. So nothing carries kinetic energy that evolves, in either build, and the premise holds for the same reason in both. Settled by simulation_agent reading the v7.2.0 documentation on 2026-09-22. AND THE HOOMD BUILD CARRIES A TRAP THE MOCK DOES NOT, which is the part worth having: HOOMD's velocity array EXISTS even though it is inert, so a kinetic temperature computed from it comes back as the set kT -- not because the engine realised anything, but because that array is a fresh Maxwell-Boltzmann draw at that kT on every step. IT IS NOT AN EMPIRICAL CONFIRMATION AND MUST NOT BE READ AS ONE. A reading that always agrees is not evidence that the thing is right; it is evidence that the reading cannot disagree. Anything that represents velocities and integrates them WOULD put the premise back, and neither build does. HOW THE FALSE SENTENCE GOT IN, because the shape matters more than the sentence: both halves -- the line count and the not-installed -- came to this seat in a message from simulation-2 and were written into an entry as plain fact, with no mark that they were relayed and unverified. This store spent the same day refusing exactly that on the microscope side, where a relayed `ZDrive` was entered only after being found in code positions. A relayed fact is a fact and a relayed fact written down unmarked is a claim this store cannot support. The line count is not restored here in any form: nothing in this entry needs it. AND NONE OF THE THREE CAN BE AN `input`. Check 62 builds its carriers from `numbers[].name` only, so a support has to be a QUANTITY to resolve; two of these three are claims carrying no numbers at all, and the third is not in the store. So the empty `inputs` was not an omission that writing a list would fix. WHAT THE SOURCE KIND IS DOING. `computed:` is right about the GRADE -- a consequence is capped at E4 and can be no better than its worst support, and max(E4, E3) is the E4 declared here. It is wrong about the SHAPE: `computed:` and `inputs` were built for a value composed from quantities, which is what tau_d and tracer_diffusivity_expected are, and this is a claim reasoned from claims. One prefix is doing two jobs and check 62 sees the seam. Raised with manager-librarian, who owns the source vocabulary: what is missing is a way to record SUPPORT BY CLAIM separately from INPUT BY QUANTITY. Nothing was invented here to make the check quieter. THE THREE SUPPORTS ARE NOW IN `supports`, NOT IN THIS PARAGRAPH. manager-librarian added the field on 2026-09-20 for exactly this entry. Two are `entry` supports whose own grades cap the inference; the third is `external` and stops the composition, which is the honest outcome -- an ungraded premise cannot cap anything, and a number that quietly ignored it would be worse than no number. The prose above is kept because it is the argument, and the field is what a check can read. THE ASYMMETRY THIS ENTRY EXISTS FOR IS UNCHANGED AND STANDS ON FIRMER GROUND. A parameter cannot be wrong about itself the way a thermostat can fail to reach a setpoint, so the simulation side is now the more certain of the two by a wider margin than the original wording claimed. Nothing about the experiment side moved: nothing actuates the sample and the only thermometer still reads the room. THE GRADE DOES NOT MOVE EITHER. `supports` carries claims and not quantities, so no grade ever composed from these three; check 62 reports this entry as resting partly on a premise the store does not hold, and that report stays correct -- the premise is answered, not absorbed. E4 comes from `computed:` and is untouched.

### [trap_heating_detection_bound](../entries/trap_heating_detection_bound.json)

The operator recalls not noticing a temperature change in the sample unless the infrared trapping laser was driven above roughly 20 percent on its dial. This records where noticing stopped, by means that were not recorded.

Identifiers: none

How it is known: recalled or assumed; the person's recollection (E5 · operator_recall:kyuhwan_20260919).

Conditions, verbatim:

> THIS IS NOT A LIMIT AND MAY NOT BE USED AS ONE. 'Keep it under 20 percent' is the sentence someone lifts out of an entry and uses to parameterise a laser, and three separate rules forbid that: safety limits live in a file a person writes and in deterministic code (P0, 2.1 rule 7), they do not transfer (10.3 rule 4), and the grade forbids it on its own -- an E5 may not parameterise an irreversible action without a person's individual approval, and raising laser power onto a sample is irreversible to the sample. Anyone needing a bound writes one in envelope/safety.json after confirming it physically. Three things this says less than it appears to. It is RECALLED, not read, which is why it is E5 while the neighbouring instrument facts are E3. It is a DETECTION BOUND and not a zero: 'did not notice' was measured by unrecorded means, and 'no heating below 20 percent' is a stronger claim than was made. And 20 PERCENT IS A DIAL READING, not a power: a percentage of an unstated maximum is not a quantity, and writing it into numbers[] would not make it one -- the same ruling that keeps a nominal magnification out of numbers[], wearing different clothes. It does not close the heating gap. A measured heating rate is still absent, and a gap that looks satisfied by an E5 recollection is a false absence running backwards. What it does is sharpen what to measure: sweep the dial with a thermometer that has a recorded position, and the bound becomes a curve.

## Disputed and withdrawn

None.

## Reading

- [he_2020_colloidal_diamond.md](../distilled/he_2020_colloidal_diamond.md)
- [kim_2026_depletion_colloidal_diamond.md](../distilled/kim_2026_depletion_colloidal_diamond.md)
- [operator_verification_20260917.md](../distilled/operator_verification_20260917.md)
- [pretti_2019_size_dependent_selection.md](../distilled/pretti_2019_size_dependent_selection.md)
- [shee_2025_active_dopants_rheology.md](../distilled/shee_2025_active_dopants_rheology.md)
- [vyas_2026_nonequilibrium_melting.md](../distilled/vyas_2026_nonequilibrium_melting.md)
- [water_viscosity.md](../distilled/water_viscosity.md)
- [what_falsifies_the_49_bench_claims.md](../distilled/what_falsifies_the_49_bench_claims.md)

## Related

- [configuration trapping](../wiki/configuration_trapping.md)
- [device optical_tweezers](../wiki/device_optical_tweezers.md)
- [observable tracer_diffusivity](../wiki/observable_tracer_diffusivity.md)
- [quantity ambient_temperature](../wiki/quantity_ambient_temperature.md)

---

Generated from the knowledge store at kbv-d027f44dadc0. Do not edit by hand: correct the store and regenerate.
