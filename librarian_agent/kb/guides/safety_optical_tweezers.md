# Safety guide: Optical tweezers (Aresis Tweez 300)

What the manufacturer's own documents on this computer say about this device's hazards, and where they say it. Everything here is the manufacturer's statement; nothing on this page was measured on this bench.

## What the manufacturer warns about

- In the tweezers software the laser power is set on a relative scale from 0 to 1, where 1 is the maximum -- about 5 W on the Tweez 305 and about 10 W on the Tweez 310 -- and an internal photodiode's reading of the actual power is shown alongside.  
  *Source: Tweez 300 User Manual, page 24 (PDF 30).*
- Before setting up the calibration photodiode the laser must be switched off, or it can injure eyes or skin and damage the photodiode. The objective must be fully retracted before the photodiode is placed on the sample holder, and its position adjusted with great care, so as not to damage the objective's front lens.  
  *Source: Tweez 300 User Manual, pages 28, 29 (PDF 34, 35).*
- The manufacturer warns that the product can expose users to nickel and other chemicals listed by the State of California as causing cancer, and that it must go to electronic-waste recycling at end of life.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 3 (PDF 5).*
- The tweezers contain no user-serviceable parts; servicing is for qualified personnel only, and the system must not be operated with covers or panels removed. Exposed connections must not be touched while power is on.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6).*
- The tweezers must be earthed through the grounding conductor of the specified, certified power cord before anything else is connected or power applied. The back-panel grounding post is only for additional earthing or equalising potential with the table or microscope.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), pages 4, 9, 8 (PDF 6, 11, 10).*
- The tweezers are designed for a research laboratory at 20 to 28 degrees Celsius and 20 to 80 per cent relative humidity, non-condensing, and must never be stored or run in a wet, damp or dusty place.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), pages 4, 11 (PDF 6, 13).*
- The ventilation openings on the back panel and underside of the tweezers must not be obstructed, to avoid fire or permanent damage.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6).*
- When the tweezers' System Manager program is closed the system goes to standby, and after 10 minutes to hibernation; to leave hibernation the key switch is turned to OFF and back to ON.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 6 (PDF 8).*
- Two back-panel inputs have absolute maximum ratings, and exceeding them can permanently damage the input: the 10 MHz reference clock input, 5 volts peak to peak, and the general-purpose GPIO A and B connectors, 5 volts.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 7 (PDF 9).*
- Several tweezers connectors are proprietary and take only Aresis equipment: the LEMO trigger connector only the original Aresis camera cable; the DisplayPort-shaped expansion connector must never go to a monitor or TV, or the tweezers or the monitor may be permanently damaged; and the RJ45 interlock connector only the Aresis laser warning sign.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 8 (PDF 10); Tweez 305/310 System Installation Guide (2021), page 20 (PDF 24).*
- Only the original external power supply may be used with the tweezers. The 2022 manual names it as an XP Power VES255PS24 -- 90 to 264 V AC input, 255 W rated -- while the 2021 System Installation Guide names it as Aresis model PWS-001.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 9 (PDF 11); Tweez 305/310 System Installation Guide (2021), page 14 (PDF 18).*
- The tweezers must be installed, or the installation supervised, by qualified personnel; an unauthorised installation voids the warranty and may cause serious injury or damage. The shipping crate is large and heavy and must be handled with care.  
  *Source: Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 10 (PDF 12); Tweez 305/310 System Installation Guide (2021), page 3 (PDF 7).*
- The manufacturer classifies the laser tweezers as a Class 4 laser device under IEC 60825-1:2014: used inappropriately, it can be a severe hazard to eyes and skin.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 1 (PDF 3).*
- Between the control laser unit and the optical unit the beam travels in an optical fibre inside a flexible stainless-steel tube, inside a non-removable stainless-steel umbilical, which the manufacturer describes as protection against damage to the fibre and against any leak of laser light.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 3 (PDF 5).*
- The tweezers' control laser unit houses an infrared fibre laser at 1064 nm, of 5 W or 10 W depending on the model, with its control electronics. 1064 nm is invisible.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 3 (PDF 5).*
- The tweezers' interlocks are built into low-level electronics hardware, independent of the computer and its software, and wherever possible a safety measure is mechanical, such as the shutter, so that it does not depend on electrical power.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), pages 4, 9 (PDF 6, 11).*
- In the optical unit the fibre ends in a fixed collimator followed immediately by a mechanical shutter, which isolates the beam from the exit aperture during start-up and emergency shutdown, and which is spring-loaded to close by itself if the control electronics fail.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 4 (PDF 6).*
- A key switch on the front of the control laser unit controls the system's main power. With the key removed the system and the laser are shut down and no emission is possible; the key can be removed only in the OFF position.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 4 (PDF 6); Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 6 (PDF 8).*
- The laser safety switch, cabled to the optical unit so it sits near the work, is the quick way to shut the laser down. Once pressed it stays engaged and must be released by turning its knob -- clockwise, in this 2022 manual -- before the laser can run again. If it is engaged, or its cable is disconnected or broken, laser operation is disabled and the internal shutter blocks the beam.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 5 (PDF 7).*
- The tweezers show laser status the same way on the laser safety switch, the laser warning sign and the control laser unit's front panel: a steady red light means the laser is powered but not emitting, and a flashing red light means it is emitting. A blue light on the front panel means system power is on.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), pages 5, 6 (PDF 7, 8); Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 6 (PDF 8).*
- The laser warning sign shows the laser's status to people who would not otherwise know it, such as anyone entering the room, and should be placed where it is clearly visible. It carries a remote interlock connector, meant for a switch or chain of switches -- a door switch, for example -- that disables the laser; disconnecting the sign also disables the laser and closes the internal shutter.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 6 (PDF 8); Tweez 305/310 System Installation Guide (2021), page 13 (PDF 17).*
- The Nikon Ti2's own interlock switch is triggered whenever light could enter the eyepieces -- when the light path selector is set to the eyepieces -- and it is wired to the tweezers' optical unit, so that laser operation is disabled in that position. The manufacturer calls it an additional measure: an infrared filter already keeps the laser out of the eyepiece path. If the interlock cable is disconnected, laser operation is disabled. The Ti2's interlock works only while the microscope is powered, and with the microscope off, tweezers laser operation is disabled too.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 7 (PDF 9); Tweez 305/310 System Installation Guide (2021), page 12 (PDF 16).*
- Users should never remove the optical unit's cover: inside, the invisible 1064 nm beam runs through open optics. Removing the cover trips an internal interlock that disables the laser and closes the shutter.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 7 (PDF 9).*
- The tweezers are meant to be used with an Aresis-supplied filter cube in the microscope's epi-fluorescence turret. That turret's mechanically actuated shutter blocks the laser from the objective and the eyepieces, and the cube's dichroic and blocking filters attenuate infrared that could reach the eyepiece path to well below the Class 1 limit.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 8 (PDF 10).*
- The manufacturer builds in three independent ways to keep the beam from leaving the exit aperture if one interlock fails: the internal mechanical shutter, an interlock on the laser module that stops emission, and switching off the radio-frequency drive to the acousto-optic deflectors, which then act as a second shutter in series.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), pages 8, 9 (PDF 10, 11).*
- The tweezers are built so that laser light leaves only through one marked exit aperture on the optical unit; every other point where the beam could be reached is covered by the interlocks.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 9 (PDF 11).*
- The supplied laser safety glasses must be worn during laser operation. One set ships with the system; everyone present where stray laser light could be must wear a pair, and providing the extra sets is the operator's responsibility.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 9 (PDF 11); Tweez 305/310 System Installation Guide (2021), page 22 (PDF 26).*
- The tweezers software keeps the laser control panel visible, shows whether the laser is on and at what power, gives quick access to an emergency shutdown, and shows the connection and state of every interlock. The laser can be switched on there only if every safety component is connected and every interlock is enabled; its status reads Standby when enabled but off, and Locking or Locked once on.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 9 (PDF 11); Tweez 300 User Manual, pages 23, 24 (PDF 29, 30).*
- The manufacturer treats training as a safety measure: it covers the nature of infrared laser radiation, the hazards, what Class 4 means, the tweezers' safety system, and safe installation and operation.  
  *Source: Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 10 (PDF 12).*
- The 2021 System Installation Guide says the laser safety switch, once pressed, stays in the disabled position until released by turning it counter-clockwise.  
  *Source: Tweez 305/310 System Installation Guide (2021), page 11 (PDF 15).*
- The sample safety shield blocks laser light scattered off the sample and is to be placed around the sample before the laser is activated. If it gets in the way of other equipment on the stage, the operator must provide a replacement or other protection at least as good.  
  *Source: Tweez 305/310 System Installation Guide (2021), page 22 (PDF 26); Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 2 (PDF 4).*

## The manufacturer's figures

These are the manufacturer's printed figures. None has been measured or confirmed here, and none is a limit anyone on this bench has set.

- Power setting max: 1 (a number with no unit) -- the top of the relative scale; the manufacturer calls it the maximum laser power *(Tweez 300 User Manual, page 24 (PDF 30))*
- Operating temperature min: 20 °C -- printed as 20 C *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6))*
- Operating temperature max: 28 °C -- printed as 28 C *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6))*
- Operating humidity min: 20 % relative humidity -- printed as 20 % *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6))*
- Operating humidity max: 80 % relative humidity -- printed as 80 %, non-condensing *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 4 (PDF 6))*
- Hibernation delay: 10 min *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 6 (PDF 8))*
- Power supply rated power: 255 W *(Tweez 305/310 General Hardware and Safety Manual (V3.0, November 2022), page 9 (PDF 11))*
- Laser wavelength: 1064 nm *(Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 3 (PDF 5))*
- 305 rated output: 5 W -- the manufacturer's figure for the Tweez 305 *(Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 3 (PDF 5))*
- 310 rated output: 10 W -- the manufacturer's figure for the Tweez 310 *(Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 3 (PDF 5))*

## What is missing

- Two editions of the two tweezers safety manuals are on this computer. This page follows the November 2022 editions installed with the tweezers software, as the person chose; the November 2021 copies in the lab's archive are the older edition and nothing here is taken from them.
- The tweezers manuals are written for the Tweez 305/310 family, rated 5 W or 10 W. This bench's unit is recorded as a Tweez 300; which rating it carries comes from the store's record of the unit, not from these manuals.
- The 107-page User Manual was read for its warnings and its laser-safety sections, not line by line; its operating chapters may hold more.
- **The manufacturer's documents disagree here**, and both readings are kept:
  - The laser safety switch, cabled to the optical unit so it sits near the work, is the quick way to shut the laser down. Once pressed it stays engaged and must be released by turning its knob -- clockwise, in this 2022 manual -- before the laser can run again. If it is engaged, or its cable is disconnected or broken, laser operation is disabled and the internal shutter blocks the beam. *(Tweez 305/310 Laser Safety Manual (V3.0, November 2022), page 5 (PDF 7))*
  - The 2021 System Installation Guide says the laser safety switch, once pressed, stays in the disabled position until released by turning it counter-clockwise. *(Tweez 305/310 System Installation Guide (2021), page 11 (PDF 15))*

---

**This page is not the lab's safety limits.** It says what the manufacturer warns about. What may be done on this bench, and every limit anyone acts on, is written by the person into the instrument's safety file after confirming it on the instrument.

<sub>Generated from the knowledge store at kbv-d2db58512e78. Do not edit by hand: correct the store and regenerate.</sub>
