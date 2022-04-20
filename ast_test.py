from typing import Dict
import ast

if __name__ == '__main__':
    new_ast = ast.parse('''
a = {
    'efe':FFF
}''').body[0]
    print(ast.dump(new_ast, indent=4))
    print(ast.unparse(new_ast))
