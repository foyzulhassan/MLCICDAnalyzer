import argparse
from tracing import Tracing
from yamlci import YamlCI


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', dest='target', type=str, help='path to target bash script to be traced', default='target.sh')
    parser.add_argument('--requirement', dest='requirement', type=str, help='path to, or for, a pip requirements file', default='requirement.txt')
    parser.add_argument('--template', dest='template', type=str, help='path to a workflow configuration template', default='dependencies.yaml')
    parser.add_argument('--workflow', dest='workflow', type=str, help='path to, or for, a workflow configuration', default='workflow.yaml')
    parser.add_argument('--workflow_name', dest='workflow_name', type=str, help='name for a new workflow configuration', default='workflow')
    parser.add_argument('--dockerfile', dest='dockerfile', type=str, help='path to a dockerfile', default='Dockerfile')
    parser.add_argument('--new_trace', dest='new_trace', help='whether the target should be traced again', action='store_true')
    return parser.parse_args()


def main():
    # Parse runtime arguments
    args = parse_args()

    # Trace the system calls of a target program
    tracing = Tracing(new_trace=args.new_trace,
                      trace_log='trace.log',
                      paths_log='paths.log',
                      target=args.target,
                      dockerfile=args.dockerfile)

    # Build and dump CI/CD YAML configuration from a system call trace
    ciyaml = YamlCI(tracing)
    ciyaml.dump(args.workflow)


if __name__ == '__main__':
    main()