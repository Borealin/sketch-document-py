import ast

if __name__ == '__main__':
    node = ast.parse('''
\\\\ gegeg
def fun():
    pass
    ''')
    print(ast.dump(node, indent=4))
