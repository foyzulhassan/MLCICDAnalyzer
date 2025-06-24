import copy
import json
import logging
import os
from pathlib import Path
import re
import time

import numpy as np
from pymoo.decomposition.asf import ASF

import recommend.utils as utils


class HeuristicRecommendations:
    def __init__(self,
                 workflow_path: str,
                 output_dir: str, 
                 duration_log_path: str, 
                 repository_dir: str,
                 job_parses: dict,
                 step_mcdm_weights: list[float, float],
                 step_chunk_count: int,
                 recommendation_threshold: dict[str, float],
                 recommendation_multiplier: dict[str, float],
    ) -> None:
        self.duration_log_path = duration_log_path
        self.duration_logger = logging.getLogger(f'{__name__}.duration')
        self.duration_logger.setLevel(logging.INFO)
        self.duration_handler = logging.FileHandler(self.duration_log_path)
        self.duration_handler.setFormatter(logging.Formatter('%(message)s'))
        self.duration_logger.addHandler(self.duration_handler)

        self.workflow_path = workflow_path
        self.workflow = utils.load_workflow(self.workflow_path)
        self.workflow_name = Path(self.workflow_path).stem.split('.')[0]
        self.job_parses = job_parses
        self.output_dir = output_dir
        self.repository_dir = repository_dir
        self.step_mcdm_weights = step_mcdm_weights
        self.step_chunk_count = step_chunk_count
        self.recommendation_threshold = recommendation_threshold
        self.recommendation_multiplier = recommendation_multiplier

        self.timestamps = self.__timestamps()
        self.recommendations_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.recommendations')
        self.heuristic_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.yaml')

    def __duration(func):
        def wrapper(self, *args, **kwargs):
            # Calculate the duration
            start_time = time.time()
            result = func(self, *args, **kwargs) 
            end_time = time.time()
            duration = end_time - start_time

            # Log the duration
            source = 'heuristic'
            function = str(func.__name__)
            self.duration_logger.info(f'"{source}","{function}","{duration}"')
            return result
        return wrapper

    def __timestamps(self) -> dict:
        """Identify timestamps in strace logs for each job"""

        def is_numeric(value) -> float | None:
            """Check whether a value is a number"""
            try:
                return float(value)
            except ValueError:
                return None

        timestamps = {}
        for job_id in self.workflow['jobs']:
            timestamps[job_id] = []
            log_path = os.path.join(self.output_dir, f'{job_id}.strace')
            with open(log_path, 'r') as log:
                for entry in log:
                    value = entry.split(maxsplit=2)[1]
                    value = is_numeric(value)
                    if value is not None:
                        timestamps[job_id].append(value)

        return timestamps

    @__duration
    def apply(self, dump: bool = False) -> dict:
        """Apply one or all recommendations to a workflow"""
        workflow = copy.deepcopy(self.workflow)
        if os.path.isfile(self.recommendations_path):
            with open(self.recommendations_path, 'r') as file:
                recommendations = json.load(file)
            for job_id in workflow['jobs']:
                if recommendations[job_id]['concurrency']:
                    workflow['jobs'][job_id]['concurrency'] = recommendations[job_id]['concurrency']

                if recommendations[job_id]['env']:
                    workflow['jobs'][job_id]['env'] = recommendations[job_id]['env']

                if recommendations[job_id]['fail-fast']:
                    if 'strategy' not in workflow['jobs'][job_id]:
                        workflow['jobs'][job_id]['strategy'] = {}
                    workflow['jobs'][job_id]['strategy']['fail-fast'] = recommendations[job_id]['fail-fast']

                # if recommendations[job_id]['needs']:
                #     workflow['jobs'][job_id]['needs'] = recommendations[job_id]['needs']

                # if recommendations[job_id]['outputs']:
                #     workflow['jobs'][job_id]['outputs'] = recommendations[job_id]['outputs']

                if recommendations[job_id]['steps']:
                    workflow['jobs'][job_id]['steps'].pop() # Remove large step which is the last in the implementation
                    workflow['jobs'][job_id]['steps'].extend(recommendations[job_id]['steps'])
                    for i, step in enumerate(workflow['jobs'][job_id]['steps']): # Render multiline strings in steps properly
                        if 'run' not in step:
                            continue
                        multiline_run = utils.to_multiline_str(step['run'].strip().replace('\\n', '\n').split('\n'))
                        workflow['jobs'][job_id]['steps'][i]['run'] = multiline_run

                if recommendations[job_id]['timeout-minutes']:
                    workflow['jobs'][job_id]['timeout-minutes'] = recommendations[job_id]['timeout-minutes']

                if recommendations[job_id]['working-directory']:
                    workflow['jobs'][job_id]['defaults'] = {'run': recommendations[job_id]['working-directory']}
        if dump:
            utils.dump_workflow(workflow, self.heuristic_path)
        return workflow

    @__duration
    def recommendations(self, dump: bool = False) -> dict:
        """Get all recommendations for a workflow"""
        recommendations = {job_id: {} for job_id in self.job_parses}

        concurrency = self.__concurrency()
        for job_id in concurrency:
            recommendations[job_id]['concurrency'] = concurrency[job_id]

        env = self.__env()
        for job_id in env:
            recommendations[job_id]['env'] = env[job_id]

        fail_fast = self.__fail_fast()
        for job_id in fail_fast:
            recommendations[job_id]['fail-fast'] = fail_fast[job_id]

        # needs, needs_env = self.__needs()
        # for job_id in needs:
        #     recommendations[job_id]['needs'] = needs[job_id]
        #     if recommendations[job_id]['env'] is not None:
        #         recommendations[job_id]['env'].update(needs_env[job_id]) if needs_env[job_id] else None
        #     else:
        #         recommendations[job_id]['env'] = needs_env[job_id]

        # outputs = self.__outputs()
        # for job_id in outputs:
        #     recommendations[job_id]['outputs'] = outputs[job_id]

        steps = self.__steps()
        for job_id in steps:
            recommendations[job_id]['steps'] = steps[job_id]

        timeout_minutes = self.__timeout_minutes()
        for job_id in timeout_minutes:
            recommendations[job_id]['timeout-minutes'] = timeout_minutes[job_id]

        working_directory = self.__working_directory()
        for job_id in working_directory:
            recommendations[job_id]['working-directory'] = working_directory[job_id]

        if dump:
            heuristic_path = os.path.join(self.output_dir, f'{self.workflow_name}.heuristic.recommendations')
            with open(heuristic_path, 'w') as file:
                json.dump(recommendations, file, indent=2)
        return recommendations

    @__duration
    def __concurrency(self) -> dict:
        """Get concurrency recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            timestamps = self.timestamps[job_id]
            duration = max(timestamps) - min(timestamps) if timestamps else 0
            recommendations[job_id] = None
            if duration >= self.recommendation_threshold['concurrency']:
                recommendations[job_id] = \
                {
                    'group': '${{ github.workflow }}-${{ github.ref }}',
                    'cancel-in-progress': True,
                }
        return recommendations

    @__duration
    def __env(self) -> dict:
        """Get environmental variables recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            recommendations[job_id] = self.job_parses[job_id]['env'] if self.job_parses[job_id]['env'] else None
        return recommendations

    @__duration
    def __fail_fast(self) -> dict:
        """Get fail-fast recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            timestamps = self.timestamps[job_id]
            duration = max(timestamps) - min(timestamps) if timestamps else 0
            if duration >= self.recommendation_threshold['fail_fast']:
                recommendations[job_id] = False
        return recommendations

    @__duration
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

    @__duration
    def __outputs(self) -> dict:
        """Get output recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            candidates = {env['key']: env['value'] for env in self.job_parses[job_id]['env']
                        if env['op'] == 'set' and '/' not in env['value'] and self.repository_dir in env['filename']}
            recommendations[job_id] = candidates if candidates else None
        return recommendations

    @__duration
    def __steps(self) -> dict:
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
            uneven_chunk_generator = utils.uneven_chunks(timestamps)
            timestamp_groups = []
            count = 0
            for i, group in enumerate(uneven_chunk_generator):
                if i >= self.step_chunk_count:
                    break
                timestamp_groups.append(group)

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
            nF = (population - approx_ideal) / (approx_nadir - approx_ideal) if all(approx_nadir - approx_ideal) else 0
            np_weights = np.array(self.step_mcdm_weights)
            decomp = ASF()
            i = decomp.do(nF, 1/np_weights).argmin()
            decision = population[i].tolist()
            decision[0] = 1/decision[0]
            decision = [int(x) for x in decision]
            decision = total_timestamp_groups[optimization_groups.index(decision)]

            # Recommend steps
            run = self.job_parses[job_id]['script'].splitlines()
            recommendations[job_id] = []
            for start, end, _ in decision:
                step = utils.to_multiline_str(run[start:end])
                recommendations[job_id].append({'run': step}) if step.strip() else None
        return recommendations

    @__duration
    def __timeout_minutes(self) -> dict:
        """Get timeout-minutes recommendations"""
        recommendations = {}
        for job_id in self.workflow['jobs']:
            timestamps = self.timestamps[job_id]
            duration = max(timestamps) - min(timestamps) if timestamps else 0
            recommendations[job_id] = None
            if duration >= self.recommendation_threshold['timeout_minutes']:
                recommendations[job_id] = (duration * self.recommendation_multiplier['timeout_minutes']) / 60 
        return recommendations

    @__duration
    def __working_directory(self) -> dict:
        """Get working-directory recommendations"""
        def __repository_paths() -> list[str]:
            """Get the paths of all files and directories in a repository"""
            paths = {self.repository_dir}
            for dirpath, dirnames, filenames in os.walk(self.repository_dir):
                paths.update([os.path.join(dirpath, name) for name in dirnames + filenames])
            return sorted(list(paths))

        recommendations = {}
        repository_paths = __repository_paths()
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
            if candidate_paths and len(paths) > 1:
                working_directory = os.path.commonpath(candidate_paths)
                if os.path.isdir(working_directory):
                    recommendations[job_id] = f'./{working_directory}' if len(working_directory) > 0 else None
        return recommendations
