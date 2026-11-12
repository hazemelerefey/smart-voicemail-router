# Optional Google Colab work

Google Colab or another free cloud notebook is optional. It is not the source of truth, and availability or free compute is not guaranteed. Local CPU tests remain the baseline.

## Before using a notebook

1. Confirm that the competition rules, dataset rights, consent, and project approval permit the intended processing location.
2. Use synthetic fixtures for ordinary development. Do not upload raw voice, identifying transcripts, or credentials to Colab unless a specific approved decision allows that exact use.
3. Remember that transcript masking does not anonymize the source recording. The default project boundary keeps raw voice local.
4. Record the notebook version, dataset snapshot reference if permitted, provider and model, runtime hardware, command or cell sequence, metrics, failures, and limitations.
5. Treat the notebook runtime as disposable. Keep reviewed source and permitted result summaries in the authorized repository workflow, not private recordings or secrets.

The notebooks and dataset live on the `local-env` branch, not in this setup draft. Do not treat Colab as required for project work or as a substitute for the project's shared EDA and approval gates.
