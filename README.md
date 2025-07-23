# URSA

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![lint](https://github.com/anmorgunov/ursa-evaluations/actions/workflows/lint.yml/badge.svg)

a library for validating, canonicalizing, and adapting retrosynthesis model outputs to the ursa benchmark standard.

## architectural principles

`ursa`'s design is guided by three principles to ensure it is robust, flexible, and maintainable.

1.  **decoupled adaptation**: the core system is agnostic to model output formats. all model-specific parsing and logic is encapsulated in pluggable "adapters", allowing the benchmark to support any model without changing the core pipeline.
2.  **inviolate contracts**: data is validated at every boundary. schemas define the expected structure of both the final canonical format and, within each adapter, the raw input. the system refuses to operate on ambiguous or invalid data.
3.  **deterministic & auditable pipeline**: every transformation is deterministic and traceable. run outputs are uniquely identified by a hash of their inputs, and the entire process is logged in a manifest. this ensures results are reproducible and verifiable.

## processing pipeline

the main `ursa.core.process_model_run` function orchestrates the workflow:
1.  **run identification**: generates a deterministic hash from the model name and source file contents.
2.  **adaptation**: invokes the specified model `adapter` to parse the raw data and transform it into the canonical `BenchmarkTree` format.
3.  **deduplication**: generates a canonical, order-invariant signature for each tree to filter out duplicate routes.
4.  **serialization**: writes the unique, validated routes to a compressed json file and creates a manifest with run statistics.

## adding a new model adapter

the adapter is the bridge from a model's unique output to `ursa`'s canonical format. the adapter is responsible for *all* parsing and reconstruction, regardless of how unstructured the raw data is.

for example, assume "new model" outputs a flat list of reaction smiles for a given target:

```json
// raw output from new model
[
  "c1ccccc1.CC(=O)Cl>>c1ccc(C(C)=O)cc1",
  "c1ccc(C(C)=O)cc1.N>>c1ccc(C(=N)C)cc1"
]
```

here is how to build an adapter for it.

#### **1. implement the adapter**

create `ursa/adapters/new_model_adapter.py`. the public `adapt` method is the entry point. its job is to parse the raw data—in this case, a list of strings—and yield complete `benchmarktree` objects.

```python
# in ursa/adapters/modely_adapter.py
from ursa.adapters.base_adapter import BaseAdapter
# ... other imports

class NewModelAdapter(BaseAdapter):
    """Adapter fore New Model's flat reaction list format."""

    def adapt(self, raw_data: Any, target: TargetInfo) -> Generator[BenchmarkTree, None, None]:
        if not isinstance(raw_data, list):
            return # fail fast on wrong data type

        try:
            # this is where bespoke reconstruction logic lives.
            # you parse the flat list and build the tree in memory.
            reconstructed_tree = self._reconstruct_tree_from_list(raw_data, target.smiles)

            # now, convert the reconstructed tree to the benchmark format.
            benchmark_tree = self._build_benchmark_tree(reconstructed_tree, target)
            yield benchmark_tree
        except UrsaException as e:
            logger.warning(f"Could not process route for {target.id}: {e}")
```

#### **2. implement reconstruction logic**

the hard work occurs in private helpers. you might parse the reaction smiles, build a graph of dependencies, and then traverse that graph to create the final tree.

```python
# ... inside NewModelAdapter ...

    def _reconstruct_tree_from_list(self, reactions: list[str], target_smiles: str) -> MyInternalNode:
        # this is the model-specific problem. parse strings, map products
        # to reactants, build a graph, find the path to the target.
        # return your own internal representation of the tree.
        ...

    def _build_benchmark_tree(self, internal_node: MyInternalNode, target: TargetInfo) -> BenchmarkTree:
        # this is a standard recursive function that walks your
        # internal tree and creates the canonical MoleculeNode objects.
        ...
```

#### **3. write tests**

create a corresponding test file in `tests/adapters/test_newmodel_adapter.py`. tests must cover:
*   successful transformation of valid data.
*   correct handling of routes containing invalid smiles.
*   correct handling of other logical failures (e.g., mismatched root molecule).

#### **4. create a processing script**

copy an existing script in the `scripts/` directory and modify it to use your new adapter.

```python
# in scripts/process_newmodel_output.py

from ursa.adapters.newmodel_adapter import NewModelAdapter
# ...

# instantiate and use your new adapter
adapter = NewModelAdapter()
process_model_run(..., adapter=adapter, ...)
```

as a result, to support outputs of a new model, all you need is to write one new adapter file, no need to change any of the core logic.