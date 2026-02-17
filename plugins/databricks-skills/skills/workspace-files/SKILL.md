---
name: workspace-files
description: >
  Explore Databricks workspace files using the Databricks CLI. Use when listing,
  browsing, or pulling files from Databricks workspaces into context for code review,
  debugging, or understanding existing notebooks and scripts. Supports .py, .sql, and .ipynb files.
allowed-tools: Read, Bash
---

# Databricks Workspace Files

## Overview

This skill provides workflows for exploring and retrieving code from Databricks workspaces using the Databricks CLI.

## Prerequisites

The Databricks CLI must be installed and configured:

```bash
databricks auth profiles
```

## Core Operations

### List workspace contents

```bash
databricks workspace list /path/to/directory
```

### Recursive listing with helper script

```bash
python scripts/list_workspace.py /path/to/directory --recursive --max-depth 3
```

### Export a file

```bash
databricks workspace export /path/to/notebook --format SOURCE
```

### Save to local file for analysis

```bash
databricks workspace export /path/to/notebook --format SOURCE -o /tmp/notebook.py
```

## Workflow

1. List the relevant root directory (`/Repos`, `/Users/<email>`, `/Shared`)
2. Navigate through directories until the target is found
3. Export files with `--format SOURCE`
4. For detailed analysis, save locally and use the Read tool

## Common Paths

- `/Repos` — Git-connected repositories
- `/Users/<email>` — User home directories
- `/Shared` — Shared workspace files

## Error Handling

- **RESOURCE_DOES_NOT_EXIST** — Verify the path by listing the parent directory
- **PERMISSION_DENIED** — Check workspace access permissions
- **Authentication errors** — Run `databricks auth profiles`
