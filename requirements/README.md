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

## Torch CPU note

On machines without a GPU, install the CPU build of torch. See the comment at the top of your member file. The CPU build is the same torch version, built without GPU support.

## AI agent

The AI agent installs base plus the member file before starting work.
