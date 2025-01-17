import argparse
import os
from pathlib import Path
import shutil
import subprocess


def parse_args():
    parser = argparse.ArgumentParser(description="Trace an application, generate a workflow, and augment it with recommendations.")
    parser.add_argument('-c', '--config_path', type=str, default=None, help='path to a configuration file')
    parser.add_argument('-d', '--docker_log', type=str, default=None, help='path to directory to store a new docker log')
    parser.add_argument('-i', '--interactive', action='store_true', help='whether to launch in interactive mode')
    parser.add_argument('-n', '--new_config', type=str, default=None, help='path to directory to generate a new config template')
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Check whether to generate a new config file
    if args.new_config is not None:
        template_path = os.path.join('res', 'options.toml')
        copy_path = os.path.join(args.new_config, 'options.toml')
        shutil.copyfile(template_path, copy_path)
        return
    
    # Check whether to generate a docker log
    if args.docker_log is not None:
        docker_path = os.path.join(args.docker_log, 'containers.docker')
        command = 'docker ps --no-trunc --format "{{.ID}}~{{.Names}}~{{.Image}}~{{.Ports}}"'
        with open(docker_path, 'w') as docker_log:
            subprocess.run(command, stdout=docker_log, shell=True)
        return

    # Imports are here to enable generation of new configs and docker logs
    import toml
    from generate.trace import TraceTarget
    from generate.parse import ParseTrace
    from generate.workflow import Workflow
    from recommend.heuristics import HeuristicRecommendations

    # Check whether to run in interactive mode
    if args.interactive:
        return

    # Load the config file and check its validity
    if args.config_path is None or not os.path.isfile(args.config_path):
        print(f'FileNotFound: No config file at "{args.config_path}"')
        return
    config = toml.load(args.config_path)

    # Trace the target script and dump the results to the output directory
    job_parses = {}
    for target_path in config['target_paths']:
        target_name = Path(target_path).stem
        trace = TraceTarget(target_path=target_path,
                            output_dir=config['output_dir'],
                            working_dir=config['working_dir'],
                            packages_path=config['packages_path'],
                            patch_dir=config['patch_dir'],
                            new_trace=config['new_trace'])
        trace.trace()
        parse = ParseTrace(target_path=target_path,
                           output_dir=config['output_dir'],
                           requirements_path=config['requirements_path'] if config['requirements_path'].strip() != '' else None,
                           docker_path=config['docker_path'] if config['docker_path'].strip() != '' else None)
        job_parse = parse.parse(dump=True)
        job_parses[target_name] = job_parse

    # Generate a workflow from the target traces
    workflow_name = config['workflow_name']
    workflow_path = os.path.join(config['output_dir'], f'{workflow_name}.base')
    workflow = Workflow(workflow_name=config['workflow_name'], 
                        output_dir=config['output_dir'], 
                        job_parses=job_parses, 
                        requirements_path=config['requirements_path'] if config['requirements_path'].strip() != '' else None)
    workflow.construct(dump=True)
    
    # Apply recommendations to workflow
    recommendations = HeuristicRecommendations(workflow_path=workflow_path,
                                               output_dir=config['output_dir'],
                                               repository_dir=config['repository_dir'],
                                               env_filter_path=config['env_filter_path'] if config['env_filter_path'].strip() != '' else None)
    recommendations.recommendations(dump=True)
    recommendations.apply_all(dump=True)


if __name__ == '__main__':
    main()
