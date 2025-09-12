# SAWRA
SAWRA (<b>S</b>ynthesizing GitHub <b>A</b>ctions <b>W</b>orkflows via LLM-Based <b>R</b>untime <b>A</b>nalysis) uses runtime information to automatically synthesize workflows, or Continuous Integration (CI) configurations, for GitHub Actions.

To generate workflows, SAWRA first runs and <i>traces</i> your test scripts in your local testing environment. It then parses these traces into actionable runtime information and uses heuristics to <i>build</i> a base workflow. SAWRA <i>refines</i> this workflow in conversation with a Large Language Model (LLM), providing it with relevant runtime information to aid its decisions.

The technical details of SAWRA, as well as our evaluation, can be found on [Zenodo](https://zenodo.org/records/17101180?preview=1&token=eyJhbGciOiJIUzUxMiJ9.eyJpZCI6ImFjZTU1YjkyLTM0ZTktNDBkMi1hMzVlLTA1OGU0OWRkNDVkNyIsImRhdGEiOnt9LCJyYW5kb20iOiI3YjUyY2FjYmVlM2QwN2M3MTAwYTM4ZjBhMmYzZDE0ZiJ9.y0QdyaIgSLwGWiseDcHa-HBpqMBpVo2SQw8BPureCrThhxg4NcCUOcA32A2QhpPyRT--fm80-hpfxPKcjFzmeA).

## Dependencies
SAWRA depends on many tools that cannot be bundled into its distributions. Because some of these tools are only available on Linux, <i>SAWRA cannot be used on Windows or MacOS, and thus it cannot produce workflows that use them.</i> <b>It is recommended to run SAWRA in a Docker container as a root user to avoid issues related to dependency resolution.</b>

To install the tools that SAWRA depends on:
```bash
apt-get install -y ltrace strace
go install github.com/rhysd/actionlint/cmd/actionlint@latest
```

## Installation
You can install SAWRA by downloading [the released archive](releases) or by building it from source into dist/:
```bash
cd sawra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make
```
You must extract the archive and add it to PATH to use it.

## Usage
You must complete and pass this TOML configuration file to SAWRA:
```toml
# The name of the project.
project_name = ""

# The name of the workflow to be produced.
# - This name will be used to create the final workflow (i.e. <workflow_name>.hybrid.yaml)
workflow_name = ""

# An ordered list of absolute paths to the user-provided test scripts.
# - Each test script represents a seperate job in the workflow.
# - The order of the paths will determine the order of the jobs in the workflow.
# - The scripts MUST be bash scripts.
target_paths = []

# An absolute path to a directory where outputs will be stored.
# - During workflow generation, various artifacts will be stored here.
# - This directory MUST exist prior to the execution.
output_dir = ""

# An absolute path to the root of the repository being tested.
repository_dir = ""

# An absolute path to a pip requirements file.
# - If no pip requirements are explicitly defined, point to an empty requirements.txt file.
requirements_path = ""

# An absolute path to a directory to run the user-provided test scripts in.
# - Usually, this is the same of the root of the repository being tested (i.e. repository_dir)
working_dir = ""

# The weights for Multi-Criteria Decision Making (MCDM) to distribute steps such that:
# 1. The difference in duration between each step is minimized.
# 2. The total number of steps is maximized.
step_mcdm_weights = [0.6, 0.4]

# The number of potential step chunks to consider when distributing commands.
# - Additional chunks can result in improved step distributions but require a significant amount of time.
step_chunk_count = 100000

# The job duration thresholds over which workflow components can be recommended.
recommendation_threshold = { concurrency = 138, fail_fast = 66, timeout_minutes = 319 }

# The multipliers to apply to job durations to determine syntax values.
# - For timeout_minutes, the multiplier is applied to job minutes, not seconds.
#   However, the associated technical paper lists the converted version for seconds.
recommendation_multiplier = { timeout_minutes = 13 }

# The configurations for OpenAI.
openai = { chat_model = "gpt-4o-mini", embedding_model = "text-embedding-ada-002", api_key = "" }

# The configurations for Qdrant.
# - The API key should be the same as the OpenAI API key.
qdrant = { hostname = "localhost", port = "6333", api_key = "" }
```

You must also have access to [Qdrant](https://qdrant.tech/). To quickly create a local instance:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

To generate a new workflow named "workflow_name.hybrid.yaml" that will be dumped into "output_dir":
```bash
sawra -mn --method hybrid PATH_TO_CONFIG
```
