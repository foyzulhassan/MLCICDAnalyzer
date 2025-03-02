import csv
import glob
import json
import os
from pathlib import Path
import re

import requirements as requirements_parser


class ParseTrace:
    def __init__(self, 
                 target_path: str,
                 output_dir: str,
                 requirements_path: str,
                 repository_dir: str,
                 filters_path: str,
                 docker_path: str = None):
        self.target_path = target_path
        self.output_dir = output_dir
        self.requirements_path = requirements_path
        self.repository_dir = repository_dir
        self.filters_path = filters_path
        self.docker_path = docker_path

        self.target_name = Path(self.target_path).stem.split('.')[0]
        self.strace_path = os.path.join(output_dir, f'{self.target_name}.strace')
        self.ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        self.timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        self.pyenv_path = os.path.join(self.output_dir, f'{self.target_name}.pyenv')
        self.pip_packages_path = os.path.join(output_dir, 'packages.pip.json')
        self.apt_packages_path = os.path.join(output_dir, 'packages.apt.json')
        self.parse_path = os.path.join(self.output_dir, f'{self.target_name}.parse')
        with open(self.filters_path, 'r') as file:
            self.filters = json.load(file)
        self.paths = []
        self.parse_trace = {}
    
    def parse(self, dump: bool = False) -> dict:
        """Parse all information from logs"""
        self.paths = self.__paths()
        self.parse_trace = \
        {
            'apt': self.__apt(),
            'env': self.__env(),
            'pip': self.__pip(),
            'script': self.__script(),
            'versions': self.__versions(),
        }
        if dump:
            with open(self.parse_path, 'w') as file:
                json.dump(self.parse_trace, file, indent=2)
        return self.parse_trace

    # ======================================================================= #
    #                                    STEPS                                #
    # ======================================================================= #

    def __apt(self) -> list[str]:
        """Parse apt packages that are unique to the strace log"""
        with open(self.apt_packages_path, 'r') as file:
            apt_packages = json.load(file)
        used_packages = set()
        for name in apt_packages:
            is_used = any(filename in self.paths for filename in apt_packages[name])
            if is_used:
                used_packages.add(name)
        used_packages = sorted(package for package in used_packages \
                            if package not in self.filters['apt'] \
                            and 'python' not in package \
                            and ':' not in package)
        return used_packages

    def __env(self) -> dict:
        """Parse environmental variables from ltrace and pyenv"""
        env = []

        # Check whether a ltrace log exists for the job and identify env variables
        if os.path.isfile(self.ltrace_path):
            with open(self.ltrace_path, 'r') as log:
                for entry in log:
                    content = re.match(r'(\d+)\s(\d+\.\d+)\s(.+?)->getenv\("(.+?)"\)\s+=\s+"(.+?)"', entry.strip())
                    if content:
                        _, _, _, key, value = content.groups()
                        env.append({'key': key, 'value': value})

        # Check whether a pyenv log exists for the job and identify env variables
        if os.path.isfile(self.pyenv_path):
            with open(self.pyenv_path, 'r') as log:
                for filename, key, value in csv.reader(log):
                    if filename:
                        env.append({'key': key, 'value': value})

        # Get the paths of non-imports, -workflows, and -documentation in the target repository
        paths = [path \
                for path in glob.glob(os.path.join(self.repository_dir, '**', '*'), recursive=True)
                if os.path.isfile(path) \
                and not path.endswith(('.yml', '.yaml', '.md')) \
                and 'site-packages' not in path \
                and 'dist-packages' not in path \
                and 'venv' not in path]

        # Filter out unused and/or blacklisted environment variables
        traced_keys, used_keys, duplicate_keys = set(entry['key'] for entry in env), set(), set()
        for path in paths:
            with open(path, 'r', errors='ignore') as file:
                content = file.read()
            used_keys.update(key for key in traced_keys if key in content)
        env = {entry['key']: entry['value'] for entry in env \
                if entry['key'] in used_keys \
                and '/' not in entry['value'] \
                and entry['key'] not in self.filters['env'] \
                and entry['key'] not in duplicate_keys \
                and not duplicate_keys.add(entry['key'])}
        return env

    def __pip(self) -> dict:
        """Parse pip packages that are unqiue to the stract log"""
        # Identify explicit requirements in a pip requirements file
        with open(self.requirements_path, 'r') as file:
            explicit_requirements = set(requirement.name for requirement in requirements_parser.parse(file))

        # Identify implicit requirements in a pip requirements file
        with open(self.pip_packages_path, 'r') as file:
            pip_packages = json.load(file)
        implicit_requirements = [pip_packages[package]['requires'] for package in pip_packages] # get all required packages
        implicit_requirements = set(item for row in implicit_requirements for item in row) # flatten 2d list and remove duplicates

        # Identify requirements in a strace log
        traced_requirements = set()
        for path in self.paths:
            content = re.match(r'(?:.*?/python\d+\.\d+/(?:site-packages|dist-packages)/)(.+?)/', path.strip())
            if content:
                package = content.group(1)
                if package in pip_packages:
                    traced_requirements.add(package)

        # Identify requirements in the strace log but not in the pip requirements file
        missing_requirements = traced_requirements.difference(explicit_requirements | implicit_requirements)
        missing_requirements = {requirement: pip_packages[requirement]['version'] if requirement in pip_packages else None for requirement in missing_requirements}
        missing_requirements = {name: missing_requirements[name] for name in sorted(missing_requirements.keys()) if name not in self.filters['pip']}
        return missing_requirements

    def __script(self) -> str:
        """Read the target script"""
        with open(self.target_path, 'r') as file:
            script = file.read()
        script = ''.join([line for line in script.splitlines(keepends=True) if line.strip() and not line.strip().startswith('#')])
        return script

    def __services(self):
        """Parse service contrainers"""
        docker_execs = [line.strip() for line in self.__script().splitlines() 
                        if line.strip().startswith(('docker exec', 'docker container exec'))]
        containers = [container for container in self.__docker()
                        if len([None for exec in docker_execs if container['id'] in exec or container['name'] in exec]) > 0
                        or len([port for port in container['ports'] if port.split(':')[0] in self.__ports()]) > 0]
        return containers

    def __versions(self) -> list[str]:
        """Parse python versions from strace log"""
        versions = set()
        for path in self.paths:
            versions.update(re.findall(r'(?<=/python)\d+.\d+(?=/site-packages|/dist-packages)', path))
        return sorted(versions) if versions else ['3.10']

    # ======================================================================= #
    #                                   UTILITY                               #
    # ======================================================================= #

    def __docker(self):
        """
        Parse docker information from the docker log
        - Docker Log == docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"
        """
        # Find open the docker log and extract its container information
        with open(self.docker_path, 'r') as log:
            containers = list(log.read().splitlines())

        # Parse containers into the following format: [{container_id-1:ID-1, container_name-1:NAME-1, image:VERSION-1, ['HOST-PORT-1:CONTAINER:PORT-1', ...]}]
        containers = [container.split('~') for container in containers]
        containers = [container if container[3] != '' else [container[0], container[1], container[2], 'None/tcp'] for container in containers]
        containers = [[container[0], container[1], container[2], [re.findall("(?<=:).*", port)[0].replace("->",":") if "->" in port else '{0}:{1}'.format(re.findall(".+?(?=\\/)", port)[0], port) 
                for port in container[3].split(', ', 1)]] for container in containers]
        containers = [{'id': container[0], 'name': container[1], 'image': container[2], 'ports': container[3]} for container in containers]
        return containers

    def __paths(self) -> list[str]:
        """Parse all distinct paths from strace log"""
        paths = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                paths.update(re.findall(r'(?<=,\s")/.+?(?=",\s)', entry))
                paths.update(re.findall(r'(?<=<)/.+?(?=>)', entry))
        return sorted(paths)

    def __ports(self):
        """Parse port information from strace"""
        ports = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                ports.update(re.findall(r'(?<=sin_port=htons\().*?(?=\))', entry))
        if '0' in ports:
            ports.remove('0')
        return list(ports)
