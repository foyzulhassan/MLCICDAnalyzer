import os
from pathlib import Path
import subprocess

from tree_sitter import Language, Parser
import tree_sitter_bash


class TraceTarget:
    def __init__(self, 
                 target_path: str, 
                 output_dir: str,
                 repository_dir: str,
                 working_dir: str,
                 packages_path: str,
                 patch_dir: str,
                 new_trace: bool):
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

    def trace(self):
        """Instrument and trace a target script with strace and ltrace"""
        if self.new_trace or not os.path.isfile(self.timestamps_path):
            self.__timestamp(dump=True)
        if self.new_trace or not os.path.isfile(self.strace_path):
            self.__strace(self.timestamps_target_path)
        if self.new_trace or not os.path.isfile(self.ltrace_path):
            self.__ltrace(self.target_path)
        if self.new_trace or not os.path.isfile(self.apt_packages_path):
            self.__apt_packages()

    def __strace(self, target_path: str = None) -> int:
        """Execute and trace an instrumented target script with strace"""
        target_path = self.target_path if target_path is None else target_path
        commands = [f'strace -f -o {self.strace_path} -qqq -ttt -z --decode-fds=path --trace=open,stat bash {target_path}']
        commands = self.__pip_packages(commands) # ran here to capture virtual environments
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode

    def __ltrace(self, target_path: str = None) -> int:
        """Execute and trace an instrumented target script with ltrace"""
        target_path = self.target_path if target_path is None else target_path
        commands = [f"ltrace -A 9999 -b -C -e 'getenv' -f -o {self.ltrace_path} -s 9999 -ttt bash {target_path}"]
        commands = self.__python_env(commands)
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode
    
    def __pip_packages(self, commands: list[str]) -> list[str]:
        """Add commands to get the installed pip packages in the target environment"""
        wrapper = []
        wrapper.extend(commands)
        wrapper.append(f'python3 {self.packages_path} pip {self.pip_packages_path}')
        return wrapper

    def __working_directory(self, commands: list[str]) -> list[str]:
        """Add commands to return to the tool environment after tracing the target"""
        wrapper = []
        wrapper.append('PREVIOUS_WORKING_DIRECTORY=$PWD')
        wrapper.append(f'cd {self.working_dir}')
        wrapper.extend(commands)
        wrapper.append('cd $PREVIOUS_WORKING_DIRECTORY')
        return wrapper

    def __python_env(self, commands: list[str]) -> list[str]:
        """Add commands to get the environment variable accesses in python scripts"""
        wrapper = []
        wrapper.append(f'export PYENV_OUTPUT_PATH={self.pyenv_path}')
        wrapper.append(f'export PYENV_REPOSITORY_DIR={self.repository_dir}')
        wrapper.append(f'export PYTHONPATH={self.patch_dir}') # executes sitecustomize which instruments the target
        wrapper.extend(commands)
        return wrapper

    def __apt_packages(self) -> int:
        """Add commands to get the installed apt packages in the target environment"""
        result = subprocess.run(f'python3 {self.packages_path} apt {self.apt_packages_path}', shell=True)
        return result.returncode

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
