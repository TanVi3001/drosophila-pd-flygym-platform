# FlyGym Runtime Environment

This guide describes the environment required to run the real FlyGym workflow
in this repository. It does not create rollouts and it does not make biological
claims. The repository remains the source of truth for code and configuration;
Google Colab is an execution environment.

## Required Versions

The verified runtime target is:

| Component | Requirement | Role |
| --- | --- | --- |
| Python | 3.12.x | Supported interpreter for the real simulation workflow |
| NumPy | `>=1.26` | Rollout arrays and analysis |
| PyYAML | `>=6.0` | FlyGym and experiment configuration |
| Matplotlib | `>=3.8,<4` | CPU-side reports and figures |
| FlyGym | `==2.1.0` | Fly, world, and simulation API |
| MuJoCo | `==3.9.0` | Physics backend used by FlyGym |
| `flygym_demo` | Importable from the FlyGym installation | Canonical locomotion helper `flygym_demo.complex_terrain.make_locomotion_fly` |

The project declares these dependencies in `pyproject.toml`. `pytest` and
`jsonschema` are development/test dependencies in the `test` extra. They are
not needed merely to run a completed rollout, but install them when running the
repository test suite.

The current real-runtime target is Python 3.12.x even though the packaging
metadata declares `requires-python >=3.12`. This is intentional: the project
context and the simulation scripts certify the FlyGym workflow on Python 3.12.

## Preflight Checker

From the repository root, run:

```bash
python scripts/check_runtime.py
```

The checker is read-only. It imports packages, checks versions, verifies the
canonical `flygym_demo` helper, and checks the configuration/scripts. It never
installs packages, starts MuJoCo, runs FlyGym, writes datasets, or writes a
report. Exit code `0` means the real runtime preflight passed. Use JSON output
for CI or diagnostics:

```bash
python scripts/check_runtime.py --json
```

`READY` means that the prerequisites are present; it is not a claim that a
simulation has already run. A clean environment still needs an explicit smoke
run.

## Windows PowerShell

Install Python 3.12 first, then from the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[simulation,test]"
python scripts/check_runtime.py
```

If PowerShell blocks activation, use the current-user execution policy required
by your organisation, or invoke the environment directly:

```powershell
.\.venv\Scripts\python.exe scripts/check_runtime.py
```

After the checker reports `READY`, run a small real smoke test:

```powershell
python scripts/run_demo.py --steps 100 --no-install-simulation
```

The demo uses the existing healthy configuration and writes the rollout/viewer
artifacts under `datasets/healthy/Healthy_001` and `dist/`. It does not create
synthetic scientific data. For a full real dataset campaign, use:

```powershell
python scripts/generate_research_dataset.py --count 20
```

That command runs the existing FlyGym pipeline for missing datasets only. It
can take substantial time and storage. The analysis suite can then process
available datasets with:

```powershell
python scripts/run_experiment_suite.py
```

## Ubuntu

Install Python 3.12 and the virtual-environment/build prerequisites using your
distribution's supported package source. On Ubuntu releases that provide these
package names:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv build-essential
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[simulation,test]"
python scripts/check_runtime.py
```

If the Ubuntu release does not provide `python3.12`, install Python 3.12 with
the distribution-approved toolchain (for example, a maintained Python build or
`pyenv`) and repeat the virtual-environment steps. Do not substitute an
uncertified interpreter merely to bypass the checker.

When preflight passes:

```bash
python scripts/run_demo.py --steps 100 --no-install-simulation
python scripts/generate_research_dataset.py --count 20
python scripts/run_experiment_suite.py
```

`run_demo.py` and `generate_research_dataset.py` require the real FlyGym,
MuJoCo, and canonical `flygym_demo` runtime. `run_experiment_suite.py` is an
analysis/report command and operates on datasets that already exist; it does
not create rollouts.

## Google Colab

Use a fresh Python 3.12 Colab runtime when available. Clone the repository and
install the project from its root:

```python
!git clone https://github.com/tuanwannafly/drosophila-pd-flygym.git
%cd /content/drosophila-pd-flygym
!python -V
!python -m pip install --upgrade pip
!python -m pip install -e ".[simulation,test]"
!python scripts/check_runtime.py
```

The install command is explicit because the checker never installs anything.
If Colab's selected Python version is not 3.12.x, switch to a compatible
runtime before installing the pinned simulation dependencies. If installation
fails, keep the complete pip error and use the package/version it identifies;
do not create a substitute rollout.

After a successful preflight, execute the real workflow from the repository
root:

```python
!python scripts/run_demo.py --steps 100 --no-install-simulation
!python scripts/generate_research_dataset.py --count 20
!python scripts/run_experiment_suite.py
```

These commands use the existing simulation, recorder, export, viewer-export,
analysis, and experiment code. Colab should be used for execution and artifact
download; the viewer bundle can be served/deployed separately according to the
existing viewer documentation.

## Troubleshooting

Inspect the active interpreter and package metadata:

```bash
python -V
python -m pip show flygym mujoco numpy PyYAML matplotlib
python -c "from flygym_demo.complex_terrain import make_locomotion_fly; print(make_locomotion_fly)"
```

If the checker reports a missing or incompatible package, activate the intended
Python 3.12 environment and reinstall from the project metadata:

```bash
python -m pip install -e ".[simulation,test]"
python scripts/check_runtime.py
```

Common causes are installing into a different interpreter, using Python 3.13
instead of the certified 3.12 target, or installing FlyGym without the
canonical demo helper. The `flygym_demo` helper check is intentional because
the repository's canonical fly factory imports it directly.

## Scientific and Operational Boundary

The environment checker is operational tooling only. It does not run a
simulation, alter FlyGym or MuJoCo, generate data, validate biological claims,
or replace the scientific pipeline. A passing preflight only means that the
declared software prerequisites and repository entry points are available.
