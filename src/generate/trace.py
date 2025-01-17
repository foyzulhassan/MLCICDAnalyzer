import os
from pathlib import Path
import subprocess


class TraceTarget:
    def __init__(self, 
                 target_path: str, 
                 output_dir: str,
                 working_dir: str,
                 packages_path: str,
                 patch_dir: str = None,
                 new_trace: bool = False):
        self.target_path = target_path
        self.target_name = Path(self.target_path).stem
        self.output_dir = output_dir
        self.working_dir = working_dir
        self.packages_path = packages_path
        self.patch_dir = patch_dir
        self.new_trace = new_trace
        os.makedirs(self.output_dir, exist_ok=True)

    def trace(self):
        """Trace a (instrumented) target script with strace and ltrace"""
        timestamped_path = os.path.join(self.output_dir, f'{self.target_name}.timestamped.sh')
        strace_path = os.path.join(self.output_dir, f'{self.target_name}.strace')
        ltrace_path = os.path.join(self.output_dir, f'{self.target_name}.ltrace')
        if self.new_trace or not os.path.isfile(timestamped_path):
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
        commands = self.__packages(commands) # done here to capture virtual environment (if used)
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
        commands.append(f'ltrace -fbTC -e *env -o {ltrace_path} bash {target_path}')
        if self.patch_dir is not None:
            commands = self.__python_env(commands)
        commands = self.__working_directory(commands)
        commands_str = '; '.join(commands)
        result = subprocess.run(commands_str, shell=True)
        return result.returncode
    
    def __packages(self, commands: list[str]) -> list[str]:
        wrapper = []
        packages_path = os.path.join(self.output_dir, 'packages.pip')
        wrapper.extend(commands)
        wrapper.append(f'python3 {self.packages_path} {packages_path}')
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

    def __timestamp(self, target_path: str = None, dump: bool = False) -> list[str]:
        """Timestamp unnested executable lines and blocks in target script"""
        if target_path is None:
            target_path = self.target_path
        timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamps')
        if os.path.isfile(timestamp_path): # Removed to enable appending
            os.remove(timestamp_path)

        lines = ['STARTING_EPOCH_TIME=$(date +%s)\n', 'PREVIOUS_TIME=0\n'] # Get initial time first to find the incremental time later
        block_depth = 0
        starting_line_number = 0
        current_line_number = 0
        with open(target_path, 'r') as target:
            for line in target:
                # Record the line
                lines.append(line if line.endswith('\n') else line + '\n')
                current_line_number += 1

                # Skip the line if it is a single-line comment or empty
                if line.strip().startswith('#') or line.strip() == '':
                    continue
                
                # Identify if the line is the header of a block
                if line.strip().startswith(('if', 'for', 'while', 'case', ': \'')) or line.strip().endswith('{'):
                    if block_depth == 0: # Indicate the start of a new block
                        starting_line_number = current_line_number
                    block_depth += 1
                    continue

                # Check if line is the end of a block and timestamp it if it is
                if line.strip().startswith(('fi', 'done', '}', 'esac', '\'')) or line.strip().endswith(('; fi', '; done', '; }', '; esac')):
                    if block_depth == 0: # End of block is indicated at root
                        raise Exception('block_depth < 0')
                    block_depth -= 1
                    if line.strip().startswith('\''): # Skip timestamping the block if it is the end of a multi-line comment
                        continue

                # Timeline line that is not the start nor end of a block or a comment
                if block_depth == 0:
                    starting_line_number = current_line_number
                lines.append(f'printf "%d,%d,%d\\n" {starting_line_number} {current_line_number} $(($(date +%s) - $STARTING_EPOCH_TIME - $PREVIOUS_TIME)) >> {timestamp_path}\n')
                lines.append('PREVIOUS_TIME=$(($(date +%s) - $STARTING_EPOCH_TIME))\n')

        # Dump timestamped target script to a file
        if dump:
            timestamp_path = os.path.join(self.output_dir, f'{self.target_name}.timestamped.sh')
            with open(timestamp_path, 'w') as script:
                script.writelines(lines)
        return lines
