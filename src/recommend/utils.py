from copy import deepcopy
from io import StringIO
from itertools import combinations
import textwrap

from jsonschema import validate
import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString


def validate_workflow(workflow: str | dict, schema: dict) -> bool:
    """Validate a workflow using a JSON schema"""
    try:
        workflow_dict = workflow_to_dict(workflow) if isinstance(workflow, str) else workflow
        validate(instance=workflow_dict, schema=schema)
        return True
    except Exception:
        return False


def workflow_to_dict(workflow: str) -> dict:
    """Convert a string workflow to a dictionary representation"""
    return get_yaml_parser().load(workflow)


def workflow_to_str(workflow: dict) -> str:
    """Convert a dictionary workflow to a string representation"""
    workflow_stream = StringIO()
    get_yaml_parser().dump(workflow, workflow_stream)
    workflow_str = workflow_stream.getvalue()
    workflow_stream.close()
    return workflow_str


def load_workflow(workflow_path: str, as_str: bool = False) -> str | dict:
    """Load a workflow and represent it as a string or dictionary"""
    workflow = None
    yaml_parser = get_yaml_parser()
    with open(workflow_path, 'r') as workflow_file:
        workflow = workflow_file.read() if as_str else yaml_parser.load(workflow_file)
    return workflow


def dump_workflow(workflow: dict, output_path: str):
    """Dump a workflow to a file"""
    copied = deepcopy(workflow)
    for job_id in copied['jobs']:
        for i, step in enumerate(copied['jobs'][job_id]['steps']):
            if 'run' in step:
                copied['jobs'][job_id]['steps'][i]['run'] = to_multiline_str(copied['jobs'][job_id]['steps'][i]['run'].splitlines())

    yaml_parser = get_yaml_parser()
    with open(output_path, 'w') as file:
        yaml_parser.dump(copied, file)


def get_yaml_parser() -> YAML:
    """Get pre-configured yaml parser"""
    ruamel.yaml.representer.RoundTripRepresenter.ignore_aliases = lambda x, y: True
    yaml_parser = YAML(pure=True)
    yaml_parser.indent(sequence=4, offset=2)
    yaml_parser.sort_base_mapping_type_on_output = False
    yaml_parser.default_style = None
    yaml_parser.width = 100
    yaml_parser.ignore_aliases = lambda *args : True
    return yaml_parser


def to_multiline_str(strings: list) -> str:
    """Retrieve multiline string that will be rendered properly"""
    newline_strings = '\n'.join(strings) + '\n'
    return LiteralScalarString(textwrap.dedent(f"""{newline_strings}"""))


def uneven_chunks(group, min_chunk_size=1):
    """Find all ways to split a group into uneven chunks."""
    if len(group) < 2:
        yield [group]
        return

    for i in range(min_chunk_size, len(group)):
        for combo in combinations(range(1, len(group)), i):
            split_points = [0] + list(combo) + [len(group)]
            yield [group[split_points[j]:split_points[j+1]] for j in range(len(split_points)-1)]