import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import toml

from generate.trace import TraceTarget
from generate.parse import ParseTrace
from generate.workflow import Workflow
from recommend.heuristics import HeuristicRecommendations
from recommend.model import ModelRecommendations


TOOL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
RES_DIR = os.path.join(TOOL_DIR, 'res')
TIMELOG = {
    'tool': -1,
    'base': -1,
    'heuristic': -1,
    'model': -1,
    'jobs': {}
}


def generate_base_workflow(job_parses: dict):
    """Generate a workflow from the target traces"""
    TIMELOG['base'] = -time.time()
    workflow = Workflow(
        workflow_name=CONFIG.workflow_name, 
        output_dir=CONFIG.output_dir, 
        job_parses=job_parses,
        has_requirements=bool(CONFIG.requirements_path))
    workflow.construct(dump=True)
    TIMELOG['base'] = round(time.time() + TIMELOG['base'])


def apply_heuristic_recommendations(workflow_path: str, job_parses: dict):
    """Apply heuristic recommendations to workflow"""
    TIMELOG['heuristic'] = -time.time()
    heuristic = HeuristicRecommendations(
        workflow_path=workflow_path,
        output_dir=CONFIG.output_dir,
        repository_dir=CONFIG.repository_dir,
        job_parses=job_parses,
        concurrency_threshold=CONFIG.concurrency_threshold,
        step_mcdm_weights=CONFIG.step_mcdm_weights,
        timeout_multiplier=CONFIG.timeout_multiplier,
        timeout_threshold=CONFIG.timeout_threshold)
    heuristic.recommendations(dump=True)
    heuristic.apply(dump=True)
    TIMELOG['heuristic'] = round(time.time() + TIMELOG['heuristic'])


def apply_model_recommendations(workflow_path: str):
    """Apply model recommendations to workflow"""
    TIMELOG['model'] = -time.time()
    model = ModelRecommendations(
        workflow_path=workflow_path,
        output_dir=CONFIG.output_dir,
        schema_path=CONFIG.schema_path,
        api_key=CONFIG.api_key)
    model.recommendations(dump=True)
    model.apply(dump=True)
    TIMELOG['model'] = round(time.time() + TIMELOG['model'])


def get_job_parses() -> dict:
    """Trace each target script, parse information from the traces, and dump it to the output directory"""
    job_parses = {}
    for target_path in CONFIG.target_paths:
        target_name = Path(target_path).stem
        TIMELOG['jobs'][target_name] = {}
        trace_target(target_path)
        job_parses[target_name] = parse_trace(target_path)
    return job_parses


def trace_target(target_path: str):
    """Trace a target script and output its result"""
    trace = TraceTarget(
        target_path=target_path,
        output_dir=CONFIG.output_dir,
        working_dir=CONFIG.working_dir,
        repository_dir=CONFIG.repository_dir,
        packages_path=CONFIG.packages_path,
        patch_dir=CONFIG.patch_dir,
        new_trace=CONFIG.new_trace)
    trace.trace()


def parse_trace(target_path: str):
    """Parse relevant information from a trace script trace"""
    target_name = Path(target_path).stem
    TIMELOG['jobs'][target_name]['parse'] = -time.time()
    parse = ParseTrace(
        target_path=target_path,
        output_dir=CONFIG.output_dir,
        requirements_path=CONFIG.requirements_path,
        repository_dir=CONFIG.repository_dir,
        filters_path=CONFIG.filters_path)
    parse = parse.parse(dump=True)
    TIMELOG['jobs'][target_name]['parse'] = round(time.time() + TIMELOG['jobs'][target_name]['parse'])
    return parse


def remove_artifacts(start_time: float):
    """Delete artifacts that were created by the tool"""
    paths = [os.path.join(CONFIG.output_dir, name) for name in os.listdir(CONFIG.output_dir) if os.path.isfile(os.path.join(CONFIG.output_dir, name))]
    print('Deleting Artifacts...')
    for path in paths:
        if not path.endswith('.yaml') and os.path.getatime(path) >= start_time:
            # Files that were accidently put in output dir are (likely) not automatically removed due to the access time check
            os.remove(path)
            print(path)


def dump_timelog():
    """Dump timelog to a file"""
    for job_id in TIMELOG['jobs']:
        for tracer in ['strace', 'ltrace']:
            tracer_path = os.path.join(CONFIG.output_dir, f'{job_id}.{tracer}')
            with open(tracer_path, 'r', errors='ignore') as file:
                start = float(file.readline().split(maxsplit=2)[1])
                for line in file:
                    pass
                end = float(line.split(maxsplit=2)[1])
            TIMELOG['jobs'][job_id][tracer] = round(end - start)
    log_path = os.path.join(CONFIG.output_dir, 'timelog.json')
    with open(log_path, 'w') as file:
        json.dump(TIMELOG, file, indent=2)


def generate_config(destination_dir: str):
    """Copy the config template to path"""
    template_path = os.path.join('res', 'template.toml')
    dest_path = os.path.join(destination_dir, 'new_config.toml')
    shutil.copyfile(template_path, dest_path)


def generate_docker(destination_dir: str):
    """Gemerate a docker log at path"""
    docker_path = os.path.join(destination_dir, 'new_docker.docker')
    command = 'docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"'
    with open(docker_path, 'w') as file:
        subprocess.run(command, stdout=file, shell=True)


def install_dependencies():
    """Install the python dependencies that this tool uses"""
    install_path = os.path.join(TOOL_DIR, 'res', 'install.sh')
    subprocess.run(f'bash {install_path}', shell=True)


def parse_config(config_path: str, new_trace: bool = False):
    """Parse options from a configuration file"""
    class Config(dict):
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__
        __delattr__ = dict.__delitem__
    config_dict = toml.load(config_path)
    config_dict['new_trace'] = new_trace
    config_dict['patch_dir'] = RES_DIR
    config_dict['packages_path'] = os.path.join(RES_DIR, 'packages.py')
    config_dict['filters_path'] = os.path.join(RES_DIR, 'filters.json')
    config_dict['schema_path'] = os.path.join(RES_DIR, 'github-workflow.json')
    config_dict['order_path'] = os.path.join(RES_DIR, 'syntax-order.txt')
    return Config(config_dict)


def parse_args():
    """Parse arguments from the command line"""
    parser = argparse.ArgumentParser(description="Synthesize GitHub Actions Workflows via Runtime-based Analysis.")
    parser.add_argument('config_path', type=str, default=None, help='path to a configuration file')
    parser.add_argument('-m', '--use-model', dest='use_model', action='store_true', default=None, help='whether to use LLM recommendations')
    parser.add_argument('-n', '--new-trace', dest='new_trace', action='store_true', default=None, help='whether to trace the target again and override existing artifacts')
    parser.add_argument('--new-config', dest='new_config', type=str, default=None, help='path to directory to generate a new configuration file template')
    parser.add_argument('--no-artifacts', dest='no_artifacts', action='store_true', default=None, help='whether keep non-yaml artifacts that the tool produces')
    return parser.parse_args()


def main():
    TIMELOG['tool'] = -time.time()
    args = parse_args()
    start_time = time.time()
    
    # Check whether to generate a new config file
    if args.new_config is not None:
        generate_config(args.new_config)
        return
    
    # Check whether a config file exists
    if args.config_path is None or not os.path.isfile(args.config_path):
        print(f'FileNotFound: No config file at "{args.config_path}"')
        return
    global CONFIG
    CONFIG = parse_config(args.config_path, args.new_trace)

    # Generate and parse traces for the target scripts
    job_parses = get_job_parses()
    base_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.base.yaml')
    heuristic_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.heuristic.yaml')

    # Generate workflows
    generate_base_workflow(job_parses)
    apply_heuristic_recommendations(workflow_path=base_path, job_parses=job_parses)
    if CONFIG.api_key and args.use_model:
        apply_model_recommendations(heuristic_path)

    # Check whether to remove artifacts besides yaml files
    if args.no_artifacts:
        remove_artifacts(start_time)
    
    # Dump logs to a file
    TIMELOG['tool'] = round(time.time() + TIMELOG['tool'])
    dump_timelog()


if __name__ == '__main__':
    main()
