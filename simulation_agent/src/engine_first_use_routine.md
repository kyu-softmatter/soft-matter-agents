# Simulation engine: first-use routine (microscope computer, WSL)

Run once per session, before the first real engine run. About 30 s total.
Every step below was run on 2026-11-05 and worked as written.

1. Distro is up
   PowerShell:  wsl.exe -l -v
   Expect: Ubuntu-24.04, VERSION 2. (It starts on first call if Stopped.)

2. Engine imports, from the side you are calling from
   PowerShell:  wsl.exe -d Ubuntu-24.04 --cd /mnt/d/soft-matter-agents -- /home/takalab/.pixi/bin/pixi run -e sim --frozen python -c "import hoomd;print(hoomd.version.version)"
   Git Bash:    the same line with MSYS_NO_PATHCONV=1 in front.
   Expect: 7.2.0
   Known failure: from Git Bash WITHOUT MSYS_NO_PATHCONV=1, wsl.exe prints
   "The system cannot find the path specified ... Wsl/ERROR_PATH_NOT_FOUND"
   and a pipe after it still reports exit 0. Read the output, not the exit code.

3. Single particle in a thermal bath (the physics check)
   Script: simulation_agent/src/single_particle_bath.py (one particle, D = 0.49 um^2/s, dt = 1 ms,
   10^6 steps = 1000 s simulated). Pass a Windows path through
   `wsl.exe -d Ubuntu-24.04 -- wslpath -a "<path>"` to get the /mnt path; paths
   with spaces work when quoted.
   Expect: "RESULT: PASS", D from MSD within 3 sigma of 0.49 at lags
   0.01, 0.1, 1, 10 s; wall time about 1 s.

4. Do not
   - run git inside WSL on this working copy (commit from Windows);
   - remove the .pixi/envs symlink a pixi run leaves behind (harmless);
   - expect Gaussian displacements below ~10 steps: HOOMD's Brownian kicks are
     uniform (single-step kurtosis 1.80, measured), Gaussian only as steps add up.
