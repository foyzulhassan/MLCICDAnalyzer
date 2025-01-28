import argparse
import glob
import os
from pathlib import Path
import shutil
import subprocess
import sys

tool_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
modules_dirs = glob.glob(os.path.join(tool_dir, '.modules/lib/python*/site-packages'))
sys.path.extend(modules_dirs)

from generate.trace import TraceTarget
from generate.parse import ParseTrace
from generate.workflow import Workflow
from recommend.heuristics import HeuristicRecommendations
from recommend.model import ModelRecommendations
import toml


def generate_base_workflow(job_parses: dict):
    """Generate a workflow from the target traces"""
    workflow = Workflow(
        workflow_name=CONFIG.workflow_name, 
        output_dir=CONFIG.output_dir, 
        job_parses=job_parses, 
        requirements_path=CONFIG.requirements_path,
        order_path=CONFIG.order_path)
    workflow.construct(dump=True)


def apply_heuristic_recommendations(workflow_path: str):
    """Apply heuristic recommendations to workflow"""
    heuristic = HeuristicRecommendations(
        workflow_path=workflow_path,
        output_dir=CONFIG.output_dir,
        repository_dir=CONFIG.repository_dir,
        env_filter_path=CONFIG.env_filter_path)
    heuristic.recommendations(dump=True)
    heuristic.apply(dump=True)


def apply_model_recommendations(workflow_path: str):
    """Apply model recommendations to workflow"""
    model = ModelRecommendations(
        workflow_path=workflow_path,
        output_dir=CONFIG.output_dir,
        schema_path=CONFIG.schema_path,
        api_key=CONFIG.api_key)
    model.recommendations(dump=True)
    model.apply(dump=True)


def get_job_parses() -> dict:
    """Trace each target script, parse information from the traces, and dump it to the output directory"""
    job_parses = {}
    for target_path in CONFIG.target_paths:
        target_name = Path(target_path).stem
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
        requirements_path=CONFIG.requirements_path,
        patch_dir=CONFIG.patch_dir,
        new_trace=CONFIG.new_trace)
    trace.trace()


def parse_trace(target_path: str):
    """Parse relevant information from a trace script trace"""
    parse = ParseTrace(
        target_path=target_path,
        output_dir=CONFIG.output_dir,
        env_filter_path=CONFIG.env_filter_path,
        docker_path=CONFIG.docker_path)
    return parse.parse(dump=True)


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
    tool_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    install_path = os.path.join(tool_dir, 'res', 'install.sh')
    subprocess.run(f'bash {install_path}', shell=True)


def parse_config(config_path: str):
    """Parse options from a configuration file"""
    class Config(dict):
        __getattr__ = dict.get
        __setattr__ = dict.__setitem__
        __delattr__ = dict.__delitem__
    config_dict = toml.load(config_path)
    return Config(config_dict)


def parse_args():
    """Parse arguments from the command line"""
    parser = argparse.ArgumentParser(description="Trace an application, generate a workflow, and augment it with recommendations.")
    parser.add_argument('-a', '--apply_recommendation', action='store_true', help='whether to apply recommendation to current workflow')
    parser.add_argument('-c', '--config_path', type=str, default=None, help='path to a configuration file')
    parser.add_argument('-d', '--new_docker', type=str, default=None, help='path to directory to store a new docker log')
    parser.add_argument('-i', '--interactive', action='store_true', help='whether to launch in interactive mode')
    parser.add_argument('-m', '--no_model', action='store_true', default=None, help='whether to not prompt for model recommendations (even if an api key is supplied)')
    parser.add_argument('-n', '--new_config', type=str, default=None, help='path to directory to generate a new config template')
    return parser.parse_args()


def main():
    args = parse_args()

    # Check whether dependencies have been installed
    if '.modules' not in os.listdir(tool_dir):
        print('DependenciesNotFound: Execute this tool with the --install option to install dependencies before running')
        return

    # Import here because dependencies are found
    from generate.trace import TraceTarget
    from generate.parse import ParseTrace
    from generate.workflow import Workflow
    from recommend.heuristics import HeuristicRecommendations
    from recommend.model import ModelRecommendations
    import toml
    
    # Check whether to generate a new config file
    if args.new_config is not None:
        generate_config(args.new_config)
        return
    
    # Check whether to generate a new docker log
    if args.new_docker is not None:
        generate_docker(args.new_docker)
        return

    # Check whether to run in interactive mode
    if args.interactive:
        return

    # Check whether a config file exists
    if args.config_path is None or not os.path.isfile(args.config_path):
        print(f'FileNotFound: No config file at "{args.config_path}"')
        return
    global CONFIG
    CONFIG = parse_config(args.config_path)

    # Generate and parse traces for the target scripts
    job_parses = get_job_parses()
    base_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.base.yaml')
    heuristic_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.heuristic.yaml')
    model_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.model.yaml')

    # Generate workflows
    generate_base_workflow(job_parses)
    apply_heuristic_recommendations(base_path)
    if CONFIG.api_key and not args.no_model:
        apply_model_recommendations(heuristic_path)


if __name__ == '__main__':
    main()
