# GPU case

GPU acceleration is optional. The CPU path remains the general test baseline, and CUDA is not required for core tests. This draft does not select a target GPU, speech model, or PyTorch build.

## Create the optional tooling environment

Run commands from the repository root. The requirements file includes only general development tools and intentionally does not install PyTorch or CUDA.

```bash
python -m venv .venv-gpu
source .venv-gpu/bin/activate
python -m pip install -r "GPU case/requirements.txt"
```

For Windows PowerShell:

```powershell
python -m venv .venv-gpu
.venv-gpu\Scripts\Activate.ps1
python -m pip install -r "GPU case/requirements.txt"
```

The current `pytest==9.2.0` and `mypy==2.4.1` pins require Python 3.10 or later according to their PyPI metadata. This is a tooling constraint, not a team decision on the project-wide Python version. The team must still choose that baseline and confirm it against local machines and the eventual application libraries.

## PyTorch and CUDA installation

Do not copy a PyTorch or CUDA wheel command from another machine. Choose the target hardware and model first, then use the [official PyTorch installation selector](https://pytorch.org/get-started/locally/) for the operating system, package manager, language, and compute platform that match the target. The exact wheel and install command are intentionally deferred until both the target hardware and model are known.

Record the selected hardware, runtime, PyTorch build, model, and measured results for each GPU experiment. Keep CUDA-specific dependencies isolated from the CPU requirements. A GPU environment does not itself establish that a model supports Egyptian Arabic or meets the project latency target.
