import sys
import os
import site
import subprocess
import importlib
import importlib.metadata
import re
import json

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
            self.trace = list(set(log.read().splitlines()))

        # Load the paths logs (or create it if it do not exist)
        if new_trace or not os.path.exists(paths_log):
            self.log_paths()
        with open(paths_log, 'r') as log:
            self.paths = log.read().splitlines()
        
        # Parse runtime information from system trace
        self.versions = self.parse_versions()
        self.requirements = self.parse_requirements()
        with open('requirements.txt', 'w') as file:
            file.write('\n'.join(self.requirements))
        
        # Parse scripts from system trace
        self.scripts = self.parse_scripts()

        # Parse containers from system trace
        self.dockerfile = dockerfile
        self.job_containers = self.parse_job_containers()
        self.service_containers = self.parse_service_containers()


    #========================================================================================================
    #                                        GENERATE TRACE-RELATED LOGS
    #========================================================================================================

    # Trace the target and write the trace log to a file
    def log_trace(self, target):
        command = f'strace --follow-forks --decode-fds=path --trace=%file --string-limit=999 --quiet=all --successful-only --output=trace.log bash {target} 2>&1'
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
        requirements.sort()
        return requirements

    # Parse configuration of a script used in target
    def parse_scripts(self, script=None):
        execve = [list(eval(re.findall("\\[(.+?)\\]", trace)[0])) for trace in self.trace if 'execve' in trace and not '<... execve resumed>' in trace]
        args = [arg for arg in execve if script == None or arg[0] == script]
        args = [[]] if len(args) == 0 else args
        return args
    
    # Parse job contrainers
    def parse_job_containers(self):
        # Find scripts executed within docker containers
        job_container_scripts = {}
        job_container_scripts['docker'] = {'exec': []}
        for parse in self.parse_scripts("docker"):
            if 'exec' in parse:
                job_container_scripts['docker']['exec'].append(parse)

        # Find images of docker containers
        job_container_scripts['docker']['img'] = ''
        if len(job_container_scripts['docker']['exec']) != 0: # Check if there are any scripts executed within the container
            image = ''
            if self.dockerfile != None: # Find the container image in dockerfile
                with open(self.dockerfile, 'r') as file:
                    dockerfile_content = file.readlines()
                for line in dockerfile_content:
                    if line.startswith('FROM'):
                        image = line.split(' ')[1]
            else: # Find the container image in docker run statements
                for script in self.scripts:
                    if ' '.join(script[:2]) == 'docker run':
                        image = [syntax for syntax in script[3:] if syntax[0] != '-'][0]
            job_container_scripts['docker']['img'] = image

        return job_container_scripts

    # Parse service contrainers
    def parse_service_containers(self):
        # Load container whitelist
        with open('containers.json', 'r') as file:
            whitelist = json.load(file)['service']

        # Find container instances in paths
        containers = []
        versionless_requirements = [requirement.split('==')[0] for requirement in self.requirements]
        for requirement in versionless_requirements:
            if requirement in whitelist:
                containers.append(requirement)

        # Find container instances in executions
        for script in self.scripts:
            for wlist in whitelist:
                if script[0] in whitelist or script[0] in whitelist[wlist]:
                    containers.append(wlist)
                    break

        containers = list(set(containers)) # Remove redundant containers
        return containers