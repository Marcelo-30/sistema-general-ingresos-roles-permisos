"""Compara el contrato público con el esquema de las páginas 3–6 del PDF."""
from pathlib import Path
from graphql import build_schema, lexicographic_sort_schema, print_schema
from app.schema import schema


def contract(value):
    # El orden y las descripciones no cambian el contrato GraphQL.
    for kind in value.type_map.values():
        kind.description = None
    return print_schema(lexicographic_sort_schema(value))


def test_contrato_exacto_del_pdf():
    expected = build_schema(Path(__file__).with_name('schema_pdf.graphql').read_text(encoding='utf-8'))
    actual = build_schema(schema.as_str())
    # Las operaciones de la actividad 3 deben permanecer intactas al extenderla.
    for type_name, old in expected.type_map.items():
        if type_name.startswith('__'):
            continue
        new = actual.get_type(type_name)
        assert new is not None
        if hasattr(old, 'fields'):
            for field_name, field in old.fields.items():
                assert str(new.fields[field_name].type) == str(field.type)
                if hasattr(field, 'args'):
                    assert {k: str(v.type) for k, v in new.fields[field_name].args.items()} == {k: str(v.type) for k, v in field.args.items()}
            if type_name not in ('Query', 'Mutation'):
                assert set(new.fields) == set(old.fields)
    assert Path('schema.graphql').read_text(encoding='utf-8').strip() == schema.as_str().strip()
