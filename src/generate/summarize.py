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
    def __init__(self, path):
        self.path = path

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
        return {key: env[key] for key in sorted(env)}


class Pyenv(Tracer):
    def __init__(self, path):
        self.path = path

    def parse(self):
        return self.__getenv()

    def __getenv(self) -> dict:
        """Parse all environmental variables from pyenv"""
        env = {}
        with open(self.path, 'r', errors='ignore') as file:
            for _, key, value in csv.reader(file):
                env[key] = value
        return {key: env[key] for key in sorted(env)}


class Strace(Tracer):
    def __init__(self, path):
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


def generate_summary(output_dir: str) -> dict:
    """Summarize the target traces based on the path suffix"""
    result = {}

    # Parse the target path and store the result
    paths = [path for path in glob.glob(os.path.join(output_dir, '*')) if path.endswith(('.ltrace', '.strace', '.pyenv'))]
    for path in paths:
        tracer = None
        match Path(path).suffix:
            case '.ltrace': tracer = Ltrace(path)
            case '.strace': tracer = Strace(path)
            case '.pyenv': tracer = Pyenv(path)
            case _: return None
        parse = tracer.parse()
        result[Path(path).name] = parse
    
    # Dump and return the result to a file
    output_path = os.path.join(output_dir, 'summary.json')
    with open(output_path, 'w') as file:
        json.dump(result, file, indent=2)
    return result


def parse_summary(summary_path: str, output_dir: str) -> None:
    """Parse the summaries of target traces"""
    with open(summary_path, 'r') as file:
        summary = json.load(file)
    for key, value in summary.items():
        content = value if isinstance(value, str) else '\n'.join(map(str, value))
        output_path = os.path.join(output_dir, f'{key}.summary')
        with open(output_path, 'w') as file:
            file.write(content)


def summarize(output_dir: str):
    summary_path = os.path.join(output_dir, 'summary.json')
    generate_summary(output_dir=output_dir)
    parse_summary(summary_path=summary_path, output_dir=output_dir)
