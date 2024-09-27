import argparse
from tracing import Tracing
from yamlci import YamlCI
import os

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script, or directory of scripts, to be traced', default='target.sh')
    parser.add_argument('--host_container', dest='host_container', type=str, help='id of the container that the target is running in', default=None)
    parser.add_argument('--requirements', dest='requirements_log', type=str, help='path to a pip requirements file', default='requirements.txt')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--trace_log', dest='trace_log', type=str, help='path to, or for, a trace log', default='trace.log')
    parser.add_argument('--paths_log', dest='paths_log', type=str, help='path to, or for, a path log', default='paths.log')
    parser.add_argument('--docker_log', dest='docker_log', type=str, help='path to a log listing the docker containers on the machine', default='docker.log')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='Workflow')
    parser.add_argument('--new_trace', dest='new_trace', help='whether the target should be traced again', action='store_true')
    parser.add_argument('--keep_log', dest='keep_log', help='whether trace logs should be preserved', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    targets = [f'{args.target}/{path}' for path in os.listdir(args.target) if os.path.isfile(os.path.abspath(f'{args.target}/{path}'))] if os.path.isdir(args.target) else [args.target]
    targets.reverse()
    tracings = []
    for i, target in enumerate(targets):
        tracings.append(Tracing(target=target,
                        new_trace=args.new_trace,
                        host_container=args.host_container,
                        trace_log=args.trace_log,
                        paths_log=args.paths_log,
                        docker_log=args.docker_log,
                        requirements_log=args.requirements_log))
        if args.keep_log:
            os.renames(args.trace_log, f'logs/{i}_{os.path.basename(target).replace(".sh", ".log")}')
    ciyaml = YamlCI(tracings)
    ciyaml.dump(args.workflow)


if __name__ == '__main__':
    main()