from functools import reduce
from typing import Dict, Any, List, Union, Optional, Tuple, Iterable, Callable
import ast
from humps import pascalize
import re
from keyword import kwlist


def is_layer_schema(schema: Dict[str, Any]) -> bool:
    """
    Use the presence of `do_objectID` and `frame` properties as a heuristic to
    identify a schema that represents a layer.
    """
    has_frame = schema.get('properties') is not None and type(schema.get('properties').get('frame')) is dict
    has_id = schema.get('properties') is not None and type(schema['properties'].get('do_objectID')) is dict
    return has_frame and has_id


def is_group_schema(schema: Dict[str, Any]) -> bool:
    """
    Use layeriness and the presence of a `layers` array as a heuristic to
    identify a schema that represents a group.
    """
    is_layer = is_layer_schema(schema)
    has_layers = schema.get('properties') is not None and type(schema['properties'].get('layers')) is dict
    return is_layer and has_layers


def is_object_schema(schema: Dict[str, Any]) -> bool:
    """
    Does the schema represent an object/class in the model?
    """
    return schema.get('properties') is not None and '_class' in schema['properties']


def generate_field_name(key: str, other_fields: Iterable[str] = ()) -> str:
    """
    Generate a field name from a key.
    """
    new_key = key
    while new_key.startswith('_'):
        new_key = new_key[1:]
    while new_key in [*other_fields, *kwlist]:
        new_key += '_'
    return new_key


def extract_id(id_: str) -> str:
    """
    Extract the class name from an ID.
    """
    return id_.replace('#', '')


def extract_ref(ref: str) -> str:
    """
    Extract the class name from a reference.
    """
    return ref.replace('#', '').replace('/definitions/', '')


def parse_def_function(func: str) -> ast.FunctionDef:
    """
    Parse a function definition.
    """
    module = ast.parse(func)
    if len(module.body) != 1:
        raise ValueError(f'Parse function: {func} failed')
    expr = module.body[0]
    if not isinstance(expr, ast.FunctionDef):
        raise ValueError(f'Parse function: {func} failed')
    return expr


def parse_lambda_function(func: str) -> ast.Lambda:
    """
    Parse a lambda function.
    """
    module = ast.parse(func)
    if len(module.body) != 1:
        raise ValueError(f'Parse function: {func} failed')
    expr = module.body[0]
    if not isinstance(expr, ast.Expr):
        raise ValueError(f'Parse function: {func} failed')
    lambda_func = expr.value
    if not isinstance(lambda_func, ast.Lambda):
        raise ValueError(f'Parse function: {func} failed')
    return lambda_func


def parse_function_call(func_call: str) -> ast.Call:
    """
    Parse a function call.
    """
    module = ast.parse(func_call)
    if len(module.body) != 1:
        raise ValueError(f'Parse function: {func_call} failed')
    expr = module.body[0]
    if not isinstance(expr, ast.Expr):
        raise ValueError(f'Parse function: {func_call} failed')
    call = expr.value
    if not isinstance(call, ast.Call):
        raise ValueError(f'Parse function: {func_call} failed')
    return call


class DataClassBuilder:
    def __init__(self):
        self.import_statements: Dict[str, Union[ast.Import, ast.ImportFrom]] = {}
        self.class_dict: Dict[str, Tuple[Dict[str, Any], Union[ast.ClassDef, ast.Assign]]] = {}

    def check_enum_import(self):
        if 'enum' not in self.import_statements:
            self.import_statements['enum'] = ast.ImportFrom(
                module='enum',
                names=[ast.alias(name='Enum', asname=None)],
                level=0
            )

    def check_dataclasses_import(self):
        if 'dataclasses' not in self.import_statements:
            self.import_statements['dataclasses'] = ast.ImportFrom(
                module='dataclasses',
                names=[
                    ast.alias(name='dataclass', asname=None),
                    ast.alias(name='field', asname=None)
                ],
                level=0
            )

    def check_fastclasses_json_import(self):
        self.check_dataclasses_import()
        if 'fastclasses' not in self.import_statements:
            self.import_statements['fastclasses_json'] = ast.ImportFrom(
                module='fastclasses_json',
                names=[
                    ast.alias(name='dataclass_json', asname=None),
                    ast.alias(name='JSONMixin', asname=None)
                ],
                level=0
            )

    def check_typing_import(self, name: str):
        if name in ['int', 'str', 'float', 'bool', 'None']:
            return
        if 'typing' not in self.import_statements:
            self.import_statements['typing'] = ast.ImportFrom(
                module='typing',
                names=[],
                level=0
            )
        if name not in [alias.name for alias in self.import_statements['typing'].names]:
            self.import_statements['typing'].names.append(ast.alias(name=name, asname=None))

    def create_literal(self, value: Any) -> ast.Subscript:
        """
        Create a literal from a value.
        """
        self.check_typing_import('Literal')
        return ast.Subscript(
            value=ast.Name(id='Literal', ctx=ast.Load()),
            slice=ast.Constant(value=value),
            ctx=ast.Load()
        )

    def create_union(self, nodes: List[ast.AST]) -> ast.AST:
        """
        Create a union from a list of nodes.
        """
        if len(nodes) > 1:
            self.check_typing_import('Union')
            return ast.Subscript(
                value=ast.Name(id='Union', ctx=ast.Load()),
                slice=ast.Tuple(elts=nodes),
                ctx=ast.Load()
            )
        else:
            return nodes[0]

    def create_optional(self, node: ast.AST) -> ast.Subscript:
        """
        Create an optional from a node.
        """
        self.check_typing_import('Optional')
        return ast.Subscript(
            value=ast.Name(id='Optional', ctx=ast.Load()),
            slice=node,
            ctx=ast.Load()
        )

    def create_list(self, node: ast.AST) -> ast.Subscript:
        """
        Create a list from a node.
        """
        self.check_typing_import('List')
        return ast.Subscript(
            value=ast.Name(id='List', ctx=ast.Load()),
            slice=node,
            ctx=ast.Load()
        )

    def create_dict(self, key: str, value: ast.AST) -> ast.Subscript:
        """
        Create a dict from key and value.
        """
        self.check_typing_import('Dict')
        self.check_typing_import(key)
        if isinstance(value, ast.Name):
            self.check_typing_import(value.id)
        return ast.Subscript(
            value=ast.Name(id='Dict', ctx=ast.Load()),
            slice=ast.Tuple(elts=[
                ast.Name(id=key, ctx=ast.Load()),
                value
            ]),
            ctx=ast.Load()
        )

    def create_any(self) -> ast.Name:
        """
        Create an any type.
        """
        self.check_typing_import('Any')
        return ast.Name(id='Any', ctx=ast.Load())

    def generate_class_name_from_key(self, key: str) -> str:
        """
        Generate a class name from a key.
        """
        class_key = key[0].upper() + key[1:]
        while class_key in self.class_dict:
            class_key += '_'
        return class_key

    def schema_to_ast_node(
            self,
            identifier: str,
            schema: Dict[str, Any],
            is_top_level: bool
    ) -> Optional[Union[
        ast.Subscript,
        ast.Name,
        ast.ClassDef,
        ast.Constant,
        ast.AST
    ]]:
        schema_type = schema.get('type')
        if schema_type == 'string':
            if schema.get('enum') is not None:
                return self.create_union([self.create_literal(value) for value in schema['enum']])
            else:
                return ast.Name(id='str', ctx=ast.Load())
        elif schema_type == 'number':
            if schema.get('enum') is not None:
                '''
                since python does not float Literals, ignore enum case
                '''
                raise Exception('enum not supported for number')
            else:
                return ast.Name(id='float', ctx=ast.Load())
        elif schema_type == 'integer':
            if schema.get('enum') is not None:
                return self.create_union([self.create_literal(value) for value in schema['enum']])
            else:
                return ast.Name(id='int', ctx=ast.Load())
        elif schema_type == 'boolean':
            if schema.get('enum') is not None:
                return self.create_union([self.create_literal(value) for value in schema['enum']])
            else:
                return ast.Name(id='bool', ctx=ast.Load())
        elif schema_type == 'null':
            return self.create_literal(None)
        elif schema_type == 'object':
            if type(schema.get('properties')) is dict:
                required = schema.get('required', [])
                additional_props = schema.get('additionalProperties') is True
                if additional_props:
                    return self.create_dict('str', ast.Name(id='Any', ctx=ast.Load()))
                else:
                    properties = schema.get('properties', {})
                    properties = dict(sorted(properties.items(),
                                             key=lambda item: required.index(item[0]) if item[0] in required else len(
                                                 required)))
                    elements = []
                    for key, value in properties.items():
                        annotation = self.schema_to_ast_node(
                            key,
                            value,
                            False
                        )
                        if annotation is not None:
                            new_key = generate_field_name(
                                key,
                                [
                                    ann_assign.target.id
                                    for ann_assign in elements
                                    if isinstance(ann_assign, ast.AnnAssign) and isinstance(ann_assign.target, ast.Name)
                                ]
                            )
                            ann_assign = ast.AnnAssign(
                                target=ast.Name(id=new_key, ctx=ast.Store()),
                                annotation=self.create_optional(annotation) if key not in required else annotation,
                                simple=1
                            )
                            if new_key != key:
                                '''
                                class_ : str = field(metadata={
                                    "fastclasses_json": {
                                        "field_name": "_class"
                                    }
                                })
                                '''
                                ann_assign.value = parse_function_call(
                                    f'field(metadata={{"fastclasses_json": {{"field_name": "{key}"}}}})')
                            if key not in required:
                                if isinstance(ann_assign.value, ast.Call):
                                    ann_assign.value.keywords.append(ast.keyword(
                                        arg='default',
                                        value=ast.Constant(value=None)
                                    ))
                                else:
                                    ann_assign.value = ast.Constant(value=None)
                            elements.append(ann_assign)
                    self.check_fastclasses_json_import()
                    new_identifier = self.generate_class_name_from_key(identifier) if not is_top_level else identifier
                    class_def = ast.ClassDef(
                        name=new_identifier,
                        bases=[ast.Name(id='JSONMixin', ctx=ast.Load())],
                        keywords=[],
                        body=elements,
                        decorator_list=[
                            ast.Name(id='dataclass_json', ctx=ast.Load()),
                            ast.Name(id='dataclass', ctx=ast.Load())
                        ]
                    )
                    if is_top_level:
                        return class_def
                    else:
                        self.class_dict[new_identifier] = (schema, class_def)
                        return ast.Constant(value=new_identifier)
            elif type(schema.get('patternProperties')) is dict:
                ast_nodes = [
                    self.schema_to_ast_node(pattern_key, pattern_schema, False)
                    for pattern_key, pattern_schema in schema.get('patternProperties').items()
                ]
                return self.create_dict('str', self.create_union(ast_nodes))
            else:
                return self.create_any()
        elif schema_type == 'array':
            if type(schema.get('items')) is dict:
                return self.create_list(self.schema_to_ast_node(
                    identifier,
                    schema['items'],
                    False
                ))
            else:
                return self.create_list(self.create_any())
        else:
            if schema.get('const') is not None:
                if type(schema['const']) is str:
                    return self.create_literal(schema['const'])
                elif type(schema['const']) is int:
                    return self.create_literal(schema['const'])
                elif type(schema['const']) is float:
                    return self.create_literal(schema['const'])
                else:
                    raise Exception(f'Unsupported const value ${schema["const"]}')
            elif schema.get('$ref') is not None:
                if is_top_level:
                    return ast.Name(id=extract_ref(schema['$ref']), ctx=ast.Load())
                else:
                    return ast.Constant(value=extract_ref(schema['$ref']))
            elif schema.get('oneOf') is not None:
                return self.create_union([
                    self.schema_to_ast_node(f'OneOf${identifier}', item, False)
                    for item in schema['oneOf']
                ])
            else:
                return self.create_any()

    def add_schema_to_top_level_declaration(self, schema: Dict[str, Any]) -> Union[ast.ClassDef, ast.Assign]:
        identifier = extract_id(schema['$id'] if '$id' in schema else 'Unknown')
        if schema.get('enum') is not None and schema.get('enumDescriptions') is not None:
            self.check_enum_import()

            def enum_pair_reducer(acc: Dict[str, str], item: Tuple[str, str]) -> Dict[str, str]:
                return {
                    **acc,
                    (generate_field_name(re.sub(r'\W', '', pascalize(item[0])), acc.keys())): item[1]
                }

            enum_pairs = reduce(
                enum_pair_reducer,
                zip(schema['enumDescriptions'], schema['enum']),
                {}
            )
            class_def = ast.ClassDef(
                name=identifier,
                bases=[ast.Name(id='Enum', ctx=ast.Load())],
                keywords=[],
                body=[
                    ast.Assign(
                        targets=[
                            ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Constant(value=value),
                        lineno=0,
                    )
                    for name, value in enum_pairs.items()
                ],
                decorator_list=[]
            )
            self.class_dict[identifier] = (schema, class_def)
            return class_def
        else:
            definition = self.schema_to_ast_node(identifier, schema, True)
            if type(definition) is ast.ClassDef:
                self.class_dict[identifier] = (schema, definition)
                return definition
            elif definition is not None:
                assign = ast.Assign(
                    targets=[ast.Name(id=identifier, ctx=ast.Store())],
                    value=definition,
                    lineno=0
                )
                self.class_dict[identifier] = (schema, assign)
                return assign

    def build(
            self,
            before_import: Optional[Callable[['DataClassBuilder', ast.Module], None]] = None,
            before_class_def: Optional[Callable[['DataClassBuilder', ast.Module], None]] = None,
            after_class_def: Optional[Callable[['DataClassBuilder', ast.Module], None]] = None
    ) -> ast.Module:
        root = ast.Module(body=[], type_ignores=[])
        if before_import is not None:
            before_import(self, root)
        root.body.extend(
            self.import_statements.values()
        )
        if before_class_def is not None:
            before_class_def(self, root)
        root.body.extend(
            [class_def[1] for class_def in self.class_dict.values()]
        )
        if after_class_def is not None:
            after_class_def(self, root)
        return root
