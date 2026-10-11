![Kefir](kefir.png)

# kefir

> distro hosted at `wednesware.kefir@wednesware.org`

Kefir is a small Python CLI that bundles a Python application into a distributable single-file executable or package using Nuitka under the hood.

It accepts either a Python script or a Python package directory and produces:

## `.kef`

* Single-file executable built in Nuitka's onefile mode.
* To run: execute `./project.kef`

## `.kar`

* Standalone bundled archive built in standalone mode.
* Generally 2-3x faster compared to `.kef` files, but require unzipping.
* To run:
1. Unzip the `.kar` file: `unzip project.kar`
2. Run the main file in the extracted archive: `./project/project`. The main file can be identified as it is the only file without an extension.

This makes it easier to ship Python projects as portable app bundles without requiring users to install a full Python environment and dependencies manually.

## Compatibility:

* Linux - Officially supported
* Windows - Not tested
* macOS - Not tested

Want kefir on another OS? Become a contributor on the [GitHub repository](https://github.com/Wednesware/kefir)!

## Why use Kefir?

- Package a Python app as a single executable
- Keep dependencies bundled with the app
- Support both script and package entry points
- Customize builds with extra modules, packages, and data files
- Pass through additional Nuitka arguments when needed
- As a distributor, you can easily provide a `.kar` and `.kef` releases for your users to choose between

## Installation

Install from Distrobase:

```bash
h2 get kefir && h2 install kefir
```

Replace `h2` with your Distrobase manager if you don't use Hydrogen.

## Requirements

- Python 3.10+
- Nuitka 2.0+
- Nitrogen 26.66+

## Quick start

### Build a single script

```bash
kefir app.py
```

This writes output into `kdist/` by default, creating files such as:

- `kdist/app.kef`
- `kdist/app.kar`

### Build a package

```bash
kefir my_package -f both -o dist
```

A package directory must contain both `__init__.py` and `__main__.py`.

### Run the built executable immediately

```bash
kefir app.py --format kef --run
```

### Include extra modules or data

```bash
kefir app.py \
  -m requests \
  -p myproject \
  -d "assets=assets" \
  --nuitka-arg="--enable-plugin=anti-bloat"
```

## CLI reference

```bash
kefir [source] [options]
```

Common options:

- `-o, --output-dir` — output directory, default `kdist`
- `-f, --format` — `both`, `kef`, or `kar`
- `-m, --module` — include a module in the build
- `-p, --package` — include a package in the build
- `-d, --data` — include data files in the form `SOURCE=DEST`
- `-j, --jobs` — number of build jobs
- `--lto` — enable or disable LTO (`yes`, `no`, `auto`)
- `--no-docstrings` — strip docstrings from the compiled output
- `--nuitka-arg` — pass additional raw Nuitka arguments
- `-r, --run` — run the generated `.kef` bundle after building
- `-v, --version` — show version information

## Example project layout

```text
my_project/
├── app.py
├── my_package/
│   ├── __init__.py
│   └── __main__.py
└── assets/
    └── config.json
```

Then:

```bash
kefir my_project/app.py
kefir my_project/my_package -f kef
```

## Dependencies

Kefir depends on the following packages:

- `nuitka>=2.0`
- `nitrogen>=26.66`

These are installed automatically when you install the package with pip.

## License

This project is distributed under the MIT License described in the repository's `LICENSE.md` file.

## Commands

```bash
kefir --help
kefir --version
```

The CLI is intentionally lightweight: it wraps Nuitka for packaging, while exposing a simple command-line interface for building `.kef` and `.kar` bundles.
