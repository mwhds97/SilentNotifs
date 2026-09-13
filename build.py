#!/usr/bin/env python3
"""Build the rootful iOS 14+ package using an existing Linux iOS toolchain.

For a standard Theos installation, use the Makefile instead. This helper needs
clang, Apple's compatible ld, lipo, ldid, an iOS SDK, Logos, and Theos headers/lib.
It does not download or install dependencies.
"""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", type=Path, required=True,
                        help="directory containing clang, ld, lipo and ldid")
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--logos", type=Path, required=True)
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--libraries", type=Path, required=True)
    parser.add_argument("--abi-converter", type=Path,
                        help="allemande executable, required with legacy arm64e compilers")
    args = parser.parse_args()
    for key, value in vars(args).items():
        if value is not None:
            setattr(args, key, value.expanduser().resolve())

    root = Path(__file__).resolve().parent
    build = root / ".build"
    build.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(args.toolchain) + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = (str(args.toolchain.parent / "lib") + os.pathsep +
                              env.get("LD_LIBRARY_PATH", ""))
    log = []

    def run(command):
        command = [str(item) for item in command]
        result = subprocess.run(command, cwd=root, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.append("+ " + " ".join(command) + "\n" + result.stdout)
        (build / "build.log").write_text("\n".join(log))
        if result.stdout:
            print(result.stdout, end="", flush=True)
        result.check_returncode()
        return result.stdout

    run([args.toolchain / "clang", "--version"])
    generated = build / "Tweak.m"
    logos = subprocess.run(["perl", str(args.logos / "bin/logos.pl"), "Tweak.x"],
                           cwd=root, env=env, text=True, capture_output=True)
    if logos.stderr:
        print(logos.stderr, end="")
    logos.check_returncode()
    generated.write_text(logos.stdout)

    slices = []
    legacy_arm64e = False
    minimum_ios = "14.0"
    for arch in ("arm64", "arm64e"):
        archdir = build / arch
        archdir.mkdir(exist_ok=True)
        obj = archdir / "Tweak.o"
        print("Compiling " + arch, flush=True)
        run([args.toolchain / "clang", "-target", arch + "-apple-ios" + minimum_ios,
             "-isysroot", args.sdk, "-I", args.headers, "-F", args.libraries,
             "-fobjc-arc", "-fblocks", "-Os", "-Wall", "-Wextra", "-Werror",
             "-Wno-unused-parameter", "-fvisibility=hidden", "-c", generated,
             "-o", obj])
        if arch == "arm64e":
            subtype = struct.unpack_from("<I", obj.read_bytes(), 8)[0]
            legacy_arm64e = not bool(subtype & 0x80000000)
            if legacy_arm64e and args.abi_converter is None:
                raise SystemExit("This compiler emits legacy arm64e metadata. Supply "
                                 "--abi-converter /path/to/allemande, or build with "
                                 "Theos and a compatible Xcode toolchain.")
        dylib = archdir / "SilentNotifs.dylib"
        link_output = run([args.toolchain / "ld", "-arch", arch, "-dylib", "-ios_version_min",
             minimum_ios, "-syslibroot", args.sdk, "-F", args.libraries,
             "-lSystem", "-lobjc", "-framework", "Foundation",
             "-framework", "AVFoundation", "-framework", "CydiaSubstrate",
             "-install_name", "/Library/MobileSubstrate/DynamicLibraries/SilentNotifs.dylib",
             obj, "-o", dylib])
        for line in link_output.splitlines():
            if "warning:" in line.lower() and not (
                    arch == "arm64e" and legacy_arm64e and args.abi_converter and
                    "incompatible arm64e ABI compiler" in line):
                raise SystemExit("Unexpected linker warning: " + line)
        slices.append(dylib)

    stage = build / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    library_dir = stage / "Library/MobileSubstrate/DynamicLibraries"
    library_dir.mkdir(parents=True)
    output = library_dir / "SilentNotifs.dylib"
    run([args.toolchain / "lipo", "-create", *slices, "-output", output])
    if legacy_arm64e:
        # Theos documents allemande as a static old-ABI conversion route.
        # This tweak has no Swift or Objective-C class implementations. Its
        # legacy CFString ISA fixups still need conversion before signing.
        conversion = run([args.abi_converter, output])
        if "ERROR:" in conversion:
            raise SystemExit("arm64e ABI conversion failed")
    run([args.toolchain / "ldid", "-S", output])
    output.chmod(0o755)
    run([args.toolchain / "lipo", "-info", output])
    shutil.copy2(root / "SilentNotifs.plist", library_dir)

    control_dir = stage / "DEBIAN"
    control_dir.mkdir()
    metadata = dict(line.split(": ", 1) for line in
                    (root / "control").read_text().splitlines() if ": " in line)
    metadata["Installed-Size"] = str((sum(p.stat().st_size for p in
                                           stage.rglob("*") if p.is_file()) + 1023) // 1024)
    (control_dir / "control").write_text("".join(
        key + ": " + value + "\n" for key, value in metadata.items()))

    package_dir = root / "packages"
    package_dir.mkdir(exist_ok=True)
    package = package_dir / "{Package}_{Version}_{Architecture}.deb".format(**metadata)
    run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", stage, package])
    print("SHA256 " + hashlib.sha256(package.read_bytes()).hexdigest())
    print(package)


if __name__ == "__main__":
    main()
