import ast
import unittest
from sketch_document_py.sketch_file_format.scripts.utils import DataClassBuilder, extract_id


class SchemaToASTNodeTest(unittest.TestCase):

    def schema_to_ast_node(self, schema) -> str:
        if isinstance(schema, dict) and '$id' not in schema:
            schema['$id'] = 'TestType'
        dataclass_builder = DataClassBuilder()
        dataclass_builder.add_schema_to_top_level_declaration(schema)
        root = ast.Module(body=[], type_ignores=[])
        for schema, class_def in dataclass_builder.class_dict.values():
            root.body.append(class_def)
        return ast.unparse(root)

    def test_string(self):
        schema = {'type': 'string'}
        assert self.schema_to_ast_node(schema) == 'TestType = str'

    def test_string_enum(self):
        schema = {'type': 'string', 'enum': ['foo', 'bar']}
        assert self.schema_to_ast_node(schema) == 'TestType = Union[Literal[\'foo\'], Literal[\'bar\']]'

    def test_number(self):
        schema = {'type': 'number'}
        assert self.schema_to_ast_node(schema) == 'TestType = float'

    def test_number_enum(self):
        schema = {'type': 'number', 'enum': [1, 2]}
        try:
            self.schema_to_ast_node(schema)
            assert False
        except Exception:
            assert True

    def test_integer(self):
        schema = {'type': 'integer'}
        assert self.schema_to_ast_node(schema) == 'TestType = int'

    def test_integer_enum(self):
        schema = {'type': 'integer', 'enum': [1, 2]}
        assert self.schema_to_ast_node(schema) == 'TestType = Union[Literal[1], Literal[2]]'

    def test_boolean(self):
        schema = {'type': 'boolean'}
        assert self.schema_to_ast_node(schema) == 'TestType = bool'

    def test_null(self):
        schema = {'type': 'null'}
        assert self.schema_to_ast_node(schema) == 'TestType = Literal[None]'

    def test_empty_object(self):
        schema = {}
        assert self.schema_to_ast_node(schema) == 'TestType = Any'

    def test_object(self):
        schema = {'type': 'object', 'properties': {'foo': {'type': 'string'}, 'bar': {'type': 'number'}}}
        assert self.schema_to_ast_node(schema) == '''@dataclass_json
@dataclass
class TestType(JSONMixin):
    foo: Optional[str] = None
    bar: Optional[float] = None'''

    def test_nested_objects(self):
        schema = {
            "type": "object",
            "properties": {
                "foo": {
                    "type": "object",
                    "properties": {
                        "bar": {
                            "type": "string"
                        },
                        "baz": {
                            "type": "number"
                        }
                    }
                }
            }
        }
        assert self.schema_to_ast_node(schema) == '''@dataclass_json
@dataclass
class TestTypeFoo(JSONMixin):
    bar: Optional[str] = None
    baz: Optional[float] = None

@dataclass_json
@dataclass
class TestType(JSONMixin):
    foo: Optional['TestTypeFoo'] = None'''

    def test_required_object_properties(self):
        schema = {
            "type": "object",
            "properties": {
                "foo": {
                    "type": "string"
                },
                "bar": {
                    "type": "number"
                }
            },
            "required": [
                "foo",
                "bar"
            ]
        }
        assert self.schema_to_ast_node(schema) == '''@dataclass_json
@dataclass
class TestType(JSONMixin):
    foo: str
    bar: float'''

    def test_objects_allow_additional_properties(self):
        schema = {
            'type': 'object',
            'properties': {'foo': {'type': 'string'}, 'bar': {'type': 'number'}},
            'additionalProperties': True,
        }
        assert self.schema_to_ast_node(schema) == '''TestType = Dict[str, Any]'''

    def test_object_pattern_properties(self):
        schema = {
            'type': 'object',
            'patternProperties': {
                'foo': {
                    'type': 'string',
                },
                'bar': {
                    '$ref': '#Bar'
                }
            }
        }
        assert self.schema_to_ast_node(schema) == '''TestType = Dict[str, Union[str, 'Bar']]'''

    def test_simple_array(self):
        schema = {'type': 'array'}
        assert self.schema_to_ast_node(schema) == 'TestType = List[Any]'

    def test_typed_array(self):
        schema = {'type': 'array', 'items': {'type': 'string'}}
        assert self.schema_to_ast_node(schema) == 'TestType = List[str]'

    def test_string_constant(self):
        schema = {'const': 'foobar'}
        assert self.schema_to_ast_node(schema) == 'TestType = Literal[\'foobar\']'

    def test_number_constant(self):
        schema = {'const': 1}
        assert self.schema_to_ast_node(schema) == 'TestType = Literal[1]'

    def test_refs(self):
        schema = {'$ref': '#Artboard'}
        assert self.schema_to_ast_node(schema) == 'TestType = Artboard'

    def test_arrays_of_refs(self):
        schema = {'type': 'array', 'items': {'$ref': '#Artboard'}}
        assert self.schema_to_ast_node(schema) == 'TestType = List[\'Artboard\']'

    def test_oneOf(self):
        schema = {
            'oneOf': [{'type': 'string'}, {'type': 'number'}],
        }
        assert self.schema_to_ast_node(schema) == 'TestType = Union[str, float]'

    def test_refs_in_oneOf(self):
        schema = {
            'oneOf': [{'$ref': '#Artboard'}, {'$ref': '#Group'}],
        }
        assert self.schema_to_ast_node(schema) == 'TestType = Union[\'Artboard\', \'Group\']'


class SchemaToTopLevelDeclarationTest(unittest.TestCase):

    def schema_to_top_level_declaration(self, schema) -> str:
        dataclass_builder = DataClassBuilder()
        dataclass_builder.add_schema_to_top_level_declaration(schema)
        return ast.unparse(dataclass_builder.build())

    def test_top_level_object_definition(self):
        schema = {
            '$id': '#FooBar',
            'description': 'A foobar',
            'type': 'object',
            'properties': {'foo': {'type': 'string'}, 'bar': {'type': 'string'}},
        }
        assert self.schema_to_top_level_declaration(schema) == '''from typing import Optional
from dataclasses import dataclass, field
from fastclasses_json import dataclass_json, JSONMixin

@dataclass_json
@dataclass
class FooBar(JSONMixin):
    foo: Optional[str] = None
    bar: Optional[str] = None'''

    def test_top_level_enum_definitions(self):
        schema = {
            '$id': '#MyEnum',
            'description': 'My enum',
            'type': 'integer',
            'enum': [0, 1, 2],
            'enumDescriptions': ['Zero', 'One', 'Two'],
        }
        assert self.schema_to_top_level_declaration(schema) == '''from enum import Enum

class MyEnum(Enum):
    Zero = 0
    One = 1
    Two = 2

    @classmethod
    def _missing_(cls, value):
        return MyEnum.Zero'''
