# Open Food Facts API

Invoke [Open Food Facts](https://es.openfoodfacts.org/) API to get nutrition facts about food recipes.

## Project Setup

For `uv` installation see [here](https://docs.astral.sh/uv/getting-started/installation/#installation-methods).

- Check available Python versions with `uv python list`
- Install a new Python version with `uv python install 3.12`
- Create virtual environment with specific Python version with `uv venv --python 3.12`
  - Alternatively, use `uv init` to kick off an empty Python project with a virtual environment.
- Activate virtual environment with `.venv/Scripts/activate`
- Check Python version with `python --version`
- Use `uv sync` to update Python dependencies defined under `pyproject.toml`