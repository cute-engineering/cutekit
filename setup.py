from setuptools import setup
from osdk import __version__

setup(
    name="osdk",
    version=__version__,
    python_requires='>=3.10',
    description="Operating System Development Kit",
    author="The DEVSE Community",
    author_email="contact@devse.wiki",
    url="https://devse.wiki/",
    packages=["osdk"],
    install_requires=[
        "requests",
    ],
    entry_points={
        "console_scripts": [
            "osdk = osdk:main",
        ],
    },
    license="MIT",
    platforms="any",
)
