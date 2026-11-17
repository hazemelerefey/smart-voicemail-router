# Requirements

## Pick your file

The name in `MEMBER.md` maps to a file by first name, lowercase:

- Hazem -> hazem.txt
- Sira -> sira.txt
- Lama -> lama.txt
- Aya -> aya.txt
- Ibthal -> ibthal.txt
- Arafa -> arafa.txt

## Install

Use Python 3.11. Create a virtual environment first, then install base plus your member file:

```
pip install -r requirements/base.txt -r requirements/<name>.txt
```

## PyTorch: one framework for the whole team

Everyone on the team uses PyTorch, the same framework, so GPU work is consistent. The pip package name is `torch`. There is no `pytorch` package that installs PyTorch; installing `pytorch` would install the wrong thing and `import torch` would fail. The member files say `torch` and that is correct.

CPU or GPU is a build choice, not a different framework. The code is identical. If you have an NVIDIA GPU, install the CUDA build of torch. If you do not, install the CPU build. See the comment at the top of your member file.

## Torch CPU note

On machines without a GPU, install the CPU build of torch. See the comment at the top of your member file. The CPU build is the same torch version, built without GPU support.

## Arafa

`arafa.txt` lists the requirements for Arafa's role (FastAPI demo). His code is not on this branch yet; it stays on his local machine while he fixes the audit issues, then he pushes it and members pull it. The requirements file is here so it is ready when his code lands.

## AI agent

The AI agent installs base plus the member file before starting work.
