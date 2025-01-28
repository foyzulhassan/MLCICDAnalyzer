import os
from pathlib import Path
import subprocess

import tree_sitter_bash as tsbash
from tree_sitter import Language, Parser


class TraceTarget:
    def __init__(self, 
                 target_path: str, 
                 output_dir: str,
                 working_dir: str,
                 repository_dir: str,
                 requirements_path: str = None,
                 patch_dir: str = None,
                 new_trace: bool = False):
        self.target_path = target_path
        self.target_name = Path(self.target_path).stem.split('.')[0]
        self.output_dir = output_dir
        self.working_dir = working_dir
        self.repository_dir = repository_dir
        self.requirements_path = requirements_path
        self.patch_dir = patch_dir
        self.new_trace = new_trace
        os.makedirs(self.output_dir, exist_ok=True)

    def trace(self):
        """Trace a (instrumented) target script with strace and ltrace"""
        timestamped_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps.sh')
        timestamps_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        strace_path = os.path.join(self.output_dir, f'{self.target_name}.strace')
        ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        if self.new_trace or not os.path.isfile(timestamps_path):
            self.__timestamp(dump=True)
        if self.new_trace or not os.path.isfile(strace_path):
            self.strace(timestamped_path) # get timestamps while tracing
        if self.new_trace or not os.path.isfile(ltrace_path):
            self.ltrace(self.target_path)

    def strace(self, target_path: str = None) -> int:
        """Execute and trace a (instrumented) target script with strace"""
        if target_path is None:
            target_path = self.target_path
        strace_path = os.path.join(self.output_dir, f'{self.target_name}.strace')
        commands = [f'strace --follow-forks --decode-fds=path --trace=%file,%network --quiet=all --successful-only --absolute-timestamps=format:unix,precision:us --output={strace_path} bash {target_path}']
        commands = self.__requirements(commands) # done here to capture virtual environment (if used)
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode

    def ltrace(self, target_path: str = None) -> int:
        """Execute and trace a (instrumented) target script with ltrace"""
        if target_path is None:
            target_path = self.target_path
        commands = []
        ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        commands.append(f'ltrace -fbTC -tt -e *env -o {ltrace_path} bash {target_path}')
        if self.patch_dir is not None:
            commands = self.__python_env(commands)
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode
    
    def __requirements(self, commands: list[str]) -> list[str]:
        wrapper = []
        requirements_path = os.path.join(self.output_dir, f'{self.target_name}.requirements')
        wrapper.extend(commands)
        diff_requirements = f' --diff {self.requirements_path}' if self.requirements_path is not None else ''
        wrapper.append(f'touch {requirements_path}')
        wrapper.append(f'pipreqs --use-local --scan-notebooks{diff_requirements} --savepath {requirements_path} {self.repository_dir}')
        return wrapper

    def __working_directory(self, commands: list[str]) -> list[str]:
        wrapper = []
        wrapper.append('PREVIOUS_WORKING_DIRECTORY=$PWD')
        wrapper.append(f'cd {self.working_dir}')
        wrapper.extend(commands)
        wrapper.append('cd $PREVIOUS_WORKING_DIRECTORY')
        return wrapper

    def __python_env(self, commands: list[str]) -> list[str]:
        wrapper = []
        pyenv_path = os.path.join(self.output_dir, f'{self.target_name}.pyenv')
        wrapper.append(f'export ENV_TRACE={pyenv_path}')
        wrapper.append(f'export PYTHONPATH={self.patch_dir}')
        wrapper.extend(commands)
        return wrapper

    def __timestamp(self, target_path: str = None, dump: bool = False) -> str:
        """Timestamp unnested executable lines and blocks in target script"""
        # Load the target script
        target_path = self.target_path if target_path is None else target_path
        timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        with open(target_path, 'r') as target_file:
            target = target_file.read().strip()

        # Insert timestamps into target script
        BASH_LANGUAGE = Language(tsbash.language())
        parser = Parser(BASH_LANGUAGE)
        tree = parser.parse(target.encode())
        lines = ['STARTING_EPOCH_TIME=$(date +%s)', 'PREVIOUS_TIME=0']
        line_num = 0
        for child in tree.root_node.children:
            if child.type == 'comment':
                continue
            line_height = child.text.decode().count('\n')+1
            lines.append(f'{child.text.decode()}')
            lines.append(f'printf "%d,%d,%d\\n" {line_num} {line_num + line_height} $(($(date +%s) - $STARTING_EPOCH_TIME - $PREVIOUS_TIME)) >> {timestamp_path}')
            lines.append('PREVIOUS_TIME=$(($(date +%s) - $STARTING_EPOCH_TIME))')
            line_num = line_num + line_height
        timestamp_target = '\n'.join(lines).strip()

        # Dump timestamped target script
        if dump:
            timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps.sh')
            with open(timestamp_path, 'w') as file:
                file.write(timestamp_target)
        return timestamp_target
