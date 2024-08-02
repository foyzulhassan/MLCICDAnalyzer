import sys
import os
import site
import subprocess
import re
import getpass

# Class that initiates and parses system traces of a program
class Tracing:
    def __init__(self,
                 new_trace = False,
                 target = 'target.sh',
                 host_container = None,
                 trace_log = 'trace.log',
                 paths_log = 'paths.log',
                 docker_log = 'docker.log',
                 requirements_log = 'requirements.txt'):
        # Load the trace logs (or create it if it do not exist)
        if new_trace or not os.path.exists(trace_log):
            self.log_trace(target, host_container)
        with open(trace_log, 'r') as log:
            self.trace = list(log.read().splitlines())

        # Load the paths logs (or create it if it do not exist)
        if new_trace or not os.path.exists(paths_log):
            self.log_paths(host_container)
        with open(paths_log, 'r') as log:
            self.paths = log.read().splitlines()

        # Parse scripts from system trace
        self.scripts = self.parse_scripts()

        # Generate a trace summary for missing/unresolvable features from the trace logs
        if new_trace and os.path.exists(trace_log):
            self.log_summary()
        
        # Parse runtime information from system trace
        self.versions = self.parse_versions()
        self.requirements_log = requirements_log if os.path.exists(requirements_log) else None
        self.requirements = self.parse_requirements(requirements_log, host_container)
        self.ports = self.parse_ports()
        
        # Parse containers from system trace
        self.docker = self.parse_docker(docker_log)
        self.job_container = self.parse_job_container()
        self.service_containers = self.parse_service_containers()

    #========================================================================================================
    #                                        GENERATE TRACE-RELATED LOGS
    #========================================================================================================

    # Trace the target and write the trace log to a file
    def log_trace(self, target, host_container=None):
        command = f'strace --follow-forks --decode-fds=path --trace=%file,%network --string-limit=999 --quiet=all --successful-only --output=trace.log bash {target}'
        if host_container is not None:
            command = command.replace(f'bash {target}', f'bash -s')
            command = f'cat {target} | docker exec -i {host_container} {command}; docker exec -it {host_container} cat trace.log > trace.log; docker exec -it {host_container} rm trace.log'
        subprocess.run(command, shell=True)

    # Parse distinct paths from system trace and write them to a file
    def log_paths(self, host_container=None):          
        paths = []
        for call in self.trace:
            paths.extend(re.findall('\"(.+?)\"', call))
            paths.extend(re.findall('<(.+?)>', call))
        # For host container, assumes that all paths exist (due to successful-only file-based strace) and non-paths don't start with '/'
        # Potential, but more complex, alternative is to check if the files exists within the container itself and return the result
        paths = list(set([path for path in paths
                          if host_container is None and os.path.exists(path)
                          or host_container is not None and path[0] == '/']))
        with open('paths.log', 'w') as log:
            log.writelines("\n".join(paths))
        
    # Generate a trace summary for missing/unresolvable features from the trace logs
    def log_summary(self):
        signals = [script[0] for script in self.scripts]
        summary = [''.join(re.findall("(?<=\\s)(.*)(?=\\s\\=)", trace)).replace(getpass.getuser(), "USERNAME") for trace in self.trace if re.findall("^(.*?)(?=\\s)", trace)[0] in signals]
        summary = list(dict.fromkeys(summary))
        with open('summary.log', 'w') as log:
            log.writelines("\n".join(summary))

    #========================================================================================================
    #                            PARSE CONFIGURATION INFORMATION FROM TRACE-RELATED LOGS
    #========================================================================================================

    # Parse language runtime versions
    def parse_versions(self):
        versions = []
        path_versions = [re.findall('(?<=[\\/]python)(.+?)(?=[\\/])', path) for path in self.paths] # Find all versions in python invocations in paths
        for path_version in path_versions: # Flatten versions to a single dimensional list
            versions.extend(path_version)
        versions = list(set(versions)) # Remove non-unique versions from the single dimensional list
        versions = [version for version in versions if len(re.findall('^\\d\\..*', version)) != 0] # Remove general or non-sense versions from the single dimensional list
        return versions

    # Parse requirements, or pip modules, that are not user-specified
    def parse_requirements(self, requirements_log, host_container=None):
        # Parse module candidates found in the python package paths
        module_paths = sys.path + [site.USER_BASE] + [site.USER_SITE]
        if host_container is not None:
            command = f'docker exec -it {host_container} python3 -c "import sys,site; print(sys.path + [site.USER_BASE] + [site.USER_SITE])"'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            module_paths = eval(result.stdout)
        module_paths = [path for path in module_paths if path.strip() != '']

        modules_candidates = []
        for path in self.paths:
            for module_path in module_paths:
                if module_path in path:
                    try:
                        new_path = path.replace(module_path, '').split('/')[1].split('.')[0]
                    except:
                        new_path = path.replace(module_path, '').split('/')[0].split('.')[0]
                    if new_path != '':
                        modules_candidates.append(new_path)
                        break
        modules_candidates = list(set(modules_candidates))

        # Retrieve all modules that are installed on the system
        command = f'pip freeze'
        subprocess.run(command, shell=True, capture_output=True, text=True)
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        modules_installed = {module.split('==')[0].strip(): module.split('==')[1].strip() for module in result.stdout.splitlines()}

        # Retrieve all the user-specified modules in the requirements log
        modules_logged = {}
        if host_container is not None:
            command = f'docker exec -it {host_container} cat {requirements_log} > requirements.txt'
            subprocess.run(command, shell=True)
        if os.path.exists(requirements_log):
            with open(requirements_log, 'r') as log:
                modules_logged = {module.split('==')[0].strip(): module.split('==')[1].strip() for module in log.readlines() if module.strip() != ''}
        
        # Remove module candidates that are not install on the system or have already been specified by the user
        modules_parsed = {module: version for module, version in modules_installed.items() if module in modules_candidates and module not in modules_logged}
        return modules_parsed

    # Parse configuration of a script used in target
    def parse_scripts(self, script=None):
        # Find all program execution calls, and their pids, in the trace log (e.g. ['1234', 'python3', 'test.py'])
        execves = [[re.findall("^(.*?)(?=\\s)", trace)[0]] + re.findall("\\[(.+?)\\]", trace)[0].replace('"', '').split(', ') for trace in self.trace if 'execve' in trace and not '<... execve resumed>' in trace]

        # Find the pids of all processes that were created directly by the target in the trace log
        child_signals = [re.findall("(?<=si_pid=)\\d*", trace)[0] for trace in [trace for trace in self.trace if '--- SIGCHLD' in trace and re.findall("^(.*?)(?=\\s)", trace)[0] == execves[0][0]]]

        # Find all the program execution calls that were directly invoked by the target
        target_scripts = [execve[1:] for execve in execves if execve[0] in child_signals and script is None or execve[1] == script]
        return target_scripts
    
    # Parse port information
    def parse_ports(self):
        ports = [''.join(re.findall("(?<=sin_port=htons\\()\\d*", trace)) for trace in self.trace] # Attempt to find all references to ports in traces
        ports = list(set([port for port in ports if port != ''])) # Remove all empty and/or duplicate ports
        return ports

    # Parse docker information from the docker log
    # - Docker Log == docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"
    def parse_docker(self, docker_log):
        # Find open the docker log and extract its container information
        if not os.path.exists(docker_log):
            return []
        with open(docker_log, 'r') as log:
            containers = list(log.read().splitlines())

        # Parse containers into the following format: [[container_id-1, container_name-1, image:version-1, ['host-port-1:container:port-1', ...]]]
        containers = [container.split('~') for container in containers]
        containers = [container if container[3] != '' else [container[0], container[1], container[2], 'None/tcp'] for container in containers]
        containers = [[container[0], container[1], container[2], [re.findall("(?<=:).*", port)[0].replace("->",":") if "->" in port else '{0}:{1}'.format(re.findall(".+?(?=\\/)", port)[0], port) 
                for port in container[3].split(', ', 1)]] for container in containers]
        containers = [{'id': container[0], 'name': container[1], 'image': container[2], 'ports': container[3]} for container in containers]
        return containers
        
    # Parse job contrainer
    def parse_job_container(self):
        command = 'cat /proc/self/cgroup | grep name=systemd'     
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        container_id = re.findall("(?<=15:name=systemd:\\/docker\/).*", result.stdout.strip())
        for container in self.docker:
            if container['id'] == container_id:
                return container
        return {'id': None, 'name': None, 'image': None, 'ports': None}

    # Parse service contrainers
    def parse_service_containers(self):
        execs = [script for script in self.scripts if script[0] == 'docker' and (script[1] == 'exec' or script[1] == 'container' and script[2] == 'exec')]
        containers = [container for container in self.docker 
                        if len([None for exec in execs if container['id'] in exec or container['name'] in exec]) > 0
                        or len([port for port in container['ports'] if port.split(':')[0] in self.ports]) > 0]
        return containers