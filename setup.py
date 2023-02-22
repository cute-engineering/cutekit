from setuptools import setup
from osdk.utils import get_version

setup(
    name="osdk",
    version=get_version(),
    python_requires='>=3.10',
    description="Operating System Development Kit",
    author="The DEVSE Community",
    author_email="contact@devse.wiki",
    url="https://devse.wiki/",
    packages=["osdk"],
    install_requires=[
        "requests",
        "graphviz"
    ],
    entry_points={
        "console_scripts": [
            "osdk = osdk:main",
        ],
    },
    license="MIT",
    platforms="any",
)
