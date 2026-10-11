import argparse, os, shutil, subprocess, sys, tempfile, zipfile, importlib.util
from dataclasses import dataclass
from pathlib import Path


VERSION = "26.1"

@dataclass(frozen=True)
class BuildOptions:
    source: Path
    output_dir: Path = Path("kdist")
    formats: tuple[str, ...] = ("kef", "kar")
    modules: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    data: tuple[str, ...] = ()
    nuitka_args: tuple[str, ...] = ()
    lto: str = "yes"
    jobs: int | None = None
    no_docstrings: bool = False
    run: bool = False

def resolve_entrypoint(source: Path) -> tuple[Path, Path, str]:
    """Return (script, import root, distribution name)."""
    if source.is_file() and source.suffix == ".py":
        return source, source.parent, source.stem
    if source.is_dir():
        main = source / "__main__.py"
        init = source / "__init__.py"
        if not main.is_file() or not init.is_file():
            raise ValueError(f"Package must contain __init__.py and __main__.py: {source}")
        return main, source.parent, source.name
    raise ValueError(f"Expected a .py file or Python package directory: {source}")

def archive_directory(dist: Path, destination: Path, project_name: str) -> None:
    """Write a standard ZIP, including executable modes and Unix symlinks."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as archive:
        for path in sorted(dist.rglob("*")):
            arcname = (Path(project_name) / path.relative_to(dist)).as_posix()
            if path.is_symlink():
                info = zipfile.ZipInfo(arcname)
                info.create_system = 3
                info.external_attr = (0o120777 << 16)
                archive.writestr(info, os.readlink(path).encode("utf-8"))
            elif path.is_dir():
                info = zipfile.ZipInfo(arcname + "/")
                info.create_system = 3
                info.external_attr = ((path.stat().st_mode & 0xFFFF) << 16) | 0x10
                archive.writestr(info, b"")
            elif path.is_file():
                archive.write(path, arcname)

def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".kefir-", dir=destination.parent)
    os.close(fd)
    staged = Path(filename)
    try:
        shutil.copy2(source, staged)
        if os.name != "nt":
            staged.chmod(staged.stat().st_mode | 0o111)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)

def atomic_archive(dist: Path, destination: Path, name: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix=".kefir-", suffix=".zip", dir=destination.parent)
    os.close(fd)
    staged = Path(filename)
    try:
        archive_directory(dist, staged, name)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)

def build(options: BuildOptions) -> list[Path]:
    if importlib.util.find_spec("nuitka") is None:
        raise ImportError("nuitka is not installed. please run `pip install nuitka`.")
    source = options.source.expanduser().resolve(strict=True)
    script, import_root, name = resolve_entrypoint(source)
    is_package = source.is_dir()
    target = source.name if is_package else str(script)
    output_dir = options.output_dir.expanduser().resolve()
    if not options.formats or any(fmt not in ("kef", "kar") for fmt in options.formats):
        raise ValueError("Formats must be kef, kar, or both")
    if options.run and "kef" not in options.formats:
        raise ValueError("--run requires the kef format")
    
    # Crucial: Nuitka must receive the TARGET script, not Kefir's own __main__.py.
    print(f"kefir: source: {source}", flush=True)
    print(f"kefir: compiling entrypoint: {script}", flush=True)
    if script.resolve() == Path(__file__).resolve():
        print("kefir: warning: you are compiling Kefir itself; the resulting executable "
              "will display Kefir's CLI help when run without arguments.", file=sys.stderr)

    output_dir.mkdir(parents=True, exist_ok=True)
    binary_name = name + (".exe" if os.name == "nt" else "")
    kef_name = name + (".kef.exe" if os.name == "nt" else ".kef")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(import_root), env.get("PYTHONPATH", "")]))

    with tempfile.TemporaryDirectory(prefix="kefir-build-") as tmp:
        work = Path(tmp)
        outputs: list[Path] = []
        for fmt in options.formats:
            mode = "onefile" if fmt == "kef" else "standalone"
            mode_dir = work / mode
            mode_dir.mkdir()
            command = [sys.executable, "-m", "nuitka", f"--mode={mode}",
                       "--assume-yes-for-downloads", f"--lto={options.lto}",
                       f"--output-dir={mode_dir}", f"--output-filename={binary_name}"]
            if is_package:
                command.append("--python-flag=-m")
            if options.jobs is not None:
                command.append(f"--jobs={options.jobs}")
            if options.no_docstrings:
                command.append("--python-flag=no_docstrings")
            for module in options.modules:
                command.append(f"--include-module={module}")
            for package in options.packages:
                command.append(f"--include-package={package}")
            for item in options.data:
                if "=" not in item:
                    raise ValueError("--data must be SOURCE=DESTINATION")
                command.append(f"--include-data-files={item}")
            command.extend(options.nuitka_args)
            command.append(target)
            print(f"kefir: building {name}.{fmt} ({mode})", flush=True)
            subprocess.run(command, cwd=import_root, env=env, check=True)
            if fmt == "kef":
                built = mode_dir / binary_name
                if not built.is_file():
                    raise FileNotFoundError(f"Nuitka onefile output missing: {built}")
                destination = output_dir / kef_name
                atomic_copy(built, destination)
            else:
                dist = mode_dir / f"{name}.dist"
                built = dist / binary_name
                if not built.is_file():
                    raise FileNotFoundError(f"Nuitka standalone output missing: {built}")
                destination = output_dir / f"{name}.kar"
                atomic_archive(dist, destination, name)
            outputs.append(destination)
            print(f"kefir: created {destination}", flush=True)

    if options.run:
        subprocess.run([str(output_dir / kef_name)], check=True)
    return outputs

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kefir", description="Compile Python applications into .kef and .kar distributions.")
    parser.add_argument("-v", "--version", action="version", version=f"Kefir v{VERSION}")
    parser.add_argument("source", nargs="?", type=Path, help="target .py file or package directory")
    parser.add_argument("-o", "--output-dir", type=Path, default=Path("kdist"))
    parser.add_argument("-f", "--format", choices=("both", "kef", "kar"), default="both")
    parser.add_argument("-m", "--module", action="append", default=[])
    parser.add_argument("-p", "--package", action="append", default=[])
    parser.add_argument("-d", "--data", action="append", default=[], metavar="SOURCE=DEST")
    parser.add_argument("-j", "--jobs", type=int)
    parser.add_argument("--lto", choices=("yes", "no", "auto"), default="yes")
    parser.add_argument("--no-docstrings", action="store_true")
    parser.add_argument("--nuitka-arg", action="append", default=[])
    parser.add_argument("-r", "--run", action="store_true")
    args = parser.parse_args(argv)
    if args.source is None:
        parser.print_help()
        return 0
    if args.jobs is not None and args.jobs < 1:
        parser.error("--jobs must be >= 1")
    if args.run and args.format == "kar":
        parser.error("--run requires --format kef or both")
    formats = ("kef", "kar") if args.format == "both" else (args.format,)
    try:
        build(BuildOptions(source=args.source, output_dir=args.output_dir,
                           formats=formats, modules=tuple(args.module),
                           packages=tuple(args.package), data=tuple(args.data),
                           nuitka_args=tuple(args.nuitka_arg), lto=args.lto,
                           jobs=args.jobs, no_docstrings=args.no_docstrings, run=args.run))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"kefir: error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
