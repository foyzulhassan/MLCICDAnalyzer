import csv
import json
import os
from pathlib import Path
import re

import requirements as requirements_parser
import tree_sitter_bash as tsbash
from tree_sitter import Language, Parser


class ParseTrace:
    def __init__(self, 
                 target_path: str,
                 output_dir: str,
                 requirements_path: str,
                 env_filter_path: str = None,
                 docker_path: str = None):
        self.target_path = target_path
        self.target_name = Path(self.target_path).stem.split('.')[0]
        self.target_content = None
        self.output_dir = output_dir
        self.requirements_path = requirements_path
        self.env_filter_path = env_filter_path
        self.strace_path = os.path.join(output_dir, f'{self.target_name}.strace')
        self.timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        self.ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        self.pyenv_path = os.path.join(self.output_dir, f'{self.target_name}.pyenv')
        self.packages_path = os.path.join(output_dir, 'packages.pip')
        self.parse_path = os.path.join(self.output_dir, f'{self.target_name}.parse')
        self.docker_path = docker_path
    
    def parse(self, dump: bool = False):
        """Parse all information from logs"""
        parse = \
        {
            'script': self.__script(),
            'versions': self.__versions(),
            'requirements': self.__requirements(),
            'env': self.__env()
        }
        if dump:
            with open(self.parse_path, 'w') as parse_file:
                json.dump(parse, parse_file, indent=2)
        return parse
        
    def __script(self) -> str:
        """Read the target script (and remove comments and blank spaces)"""
        with open(self.target_path, 'r') as target_file:
            script = target_file.read().strip()
        BASH_LANGUAGE = Language(tsbash.language())
        children = Parser(BASH_LANGUAGE).parse(script.encode()).root_node.children
        lines = [child.text.decode() for child in children if child.type != 'comment']
        script = '\n'.join(lines)
        return script

    def __versions(self) -> list[str]:
        """Parse python versions from strace log"""
        versions = set()
        for path in self.__paths():
            versions.update(re.findall(r'(?<=/python)(.+?)(?=/)', path)) # Find all versions in python invocations in paths
        versions = [version for version in versions if re.search(r'^\d(\.\d)(\d|\.\d)*$', version)] # Remove general or non-sense versions
        return versions if versions else ['3.10']

    def __requirements(self) -> dict[str,str]:
        """Parse requirements, or pip modules, that are not in a pip requirements file"""
        # Identify explicit requirements in a pip requirements file
        with open(self.requirements_path, 'r') as requirements_file:
            explicit_requirements = set(requirement.name for requirement in requirements_parser.parse(requirements_file))

        # Identify implicit requirements in a pip requirements file
        with open(self.packages_path, 'r') as packages_file:
            packages = json.load(packages_file)
        implicit_requirements = [packages[package]['requires'] for package in packages] # get all required packages
        implicit_requirements = set(item for row in implicit_requirements for item in row) # flatten 2d list and remove duplicates

        # Identify requirements in a strace log
        with open(self.strace_path, 'r') as strace_file:
            traced_requirements = set(re.findall(r'(?<=/site-packages/)(.+?)(?=/|"|>|\-\d)', entry) if 'site-packages' in entry else '' for entry in strace_file)
            traced_requirements = {requirement.strip('_').removesuffix('.libs').lower() for requirement in traced_requirements if not requirement.endswith('.py')}
            traced_requirements.remove('pycache') if 'pycache' in traced_requirements else None
            traced_requirements.remove('') if '' in traced_requirements else None

        # Identify requirements in the strace log but not in the pip requirements file
        missing_requirements = traced_requirements.difference(explicit_requirements | implicit_requirements)
        missing_requirements = {requirement: packages[requirement]['version'] if requirement in packages else None for requirement in missing_requirements}
        missing_requirements = {name: missing_requirements[name] for name in sorted(missing_requirements.keys())}
        return missing_requirements
    
    def __env(self) -> list[dict]:
        """Parse environmental variables from ltrace and pyenv"""
        candidates = []

        # Check whether a ltrace log exists for the job and identify env variables
        if os.path.isfile(self.ltrace_path):
            with open(self.ltrace_path, 'r') as log:
                for entry in log:
                    key = re.match(r'(?<=getenv\(").+?(?=")', entry)
                    value = re.match(r'(?<==\s").+?(?=")', entry)
                    if key and value:
                        candidates.append({'op': 'get', 'filename': 'ltrace', 'key': key.string.strip(), 'value': os.getenv(key.string.strip())})

                    key = re.match(r'(?<=setenv\(").+?(?=")', entry)
                    value = re.match(r'(?<=,\s").+(?=")', entry)
                    if key and value:
                        candidates.append({'op': 'set', 'filename': 'ltrace', 'key': key.string.strip(), 'value': value.string.strip()})
                        
        # Check whether a pyenv log exists for the job and identify env variables
        if os.path.isfile(self.pyenv_path):
            with open(self.pyenv_path, 'r') as log:
                for filename, key, value in csv.reader(log):
                    candidates.append({'op': 'get', 'filename': filename, 'key': key, 'value': value})

        # Get the filtered out env variables
        if self.env_filter_path is not None:
            with open(self.env_filter_path, 'r') as log:
                filter = [entry.strip() for entry in log if not entry.strip().startswith('#')]

        # Eliminate duplicate or filtered candidate keys
        used, env = [], []
        for candidate in candidates:
            if candidate['key'] in used or candidate['key'] in filter:
                continue
            env.append(candidate)
            used.append(candidate['key'])
        return env

    def __paths(self) -> list[str]:
        """Parse all distinct paths from strace log"""
        paths = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                paths.update(re.findall(r'(?<=")/(.+?)(?=")', entry))
                paths.update(re.findall(r'(?<=<)/(.+?)(?=>)', entry))
        paths = ['/' + path for path in paths]
        return paths

    def __ports(self):
        """Parse port information from strace"""
        ports = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                ports.update(re.findall(r'(?<=sin_port=htons\().*?(?=\))', entry))
        if '0' in ports:
            ports.remove('0')
        return list(ports)

    def __docker(self):
        """
        Parse docker information from the docker log
        # - Docker Log == docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"
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

    def __services(self):
        """Parse service contrainers"""
        docker_execs = [line.strip() for line in self.__script().splitlines() 
                        if line.strip().startswith(('docker exec', 'docker container exec'))]
        containers = [container for container in self.__docker()
                        if len([None for exec in docker_execs if container['id'] in exec or container['name'] in exec]) > 0
                        or len([port for port in container['ports'] if port.split(':')[0] in self.__ports()]) > 0]
        return containers
