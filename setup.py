import pathlib
from setuptools import setup, find_packages

# Read the requirements from requirements.txt
here = pathlib.Path(__file__).parent
requirements_path = here / "requirements.txt"
if requirements_path.is_file():
    with requirements_path.open(encoding="utf-8") as f:
        install_requires = [line.strip() for line in f if line.strip() and not line.startswith("#")]
else:
    install_requires = []

setup(
    name="cnpj_extractor",
    version="0.1.0",
    description="CNPJ data extractor and loader",
    packages=find_packages(include=["cnpj_extractor", "cnpj_extractor.*"]),
    python_requires=">=3.9",
    install_requires=install_requires,
    include_package_data=True,
    zip_safe=False,
)

