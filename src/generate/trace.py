from email.parser import HeaderParser
import json
import logging
import os
from pathlib import Path
import subprocess
import time

from tqdm import tqdm
from tree_sitter import Language, Parser
import tree_sitter_bash


class TraceTarget:
    def __init__(self, 
                 target_path: str, 
                 output_dir: str,
                 duration_log_path: str,
                 repository_dir: str,
                 working_dir: str,
                 packages_path: str,
                 patch_dir: str,
                 new_trace: bool):
        self.duration_log_path = duration_log_path
        self.duration_logger = logging.getLogger(f'{__name__}.duration')
        self.duration_logger.setLevel(logging.INFO)
        self.duration_handler = logging.FileHandler(self.duration_log_path)
        self.duration_handler.setFormatter(logging.Formatter('%(message)s'))
        self.duration_logger.addHandler(self.duration_handler)

        self.target_path = target_path
        self.output_dir = output_dir
        self.repository_dir = repository_dir
        self.working_dir = working_dir
        self.packages_path = packages_path
        self.patch_dir = patch_dir
        self.new_trace = new_trace

        self.target_name = Path(self.target_path).stem.split('.')[0]
        self.timestamps_target_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps.sh')
        self.timestamps_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        self.strace_path = os.path.join(self.output_dir, f'{self.target_name}.strace')
        self.ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        self.pip_packages_path = os.path.join(self.output_dir, 'packages.pip.json')
        self.apt_packages_path = os.path.join(self.output_dir, 'packages.apt.json')
        self.pyenv_path = os.path.join(self.output_dir, f'{self.target_name}.pyenv')
        os.makedirs(self.output_dir, exist_ok=True)

    def __duration(func):
        def wrapper(self, *args, **kwargs):
            # Calculate the duration
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Log the duration
            source = 'trace'
            function = str(func.__name__)
            self.duration_logger.info(f'"{source}","{function}","{duration}"')
            return result
        return wrapper

    @__duration
    def trace(self):
        """Instrument and trace a target script with strace and ltrace"""
        if self.new_trace or not os.path.isfile(self.timestamps_target_path):
            self.__timestamp(dump=True)
        if self.new_trace or not os.path.isfile(self.strace_path):
            self.__strace(self.timestamps_target_path)
        if self.new_trace or not os.path.isfile(self.ltrace_path):
            self.__ltrace(self.target_path)
        if self.new_trace or not os.path.isfile(self.pip_packages_path):
            self.__pip_packages(dump=True, verbose=True)
        if self.new_trace or not os.path.isfile(self.apt_packages_path):
            self.__apt_packages(dump=True, verbose=True)

    @__duration
    def __strace(self, target_path: str = None) -> int:
        """Execute and trace an instrumented target script with strace"""
        target_path = self.target_path if target_path is None else target_path
        commands = [f'strace -f -o {self.strace_path} -qqq -ttt -z --decode-fds=path --trace=%file bash {target_path}']
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode

    @__duration
    def __ltrace(self, target_path: str = None) -> int:
        """Execute and trace an instrumented target script with ltrace"""
        target_path = self.target_path if target_path is None else target_path
        commands = [f"ltrace -A 9999 -b -C -e 'getenv' -f -o {self.ltrace_path} -s 9999 -ttt bash {target_path}"]
        commands = self.__python_env(commands)
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode

    @__duration
    def __working_directory(self, commands: list[str]) -> list[str]:
        """Add commands to return to the tool environment after tracing the target"""
        wrapper = []
        wrapper.append('PREVIOUS_WORKING_DIRECTORY=$PWD')
        wrapper.append(f'cd {self.working_dir}')
        wrapper.extend(commands)
        wrapper.append('cd $PREVIOUS_WORKING_DIRECTORY')
        return wrapper

    @__duration
    def __python_env(self, commands: list[str]) -> list[str]:
        """Add commands to get the environment variable accesses in python scripts"""
        wrapper = []
        wrapper.append(f'export PYENV_OUTPUT_PATH={self.pyenv_path}')
        wrapper.append(f'export PYENV_REPOSITORY_DIR={self.repository_dir}')
        wrapper.append(f'export PYTHONPATH={self.patch_dir}') # executes sitecustomize which instruments the target
        wrapper.extend(commands)
        return wrapper

    @__duration
    def __timestamp(self, target_path: str = None, dump: bool = False) -> str:
        """Timestamp unnested executable lines and blocks in target script"""
        # Load the target script
        target_path = self.target_path if target_path is None else target_path
        with open(target_path, 'r') as file:
            target = file.read().strip()

        # Delete any existing timestamp log
        if os.path.isfile(self.timestamps_path):
            os.remove(self.timestamps_path)

        # Insert timestamp monitoring code between shallow nodes (i.e. depth 1) in the target
        parser = Parser(Language(tree_sitter_bash.language()))
        shallow_nodes = parser.parse(target.encode()).root_node.children
        lines = ['STARTING_EPOCH_TIME=$(date +%s)', 'PREVIOUS_TIME=0']
        line_num = 0
        for node in shallow_nodes:
            if node.type == 'comment':
                continue
            if node.type == '&':
                lines[-1] = f'{lines[-1]} &' 
                continue
            text = node.text.decode()
            line_height = text.count('\n')+1
            lines.append(f'{text}')
            lines.append(f'printf "%d,%d,%d\\n" {line_num} {line_num + line_height} $(($(date +%s) - $STARTING_EPOCH_TIME - $PREVIOUS_TIME)) >> {self.timestamps_path}')
            lines.append('PREVIOUS_TIME=$(($(date +%s) - $STARTING_EPOCH_TIME))')
            line_num = line_num + line_height
        timestamp_target = '\n'.join(lines).strip()

        # Dump the target with timestamp monitoring code
        if dump:
            with open(self.timestamps_target_path, 'w') as file:
                file.write(timestamp_target)
        return timestamp_target

    @__duration
    def __pip_packages(self, dump: bool = False, verbose: bool = False):
        """Add commands to get the installed pip packages in the target environment"""
        process = subprocess.run('pip freeze  | sed s/=.*//', capture_output=True, text=True, shell=True)
        package_names = process.stdout.splitlines()
        packages = {}
        for package_name in tqdm(package_names, disable=not verbose, desc='SAWRA: Recording PIP Packages'):
            process = subprocess.run(f'pip show --no-input {package_name}', capture_output=True, text=True, shell=True)
            header = HeaderParser().parsestr(process.stdout)
            requires = {require for require in header['Requires'].split(', ') if require.strip() != ''} if 'Requires' in header else set()
            packages[package_name] = {
                'version': header['Version'],
                'requires': sorted(list(requires))}
        if dump:
            with open(self.pip_packages_path, 'w') as file:
                json.dump(packages, file, indent=2)
        return packages

    @__duration
    def __apt_packages(self, dump: bool = False, verbose: bool = False):
        """Add commands to get the installed apt packages in the target environment"""
        process = subprocess.run('dpkg --get-selections | grep -v deinstall', capture_output=True, text=True, shell=True)
        package_names = [line.split()[0] for line in process.stdout.splitlines()]
        packages = {}
        for package_name in tqdm(package_names, disable=not verbose, desc='SAWRA: Recording APT Packages'):
            process = subprocess.run(f'dpkg -L {package_name}', capture_output=True, text=True, shell=True)
            filenames = [filename for filename in process.stdout.splitlines() if os.path.isfile(filename)]
            packages[package_name] = filenames
        if dump:
            with open(self.apt_packages_path, 'w') as file:
                json.dump(packages, file, indent=2)