# Quantity: hexatic_order_parameter

Every entry in the store about the quantity hexatic_order_parameter.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> |Psi_6| = |(1/N) sum_j psi_6,j|: the magnitude of the six-fold bond-orientational order averaged over all N particles, where psi_6,j is particle j's local bond-orientational order.

- unit: `1`
- kind: physical

## Values

| quantity | value | unit | how it is known | grade and source as recorded | conditions | identifiers | subject | entry |
|---|---|---|---|---|---|---|---|---|
| hexatic_correlation_exponent | 0.25 | 1 | from a document, a reading off the instrument, or another project's record; published literature | E3 · literature:src_vyas_2026_nonequilibrium_melting | none stated | none | quantity hexatic_correlation_exponent, quantity hexatic_order_parameter | [driven_2d_dipolar_crystal_melting_follows_defect_densities_in_simulation](../entries/driven_2d_dipolar_crystal_melting_follows_defect_densities_in_simulation.json) |

## Claims

### [charged_colloids_2d_driven_melting_follows_defect_densities_in_experiment](../entries/charged_colloids_2d_driven_melting_follows_defect_densities_in_experiment.json)

In experiment, a two-dimensional crystal of charged PMMA microspheres at an oil-water interface, melted either thermally by changing the density or by spinning magnetic TPM-haematite particles held beneath a fraction of the sites, loses hexatic order as a function of isolated disclination density along one curve for both routes and loses translational order as isolated dislocations appear, as the simulations do.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; published literature (E3 · literature:src_vyas_2026_nonequilibrium_melting).

Conditions, verbatim:

> AN EXPERIMENT, NOT A MODEL RESULT. The particles repel as permanent dipoles, U = A/r^3; a droplet about 1 cm across holds about 1e5 particles and each analysed sample about 1e3 to 1e4; the magnetic particles are rotated by an external rotating field and their flows break detailed balance. The authors read both routes as topological rather than thermal melting. The simulation side is driven_2d_dipolar_crystal_melting_follows_defect_densities_in_simulation.

### [driven_2d_dipolar_crystal_has_no_single_effective_temperature](../entries/driven_2d_dipolar_crystal_has_no_single_effective_temperature.json)

In the same simulations, no single effective temperature describes the driven crystal: its fluid is superdiffusive where the thermal fluid is diffusive, and hexatic order and disclination density plotted against dislocation density give separate curves for driven and thermal melting, so each transition is predicted by its own defect density but the two are not tied together by one temperature.

Identifiers: none

How it is known: from a document, a reading off the instrument, or another project's record; published literature (E3 · literature:src_vyas_2026_nonequilibrium_melting).

Conditions, verbatim:

> A MODEL RESULT, filed apart from the experiment. Molecular dynamics in HOOMD-Blue v4.4.1 with custom plug-ins described only in the Supplementary Information: two-dimensional particles with dipolar repulsion U = A/r^3, a fraction of sites being spinners whose rotlet flow, cut off at 1.5 particle radii, adds transverse forces; roughly 1e5 to 1e6 particles; integrator, thermostat and time step not stated in the file. Thermal melting is by the inverse temperature Gamma = A (pi rho)^(3/2)/kT, driven melting by the ratio of spinner drag to dipolar force. The paper reports the same comparison in its experiments (Fig. 5). It finds no measurable odd-elastic signature, a rough estimate giving odd-to-conventional elastic constants of order 1e-2 (Supplementary Information).

## Disputed and withdrawn

None.

## Reading

None.

## Related

- [quantity hexatic_correlation_exponent](../wiki/quantity_hexatic_correlation_exponent.md)

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
