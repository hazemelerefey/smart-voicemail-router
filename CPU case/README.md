# CPU case

Use this path for general repository tooling and as the proposed reproducible baseline for core tests. The v1.3 architecture requires core tests not to depend on CUDA. The speech models are selected (Whisper large-v3 for transcription, wav2vec2 XLS-R 300M for audio classification), but no application runtime is installed in this setup draft.

## Create the environment

Run commands from the repository root. The environment stays local and is excluded by `.gitignore`.

```bash
python -m venv .venv-cpu
source .venv-cpu/bin/activate
python -m pip install -r "CPU case/requirements.txt"
```

For Windows PowerShell, create the environment and install the same requirements with:

```powershell
python -m venv .venv-cpu
.venv-cpu\Scripts\Activate.ps1
python -m pip install -r "CPU case/requirements.txt"
```

The current `pytest==9.2.0` and `mypy==2.4.1` pins require Python 3.10 or later according to their PyPI metadata. This is a tooling constraint, not a team decision on the project-wide Python version. The team must still choose that baseline and confirm it against local machines and the eventual application libraries.

## Included tools

The requirements file pins only general development tools: `pytest`, `ruff`, and `mypy`. It does not install PyTorch, CUDA, an STT engine, audio libraries, or a text or voice model. Add runtime packages only after the team confirms the implementation and compatibility.

This draft does not contain application tests. Once tests are added, run them from the repository root with `python -m pytest`. A tool version check is not a product test and does not establish model accuracy or runtime performance.
