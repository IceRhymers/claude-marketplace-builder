---
name: lineage
description: >
  Explore Databricks Unity Catalog data lineage. Use when tracing data flow between tables,
  understanding how data assets are connected, finding upstream data sources or downstream
  consumers, or investigating column-level data dependencies.
allowed-tools: Read, Bash
---

# Databricks Lineage

## Overview

Trace data lineage at both table and column levels in Databricks Unity Catalog. Discover how data assets are connected across notebooks, jobs, pipelines, and dashboards.

## Prerequisites

Databricks CLI configured with Unity Catalog lineage tracking enabled:

```bash
databricks auth profiles
```

## Core Operations

### Table lineage

```bash
python scripts/get_table_lineage.py <catalog>.<schema>.<table>
python scripts/get_table_lineage.py main.sales.orders --direction upstream
```

### Column lineage

```bash
python scripts/get_column_lineage.py <catalog>.<schema>.<table> <column>
python scripts/get_column_lineage.py main.sales.orders total_amount --direction upstream
```

### Search and explore

```bash
python scripts/search_lineage.py <pattern> --catalog main --depth 2
```

## Workflow: Impact Analysis

1. Check downstream consumers before schema changes:
   ```bash
   python scripts/get_table_lineage.py catalog.schema.table --direction downstream
   ```
2. For column changes, check column dependencies:
   ```bash
   python scripts/get_column_lineage.py catalog.schema.table column_name --direction downstream
   ```
3. Pull affected notebooks into context with the `workspace-files` skill

## Workflow: Data Discovery

1. Search for tables by domain: `python scripts/search_lineage.py sales --depth 2`
2. Explore the lineage graph to understand pipeline architecture
3. Pull relevant notebooks/scripts into context for transformation details

## Lineage Entity Types

| Entity | Description |
|--------|-------------|
| TABLE | Unity Catalog managed or external tables |
| NOTEBOOK | Databricks notebooks that read/write data |
| JOB | Scheduled job runs |
| PIPELINE | Delta Live Tables pipelines |
| DASHBOARD | SQL dashboards that query tables |
