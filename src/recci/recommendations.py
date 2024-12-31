import re
import os
import glob
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from pandas import DataFrame
from ruamel.yaml import YAML
import json
import copy
import bashlex


def recommend_working_directory(workflow: dict, repository_paths: list[str]) -> dict:
    result = copy.deepcopy(workflow)
    
    for job in workflow['jobs']:
        # Get all relative paths in the job 
        relative_paths = set()
        root_path = repository_paths[0]
        tokens = str(workflow['jobs'][job]['steps'][-1]).split()
        for token in tokens:
            relative_match = len(re.findall('\.{1}\/|\.{2}\/', token)) > 0
            absolute_match = token.strip().startswith('/')
            root_match = os.path.join(root_path, token) in repository_paths
            if relative_match or absolute_match or root_match:
                path_token = token.replace(f'{root_path}/', '')
                path_token = os.path.abspath(os.path.join(root_path, path_token))
                relative_paths.add(path_token)
        
        # Find common directory (i..e working-directory) of paths
        relative_paths = list(relative_paths)
        relative_paths = [relative_path for relative_path in relative_paths if relative_path in repository_paths]
        relative_paths = [relative_path.replace(f'{root_path}/', '') for relative_path in relative_paths]
        working_directory = os.path.commonpath(relative_paths).strip()
        if len(working_directory) > 0:
            result['jobs'][job]['steps'][-1]['working-directory'] = f'./{working_directory}'
    return result


def recommend_pip(workflow: dict) -> dict:
    result = copy.deepcopy(workflow)
    for job in workflow['jobs']:
        pass
    return result


def recommend_permissions(workflow: dict):
    pass


def recommend_needs():
    pass


def recommend_timeout_minutes():
    pass


def get_recursive_paths(root: str) -> list:
    repository_paths = {root}
    for dirpath, dirnames, filenames in os.walk(root):
        paths = [os.path.join(dirpath, name) for name in dirnames + filenames]
        repository_paths.update(paths)
    repository_paths = list(repository_paths)
    repository_paths.sort(key=len)
    return repository_paths
