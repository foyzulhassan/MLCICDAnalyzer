# SAWRA
SAWRA (<b>S</b>ynthesizing GitHub <b>A</b>ctions <b>W</b>orkflows via LLM-Based <b>R</b>untime <b>A</b>nalysis) uses runtime information to automatically generate workflows, or Continuous Integration (CI) configurations, for GitHub Actions.

To generate workflows, SAWRA first runs and <i>traces</i> your test scripts in your local testing environment. It then parses these traces into actionable runtime information and uses heuristics to <i>build</i> a base workflow. SAWRA <i>refines</i> this workflow in conversation with a Large Language Model (LLM), providing it with relevant runtime information to aid its decisions.

The technical details of SAWRA, as well as our evaluation, can be found on [Zenodo](https://zenodo.org/records/17101180?preview=1&token=eyJhbGciOiJIUzUxMiJ9.eyJpZCI6ImFjZTU1YjkyLTM0ZTktNDBkMi1hMzVlLTA1OGU0OWRkNDVkNyIsImRhdGEiOnt9LCJyYW5kb20iOiI3YjUyY2FjYmVlM2QwN2M3MTAwYTM4ZjBhMmYzZDE0ZiJ9.y0QdyaIgSLwGWiseDcHa-HBpqMBpVo2SQw8BPureCrThhxg4NcCUOcA32A2QhpPyRT--fm80-hpfxPKcjFzmeA).

## Dependencies
To install the dependencies that SAWRA uses, run the following commands:
```bash
sudo apt-get install -y ltrace strace
go install github.com/rhysd/actionlint/cmd/actionlint@latest
```

## Installation
To build SAWRA from source, run the following commands:
```bash
cd sawra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make
```
The same build is provided in our releases.

## Usage
To run SAWRA, you must complete and pass it the following configuration file:
```toml
# name of the project
project_name = ""

# name of the workflow to be produced (will be used to create the output directory)
workflow_name = ""

# ordered list of absolute paths to target scripts 
target_paths = []

# absolute path to a directory where outputs will be stored
output_dir = ""

# absolute path to a directory of the repository
repository_dir = ""

# absolute path to a pip requirements file
requirements_path = ""

# absolute path to a directory to run targets in
working_dir = ""

# weights for Multi-Criteria Decision Making (MCDM) to distribute steps such that:
# - the difference in duration between each step is minimized
# - the total number of steps is maximized
step_mcdm_weights = [0.6, 0.4]

# number of potential step chunks to consider when distributing commands
step_chunk_count = 100000

# job duration thresholds over which syntax can be recommended
recommendation_threshold = { concurrency = 138, fail_fast = 66, timeout_minutes = 319 }

# multipliers to apply to job durations to determine syntax values
recommendation_multiplier = { timeout_minutes = 13 }

# OpenAI configuration
openai = { chat_model = "gpt-4o-mini", embedding_model = "text-embedding-ada-002", api_key = "" }

# Qdrant server configuration
# - the API key should usually be the same as the openai API key
qdrant = { hostname = "localhost", port = "6333", api_key = "" }
```

You must have a [Qdrant](https://qdrant.tech/) instance running, and it must be registered in the configuration file. To quickly create a local instance, run the following commands:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

You can run the following commands to generate a workflow:
```bash
sawra/sawra -mn PATH_TO_CONFIG
```
The final workflow is called "workflow_name.hybrid.yaml" where "workflow_name" is specified in the configuration file. It will be dumped into the output directory mentioned in the same file.
