import json
import copy
import os
from pathlib import Path
import re

from deepdiff import DeepDiff, Delta
from deepdiff.serialization import json_dumps, json_loads
from itertools import combinations
import numpy as np
from pymoo.decomposition.asf import ASF
import recommend.utils as utils


class HeuristicRecommendations:
    def __init__(self,
                 workflow_path: str,
                 output_dir: str, 
                 repository_dir: str, 
                 env_filter_path: str = None):
        self.workflow_path = workflow_path
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        
        self.repository_dir = repository_dir
        self.repository_paths = self.__repository_paths()

        self.env_filter_path = env_filter_path
        self.env_filter = self.__env_filter() if self.env_filter_path is not None else []
        self.output_dir = output_dir

    def apply(self, id: int = None, dump: bool = False) -> dict:
        """Apply one or all recommendations to a workflow"""
        workflow = copy.deepcopy(self.workflow)
        heuristic_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.recommendations')
        if os.path.isfile(heuristic_path):
            delta = Delta(delta_path=heuristic_path, deserializer=json_loads)
            edit_actions = self.__parse_recommendations(delta)
            if id is not None:
                workflow += Delta(edit_actions[id], serializer=json_dumps, always_include_values=True)
            else:
                for action in edit_actions:
                    workflow += Delta(action, serializer=json_dumps, always_include_values=True)
            if dump:
                workflow_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.yaml')
                utils.dump_workflow(workflow, workflow_path)
        return workflow

    def recommendations(self, dump: bool = False) -> dict:
        """Get all recommendations for a workflow"""
        improved_workflow = copy.deepcopy(self.workflow)

        concurrency = self.__concurrency()
        for job_id in concurrency:
            if concurrency[job_id] is None:
                continue
            improved_workflow['jobs'][job_id]['concurrency'] = concurrency[job_id]

        env = self.__env()
        for job_id in env:
            if env[job_id] is None:
                continue
            improved_workflow['jobs'][job_id]['env'] = env[job_id]

        needs, needs_env = self.__needs()
        for job_id in needs:
            if needs[job_id] is not None:
                improved_workflow['jobs'][job_id]['needs'] = needs[job_id]
            if needs_env[job_id] is not None:
                improved_workflow['jobs'][job_id]['env'] = needs_env[job_id]

        outputs = self.__outputs()
        for job_id in outputs:
            if outputs[job_id] is None:
                continue
            improved_workflow['jobs'][job_id]['outputs'] = outputs[job_id]

        steps = self.__steps()
        for job_id in steps:
            if steps[job_id] is None:
                continue
            improved_workflow['jobs'][job_id]['steps'].pop() # Remove large step which is the last in the implementation
            improved_workflow['jobs'][job_id]['steps'].extend(steps[job_id])
            for i in range(len(improved_workflow['jobs'][job_id]['steps'])): # Render multiline strings in steps properly
                if 'run' not in improved_workflow['jobs'][job_id]['steps'][i]:
                    continue
                improved_workflow['jobs'][job_id]['steps'][i]['run'] = utils.to_multiline_str(
                    improved_workflow['jobs'][job_id]['steps'][i]['run'] \
                        .strip() \
                        .replace('\\n', '\n') \
                        .split('\n'))

        timeout_minutes = self.__timeout_minutes()
        for job_id in timeout_minutes:
            if timeout_minutes[job_id] is None:
                continue
            improved_workflow['jobs'][job_id]['timeout-minutes'] = timeout_minutes[job_id]

        working_directory = self.__working_directory()
        for job_id in working_directory:
            if working_directory[job_id] is None:
                continue
            if 'defaults' not in improved_workflow['jobs'][job_id]:
                improved_workflow['jobs'][job_id]['defaults'] = {'run': {'working-directory': None}}
            improved_workflow['jobs'][job_id]['defaults']['run']['working-directory'] = working_directory[job_id]

        diff = DeepDiff(self.workflow, improved_workflow)
        delta = Delta(diff, serializer=json_dumps, always_include_values=True)
        delta_dict = delta.to_dict()

        if dump:
            heuristic_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.recommendations')
            with open(heuristic_path, 'w') as file:
                delta.dump(file) if delta_dict else json.dump({})
        return json.loads(delta.dumps()) if delta_dict else self.workflow

    def __concurrency(self, threshold: int = 600) -> dict:
        """Get concurrency recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a strace log exists for the job
            log_path = os.path.join(self.output_dir, f'{job_id}.strace')
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

    def __env(self) -> dict:
        """Get environmental variables recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = None
            candidate_env = {}

            # Check whether a pyenv log exists for the job and identify env variables
            pyenv_log_path = os.path.join(self.output_dir, f'{job_id}.pyenv')
            if os.path.isfile(pyenv_log_path):
                with open(pyenv_log_path, 'r') as log:
                    for entry in log:
                        if not entry.strip():
                            continue
                        key, value = entry.split('=', 1)
                        candidate_env[key.strip()] = value.strip()

            # Check whether a ltrace log exists for the job and identify env variables
            ltrace_log_path = os.path.join(self.output_dir, f'{job_id}.ltrace')
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

    def __needs(self) -> tuple[dict, dict]:
        """Get needs recommendations"""
        needs = {}
        env = self.__env()
        outputs = self.__outputs()
        for current_id in self.workflow['jobs']:
            needs[current_id] = None
            for previous_id in self.workflow['jobs']:
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

    def __outputs(self) -> dict:
        """Get output recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = None
            candidate_outputs = {}

            # Check whether an ltrace log exists for the job and identify env variables
            ltrace_log_path = os.path.join(self.output_dir, f'{job_id}.ltrace')
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

    def __steps(self, weights: list[float, float] = [0.7, 0.3]) -> dict:
        """Get steps recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a timestamp log exists for the job
            timestamp_path = os.path.join(self.output_dir, f'{job_id}.timestamps')
            if not os.path.isfile(timestamp_path):
                continue
            
            # Get the timestamps from the timestamp log
            timestamps = []
            with open(timestamp_path, 'r') as log:
                for entry in log:
                    if entry.strip() == '':
                        continue
                    timestamp = [int(value) for value in entry.split(',')]
                    timestamps.append(timestamp)
            
            # Seperate timestamps into all possible uneven groups
            timestamp_groups = list(self.__uneven_chunks(timestamps))

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
            run = self.workflow['jobs'][job_id]['steps'][-1]['run'].splitlines()
            recommendations[job_id] = []
            for start, end, _ in decision:
                step = utils.to_multiline_str(run[start-1:end])
                #step = '\n'.join(run[start-1:end])
                recommendations[job_id].append({'run': step})
        return recommendations

    def __timeout_minutes(self, multiplier: int = 1.2) -> dict:
        """Get timeout-minutes recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = None

            # Check whether a strace log exists for the job
            log_path = os.path.join(self.output_dir, f'{job_id}.strace')
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

    def __working_directory(self) -> dict:
        """Get working-directory recommendations"""
        recommendations = {}
        repository_paths = self.repository_paths
        for job_id in self.workflow['jobs']:
            # Split steps in job into distinct tokens
            tokens = set()
            for step in self.workflow['jobs'][job_id]['steps']:
                if 'run' not in step:
                    continue
                step_tokens = step['run'].split()
                tokens.update(step_tokens)

            # Identify tokens that are paths
            paths = set()
            for token in tokens:
                is_root_path = os.path.join(self.repository_dir, token) in repository_paths
                is_relative_path = len(re.findall('\.{1}\/|\.{2}\/', token)) > 0
                is_absolute_path = token.strip().startswith('/')
                if is_root_path or is_relative_path or is_absolute_path:
                    # Normalize representations of paths
                    normalized_path = token.replace(f'{self.repository_dir}/', '')
                    normalized_path = os.path.abspath(os.path.join(self.repository_dir, normalized_path))
                    paths.add(normalized_path)
            
            # Identify common (parent) directory of paths (i.e. working directory)
            candidate_paths = [path.replace(f'{self.repository_dir}/', '') for path in paths if path in repository_paths]
            recommendations[job_id] = None
            if candidate_paths:
                working_directory = os.path.commonpath(candidate_paths)
                recommendations[job_id] = f'./{working_directory}' if len(working_directory) > 0 else None
        return recommendations

    def __repository_paths(self) -> list[str]:
        """Get the paths of all files and directories in a repository"""
        paths = {self.repository_dir}
        for dirpath, dirnames, filenames in os.walk(self.repository_dir):
            paths.update([os.path.join(dirpath, name) for name in dirnames + filenames])
        return sorted(list(paths))
    
    def __env_filter(self) -> list[str]:
        """Get the environmental variable filter"""
        filter = []
        with open(self.env_filter_path, 'r') as log:
            for entry in log:
                if entry.strip().startswith('#'):
                    continue
                filter.append(entry.strip())
        return filter

    def __uneven_chunks(self, group, min_chunk_size=1):
        """Find all ways to split a group into uneven chunks."""
        if len(group) < 2:
            yield [group]
            return

        for i in range(min_chunk_size, len(group)):
            for combo in combinations(range(1, len(group)), i):
                split_points = [0] + list(combo) + [len(group)]
                yield [group[split_points[j]:split_points[j+1]] for j in range(len(split_points)-1)]

    def __parse_recommendations(self, delta: Delta) -> list:
        """Parse individual requirements from Delta"""
        edit_actions = []
        for group, actions in delta.to_dict().items():
            for name, action in actions.items():
                edit_actions.append({group: {name: action}})
        return edit_actions
