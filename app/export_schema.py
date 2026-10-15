from pathlib import Path
from .schema import schema

if __name__ == '__main__':
    Path('schema.graphql').write_text(schema.as_str() + '\n', encoding='utf-8')
    print('Esquema exportado a schema.graphql.')
