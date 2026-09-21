# 017 — rulings

Items considered from `agentic-microscope` under §10.2 row 3, which opened
when the person wrote `envelope/safety.json` (`c1404bf`). Judged by
`manager-microscope` on 2026-09-20. **No number crossed by this seat's hand**
— every transfer below is a request to the librarian with a location, per
§10.3's routing.

```
transfer  | branch label lied, integer authoritative | slot A4 | 10.3 rule 2
downgrade | anything keyed by that branch's label    | E5      | 10.3 rule 2
transfer  | camera read noise, keyed by mode         | slot A1 | 10.3 rule 1
transfer  | quantum efficiency, peak and curve       | slot A1 | 10.3 rule 1
transfer  | sensor array and pixel pitch             | slot A6 | 10.3 rule 1
discard   | full well, dark current                  | no axis asks for either
discard   | the Micro-Manager .cfg as a file         | 10.2.1, one machine at one moment
discard   | nominal magnification with back-derived precision | 5.3 refuses it; already recorded
```

**The drops are as much of the result as the transfers** (§9.3), and two of
the three are drops of things it would have been easy to take: the `.cfg`
because it is exactly what was asked for, and full well because it sits in
the same block as figures that did transfer.

**The first line is the one to read twice.** What transfers is not a value
and not a label — it is that on that branch the enum name was wrong and the
integer was right, which cost that project a two-day false falsification.
Carrying the label would have carried the defect; carrying the discipline is
what §10.2.1 means by *not transplanted as it stands*.
