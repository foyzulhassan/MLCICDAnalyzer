from argparse import ArgumentParser
from email.parser import HeaderParser
import json
import subprocess


def parse_packages(output_path: str, dump: bool = False):
    process = subprocess.run('pip freeze  | sed s/=.*//', capture_output=True, text=True, shell=True)
    package_names = process.stdout.splitlines()
    packages = {}
    for package_name in package_names:
        process = subprocess.run(f'pip show --no-input {package_name}', capture_output=True, text=True, shell=True)
        header = HeaderParser().parsestr(process.stdout)
        requires = {require for require in header['Requires'].split(', ') if require.strip() != ''} if 'Requires' in header else set()
        packages[package_name] = {
            'version': header['Version'],
            'requires': sorted(list(requires))}
    if dump:
        with open(output_path, 'w') as output_file:
            json.dump(packages, output_file, indent=2)
    return packages


def parse_args():
    parser = ArgumentParser(description='Parse the versions and requirements of installed pip packages')
    parser.add_argument('output_path', type=str, help='path to a file to output results')
    return parser.parse_args()


def main():
    args = parse_args()
    parse_packages(args.output_path, dump=True)


if __name__ == '__main__':
    main()
