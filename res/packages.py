from argparse import ArgumentParser
from email.parser import HeaderParser
import json
import os
import subprocess
from tqdm import tqdm


def parse_pip(output_path: str, dump: bool = False, verbose: bool = False):
    process = subprocess.run('pip freeze  | sed s/=.*//', capture_output=True, text=True, shell=True)
    package_names = process.stdout.splitlines()
    packages = {}
    for package_name in tqdm(package_names, disable=not verbose):
        process = subprocess.run(f'pip show --no-input {package_name}', capture_output=True, text=True, shell=True)
        header = HeaderParser().parsestr(process.stdout)
        requires = {require for require in header['Requires'].split(', ') if require.strip() != ''} if 'Requires' in header else set()
        packages[package_name] = {
            'version': header['Version'],
            'requires': sorted(list(requires))}
    if dump:
        with open(output_path, 'w') as file:
            json.dump(packages, file, indent=2)
    return packages


def parse_apt(output_path: str, dump: bool = False, verbose: bool = False):
    process = subprocess.run('dpkg --get-selections | grep -v deinstall', capture_output=True, text=True, shell=True)
    package_names = [line.split()[0] for line in process.stdout.splitlines()]
    packages = {}
    for package_name in tqdm(package_names, disable=not verbose):
        process = subprocess.run(f'dpkg -L {package_name}', capture_output=True, text=True, shell=True)
        filenames = [filename for filename in process.stdout.splitlines() if os.path.isfile(filename)]
        packages[package_name] = filenames
    if dump:
        with open(output_path, 'w') as file:
            json.dump(packages, file, indent=2)


def parse_args():
    parser = ArgumentParser(description='Parse the versions and requirements of installed packages')
    parser.add_argument('package_repository', type=str, help='whether to parse pip or apt packages')
    parser.add_argument('output_path', type=str, help='path to a file to output results')
    parser.add_argument('-v', '--verbose', action='store_true', help='whether to show progress messages')
    return parser.parse_args()


def main():
    args = parse_args()
    match args.package_repository:
        case 'pip':
            parse_pip(args.output_path, dump=True, verbose=args.verbose)
        case 'apt':
            parse_apt(args.output_path, dump=True, verbose=args.verbose)
        case _:
            raise Exception('RepositoryError: An invalid package repository was provided.')


if __name__ == '__main__':
    main()
