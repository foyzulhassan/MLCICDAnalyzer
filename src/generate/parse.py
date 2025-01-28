import json
import os
from pathlib import Path
import re
import tree_sitter_bash as tsbash
from tree_sitter import Language, Parser


class ParseTrace:
    def __init__(self, 
                 target_path: str,
                 output_dir: str,
                 env_filter_path: str = None,
                 docker_path: str = None):
        self.target_path = target_path
        self.target_name = Path(self.target_path).stem.split('.')[0]
        self.target_content = None
        self.output_dir = output_dir
        self.env_filter_path = env_filter_path
        self.strace_path = os.path.join(output_dir, f'{self.target_name}.strace')
        self.timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        self.ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        self.pyenv_path = os.path.join(self.output_dir, f'{self.target_name}.pyenv')
        self.requirements_path = os.path.join(output_dir, f'{self.target_name}.requirements')
        self.docker_path = docker_path
    
    def parse(self, dump: bool = False):
        """Parse all information from logs"""
        parse = {
            'script': self.__script(),
            'versions': self.__versions(),
            'requirements': self.__requirements(),
            'ports': self.__ports(),
            'services': self.__services() if self.docker_path else None,
            'knowledge': self.__knowledge(dump=dump)}
        if dump:
            parse_path = os.path.join(self.output_dir, f'{self.target_name}.parse')
            with open(parse_path, 'w') as parse_file:
                json.dump(parse, parse_file, indent=2)
        return parse
    
    def __knowledge(self, dump: bool = False):
        """Parse information from logs into natural language statements"""
        knowledge = []

        if self.strace_path is not None and os.path.isfile(self.strace_path):
            # The total amount of time that each job took
            with open(self.strace_path, 'r') as file:
                timestamps = [float(entry.split(maxsplit=2)[1]) for entry in file.readlines()]
            duration = round(max(timestamps) - min(timestamps)) if len(timestamps) > 0 else None
            if duration is not None:
                knowledge += [f'The job named "{self.target_name}" took {duration} seconds to complete\n']

        if self.requirements_path is not None and os.path.isfile(self.requirements_path):
            requirements = self.__requirements()
            requirements_str = ' '.join(sorted([f'{name}=={version}' if version is not None else name for name, version in requirements.items()]))
            if requirements_str.strip() != '':
                knowledge += [f'The job named "{self.target_name}" used the following python requirements: {requirements_str}\n']

        if self.timestamp_path is not None and os.path.isfile(self.timestamp_path):
            # The amount of time that each line took
            with open(self.timestamp_path, 'r') as file:
                timestamps = [[int(item) for item in entry.split(',')] for entry in file.readlines() if entry.strip() != '']
            if len(timestamps) > 0:
                knowledge += [f'Lines {start}-{end} in the run named "Execute Tests" in the job named "{self.target_name}" was executed in {duration} seconds\n' 
                                if start != end else 
                                f'Line {start} in the run named "Execute Tests" in the job named "{self.target_name}" was executed in {duration} seconds\n' 
                                for start, end, duration in timestamps]

        if self.ltrace_path is not None and os.path.isfile(self.ltrace_path):
            # The environmental variables that were get or set during each job (ltrace, pyenv)
            envs = self.__env()
            get_str = ' '.join([f'{env["key"]}={env["value"]}' for env in envs if env["op"] == "get"])
            set_str = ' '.join([f'{env["key"]}={env["value"]}' for env in envs if env["op"] == "set"])
            if get_str.strip() != '':
                knowledge += [f'The job named "{self.target_name}" got the following environmental variables: {get_str}\n']
            if set_str.strip() != '':
                knowledge += [f'The job named "{self.target_name}" set the following environmental variables: {set_str}\n']
        
        if dump:
            knowledge_path = os.path.join(self.output_dir, f'{self.target_name}.knowledge')
            with open(knowledge_path, 'w') as file:
                file.writelines(knowledge)
        return knowledge
        
    def __script(self) -> str:
        """Read the target script (and remove comments and blank spaces)"""
        with open(self.target_path, 'r') as target_file:
            script = target_file.read().strip()
        BASH_LANGUAGE = Language(tsbash.language())
        parser = Parser(BASH_LANGUAGE)
        tree = parser.parse(script.encode())
        lines = []
        for child in tree.root_node.children: # Remove comments
            if child.type != 'comment':
                lines.append(child.text.decode())
        script = '\n'.join(lines)
        return script

    def __versions(self) -> list[str]:
        """Parse python versions from strace log"""
        versions = set()
        for path in self.__paths():
            versions.update(re.findall(r'(?<=/python)(.+?)(?=/)', path)) # Find all versions in python invocations in paths
        versions = [version for version in versions if re.search(r'^\d(\.\d)(\d|\.\d)*$', version)] # Remove general or non-sense versions
        return versions

    def __requirements(self) -> dict[str,str]:
        """Parse requirements, or pip modules, that are not in a pip requirements file"""
        with open(self.requirements_path, 'r') as file:
            entries = [entry.strip() for entry in file.readlines()]
        requirements = {}
        for entry in entries:
            if '==' in entry:
                name, version = entry.split('==', 1)
                requirements[name] = version
            else:
                requirements[entry] = None
        return requirements
    
    def __env(self) -> dict:
        """Parse environmental variables from ltrace and pyenv"""
        candidates = []
        # Check whether a ltrace log exists for the job and identify env variables
        if os.path.isfile(self.ltrace_path):
            with open(self.ltrace_path, 'r') as log:
                for entry in log:
                    key = re.findall(r'(?<=getenv\(").+?(?=")', entry)
                    value = re.findall(r'(?<==\s").+?(?=")', entry)
                    if key and value:
                        candidates.append({'op': 'get', 'key': key[0].strip(), 'value': os.getenv(key[0].strip())})

                    key = re.findall(r'(?<=setenv\(").+?(?=")', entry)
                    value = re.findall(r'(?<=,\s").+(?=")', entry)
                    if key and value:
                        candidates.append({'op': 'set', 'key': key[0].strip(), 'value': value[0].strip()})
                        
        # Check whether a pyenv log exists for the job and identify env variables
        if os.path.isfile(self.pyenv_path):
            with open(self.pyenv_path, 'r') as log:
                for entry in log:
                    if not entry.strip():
                        continue
                    key, value = entry.split('=', 1)
                    candidates.append({'op': 'get', 'key': key.strip(), 'value': value.strip()})

        # Get the filtered out env variables
        filter = []
        if self.env_filter_path is not None:
            with open(self.env_filter_path, 'r') as log:
                for entry in log:
                    if entry.strip().startswith('#'):
                        continue
                    filter.append(entry.strip())

        # Eliminate duplicate or filtered candidate keys
        used_keys, env = [], []
        for candidate in candidates:
            if candidate['key'] in used_keys or candidate['key'] in filter:
                continue
            env.append(candidate)
            used_keys.append(candidate['key'])
        return env

    def __ports(self):
        """Parse port information from strace"""
        ports = set()
        with open(self.strace_path, 'r') as strace:
            for entry in strace:
                ports.update(re.findall(r'(?<=sin_port=htons\().*?(?=\))', entry))
        if '0' in ports:
            ports.remove('0')
        return list(ports)

    def __services(self):
        """Parse service contrainers"""
        docker_execs = [line.strip() for line in self.__script().splitlines() 
                        if line.strip().startswith(('docker exec', 'docker container exec'))]
        containers = [container for container in self.__docker()
                        if len([None for exec in docker_execs if container['id'] in exec or container['name'] in exec]) > 0
                        or len([port for port in container['ports'] if port.split(':')[0] in self.__ports()]) > 0]
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
