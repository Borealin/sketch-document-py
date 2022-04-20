import ast
from typing import Any, Dict, Optional

from schema_fetcher import get_schemas, Schemas
from utils import is_layer_schema, is_group_schema, is_object_schema, DataClassBuilder, extract_id, \
    parse_lambda_function, parse_def_function, parse_function_call
import sys


def generate(path: str, schemas: Schemas):
    definitions: Dict[str, Any] = {
        **schemas.document.get("definitions", {}),
        **schemas.fileFormat.get('definitions', {}),
        **schemas.meta.get('definitions', {}),
        **schemas.user.get('definitions', {}),
    }
    contents = {
        **schemas.fileFormat,
        '$id': '#Contents',
    }
    document = {
        **schemas.document,
        '$id': '#Document',
    }
    any_layer = {
        "description": "Union of all layers",
        "$id": "#AnyLayer",
        "oneOf": [
            {
                "$ref": schema['$id']
            }
            for schema in definitions.values()
            if is_layer_schema(schema)
        ]
    }
    any_group = {
        "description": "Union of all group layers",
        "$id": "#AnyGroup",
        "oneOf": [
            {
                "$ref": schema['$id']
            }
            for schema in definitions.values()
            if is_group_schema(schema)
        ]
    }
    any_object = {
        "description": "Union of all objects, i.e. objects with a _class property",
        "$id": "#AnyObject",
        "oneOf": [
            {
                "$ref": schema['$id']
            }
            for schema in definitions.values()
            if is_object_schema(schema)
        ]
    }

    def map_definitions(schema: Dict[str, Any]) -> str:
        klass = schema['properties']['_class'] if 'properties' in schema and '_class' in schema['properties'] else None
        return str(klass['const']) if type(klass) is dict and 'const' in klass else ''

    all_classes = list(set(sorted([
        klass
        for klass in [
            map_definitions(schema)
            for schema in definitions.values()
        ]
        if len(klass) > 0
    ])))

    class_values = {
        "description": "Enum of all possible _class property values",
        "$id": "#ClassValue",
        "enum": all_classes,
        "enumDescriptions": all_classes
    }

    all_definitions = {
        **definitions,
        'Contents': contents,
        'Document': document,
        'AnyLayer': any_layer,
        'AnyGroup': any_group,
        'AnyObject': any_object,
        'ClassValue': class_values
    }
    data_class_builder = DataClassBuilder()
    for definition in all_definitions.values():
        data_class_builder.add_schema_to_top_level_declaration(definition)

    def build_class_map() -> ast.Assign:
        class_map = {}
        for sketch_class in all_classes:
            for schema in definitions.values():
                klass = schema['properties']['_class'] if 'properties' in schema and '_class' in schema[
                    'properties'] else None
                if type(klass) is dict and 'const' in klass and klass['const'] == sketch_class and type(schema) is dict:
                    class_map[sketch_class] = extract_id(schema['$id'])
                    break
        return ast.Assign(
            targets=[
                ast.Name(id='class_map', ctx=ast.Store())
            ],
            value=ast.Dict(
                keys=[
                    ast.Constant(value=key)
                    for key in class_map.keys()
                ],
                values=[
                    ast.Name(id=value, ctx=ast.Load())
                    for value in class_map.values()
                ]
            ),
            lineno=0,
        )

    def insert_encoder_and_decoder_to_class(builder: DataClassBuilder):
        to_object_call = ast.Name(id='to_object', ctx=ast.Load())
        list_to_object_lambda = parse_lambda_function(
            'lambda lst: [to_object(x) for x in lst if x is not None]'
        )

        def insert_encoder_and_decoder(
                class_def: ast.ClassDef,
                field_name: str,
                encoder: Optional[ast.expr] = None,
                decoder: Optional[ast.expr] = None
        ):
            layers_ann_assign = next(
                element
                for element in class_def.body
                if isinstance(element, ast.AnnAssign)
                and isinstance(element.target, ast.Name)
                and element.target.id == field_name
            )
            if layers_ann_assign is not None:
                old_value = layers_ann_assign.value
                new_value = old_value
                if not isinstance(old_value, ast.Call):
                    new_value = parse_function_call('field(metadata={"fastclasses_json": {}})')
                    if old_value is not None:
                        new_value.keywords.append(ast.keyword(
                            arg='default',
                            value=old_value
                        ))
                fastclasses_dict_value = None
                for keyword in new_value.keywords:
                    if keyword.arg == 'metadata' and isinstance(keyword.value, ast.Dict):
                        for key, value in zip(keyword.value.keys, keyword.value.values):
                            if isinstance(key, ast.Constant) \
                                    and key.value == 'fastclasses_json' \
                                    and isinstance(value, ast.Dict):
                                fastclasses_dict_value = value
                                break
                if fastclasses_dict_value is not None:
                    if encoder is not None:
                        fastclasses_dict_value.keys.append(ast.Constant(value='encoder'))
                        fastclasses_dict_value.values.append(encoder)
                    if decoder is not None:
                        fastclasses_dict_value.keys.append(ast.Constant(value='decoder'))
                        fastclasses_dict_value.values.append(decoder)
                layers_ann_assign.value = new_value

        for identifier, (schema, cdef) in builder.class_dict.items():
            if is_group_schema(schema):
                insert_encoder_and_decoder(
                    class_def=cdef,
                    field_name='layers',
                    encoder=None,
                    decoder=list_to_object_lambda
                )

    def before_class_def(builder: DataClassBuilder, root: ast.Module) -> None:
        to_object_func = parse_def_function('''def to_object(obj: Dict[str, Any]) -> Optional['AnyObject']:
    if (obj is not None) and ('_class' in obj.keys()) and (obj['_class'] in class_map.keys()):
        return class_map[obj['_class']].from_dict(obj)
    else:
        return None''')
        root.body.append(to_object_func)

    def after_class_def(builder: DataClassBuilder, root: ast.Module) -> None:
        insert_encoder_and_decoder_to_class(builder)
        root.body.append(build_class_map())

    module_ast = data_class_builder.build(
        None,
        before_class_def,
        after_class_def
    )
    print(ast.dump(module_ast, indent=4))
    with open(path, 'w') as f:
        f.write(ast.unparse(module_ast))


if __name__ == '__main__':
    argv = sys.argv
    if len(argv) < 2:
        print('missing output file path')
        sys.exit(1)
    out_path = argv[1]
    version = argv[2] if len(argv) > 2 else 'latest'
    generate(out_path, get_schemas(version))
