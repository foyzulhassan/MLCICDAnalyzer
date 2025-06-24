from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
import csv
import glob
import json
import os
from pathlib import Path
import re


class Tracer(ABC):
    @abstractmethod
    def __init__(self, path):
        self.path = path

    @abstractmethod
    def parse(self):
        pass


class Ltrace(Tracer):
    def __init__(self, path: str, filter: list[str] = []):
        self.path = path
        self.filter = filter

    def parse(self):
        return self.__getenv()

    def __getenv(self) -> dict:
        """Parse all environmental variables from ltrace"""
        env = {}
        with open(self.path, 'r', errors='ignore') as file:
            for entry in file:
                content = re.match(r'(\d+)\s(\d+\.\d+)\s(.+?)->getenv\("(.+?)"\)\s+=\s+"(.+?)"', entry.strip())
                if content:
                    _, _, _, key, value = content.groups()
                    env[key] = value
        return {key: env[key] for key in sorted(env) if key not in self.filter}


class Pyenv(Tracer):
    def __init__(self, path: str, filter: list[str] = []):
        self.path = path
        self.filter = filter

    def parse(self):
        return self.__getenv()

    def __getenv(self) -> dict:
        """Parse all environmental variables from pyenv"""
        env = {}
        with open(self.path, 'r', errors='ignore') as file:
            for _, key, value in csv.reader(file):
                env[key] = value
        return {key: env[key] for key in sorted(env) if key not in self.filter}


class Strace(Tracer):
    def __init__(self, path: str):
        self.path = path

    def parse(self):
        return self.__paths()

    def __paths(self) -> list[str]:
        """Parse all distinct paths from strace log"""
        paths = set()
        with open(self.path, 'r', errors='ignore') as file:
            for entry in file:
                paths.update(re.findall(r'(?<=,\s")/.+?(?=",\s)', entry.strip()))
                paths.update(re.findall(r'(?<=<)/.+?(?=>)', entry.strip()))
        return sorted(paths)


def summarize(output_dir: str, filter_path: str):
    """Summarize the target traces based on the path suffix"""
    result = {}

    # Load the summary filter
    with open(filter_path, 'r') as file:
        filter = json.load(file)

    # Parse the target path and store the result
    paths = [path for path in glob.glob(os.path.join(output_dir, '*')) if path.endswith(('.ltrace', '.strace', '.pyenv'))]
    for path in paths:
        tracer = None
        match Path(path).suffix:
            case '.ltrace': tracer = Ltrace(path=path, filter=filter['env'])
            case '.strace': tracer = Strace(path=path)
            case '.pyenv': tracer = Pyenv(path=path, filter=filter['env'])
            case _: return None
        parse = tracer.parse()
        result[Path(path).name] = parse

    # Dump and return the result to a file
    output_path = os.path.join(output_dir, 'summary.json')
    with open(output_path, 'w') as file:
        json.dump(result, file, indent=2)
    return result
