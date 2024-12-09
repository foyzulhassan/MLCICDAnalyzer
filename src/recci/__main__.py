import argparse
from recci.parse_yaml import YamlParser
from recci.environment_rec import EnvironmentRecommendation
from recci.output_rec import OutputRecommendation

def main():
    parser = argparse.ArgumentParser(description="Generate recommendations for CI workflows.")
    parser.add_argument('--yaml', required=True, help="Path to the GitHub Actions YAML workflow.")
    parser.add_argument('--strace', help="Path to the strace log.")
    parser.add_argument('--code_dir', help="Path to the codebase directory.")
    args = parser.parse_args()

    # Parse and validate YAML
    yaml_parser = YamlParser(args.yaml)
    if not yaml_parser.validate_yaml():
        print("Fix the YAML file before proceeding.")
        return

    # Process each job
    jobs = yaml_parser.get_jobs()
    env_rec = EnvironmentRecommendation()
    output_rec = OutputRecommendation()

    for job_id, job in jobs.items():
        # Apply environment recommendations
        env_rec.generate_recommendation(job_id, job, strace_file=args.strace, code_dir=args.code_dir)

        # Apply output recommendations
        output_rec.generate_recommendation(job_id, job, strace_file=args.strace, code_dir=args.code_dir)

    # Output recommendations
    env_rec.output_recommendations()
    output_rec.output_recommendations()

if __name__ == "__main__":
    main()