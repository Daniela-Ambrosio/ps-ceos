#!/usr/bin/env python3
import sys
from cnpj_extractor.cli import executar_cli
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

if __name__ == "__main__":
    sys.exit(executar_cli())
