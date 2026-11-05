"""One Brownian particle in a thermal bath, HOOMD CPU.

Units: length um, time s, energy kT (so kT = 1).
Input D is a computed value (Stokes-Einstein, 1 um sphere, water at 25 C,
viscosity 0.89 mPa s assumed), used only as the test's input: D = 0.49 um^2/s.
gamma = kT / D.

Checks (each against the input D, with its statistical error):
  1. MSD(tau) per axis = 2 D tau, at several lags (time-averaged, one trajectory)
  2. 3D MSD(tau) = 6 D tau
  3. displacement distribution is Gaussian (kurtosis 3) and isotropic
"""
import os, sys, tempfile, time
import numpy as np
import hoomd, gsd.hoomd

D_in = 0.49            # um^2/s
kT = 1.0
gamma = kT / D_in      # kT s / um^2
dt = 1e-3              # s
steps = 1_000_000      # 1000 s simulated
every = 10             # record every 10 steps -> tau0 = 0.01 s
L = 2000.0             # um, box far larger than the excursion (~54 um rms)

out = os.path.join(tempfile.mkdtemp(prefix="sp_bath_"), "traj.gsd")
sim = hoomd.Simulation(device=hoomd.device.CPU(), seed=12345)
snap = hoomd.Snapshot()
snap.configuration.box = [L, L, L, 0, 0, 0]
snap.particles.N = 1
snap.particles.types = ["A"]
snap.particles.position[:] = [[0, 0, 0]]
sim.create_state_from_snapshot(snap)

bd = hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=kT, default_gamma=gamma)
sim.operations.integrator = hoomd.md.Integrator(dt=dt, methods=[bd])
sim.operations.writers.append(hoomd.write.GSD(
    filename=out, trigger=hoomd.trigger.Periodic(every), mode="xb",
    dynamic=["property", "momentum"]))

t0 = time.time()
sim.run(steps)
wall = time.time() - t0
sim.operations.writers[0].flush()

with gsd.hoomd.open(out, "r") as f:
    x = np.array([fr.particles.position[0] + fr.particles.image[0] * L for fr in f])
tau0 = dt * every
M = len(x)
print(f"hoomd {hoomd.version.version} CPU | N=1 | {steps} steps of {dt} s | wall {wall:.1f} s | TPS {sim.tps:.0f}")
print(f"frames {M}, tau0 {tau0} s, input D = {D_in} um^2/s (computed, not measured)")

ok = True
print("\nlag tau [s] | MSD_x  MSD_y  MSD_z [um^2] | 2D tau | D from 3D MSD [um^2/s] | rel. err (1 sigma)")
for k in (1, 10, 100, 1000):
    d = x[k:] - x[:-k]
    tau = k * tau0
    msd_ax = (d ** 2).mean(axis=0)
    D_fit = (d ** 2).sum(axis=1).mean() / (6 * tau)
    n_indep = (M - k) / k                      # independent increments at this lag
    rel = np.sqrt(2 / (3 * n_indep))           # std error of a 3D variance estimate
    flag = abs(D_fit / D_in - 1) < 3 * rel
    ok &= flag
    print(f"{tau:10.2f} | {msd_ax[0]:.4g} {msd_ax[1]:.4g} {msd_ax[2]:.4g} | {2*D_in*tau:.4g} | "
          f"{D_fit:.4f} | {rel:.3%} {'ok' if flag else 'OUT'}")

d1 = x[1:] - x[:-1]
kurt = (d1 ** 4).mean(axis=0) / ((d1 ** 2).mean(axis=0) ** 2)
mean_drift = d1.mean(axis=0) / tau0
print(f"\nkurtosis per axis (Gaussian = 3, err ~{np.sqrt(96/len(d1)):.3f}): {np.round(kurt, 3)}")
print(f"mean drift per axis [um/s] (should be ~0): {np.round(mean_drift, 4)}")
ok &= bool(np.all(abs(kurt - 3) < 5 * np.sqrt(96 / len(d1))))
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
