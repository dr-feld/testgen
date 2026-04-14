# run.py
import logging
from pathlib import Path
from testgen.config.loader import load_app_config
from testgen.core.runner import Runner

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

config = load_app_config("config.yaml")
runner = Runner(config)

# Запусти на одном файле
paths = runner.run_file(Path("tests/fixtures/sample.cpp"))

print("\nСгенерированные файлы:")
for p in paths:
    print(f"  {p}")