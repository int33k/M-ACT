"""Setup script for MACT CLI - allows pip install from GitHub"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="mact-cli",
    version="1.0.2",
    description="MACT (Mirrored Active Collaborative Tunnel) - Git-driven collaborative development tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="MACT Team",
    author_email="22btcs042hy@manuu.edu.in",
    url="https://m-act.live",
    project_urls={
        "Source": "https://github.com/int33k/M-ACT",
        "Documentation": "https://github.com/int33k/M-ACT/tree/main/.docs",
        "Bug Tracker": "https://github.com/int33k/M-ACT/issues",
    },
    packages=find_packages(exclude=["tests", "backend", "proxy", "deployment", "scripts"]),
    include_package_data=True,
    package_data={
        "": ["third_party/frp/frpc", "third_party/frp/frpc.toml", "third_party/frp/LICENSE"],
    },
    install_requires=[
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "mact=cli.cli:main",              # Client CLI for developers
            # Note: mact-admin is only available when installed with "pip install -e ." 
            # on the server (not in client pip installs from GitHub)
        ],
    },
    extras_require={
        "server": [
            # Server-side dependencies for admin CLI
            "flask>=2.0.0",
            "flask-cors>=3.0.0",
            "starlette>=0.19.0",
            "uvicorn>=0.15.0",
            "httpx>=0.23.0",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Version Control :: Git",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    keywords="tunnel development collaboration git frp reverse-proxy real-time",
    license="MIT",
    zip_safe=False,
)
