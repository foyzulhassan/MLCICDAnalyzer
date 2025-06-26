import argparse
import os
from pathlib import Path
import subprocess
import shutil
import time

import toml

from generate.trace import TraceTarget
from generate.parse import ParseTrace
from generate.summarize import summarize
from generate.workflow import Workflow
from recommend.heuristics import HeuristicRecommendations
from recommend.model import ModelRecommendations
from recommend.hybrid import VectorRecommendations, QdrantVectorizer


TOOL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
RES_DIR = os.path.join(TOOL_DIR, 'res')
CONSOLE_WIDTH = os.get_terminal_size().columns


def generate_base_workflow(job_parses: dict):
    """Generate a workflow from the target traces"""
    workflow = Workflow(
        workflow_name=CONFIG.workflow_name, 
        output_dir=CONFIG.output_dir, 
        job_parses=job_parses,
        has_requirements=bool(CONFIG.requirements_path))
    workflow.construct(dump=True)


def apply_heuristic_recommendations(workflow_path: str, job_parses: dict):
    """Apply heuristic recommendations to workflow"""
    workflow_name = Path(workflow_path).stem
    print_divider('HEURISTICS', is_start=True, is_major=True)
    heuristic = HeuristicRecommendations(
        workflow_path=workflow_path,
        output_dir=CONFIG.output_dir,
        duration_log_path=CONFIG.duration_log_path,
        repository_dir=CONFIG.repository_dir,
        job_parses=job_parses,
        step_mcdm_weights=CONFIG.step_mcdm_weights,
        step_chunk_count=CONFIG.step_chunk_count,
        recommendation_threshold=CONFIG.recommendation_threshold,
        recommendation_multiplier=CONFIG.recommendation_multiplier)
    print_divider(f'ANALYSIS ~ {workflow_name}', is_start=True, is_major=False)
    heuristic.recommendations(dump=True)
    print_divider(f'ANALYSIS ~ {workflow_name}', is_start=False, is_major=False)
    print_divider(f'RECOMMENDING ~ {workflow_name}', is_start=True, is_major=False)
    heuristic.apply(dump=True)
    print_divider(f'RECOMMENDING ~ {workflow_name}', is_start=False, is_major=False)
    print_divider('HEURISTICS', is_start=False, is_major=True)


def apply_model_recommendations(workflow_path: str) -> dict:
    """Apply model recommendations to workflow"""
    print_divider('MODEL', is_start=True, is_major=True)
    model = ModelRecommendations(
        workflow_path=workflow_path,
        target_paths=CONFIG.target_paths,
        template_path=CONFIG.model_template_path,
        instruction_path=CONFIG.model_instruction_path,
        output_dir=CONFIG.output_dir,
        duration_log_path=CONFIG.duration_log_path,
        usage_log_path=CONFIG.usage_log_path,
        api_key=CONFIG.openai['api_key'],
        chat_model=CONFIG.openai['chat_model'])
    print_divider('MODEL', is_start=False, is_major=True)
    return model.apply()


def apply_hybrid_recommendations(workflow_path: str) -> tuple[dict, dict]:
    """Apply hybrid recommendations to workflow"""
    print_divider('VECTOR', is_start=True, is_major=True)
    print_divider('VECTORIZE', is_start=True, is_major=False)
    vectorizer = QdrantVectorizer(
        project_name=CONFIG.project_name,
        output_dir=CONFIG.output_dir,
        
        duration_log_path=CONFIG.duration_log_path,
        usage_log_path=CONFIG.usage_log_path,

        embedding_hostname=CONFIG.qdrant['hostname'],
        embedding_port=CONFIG.qdrant['port'],
        embedding_api_key=CONFIG.qdrant['api_key'],
        embedding_model=CONFIG.openai['embedding_model'],
    )
    vectorizer.vectorize()
    print_divider('VECTORIZE', is_start=False, is_major=False)
    print_divider('GENERATE', is_start=True, is_major=False)
    vector = VectorRecommendations(
        project_name=CONFIG.project_name,
        output_dir=CONFIG.output_dir,
        hybrid_mode=False,

        workflow_path=workflow_path,
        requirements_path=CONFIG.requirements_path,
        target_paths=CONFIG.target_paths,
        assemble_prompt_path=CONFIG.assemble_prompt_path,
        job_prompt_path=CONFIG.job_prompt_path,

        duration_log_path=CONFIG.duration_log_path,
        usage_log_path=CONFIG.usage_log_path,
        
        chat_model=CONFIG.openai['chat_model'],
        chat_api_key=CONFIG.openai['api_key'],
        embedding_hostname=CONFIG.qdrant['hostname'],
        embedding_port=CONFIG.qdrant['port'],
        embedding_api_key=CONFIG.qdrant['api_key'],
        embedding_model=CONFIG.openai['embedding_model'])
    vector_workflow = vector.apply()
    hybrid = VectorRecommendations(
        project_name=CONFIG.project_name,
        output_dir=CONFIG.output_dir,
        hybrid_mode=True,

        workflow_path=workflow_path,
        requirements_path=CONFIG.requirements_path,
        target_paths=CONFIG.target_paths,
        assemble_prompt_path=CONFIG.heuristic_assemble_prompt_path,
        job_prompt_path=CONFIG.job_prompt_path,

        duration_log_path=CONFIG.duration_log_path,
        usage_log_path=CONFIG.usage_log_path,
        
        chat_model=CONFIG.openai['chat_model'],
        chat_api_key=CONFIG.openai['api_key'],
        embedding_hostname=CONFIG.qdrant['hostname'],
        embedding_port=CONFIG.qdrant['port'],
        embedding_api_key=CONFIG.qdrant['api_key'],
        embedding_model=CONFIG.openai['embedding_model'])
    hybrid_workflow = hybrid.apply()
    print_divider('GENERATE', is_start=False, is_major=False)
    print_divider('VECTOR', is_start=False, is_major=True)
    return vector_workflow, hybrid_workflow


def get_job_parses() -> dict:
    """Trace each target script, parse information from the traces, and dump it to the output directory"""
    job_parses = {}
    print_divider('MONITORING', is_start=True, is_major=True)
    for target_path in CONFIG.target_paths:
        target_name = Path(target_path).stem
        trace_target(target_path)
        job_parses[target_name] = parse_trace(target_path)
    summarize(CONFIG.output_dir, CONFIG.filters_path)
    print_divider('MONITORING', is_start=False, is_major=True)
    return job_parses


def trace_target(target_path: str):
    """Trace a target script and output its result"""
    target_name = Path(target_path).stem
    print_divider(f'TRACE ~ {target_name}', is_start=True, is_major=False)
    trace = TraceTarget(
        target_path=target_path,
        output_dir=CONFIG.output_dir,
        duration_log_path=CONFIG.duration_log_path,
        working_dir=CONFIG.working_dir,
        repository_dir=CONFIG.repository_dir,
        packages_path=CONFIG.packages_path,
        patch_dir=CONFIG.patch_dir,
        new_trace=CONFIG.new_trace)
    trace.trace()
    print_divider(f'TRACE ~ {target_name}', is_start=False, is_major=False)


def parse_trace(target_path: str):
    """Parse relevant information from a trace script trace"""
    target_name = Path(target_path).stem
    print_divider(f'PARSE ~ {target_name}', is_start=True, is_major=False)
    parse = ParseTrace(
        target_path=target_path,
        output_dir=CONFIG.output_dir,
        duration_log_path=CONFIG.duration_log_path,
        requirements_path=CONFIG.requirements_path,
        repository_dir=CONFIG.repository_dir,
        filters_path=CONFIG.filters_path,
        new_trace=CONFIG.new_trace)
    parse = parse.parse(dump=True)
    print_divider(f'PARSE ~ {target_name}', is_start=False, is_major=False)
    return parse


def remove_artifacts():
    """Delete artifacts that were created by the tool"""
    paths = [os.path.join(CONFIG.output_dir, name) for name in os.listdir(CONFIG.output_dir) if os.path.isfile(os.path.join(CONFIG.output_dir, name))]
    print_divider('TEARDOWN', is_start=True, is_major=True)
    print('Deleting Artifacts...')
    for path in paths:
        if not path.endswith('.yaml') and os.path.getatime(path) >= START_TIME:
            # Files that were accidently put in output dir are (likely) not automatically removed due to the access time check
            os.remove(path)
            print(path)
    print_divider('TEARDOWN', is_start=False, is_major=True)


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


def print_divider(label: str, is_start: bool, is_major: bool = False):
    if not ARGS.quiet:
        print(f" {round(time.time() - START_TIME, 1)}s ~ {'START' if is_start else 'END'} ~ {label.strip()} ".center(CONSOLE_WIDTH, '=' if is_major else '.'))


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
    config_dict['model_template_path'] = os.path.join(RES_DIR, 'templates', 'model.template.txt')
    config_dict['model_instruction_path'] = os.path.join(RES_DIR, 'instructions', 'model.instructions.txt')
    config_dict['assemble_prompt_path'] = os.path.join(RES_DIR, 'instructions', 'assemble.instructions.txt')
    config_dict['heuristic_assemble_prompt_path'] = os.path.join(RES_DIR, 'instructions', 'heuristic.assemble.instructions.txt')
    config_dict['job_prompt_path'] = os.path.join(RES_DIR, 'instructions', 'job.instructions.txt')
    config_dict['duration_log_path'] = os.path.join(config_dict['output_dir'], 'duration.log')
    config_dict['usage_log_path'] = os.path.join(config_dict['output_dir'], 'usage.log')
    return Config(config_dict)


def parse_args():
    """Parse arguments from the command line"""
    parser = argparse.ArgumentParser(description="Synthesize GitHub Actions Workflows via Runtime-based Analysis.")
    parser.add_argument('config_path', type=str, default=None, help='path to a configuration file')
    parser.add_argument('-m', '--use-model', dest='use_model', action='store_true', help='whether to use LLM recommendations')
    parser.add_argument('-n', '--new-trace', dest='new_trace', action='store_true', help='whether to trace the target again and override existing artifacts')
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help='whether to print stage markers')
    parser.add_argument('--new-config', dest='new_config', type=str, default=None, help='path to directory to generate a new configuration file template')
    parser.add_argument('--no-artifacts', dest='no_artifacts', action='store_true', help='whether keep non-yaml artifacts that the tool produces')
    return parser.parse_args()


def main():
    global ARGS
    ARGS = parse_args()
    
    # Check whether to generate a new config file
    if ARGS.new_config is not None:
        generate_config(ARGS.new_config)
        return
    
    # Check whether a config file exists
    if ARGS.config_path is None or not os.path.isfile(ARGS.config_path):
        print(f'FileNotFound: No config file at "{ARGS.config_path}"')
        return
    global CONFIG
    CONFIG = parse_config(ARGS.config_path, ARGS.new_trace)

    # Reset the logs
    with open(CONFIG.duration_log_path, 'w') as file:
        file.write('source,function,duration\n')
    with open(CONFIG.usage_log_path, 'w') as file:
        file.write('source,purpose,prompt_tokens,completion_tokens,total_tokens\n')

    # Start the timer
    global START_TIME
    START_TIME = time.time()

    # Generate and parse traces for the target scripts
    job_parses = get_job_parses()
    base_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.base.yaml')
    heuristic_path = os.path.join(CONFIG.output_dir, f'{CONFIG.workflow_name}.heuristic.yaml')

    # Generate workflows
    generate_base_workflow(job_parses)
    apply_heuristic_recommendations(workflow_path=base_path, job_parses=job_parses)
    if CONFIG.openai['api_key'] and CONFIG.qdrant['api_key'] and ARGS.use_model:
        apply_model_recommendations(heuristic_path)
        apply_hybrid_recommendations(heuristic_path)

    # Check whether to remove artifacts besides yaml files
    if ARGS.no_artifacts:
        remove_artifacts()


if __name__ == '__main__':
    main()
