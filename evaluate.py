import argparse
import json
import os
import itertools
import ruamel.yaml
import codebleu
import graphtage
import matplotlib.pyplot as plt
from datetime import datetime
from collections import OrderedDict

def calc_shared_lines(reference: str, hypothesis: str) -> float:
    """Caclulate the proportion of shared lines between strings (ignoring leading/trailing whitespace and order)"""
    reference_lines = [line.strip() for line in reference.splitlines()]
    hypothesis_lines = [line.strip() for line in hypothesis.splitlines()]
    exact_matches = len([None for line in reference_lines if line in hypothesis_lines and not hypothesis_lines.remove(line)])
    accuracy = exact_matches / len(reference_lines)
    return accuracy

def calc_num_of_edits(reference_path: str, hypothesis_path: str) -> int:
    """Number of differences resulting from a semantic diff between the reference and hypothesis"""
    reference_tree = graphtage.yaml.build_tree(reference_path)
    hypothesis_tree = graphtage.yaml.build_tree(hypothesis_path)
    edits = list(reference_tree.get_all_edits(hypothesis_tree))
    return len(edits)

def calc_code_bleu(reference: str, hypothesis: str, lang: str) -> dict[str, float]:
    """Calculate the BLEU score for a hypothesis string given a reference string"""
    code_bleu = codebleu.calc_codebleu([reference], [hypothesis], lang=lang, weights=(0.25, 0.25, 0.25, 0.25), tokenizer=None)
    return code_bleu

def complete_evaluation(reference_path: str, hypothesis_path: str):
    """Conduct all available evaluations on the given hypothesis"""
    reference_path = reference_path
    hypothesis_path = hypothesis_path
    with open(reference_path, 'r') as yaml:
        reference_yaml = yaml.read()
    with open(hypothesis_path, 'r') as yaml:
        hypothesis_yaml = yaml.read()
    reference_js = yaml_to_javascript(reference_path)
    hypothesis_js = yaml_to_javascript(hypothesis_path)

    shared_lines = calc_shared_lines(reference_yaml, hypothesis_yaml)
    code_bleu = calc_code_bleu(reference_js, hypothesis_js, 'javascript')
    num_of_edits = calc_num_of_edits(reference_path, hypothesis_path)
    result = {**code_bleu, **{'shared_lines': shared_lines, 'num_of_edits': num_of_edits}}
    return result

def yaml_to_javascript(path: str) -> str:
    """Convert YAML to javascript object and return dumped filename"""
    with open(path, 'r') as file:
        yaml = ruamel.yaml.YAML(typ='safe').load(file)
    jsons = json.dumps(yaml, separators=(',', ':'))
    javascript = 'const object = ' + jsons.replace('\n', '; ')
    return javascript

def load_batch(path: str):
    """Load all YAMLs that are within file structures with the following format: path/repo_name/version.yaml"""
    return {os.path.basename(dirpath): list(map(lambda filename: f'{dirpath}/{filename}', filenames)) for dirpath, _, filenames in os.walk(path) if filenames}

def evaluate_batch(batch: dict[str, list[str]], reference_name: str):
    """Conduct complete evaluation on YAMLs within batch on their respective references"""
    result = {}
    for group, files in batch.items():
        for hypothesis_path in files:
            basename = os.path.basename(hypothesis_path)
            if basename == reference_name:
                continue
            reference_path = f'{os.path.dirname(hypothesis_path)}/{reference_name}'
            if group not in result:
                result[group] = {}
            result[group][basename] = complete_evaluation(reference_path, hypothesis_path)
    return result

def organize_batch_result(batch_result: dict, dump: bool = False):
    """Parse batch result to produce something that is easier to plot"""
    metrics = list(list(list(batch_result.values())[0].values())[0].keys())
    organized_result = {metric: {} for metric in metrics}
    for _, hypotheses in batch_result.items():
        for version, metrics in hypotheses.items():
            for metric, value in metrics.items():
                if version not in organized_result[metric]:
                    organized_result[metric][version] = []
                organized_result[metric][version].append(value)
    if dump:
        with open(f"{datetime.now().strftime('%m-%d-%y_%H-%M-%S')}-result.json", 'w') as file:
            json.dump(organized_result, file)
    return organized_result

def plot_batch_result(organized_result: dict, rows: int = 2, cols: int = 4, order: list = None):
    """Plot organized batch results"""
    results = organized_result
    versions: list[str] = list(list(list(results.values())[0].keys()))
    if order is not None and set(versions) == set(order):
        versions = order
        results = {metric: OrderedDict((yaml, yamls[yaml]) for yaml in order) for metric, yamls in results.items()}
    versions = [version.removesuffix('.yaml').removesuffix('.yml') for version in versions]
    figure, xaxes = plt.subplots(rows, cols)
    locations = list(itertools.product(range(rows), range(cols)))
    for i, (metric, yamls) in enumerate(results.items()):
        data = list(list(yamls.values()))
        row, col = locations[i]
        xaxes[row, col].boxplot(data, showmeans=True)
        xaxes[row, col].set_title(metric)
        xaxes[row, col].set_xticklabels(versions)
        xaxes[row, col].get_xaxis().tick_bottom()
        xaxes[row, col].get_yaxis().tick_left()
    manager = plt.get_current_fig_manager()
    manager.window.showMaximized()
    plt.show()

def parse_args():
    """Parse CLI arguments and return them"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--single', dest='single_paths', nargs="2", help='Paths to the reference YAML and the hypothesis YAML')
    parser.add_argument('--batch', dest='batch_info', nargs="2", help='Batch evaluation using a directory of sub-directories that contain YAMLs')
    parser.add_argument('--save', dest='save', help='Whether evaluation logs should be saved', action='store_true')
    parser.add_argument('--plot', dest='plot_path', type=str, help='Plot an existing evaluation log')
    parser.add_argument('--order', dest='plot_order', nargs="+", help='Order to plot the YAMLs in a batch directory')
    return parser.parse_args()

def main():
    args = parse_args()

    if args.plot_path:
        with open(args.plot_path, 'r') as file:
            organized_result = json.load(file)
        plot_batch_result(organized_result, order=args.plot_order)
    elif args.batch_info:
        batch_path, reference_filename = args.batch_info[0], args.batch_info[1]
        batch = load_batch(batch_path)
        batch_result = evaluate_batch(batch, reference_filename)
        organized_result = organize_batch_result(batch_result, args.save)
        plot_batch_result(organized_result, order=args.plot_order)
    elif args.single_paths:
        reference_path, hypothesis_path = args.single_paths[0], args.single_paths[1]
        print(complete_evaluation(reference_path, hypothesis_path))

if __name__ == '__main__':
    main()