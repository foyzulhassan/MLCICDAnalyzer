import copy
import os
from pathlib import Path
import re
import subprocess

from itertools import combinations
import numpy as np
from pymoo.decomposition.asf import ASF


class Recommendations:
    def __init__(self, log_dir: str, patch_path: str, root_dir: str, env_filter_path: str = None):
        self.log_dir = log_dir
        self.patch_path = patch_path
        self.root_dir = root_dir
        self.env_filter = self.get_env_filter(env_filter_path) if env_filter_path is not None else []

    def strace(self, target_path: str):
        """Execute and trace a target script with strace"""
        output_path = os.path.join(self.log_dir, f'{Path(target_path).stem}.strace')
        command = f'strace --follow-forks --decode-fds=path --trace=%file,%network --quiet=all --successful-only --absolute-timestamps=format:unix,precision:us --output={output_path} bash {target_path}'
        subprocess.run(command, shell=True)

    def ltrace(self, target_path: str, pyenv: bool = False):
        """Execute and trace a target script with ltrace (and pyenv if desired)"""
        commands = []
        if pyenv:
            pyenv_output_path = os.path.join(self.log_dir, f'{Path(target_path).stem}.pyenv')
            commands.append(f'export ENV_TRACE={pyenv_output_path}')
            commands.append(f'export PYTHONPATH={self.patch_path}')
        ltrace_output_path = os.path.join(self.log_dir, f'{Path(target_path).stem}.ltrace')
        commands.append(f'ltrace -fbTC -e *env -o {ltrace_output_path} bash {target_path}')
        commands_str = '; '.join(commands)
        subprocess.run(commands_str, shell=True)

    def timestamp_lines(self, target_path: str, strace: bool = False) -> list[str]:
        """Timestamp each line of a target script and execute it"""
        timestamp_path = os.path.join(self.log_dir, f'{Path(target_path).stem}.timestamps')
        if os.path.isfile(timestamp_path):
            os.remove(timestamp_path)
        lines = ['STARTING_EPOCH_TIME=$(date +%s)\n', 'PREVIOUS_TIME=0\n']
        depth = 0
        block = ''
        starting_line_number = 0
        line_number = 0
        with open(target_path, 'r') as target:
            for line in target:
                # Record the current line that is read
                lines.append(line)
                line_number += 1

                # Check if line is empty or a comment and do not timestamp it if it is
                if line.strip().startswith('#') or line.strip() == '':
                    continue
                
                # Check if line is the start of a block and do not timestamp it if it is
                if line.strip().startswith(('if', 'for', 'while', 'case', ': \'')) or line.strip().endswith('{'):
                    if depth == 0:
                        starting_line_number = line_number
                    depth += 1
                    block += line
                    continue

                # Check if line is the end of a block and timestamp it if it is
                if line.strip().startswith(('fi', 'done', '}', 'esac', '\'')) or line.strip().endswith(('; fi', '; done', '; }', '; esac')):
                    depth -= 1
                    if depth < 0:
                        raise Exception('depth < 0')
                    if not line.strip().startswith('\''):
                        lines.append(f'printf "%d,%d,%d\\n" {starting_line_number} {line_number} $(($(date +%s) - $STARTING_EPOCH_TIME - $PREVIOUS_TIME)) >> {timestamp_path}\n')
                        lines.append('PREVIOUS_TIME=$(($(date +%s) - $STARTING_EPOCH_TIME))\n')
                    block = ''
                    continue

                # Timeline line that is not the start nor end of a block or a comment
                if depth == 0:
                    starting_line_number = line_number
                    lines.append(f'printf "%d,%d,%d\\n" {starting_line_number} {line_number} $(($(date +%s) - $STARTING_EPOCH_TIME - $PREVIOUS_TIME)) >> {timestamp_path}\n')
                    lines.append('PREVIOUS_TIME=$(($(date +%s) - $STARTING_EPOCH_TIME))\n')
                else:
                    block += line
        
        timestamp_script_path = os.path.join(self.log_dir, f'{Path(target_path).stem}.timestamp-script')
        with open(timestamp_script_path, 'w') as script:
            script.writelines(lines)
        if strace:
            self.strace(timestamp_script_path)
        else:
            subprocess.run(f'bash {timestamp_script_path}', shell=True)
        os.remove(timestamp_script_path)
    
    def get_repository_paths(self, root_dir: str) -> list[str]:
        """Get the absolute paths of all files and directories in a repository"""
        paths = {root_dir}
        for dirpath, dirnames, filenames in os.walk(root_dir):
            paths.update([os.path.join(dirpath, name) for name in dirnames + filenames])
        return sorted(list(paths))
    
    def get_env_filter(self, env_filter_path: str) -> list[str]:
        filter = []
        with open(env_filter_path, 'r') as log:
            for entry in log:
                if entry.strip().startswith('#'):
                    continue
                filter.append(entry.strip())
        return filter

    def uneven_chunks(self, group, min_chunk_size=1):
        """Find all ways to split a group into uneven chunks."""
        if len(group) < 2:
            yield [group]
            return

        for i in range(min_chunk_size, len(group)):
            for combo in combinations(range(1, len(group)), i):
                split_points = [0] + list(combo) + [len(group)]
                yield [group[split_points[j]:split_points[j+1]] for j in range(len(split_points)-1)]


class HeuristicRecommendations(Recommendations):
    def get_recommendations(self, workflow: dict) -> dict:
        """Get all recommendations for a workflow"""
        recommendations = {'jobs': {job_id: {} for job_id in workflow['jobs']}}

        concurrency = self.concurrency(workflow)
        for job_id in concurrency:
            if concurrency[job_id] is None:
                continue
            recommendations['jobs'][job_id]['concurrency'] = concurrency[job_id]

        env = self.env(workflow)
        for job_id in env:
            if env[job_id] is None:
                continue
            recommendations['jobs'][job_id]['env'] = env[job_id]

        needs, needs_env = self.needs(workflow)
        for job_id in needs:
            if needs[job_id] is not None:
                recommendations['jobs'][job_id]['needs'] = needs[job_id]
            if needs_env[job_id] is not None:
                recommendations['jobs'][job_id]['env'] = needs_env[job_id]

        outputs = self.outputs(workflow)
        for job_id in outputs:
            if outputs[job_id] is None:
                continue
            recommendations['jobs'][job_id]['outputs'] = outputs[job_id]

        steps = self.steps(workflow)
        for job_id in steps:
            if steps[job_id] is None:
                continue
            recommendations['jobs'][job_id]['steps'] = copy.deepcopy(workflow['jobs'][job_id]['steps'])
            recommendations['jobs'][job_id]['steps'].pop() # Remove large step which is the last in the implementation
            recommendations['jobs'][job_id]['steps'].extend(steps[job_id])

        timeout_minutes = self.timeout_minutes(workflow)
        for job_id in timeout_minutes:
            if timeout_minutes[job_id] is None:
                continue
            recommendations['jobs'][job_id]['timeout-minutes'] = timeout_minutes[job_id]

        working_directory = self.working_directory(workflow)
        for job_id in working_directory:
            if working_directory[job_id] is None:
                continue
            recommendations['jobs'][job_id]['defaults']['run']['working-directory'] = working_directory[job_id]

        return recommendations

    def concurrency(self, workflow: dict, threshold: int = 600):
        recommendations = {}
        for job_id in workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a strace log exists for the job
            log_path = os.path.join(self.log_dir, f'{job_id}.strace')
            if not os.path.isfile(log_path):
                continue
            
            # Identify ip addresses and timestamps in strace log
            addresses = []
            timestamps = []
            with open(log_path, 'r') as log:
                for entry in log:
                    address = re.findall('(?<=inet_addr\\(\").+?(?=\"\\))', entry)
                    addresses.extend(address)
                    timestamp = float(entry.split(maxsplit=2)[1])
                    timestamps.append(timestamp)

            # Recommend concurrency if an ip address is present or duration is past a threshold
            duration = max(timestamps) - min(timestamps)
            if addresses or duration >= threshold:
                recommendations[job_id] = {
                    'group': '${{ github.workflow }}-${{ github.ref }}',
                    'cancel-in-progress': True
                }
        return recommendations

    def env(self, workflow: dict) -> dict:
        recommendations = {}
        for job_id in workflow['jobs']:
            recommendations[job_id] = None
            candidate_env = {}

            # Check whether a pyenv log exists for the job and identify env variables
            pyenv_log_path = os.path.join(self.log_dir, f'{job_id}.pyenv')
            if os.path.isfile(pyenv_log_path):
                with open(pyenv_log_path, 'r') as log:
                    for entry in log:
                        if not entry.strip():
                            continue
                        key, value = entry.split('=')
                        candidate_env[key.strip()] = value.strip()

            # Check whether a ltrace log exists for the job and identify env variables
            ltrace_log_path = os.path.join(self.log_dir, f'{job_id}.ltrace')
            if os.path.isfile(ltrace_log_path):
                with open(ltrace_log_path, 'r') as log:
                    for entry in log:
                        key = re.findall(r'(?<=getenv\(").+?(?=")', entry)
                        value = re.findall(r'(?<==\s").+?(?=")', entry)
                        if key and value:
                            # Cannot use ltrace values directly due to abbreviation
                            candidate_env[key[0].strip()] = os.getenv(key[0].strip())
            
            # Recommend uncommon env variables
            if candidate_env:
                recommendations[job_id] = {key: value for key, value in candidate_env.items() if key not in self.env_filter}
        return recommendations

    def needs(self, workflow: dict) -> tuple[dict, dict]:
        needs = {}
        env = self.env(workflow)
        outputs = self.outputs(workflow)
        for current_id in workflow['jobs']:
            needs[current_id] = None
            for previous_id in workflow['jobs']:
                # Check if there are more previous job ids
                if current_id == previous_id:
                    break

                # Check if env has been recommended
                if env[current_id] is None:
                    continue
                
                # Check if each key in current id env is output in a prior job
                for key in env[current_id]:
                    if outputs[previous_id] is None or key not in outputs[previous_id]:
                        continue
                    needs[current_id] = previous_id # Gets the most recent job that provides the same output
                    env[current_id][key] = f'${{needs.{previous_id}.outputs.{key}}}'
        return needs, env

    def outputs(self, workflow: dict) -> dict:
        recommendations = {}
        for job_id in workflow['jobs']:
            recommendations[job_id] = None
            candidate_outputs = {}

            # Check whether an ltrace log exists for the job and identify env variables
            ltrace_log_path = os.path.join(self.log_dir, f'{job_id}.ltrace')
            if os.path.isfile(ltrace_log_path):
                with open(ltrace_log_path, 'r') as log:
                    for entry in log:
                        key = re.findall(r'(?<=setenv\(").+?(?=")', entry)
                        #(?<=,\s").+?(?="(\.\.\.)?,)
                        value = re.findall(r'(?<=,\s").+(?=")', entry)
                        if key and value:
                            # TODO: Fix potential issues with key and value abbreviation
                            candidate_outputs[key[0].strip()] = value[0].strip()
            
            # Recommend uncommon env variables
            if candidate_outputs:
                recommendations[job_id] = {key: value for key, value in candidate_outputs.items() if key not in self.env_filter}
        return recommendations

    def steps(self, workflow: dict, weights: list[float, float] = [0.7, 0.3]) -> dict:
        recommendations = {}
        for job_id in workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a timestamp log exists for the job
            log_path = os.path.join(self.log_dir, f'{job_id}.timestamps')
            if not os.path.isfile(log_path):
                continue
            
            # Get the timestamps from the timestamp log
            timestamps = []
            with open(log_path, 'r') as log:
                for entry in log:
                    if entry.strip() == '':
                        continue
                    timestamp = [int(value) for value in entry.split(',')]
                    timestamps.append(timestamp)
            
            # Seperate timestamps into all possible uneven groups
            timestamp_groups = list(self.uneven_chunks(timestamps))

            # Find the total start, end, and duration of each group
            total_timestamp_groups = []
            for combos in timestamp_groups:
                total_combos = []
                for group in combos:
                    transposed = list(map(list, zip(*group)))
                    total_combos.append([min(transposed[0]), max(transposed[1]), sum(transposed[2])])
                total_timestamp_groups.append(total_combos)
            
            # Find optimization content
            optimization_groups = []
            for combos in total_timestamp_groups:
                duration_difference = 0
                for i in range(len(combos)-1):
                    duration_difference += abs(combos[i][2] - combos[i+1][2])
                optimization_groups.append([len(combos), duration_difference])

            # Use multi-criteria decision making to find group that minimizes the spread of durations across groups but maximizes the number of groups
            # https://pymoo.org/getting_started/part_3.html#Pseudo-Weights
            population = np.array([[1/row[0] if row[0] != 0 else 0, row[1]] for row in optimization_groups])
            approx_ideal = population.min(axis=0)
            approx_nadir = population.max(axis=0)
            nF = (population - approx_ideal) / (approx_nadir - approx_ideal)
            np_weights = np.array(weights)
            decomp = ASF()
            i = decomp.do(nF, 1/np_weights).argmin()
            decision = population[i].tolist()
            decision[0] = 1/decision[0]
            decision = [int(x) for x in decision]
            decision = total_timestamp_groups[optimization_groups.index(decision)]

            # Recommend steps
            run = workflow['jobs'][job_id]['steps'][-1]['run'].splitlines()
            recommendations[job_id] = []
            for start, end, _ in decision:
                step = '\n'.join(run[start-1:end])
                recommendations[job_id].append({'run': step})
        return recommendations

    def timeout_minutes(self, workflow: dict, multiplier: int = 1.2) -> dict:
        recommendations = {}
        for job_id in workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a strace log exists for the job
            log_path = os.path.join(self.log_dir, f'{job_id}.strace')
            if not os.path.isfile(log_path):
                continue
            
            # Identify timestamps in a strace log
            timestamps = []
            with open(log_path, 'r') as log:
                for entry in log:
                    timestamp = float(entry.split(maxsplit=2)[1])
                    timestamps.append(timestamp)

            # Recommend timeout that is MULTIPLIER times the duration
            duration = max(timestamps) - min(timestamps)
            recommendations[job_id] = round(duration * multiplier)
        return recommendations

    def working_directory(self, workflow: dict) -> dict:
        recommendations = {}
        repository_paths = self.get_repository_paths(self.root_dir)
        for job_id in workflow['jobs']:
            # Split steps in job into distinct tokens
            tokens = set()
            for step in workflow['jobs'][job_id]['steps']:
                if 'run' not in step:
                    continue
                step_tokens = step['run'].split()
                tokens.update(step_tokens)

            # Identify tokens that are paths
            paths = set()
            for token in tokens:
                is_root_path = os.path.join(self.root_dir, token) in repository_paths
                is_relative_path = len(re.findall('\.{1}\/|\.{2}\/', token)) > 0
                is_absolute_path = token.strip().startswith('/')
                if is_root_path or is_relative_path or is_absolute_path:
                    # Normalize representations of paths
                    normalized_path = token.replace(f'{self.root_dir}/', '')
                    normalized_path = os.path.abspath(os.path.join(self.root_dir, normalized_path))
                    paths.add(normalized_path)
            
            # Identify common (parent) directory of paths (i.e. working directory)
            candidate_paths = [path.replace(f'{self.root_dir}/', '') for path in paths if path in repository_paths]
            working_directory = os.path.commonpath(candidate_paths).strip()
            recommendations[job_id] = f'./{working_directory}' if len(working_directory) > 0 else None
        return recommendations
