# Observable: tracer_diffusivity

Every entry in the store about the observable tracer_diffusivity.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/observables.json:

> The short-time translational self-diffusion coefficient of dilute spherical tracers in the sample: the proportionality between mean squared displacement and lag time in the free regime, before hindrance by walls or by neighbouring particles sets in.

- units: ["um^2/s", "m^2/s"]
- estimator: Weighted least-squares fit of the mean squared displacement of single-particle positions against lag time, with the intercept left free so that localisation error stays out of the slope. D = slope / (2 * spatial_dimensions). Fit range: lags from one save interval up to max_lag_time, which must satisfy both bounds -- below the diffusive time tau_d, so the tracer is still free, and short enough against the record that every lag in the fit is determined. The plan declares the value and shows both. Weighting: by the number of independent displacements at each lag. A record of length T yields about T/tau of them at lag tau, so the variance of the MSD estimate grows sharply with lag, and equal weights hand the slope to the points that have the fewest samples. This is not a refinement: measured on the simulation side, equal weights over whole-record lags gave a 7 percent bias at 0.16 percent relative standard error -- a number that looks precise and is wrong, which is the failure a shared estimator exists to prevent.

## Values

None.

## Claims

### [declared_versus_inferred_temperature](../entries/declared_versus_inferred_temperature.json)

Temperature enters the two sides differently, and the difference is not symmetric. In the `bd_overdamped` simulation the declared temperature is realised by construction -- it is a parameter of the noise amplitude and there is no mechanism that could fail to realise it -- so citing a temperature there records WHY the number was chosen and is not evidence about the model's temperature. In the experiment nothing actuates the sample and the only thermometer reads the room, so a temperature used there is INFERRED, and citing the same entry is a claim about the sample. The uncertainty therefore sits entirely on the experiment side.

Identifiers: none

How it is known: computed; computed from other values (E4 · computed:temperature_asymmetry).

Conditions, verbatim:

> Holds while both halves hold, and each is separately falsifiable. The experiment half rests on sample_temperature_not_actuated and on lab_ambient_temperature being a reading of the room: connect the temperature stage, or record where the thermometer sits relative to the sample, and it changes. The simulation half rested on a premise this store does not hold -- and it was ANSWERED on 2026-09-20, in a better form than it was asked. There is no thermostat in `bd_overdamped`: the integrator is a position-only Wiener increment, positions + normal(0, sqrt(2*D*dt)) with D = k_B*T/(3*pi*eta*d), so no velocity is represented, there is no kinetic energy, and there is nothing to thermostat. Temperature is a parameter of the noise amplitude. So the premise is true CONSTITUTIVELY rather than empirically, and the confirmation this entry asked for is one that configuration cannot supply -- asking for it was the error, not leaving it open. E4 rather than E3 because a consequence is never better than the derivation that produced it, whatever the grade of its inputs. What this entry does NOT say is how large the experiment-side uncertainty is; that needs the thermometer's distance from the sample and how well the two track, and neither is known. WHAT THIS ENTRY RESTS ON, NAMED, BECAUSE CHECK 62 FOUND IT HAD NO `inputs` AND THE PROSE IS WHERE THEY WERE. Three supports. (1) sample_temperature_not_actuated, E3 -- nothing drives the sample temperature. (2) no_thermometer_at_the_sample, E3 -- the only reading is the room's, which is what makes the experiment side INFERRED rather than measured. (3) the declared temperature being realised in `bd_overdamped`, which this store does NOT hold and should not. It is settled and the settlement lives outside this store, in contracts/capabilities/simulation.json's `temperature_realisation` field, marked `kind: constitutive` and measured from the integrator's code by simulation-2 rather than read off a label (976522e). It is recorded in a field a check can read rather than in prose, which is why this entry can point at it. IT HOLDS FOR BOTH BUILDS OF THIS CONFIGURATION, AND THE SENTENCE THAT SAID OTHERWISE WAS WRONG TWICE OVER. This read `the HOOMD backend is unconfirmed, and hoomd_backend.py exists at 456 lines without being installed`. HOOMD 7.2.0 has been installed since the morning of 2026-09-22 -- verified here by importing it rather than by being told: version 7.2.0, gpu_enabled False, mpi_enabled False. And the exception it drew was unnecessary: hoomd.md.methods.Brownian does not evolve velocities either. Its documentation says particle velocities are completely decoupled from positions and that a fresh velocity distribution is drawn at the set temperature every step, while the position update carries no velocity term. So nothing carries kinetic energy that evolves, in either build, and the premise holds for the same reason in both. Settled by simulation_agent reading the v7.2.0 documentation on 2026-09-22. AND THE HOOMD BUILD CARRIES A TRAP THE MOCK DOES NOT, which is the part worth having: HOOMD's velocity array EXISTS even though it is inert, so a kinetic temperature computed from it comes back as the set kT -- not because the engine realised anything, but because that array is a fresh Maxwell-Boltzmann draw at that kT on every step. IT IS NOT AN EMPIRICAL CONFIRMATION AND MUST NOT BE READ AS ONE. A reading that always agrees is not evidence that the thing is right; it is evidence that the reading cannot disagree. Anything that represents velocities and integrates them WOULD put the premise back, and neither build does. HOW THE FALSE SENTENCE GOT IN, because the shape matters more than the sentence: both halves -- the line count and the not-installed -- came to this seat in a message from simulation-2 and were written into an entry as plain fact, with no mark that they were relayed and unverified. This store spent the same day refusing exactly that on the microscope side, where a relayed `ZDrive` was entered only after being found in code positions. A relayed fact is a fact and a relayed fact written down unmarked is a claim this store cannot support. The line count is not restored here in any form: nothing in this entry needs it. AND NONE OF THE THREE CAN BE AN `input`. Check 62 builds its carriers from `numbers[].name` only, so a support has to be a QUANTITY to resolve; two of these three are claims carrying no numbers at all, and the third is not in the store. So the empty `inputs` was not an omission that writing a list would fix. WHAT THE SOURCE KIND IS DOING. `computed:` is right about the GRADE -- a consequence is capped at E4 and can be no better than its worst support, and max(E4, E3) is the E4 declared here. It is wrong about the SHAPE: `computed:` and `inputs` were built for a value composed from quantities, which is what tau_d and tracer_diffusivity_expected are, and this is a claim reasoned from claims. One prefix is doing two jobs and check 62 sees the seam. Raised with manager-librarian, who owns the source vocabulary: what is missing is a way to record SUPPORT BY CLAIM separately from INPUT BY QUANTITY. Nothing was invented here to make the check quieter. THE THREE SUPPORTS ARE NOW IN `supports`, NOT IN THIS PARAGRAPH. manager-librarian added the field on 2026-09-20 for exactly this entry. Two are `entry` supports whose own grades cap the inference; the third is `external` and stops the composition, which is the honest outcome -- an ungraded premise cannot cap anything, and a number that quietly ignored it would be worse than no number. The prose above is kept because it is the argument, and the field is what a check can read. THE ASYMMETRY THIS ENTRY EXISTS FOR IS UNCHANGED AND STANDS ON FIRMER GROUND. A parameter cannot be wrong about itself the way a thermostat can fail to reach a setpoint, so the simulation side is now the more certain of the two by a wider margin than the original wording claimed. Nothing about the experiment side moved: nothing actuates the sample and the only thermometer still reads the room. THE GRADE DOES NOT MOVE EITHER. `supports` carries claims and not quantities, so no grade ever composed from these three; check 62 reports this entry as resting partly on a premise the store does not hold, and that report stays correct -- the premise is answered, not absorbed. E4 comes from `computed:` and is untouched.

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [quantity temperature](../wiki/quantity_temperature.md)

---

Generated from the knowledge store at kbv-058ce14eea72. Do not edit by hand: correct the store and regenerate.
