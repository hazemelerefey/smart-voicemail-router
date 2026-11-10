# Setup guide

This repository draft contains project documents and general development tools. It does not yet include application code, an application runtime, a dataset, or a selected model.

## Choose an environment

- Start with the [CPU environment](CPU%20case/README.md) for general tooling and future core tests. Core tests should not require CUDA.
- The [GPU environment](GPU%20case/README.md) is optional. Its requirements file intentionally contains no PyTorch or CUDA package.
- [Google Colab guidance](Google%20Colab/README.md) is optional and follows the same dataset permission and privacy rules as local work.

The requirements paths are `CPU case/requirements.txt` and `GPU case/requirements.txt`. They pin only `pytest==9.2.0`, `mypy==2.4.1`, and `ruff==0.17.4`. PyPI metadata for pytest 9.2.0 and mypy 2.4.1 requires Python 3.10 or later. This is the interpreter minimum for these current general tooling pins, not a settled project-wide Python baseline. The team still needs to decide the project's Python version and confirm it against team machines and the eventual selected libraries.

## PyTorch and CUDA

GPU acceleration is optional. Do not install a guessed PyTorch wheel. First select the target hardware and model, then use the [official PyTorch installation selector](https://pytorch.org/get-started/locally/) to choose the operating system, package manager, language, and compute platform. Record the resulting wheel choice and environment for the experiment. The exact PyTorch/CUDA wheel is deferred until hardware and model selection.

## Data

No dataset or sample audio is included in this draft. Confirm data source, rights, consent, competition rules, and permitted processing location before use. Never force-add private recordings or transcripts. Only reviewed, approved derived summaries may be considered for later commit, if their specific content and use have been approved.
