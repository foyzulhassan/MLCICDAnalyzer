import sys
import os
import site
import subprocess
import importlib
import importlib.metadata
import re

# Class that initiates and parses system traces of a program
class Tracing:
    def __init__(self,
                 new_trace = False,
                 trace_log = 'trace.log',
                 paths_log = 'paths.log',
                 target = 'target.sh'):
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
    
    #========================================================================================================
    #                                        GENERATE TRACE-RELATED LOGS
    #========================================================================================================

    # Trace the target and write the trace log to a file
    def log_trace(self, target):
        command = f'strace --follow-forks --decode-fds=path --trace=%file --string-limit=9999999 --output=trace.log bash {target} 2>&1'
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
    def parse_script(self, script):
        execve = [list(eval(re.findall("\\[(.+?)\\]", trace)[0])) for trace in self.trace if 'execve' in trace and not '<... execve resumed>' in trace]
        args = [arg for arg in execve if arg[0] == script]
        args = [[]] if len(args) == 0 else args
        return args