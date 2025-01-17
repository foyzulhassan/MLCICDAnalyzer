import json
import os
from pathlib import Path
import re
import requirements as requirements_parser


class ParseTrace:
    def __init__(self, 
                 target_path: str,
                 output_dir: str,
                 requirements_path: str = None,
                 docker_path: str = None):
        self.target_path = target_path
        self.target_name = Path(self.target_path).stem
        self.output_dir = output_dir
        self.strace_path = os.path.join(output_dir, f'{self.target_name}.strace')
        self.packages_path = os.path.join(output_dir, 'packages.pip')
        self.requirements_path = requirements_path
        self.docker_path = docker_path
    
    def parse(self, dump: bool = False):
        """Parse all information from logs"""
        parse = {
            'script': self.script(),
            'versions': self.versions(),
            'requirements': self.requirements() if self.requirements_path is not None else None,
            'ports': self.ports(),
            'services': self.services() if self.docker_path is not None else None}
        if dump:
            parse_path = os.path.join(self.output_dir, f'{self.target_name}.parse')
            with open(parse_path, 'w') as parse_file:
                json.dump(parse, parse_file, indent=2)
        return parse

    def script(self) -> str:
        """Read the target script"""
        with open(self.target_path, 'r') as target_file:
            script = target_file.read()
        return script

    def versions(self) -> list[str]:
        """Parse python versions from strace log"""
        versions = set()
        for path in self.__paths():
            versions.update(re.findall(r'(?<=/python)(.+?)(?=/)', path)) # Find all versions in python invocations in paths
        versions = [version for version in versions if re.search(r'^\d(\.\d)(\d|\.\d)*$', version)] # Remove general or non-sense versions
        return versions

    def requirements(self) -> dict[str,str]:
        """Parse requirements, or pip modules, that are not in a pip requirements file"""
        # Identify requirements in a pip requirements file
        pip_requirements = set()
        with open(self.requirements_path, 'r') as requirements_file:
            for requirement in requirements_parser.parse(requirements_file):
                pip_requirements.add(requirement.name)
        
        # Identify requirements in a strace log
        trace_requirements = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                trace_requirements.update(re.findall(r'(?<=/site-packages/)(.+?)(?=/|"|>|\-\d)', entry))
        trace_requirements = {requirement.strip('_').removesuffix('.libs').lower() for requirement in trace_requirements if not requirement.endswith('.py')}
        if 'pycache' in trace_requirements:
            trace_requirements.remove('pycache')

        # Identify requirements in the strace log but not in the pip requirements file (and remove redundant)
        with open(self.packages_path, 'r') as packages_file:
            packages = json.load(packages_file)
        required = set()
        for package in packages:
            required.update(packages[package]['requires'])
        unique_requirements = {requirement: packages[requirement]['version'] if requirement in packages else None 
                               for requirement in trace_requirements.difference(pip_requirements) 
                               if requirement not in required}
        return unique_requirements

    def ports(self):
        """Parse port information from strace"""
        ports = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                ports.update(re.findall(r'(?<=sin_port=htons\().*?(?=\))', entry))
        if '0' in ports:
            ports.remove('0')
        return list(ports)

    def services(self):
        """Parse service contrainers"""
        docker_execs = [line.strip() for line in self.script().splitlines() 
                        if line.strip().startswith(('docker exec', 'docker container exec'))]
        containers = [container for container in self.__parse_docker()
                        if len([None for exec in docker_execs if container['id'] in exec or container['name'] in exec]) > 0
                        or len([port for port in container['ports'] if port.split(':')[0] in self.ports()]) > 0]
        return containers
    
    def __paths(self) -> list[str]:
        """Parse all distinct paths from strace log"""
        paths = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                paths.update(re.findall(r'(?<=")/(.+?)(?=")', entry))
                paths.update(re.findall(r'(?<=<)/(.+?)(?=>)', entry))
        paths = ['/' + path for path in paths]
        return paths

    def __parse_docker(self):
        # Parse docker information from the docker log
        # - Docker Log == docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"

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
