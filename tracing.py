import sys
import os
import site
import subprocess
import importlib
import importlib.metadata
import re
import getpass

# Class that initiates and parses system traces of a program
class Tracing:
    def __init__(self,
                 new_trace = False,
                 trace_log = 'trace.log',
                 paths_log = 'paths.log',
                 target = 'target.sh',
                 dockerfile = None):
        # Load the trace logs (or create it if it do not exist)
        if new_trace or not os.path.exists(trace_log):
            self.log_trace(target=target)
        with open(trace_log, 'r') as log:
            self.trace = list(log.read().splitlines())

        # Load the paths logs (or create it if it do not exist)
        if new_trace or not os.path.exists(paths_log):
            self.log_paths()
        with open(paths_log, 'r') as log:
            self.paths = log.read().splitlines()

        # Parse scripts from system trace
        self.scripts = self.parse_scripts()

        # Generate a trace summary for missing/unresolvable features from the trace logs
        if new_trace and os.path.exists(trace_log):
            self.log_summary()
        
        # Parse runtime information from system trace
        self.versions = self.parse_versions()
        self.requirements = self.parse_requirements()
        with open('requirements.txt', 'w') as file:
            file.write('\n'.join(self.requirements))
        self.ports = self.parse_ports()
        
        # Parse containers from system trace
        self.dockerfile = dockerfile
        self.job_containers = self.parse_job_containers()
        self.service_containers = self.parse_service_containers()


    #========================================================================================================
    #                                        GENERATE TRACE-RELATED LOGS
    #========================================================================================================

    # Trace the target and write the trace log to a file
    def log_trace(self, target):
        command = f'strace --follow-forks --decode-fds=path --trace=%file,%network --string-limit=999 --quiet=all --successful-only --output=trace.log bash {target} 2>&1'
        subprocess.run(command, shell=True)

    # Parse distinct paths from system trace and write them to a file
    def log_paths(self):          
        paths = []
        for call in self.trace:
            paths.extend(re.findall('\"(.+?)\"', call))
            paths.extend(re.findall('<(.+?)>', call))
        paths = list(set([path for path in paths if os.path.exists(path)]))
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

    # Parse requirements, or library/module dependencies
    def parse_requirements(self):
        # Parse module candidates found in the python package paths
        module_paths = sys.path + [site.USER_BASE] + [site.USER_SITE]
        modules = []
        for path in self.paths:
            for module_path in module_paths:
                if module_path in path:
                    try:
                        new_path = path.replace(module_path, '').split('/')[1].split('.')[0]
                    except:
                        new_path = path.replace(module_path, '').split('/')[0].split('.')[0]
                    if new_path != '':
                        modules.append(new_path)
                    break
        modules = list(set(modules))
        
        # Select module candidates that are third-party python modules
        requirements = []
        for module in modules:
            try:
                # Third-Party Python Modules
                module_name = importlib.import_module(module).__name__
                module_version = importlib.metadata.version(module_name)
                requirements.append(f'{module_name}=={module_version}')
            except importlib.metadata.PackageNotFoundError:
                # Built-In Python Modules
                pass
            except ModuleNotFoundError:
                # Files that are not Python Modules
                pass
            except Exception:
                # Miscellaneous Import Errors
                pass
        requirements.sort()
        return requirements

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

    # Parse job contrainers
    def parse_job_containers(self):
        job_container_scripts = {'docker': {'img': [], 'exec': []}}
        command = 'docker ps --no-trunc --format "{{.Image}}~{{.ID}}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        # Find scripts executed within docker containers        
        containers = result.stdout.strip().splitlines()
        containers = dict([container.split('~', 1) for container in containers])
        containers = {image: id for image, id in containers.items()}
        
        images = []
        for parse in self.scripts:
            if 'exec' in parse:
                job_container_scripts['docker']['exec'].append(parse)
                images.extend([image for image, id in containers.items() if id in ' '.join(parse)])
        images = list(set(images))
        job_container_scripts['docker']['img'] = images

        return job_container_scripts

    # Parse service contrainers
    def parse_service_containers(self):
        # Find the images and exposed ports of all running containers
        command = 'docker ps --format "{{.Image}}~{{.Ports}}"'
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        # Parse containers into the following format: {'image:version': ['host-port-1:container:port-1', ...]}
        containers = result.stdout.strip().splitlines()
        containers = [container.split('~', 1) for container in containers]
        containers = [[container[0], [re.findall("(?<=:).*", port)[0].replace("->",":") if "->" in port else '{0}:{1}'.format(re.findall(".+?(?=\\/)", port)[0], port) 
                        for port in container[1].split(', ', 1)]] for container in containers]

        # Remove containers that do not have at least 1 port in the trace log (and are thus not being used by the target)
        containers = [container for container in containers if len([port for port in container[1] if port.split(':')[0] in self.ports]) > 0]
        return containers