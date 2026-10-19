# Quantity: tau_d

Every entry in the store about the quantity tau_d.

Generated from the store; cite the entries, as `kb:<entry_id>`, not this page.

## What it is

From the managers' registry, contracts/quantities.json:

> Diffusive time: the time a sphere needs to diffuse its own diameter. A derived quantity with a formula rather than a stored value, and it keeps a dimension -- length squared over a diffusivity is a time.

- unit: `s`
- kind: physical

## Values

None.

## Claims

### [tau_d](../entries/tau_d.json)

The diffusive time is the time a sphere needs to diffuse its own diameter, and it sets the shortest record length from which a mean squared displacement can be read.

Identifiers: none

How it is known: computed; computed from other values (E4 · computed:diffusive_time).

Conditions, verbatim:

> A length squared over a diffusivity is a TIME, and the unit above says so: this is a derived quantity that keeps a dimension, not a dimensionless group. Physically: spherical tracer, bulk fluid, no slip, overdamped. Near a wall the drag is corrected separately rather than absorbed into this time, or the time unit changes with stage position and nothing can be compared. ITS INPUTS ARE FORMAL PARAMETERS, AND THAT IS THE COMPLETE AND PERMANENT STATE. `bead_diameter` and `diffusivity` name the ARGUMENTS of a relation, not particular values in this store, and check 62 correctly reports that nothing carries them. That is not a gap waiting on a later milestone -- 4.3.1 separates looked-for-and-absent from there-is-nothing-to-look-for, and this is the second. Binding them to entries would be worse than leaving them: pointing `bead_diameter` at tracer_diameter_measured would make a relation true of ANY sphere read as a claim about one bottle on one bench, which is the instance/type error with the subject changed. AND A FORMULA HAS NO WORST INPUT TO INHERIT. 5.3's max(E4, worst input) is a rule about a computed VALUE, where the inputs are numbers carrying grades. A relation composes no numbers, so there is no worst input -- not one the store is missing, one the object does not have. This entry is E4 because the relation is textbook, which is what grade_tag and src_colloid_dynamics say, and it would still be E4 in a store holding no diameters at all. Ruled 2026-09-20 under task 020: a derived_quantity whose inputs are formal parameters is a COMPLETE entry and belongs on no fix list. Nothing check 62 reads was changed to make it say so.

## Disputed and withdrawn

None.

## Reading

- [implementing_61_and_62.md](../distilled/implementing_61_and_62.md)
- [verification_of_017_20260919.md](../distilled/verification_of_017_20260919.md)

## Related

None.

---

Generated from the knowledge store at kbv-37b1958fb73d. Do not edit by hand: correct the store and regenerate.
