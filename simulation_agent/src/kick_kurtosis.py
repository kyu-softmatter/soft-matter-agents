"""Kurtosis of single-step Brownian displacements vs number of steps summed.
Uniform kicks predict 3 - 1.2/n; Gaussian kicks predict 3 for every n."""
import numpy as np, hoomd
sim = hoomd.Simulation(device=hoomd.device.CPU(), seed=7)
s = hoomd.Snapshot(); s.configuration.box = [2000] * 3 + [0] * 3
s.particles.N = 1; s.particles.types = ["A"]; s.particles.position[:] = [[0, 0, 0]]
sim.create_state_from_snapshot(s)
sim.operations.integrator = hoomd.md.Integrator(dt=1e-3, methods=[
    hoomd.md.methods.Brownian(filter=hoomd.filter.All(), kT=1.0, default_gamma=1 / 0.49)])
x = np.empty((200_000, 3))
for i in range(len(x)):
    sim.run(1)
    x[i] = sim.state.get_snapshot().particles.position[0]
for n in (1, 2, 5, 10, 50):
    d = (x[n:] - x[:-n])[::n]
    k = ((d ** 4).mean(0) / (d ** 2).mean(0) ** 2).mean()
    print(f"n={n:3d} steps: kurtosis {k:.3f}   uniform predicts {3 - 1.2 / n:.3f}   Gaussian 3.000"
          f"   (err ~{np.sqrt(96 / (3 * len(d))):.3f})")
