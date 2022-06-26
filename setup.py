from setuptools import setup

setup(
    name="osdk",
    version="0.0.1",
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
