from setuptools import setup
from cutekit.const import VERSION_STR, DESCRIPTION

setup(
    name="cutekit",
    version=VERSION_STR,
    python_requires='>=3.10',
    description=DESCRIPTION,
    author="Cute Engineering",
    author_email="contact@cute.engineering",
    url="https://cute.engineering/",
    packages=["cutekit"],
    install_requires=[
        "requests",
        "graphviz"
    ],
    entry_points={
        "console_scripts": [
            "ck = cutekit:main",
            "cutekit = cutekit:main",
            "cute-engineering-cutekit = cutekit:main",
        ],
    },
    license="MIT",
    platforms="any",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
)
