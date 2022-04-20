# `.sketch` document for python

[Sketch](https://sketch.com) stores documents in `.sketch` format, a zipped
archive of JSON formatted data and binary data such as images.

Inspired by [sketch-hq/sketch-document](https://github.com/sketch-hq/sketch-document)

## Sketch file format schemas and APIs.

This project contains the APIs to work with Sketch
documents and document elements in Python dataclass.

- `sketch-file-format-py`: Python dataclass type hint to strongly type objects
  representing Sketch documents, or fragments of Sketch documents in TypeScript
  projects.
- `sketch-file`: Python APIs to read and write `.sketch` files.
