# `.sketch` document for python

[Sketch](https://sketch.com) stores documents in `.sketch` format, a zipped
archive of JSON formatted data and binary data such as images.

Inspired by [sketch-hq/sketch-document](https://github.com/sketch-hq/sketch-document)

Built package is avaliable in [Pypi](https://pypi.org/project/sketch-document-py/), install with Pip
```shell
pip install sketch-document-py
```

## Sketch file format schemas and APIs.

This project contains the APIs to work with Sketch
documents and document elements in Python dataclass.

- `sketch-file-format-py`: Python dataclass type hint to strongly type objects
  representing Sketch documents, or fragments of Sketch documents in TypeScript
  projects.
- `sketch-file`: Python APIs to read and write `.sketch` files.
## Development

To build this project, you need install Python build dependency management tool [Poetry](https://python-poetry.org/), to install Poetry , follow [Poetry installation guide](https://python-poetry.org/docs/#installation)

To install nessasary deps and CLI tools, including a task runner [Poe the Poet](https://github.com/nat-n/poethepoet)(CLI executable named `poe`) that work with Poetry, run command:
> This will also install current package to your environment root

> For further usages of Poetry Install, check [Poetry Install](https://python-poetry.org/docs/cli/#install)

```shell
poetry install
```

To generate Sketch Dataclass type file, which is nessasary for build or install development, run command:
> For further usages of Poe the Poet, check [Poe the Poet Homepage](https://github.com/nat-n/poethepoet)
```shell
poe gen_types
```

To check project typing, run command:
> For further usages of Mypy, check [Mypy Documentation](https://mypy.readthedocs.io/en/stable/)
```shell
poe mypy
```

To run project test and coverage, run command:
> For further usages of Coverage, check [Coverage.py Documentation](https://coverage.readthedocs.io/en/6.3.2/)
```shell
poe test
```

To build project to wheel and tar, run command:
> For further usages of Poetry build, check [Poetry Build](https://python-poetry.org/docs/cli/#build)
```shell
poe build
```

To publish project, run command:
> For further usages of Poetry, check [Poetry Publish](https://python-poetry.org/docs/cli/#publish)
```shell
poe publish
```

For further usages of Poetry, check [Poetry Documentation](https://python-poetry.org/docs)