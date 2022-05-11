import ast
import enum
from typing import Any, Dict, Optional

from .schema_fetcher import get_schemas, Schemas
from .utils import is_layer_schema, is_group_schema, is_object_schema, DataClassBuilder, extract_id, \
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

    all_definitions: Dict[str, Any] = {
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

    def build_class_map() -> ast.AnnAssign:
        class_map = {}
        for sketch_class in all_classes:
            for schema in definitions.values():
                klass = schema['properties']['_class'] if 'properties' in schema and '_class' in schema[
                    'properties'] else None
                if type(klass) is dict and 'const' in klass and klass['const'] == sketch_class and type(schema) is dict:
                    class_map[sketch_class] = extract_id(schema['$id'])
                    break
        return ast.AnnAssign(
            target=ast.Name(id='class_map', ctx=ast.Store()),
            annotation=ast.Subscript(
                value=ast.Name(id='Dict', ctx=ast.Load()),
                slice=ast.Tuple(elts=[
                    ast.Name(id='str', ctx=ast.Load()),
                    ast.Subscript(
                        value=ast.Name(id='Type', ctx=ast.Load()),
                        slice=ast.Name(id='JSONMixin', ctx=ast.Load()),
                        ctx=ast.Load()
                    )
                ], ctx=ast.Load())
            ),
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
            simple=1,
        )

    def insert_encoder_and_decoder_to_class(builder: DataClassBuilder):
        to_object_call = ast.Name(id='to_object', ctx=ast.Load())
        list_to_object_lambda = parse_lambda_function(
            'lambda lst: [to_object(x) for x in lst]'
        )
        for element in [
            element
            for identifier, (schema, cdef) in builder.class_dict.items()
            if isinstance(cdef, ast.ClassDef)
            for element in cdef.body
            if isinstance(element, ast.AnnAssign)
        ]:
            union_type = check_ann_assign_contains_union(element)
            if union_type is not UnionAnnAssignType.NOT_UNION:
                old_value = element.value
                new_value = parse_function_call(
                    'field(metadata={"fastclasses_json": {}})'
                ) if not isinstance(old_value, ast.Call) else old_value
                if not isinstance(old_value, ast.Call) and old_value is not None:
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
                    if union_type is UnionAnnAssignType.UNION or union_type is UnionAnnAssignType.OPTIONAL_UNION:
                        fastclasses_dict_value.keys.append(ast.Constant(value='decoder'))
                        fastclasses_dict_value.values.append(to_object_call)
                    elif union_type is UnionAnnAssignType.LIST_UNION:
                        fastclasses_dict_value.keys.append(ast.Constant(value='decoder'))
                        fastclasses_dict_value.values.append(list_to_object_lambda)
                element.value = new_value

    def before_class_def(builder: DataClassBuilder, root: ast.Module) -> None:
        builder.check_typing_import('Type')
        to_object_func = parse_def_function('''def to_object(obj: 'Any') -> Optional['Any']:
    if obj is not None and isinstance(obj, dict) and '_class' in obj.keys() and (obj['_class'] in class_map.keys()):
        return class_map[obj['_class']].from_dict(obj)
    else:
        return obj''')
        root.body.append(to_object_func)

    def after_class_def(builder: DataClassBuilder, root: ast.Module) -> None:
        insert_encoder_and_decoder_to_class(builder)
        root.body.append(build_class_map())

    module_ast = data_class_builder.build(
        None,
        before_class_def,
        after_class_def
    )
    # print(ast.dump(module_ast, indent=4))
    with open(path, 'w') as f:
        f.write(ast.unparse(module_ast))


class UnionAnnAssignType(enum.Enum):
    UNION = 1
    LIST_UNION = 2
    OPTIONAL_UNION = 3
    NOT_UNION = 4


def check_ann_assign_contains_union(ann_assign: ast.AnnAssign) -> UnionAnnAssignType:
    """
    Check if the annotation assign contains a Union annotation.
    e.g. a: Union[int, str], b: List[Union[int, str]], c: Optional[Union[int, str]]
    :param ann_assign: input ann_assign
    """

    def check_subscript(subscript: ast.Subscript) -> UnionAnnAssignType:
        if isinstance(subscript.value, ast.Name):
            if subscript.value.id == 'Union':
                return UnionAnnAssignType.UNION
            elif subscript.value.id == 'List' and isinstance(subscript.slice, ast.Subscript):
                if check_subscript(subscript.slice) == UnionAnnAssignType.UNION:
                    return UnionAnnAssignType.LIST_UNION
            elif subscript.value.id == 'Optional' and isinstance(subscript.slice, ast.Subscript):
                if check_subscript(subscript.slice) == UnionAnnAssignType.UNION:
                    return UnionAnnAssignType.OPTIONAL_UNION
        return UnionAnnAssignType.NOT_UNION

    if isinstance(ann_assign.annotation, ast.Subscript):
        return check_subscript(ann_assign.annotation)
    return UnionAnnAssignType.NOT_UNION


def main():
    import argparse
    from os.path import join, dirname, abspath
    parser = argparse.ArgumentParser(description='Generate Sketch dataclass typing file.')
    parser.add_argument('--out', type=str, help='Path to Sketch JSON schema file, default ../types.py',
                        default=join(dirname(dirname(abspath(__file__))), 'types.py'))
    parser.add_argument('--version', type=str,
                        help='Sketch Schema version, follow @sketch-hq/sketch-file-format npm package version, default latest',
                        default='latest')
    args = parser.parse_args()
    generate(args.out, get_schemas(args.version))


if __name__ == '__main__':
    main()
