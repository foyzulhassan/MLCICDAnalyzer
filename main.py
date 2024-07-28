import argparse
from tracing import Tracing
from yamlci import YamlCI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script to be traced', default='target.sh')
    parser.add_argument('--requirements', dest='requirements_log', type=str, help='path to a pip requirements file', default='requirements.txt')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--trace_log', dest='trace_log', type=str, help='path to, or for, a trace log', default='trace.log')
    parser.add_argument('--paths_log', dest='paths_log', type=str, help='path to, or for, a path log', default='paths.log')
    parser.add_argument('--docker_log', dest='docker_log', type=str, help='path to a log listing the docker containers on the machine', default='docker.log')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='Workflow')
    parser.add_argument('--new_trace', dest='new_trace', help='whether the target should be traced again', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    tracing = Tracing(new_trace=args.new_trace,
                      trace_log=args.trace_log,
                      paths_log=args.paths_log,
                      target=args.target,
                      docker_log=args.docker_log,
                      requirements_log=args.requirements_log)
    ciyaml = YamlCI(tracing)
    ciyaml.dump(args.workflow)


if __name__ == '__main__':
    main()