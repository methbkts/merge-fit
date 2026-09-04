# merge-fit

Merge two sequential activity files in the FIT format into one activity file.

`merge-fit` reads the records and session metadata from both input files, appends the
second activity after the first, adjusts cumulative distance, and writes a new FIT file
with combined session statistics.

## Requirements

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)

## Installation

Clone the repository and install its dependencies:

```sh
git clone <repository-url>
cd merge-fit
uv sync
```

The project uses the following runtime libraries:

- [`fitparse`](https://github.com/dtcooper/python-fitparse) to read FIT files
- [`fit-tool`](https://github.com/polyvertex/fit-tool) to build FIT files

## Usage

Pass the activity files in chronological order:

```sh
uv run merge-fit first-activity.fit second-activity.fit
```

By default, the output is written beside the first input file using this name:

```text
<first-file>_<second-file>_merged.fit
```

Specify a different output path with `--output` or `-o`:

```sh
uv run merge-fit first-activity.fit second-activity.fit \
  --output merged-activity.fit
```

The command prints the output path and a basic validation summary after writing the
file.

To see all options:

```sh
uv run merge-fit --help
```

## What Is Combined

- Record data from both activities
- Cumulative distance, with the second file offset by the first file's final distance
- Total elapsed and timer time
- Total calories
- Heart-rate, altitude, speed, and geographic summary values
- FIT session, event, device, sport, and activity messages

## Input Assumptions

- Both files are valid FIT activity files with compatible activity metadata.
- The first file precedes the second file in time.
- Both files contain session metadata, device metadata, sport metadata, and record
  timestamps.
- The files provide the summary fields needed to calculate the combined session.

The current implementation preserves the sport, sub-sport, and selected metadata from the
first file. If the first file does not contain a supported sub-sport, the merged activity
uses `GENERIC`. It is intended for combining two parts of one activity, not for merging
arbitrary FIT file types or unrelated activities.

The current implementation preserves selected metadata from the first file.
It is intended for combining two parts of one activity, not for merging
arbitrary FIT file types or unrelated activities.

## Development

Install development dependencies with:

```sh
uv sync --dev
```

Run linting and formatting locally:

```sh
uv run ruff check
uv run ruff format --check
```

The same checks run in GitHub Actions for pushes and pull requests.

## License

This project is licensed under the [MIT License](./LICENSE).
