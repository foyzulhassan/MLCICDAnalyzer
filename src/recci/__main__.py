import argparse
from recci.parse_yaml import YamlParser
from recci.environment_rec import EnvironmentRecommendation
from recci.output_rec import OutputRecommendation

def main():
    parser = argparse.ArgumentParser(description="Generate recommendations for GitHub Actions YAML workflows.")
    parser.add_argument('--yaml', type=str, required=True, help="Path to the YAML file.")
    parser.add_argument('--strace', type=str, help="Path to the strace output file.")
    parser.add_argument('--code_dir', type=str, help="Path to the directory containing the codebase.")
    args = parser.parse_args()

    # Parse and validate YAML
    yaml_parser = YamlParser(args.yaml)
    try:
        yaml_parser.validate_yaml()
        workflow = yaml_parser.get_workflow()
    except Exception as e:
        print(f"Error: {e}")
        return

    # Generate recommendations
    env_rec = EnvironmentRecommendation(workflow)
    env_rec.generate_recommendation(strace_file=args.strace, code_dir=args.code_dir)
    env_rec.output_recommendations()

    output_rec = OutputRecommendation(yaml_parser.workflow)
    output_rec.generate_recommendation(strace_file=args.strace, code_dir=args.code_dir)
    output_rec.output_recommendations()

if __name__ == '__main__':
    main()
