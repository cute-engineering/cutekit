from setuptools import setup
from osdk.const import VERSION

setup(
    name="osdk",
    version=VERSION,
    python_requires='>=3.10',
    description="Operating System Development Kit",
    author="Cute Engineering",
    author_email="contact@cute.engineering",
    url="https://cute.engineering/",
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
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
)
