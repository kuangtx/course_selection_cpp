"""Build and install the native module for the Python running this script."""
import argparse
import importlib.machinery
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generator', help='Optional CMake generator, e.g. Ninja')
    args = parser.parse_args()
    build = ROOT / 'build' / ('native-' + sys.implementation.cache_tag)
    pybind_dir = subprocess.check_output(
        [sys.executable, '-m', 'pybind11', '--cmakedir'], text=True).strip()
    command = ['cmake', '-S', str(ROOT / 'backend/core/cpp'), '-B', str(build),
               '-DCMAKE_BUILD_TYPE=Release', '-DPYBIND11_FINDPYTHON=ON',
               '-DPython3_EXECUTABLE=' + sys.executable, '-Dpybind11_DIR=' + pybind_dir]
    if args.generator:
        command += ['-G', args.generator]
    subprocess.run(command, check=True)
    subprocess.run(['cmake', '--build', str(build), '--config', 'Release',
                    '--parallel', '2'], check=True)
    modules = [p for p in build.rglob('_planner*') if p.is_file()
               and any(p.name == '_planner' + suffix
                       for suffix in importlib.machinery.EXTENSION_SUFFIXES)]
    if len(modules) != 1:
        raise RuntimeError(f'Expected one native module, found: {modules}')
    destination = ROOT / 'backend/core' / modules[0].name
    shutil.copy2(modules[0], destination)
    print(f'Installed {destination}')


if __name__ == '__main__':
    main()
