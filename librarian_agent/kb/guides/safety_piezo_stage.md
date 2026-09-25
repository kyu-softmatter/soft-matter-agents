# Safety guide: Piezo stage and its controller (Queensgate)

What the manufacturer's own documents on this computer say about this device's hazards, and where they say it. Everything here is the manufacturer's statement; nothing on this page was measured on this bench.

## What the manufacturer warns about

- The piezo controller's stage and interface connectors are sensitive to electrostatic discharge, so connector covers should be removed and cables connected only with static-safe handling.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 2 (PDF 2); NanoFlash Reflash Application User Manual, page 2 (PDF 2).*
- The piezo controller's covers must not be removed: there are no user-serviceable parts inside, and opening it exposes high-voltage hazards and voids the warranty.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 2 (PDF 2); NanoFlash Reflash Application User Manual, page 2 (PDF 2).*
- The piezo controller generates high voltages to drive the piezo actuators and relies on a protective earth, provided through its approved external power supply, to keep accessible parts safe if insulation fails. Only approved stages and cables may be used with it, and it must not be used if it shows any damage or seems faulty.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 2 (PDF 2); NanoFlash Reflash Application User Manual, page 2 (PDF 2); Nanobench 6000 User Manual (issue 4), page 5 (PDF 5).*
- The piezo controller is meant for dry, climate-controlled indoor rooms. Significant dust or acoustic or mechanical vibration can cause faults or damage, its fan vents must not be restricted, and humidity is best kept low during long operation.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 2 (PDF 2); NanoFlash Reflash Application User Manual, page 2 (PDF 2).*
- The manufacturer says to read the manual before using the piezo controller, because incorrect use can cause injury or damage, and to switch it off and remove the mains plug whenever it is not in use.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 2 (PDF 2); NanoFlash Reflash Application User Manual, page 2 (PDF 2).*
- If the piezo controller is reached over Ethernet through a hub, that hub must connect only to computers meant to talk to the controller, and never to a wider corporate network or the internet.  
  *Source: NPC-D Series Controller Interface Library manual (revision 6.0), page 16 (PDF 16).*
- Reprogramming the piezo controller's firmware with NanoFlash cannot damage it even if interrupted, since programming can always be resumed; but the wrong firmware version, while harmless to the controller, may leave it unable to drive stages or missing key features until the right one is loaded.  
  *Source: NanoFlash Reflash Application User Manual, pages 5, 13 (PDF 5, 13).*
- The piezo controller gives only limited protection against settings that would damage a connected stage; configuring it is for engineers or technicians with enough expertise to do it safely.  
  *Source: Nanobench 6000 User Manual (issue 4), page 5 (PDF 5).*
- Raising the piezo controller's security level exposes settings that can damage the stage or the controller -- for example, too small an integrator time constant makes the loop unstable and damages the stage. NanoBench warns when a higher level is entered.  
  *Source: Nanobench 6000 User Manual (issue 4), page 8 (PDF 8).*
- The piezo controller performs a safety shutdown if parts of its circuit board get hot enough to be damaged, and shows it on an over-temperature light. The first thing to check is that its air vents are not covered; if it recurs with the vents clear, the manufacturer asks to be contacted.  
  *Source: Nanobench 6000 User Manual (issue 4), pages 9, 16 (PDF 9, 16).*
- Wrong control-loop settings -- the position, velocity and acceleration loop gains and time constants, and the trajectory limits -- can make the piezo stage unstable and damage it mechanically, and such damage is not covered by the manufacturer's warranty.  
  *Source: Nanobench 6000 User Manual (issue 4), pages 12, 30, 31 (PDF 12, 30, 31).*
- In NanoBench, storing a stage calibration preset overwrites the settings held in it, and deleting a preset from the stage's memory cannot be undone.  
  *Source: Nanobench 6000 User Manual (issue 4), page 29 (PDF 29).*

## The manufacturer's figures

None.

## What is missing

- **The piezo stage's and controller's hardware manual, including the environmental Table 2.1 the controller's software manuals refer to.** Every piezo manual in the archive is for software; the controller's operating temperature and humidity limits are stated to be in a table that none of them contains. What would close it: the Queensgate NPC-D-6000 controller and SP-XYZ-600 stage manuals.
- Four release notes for the piezo controller's software are in the archive and were catalogued; they carry no safety statement.

---

**This page is not the lab's safety limits.** It says what the manufacturer warns about. What may be done on this bench, and every limit anyone acts on, is written by the person into the instrument's safety file after confirming it on the instrument.

<sub>Generated from the knowledge store at kbv-0b89056cf256. Do not edit by hand: correct the store and regenerate.</sub>
