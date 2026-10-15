from pathlib import Path
from graphql import build_schema, print_schema, lexicographic_sort_schema, GraphQLArgument, GraphQLNonNull, GraphQLID
from app.schema import schema


def test_complete_contract_from_three_pdfs():
    expected=build_schema('\n'.join(Path('tests',p).read_text(encoding='utf-8-sig') for p in ('schema_pdf.graphql','finance_pdf.graphql','access_pdf.graphql')))
    protected={
        'Query':('companyUsers','accounts','concepts','accountConcepts','transactions','accountBalance','roles','role','permissions','rolePermissions'),
        'Mutation':('createCompanyUser','deactivateCompanyUser','createAccount','createConcept','assignConceptToAccount','removeConceptFromAccount','createTransaction','deleteTransaction','createRole','deactivateRole','createPermission','assignPermissionToRole','removePermissionFromRole','assignRole'),
    }
    for kind,fields in protected.items():
        for name in fields:
            expected.get_type(kind).fields[name].args['actorCompanyUserId']=GraphQLArgument(GraphQLNonNull(GraphQLID))
    actual=build_schema(schema.as_str())
    for contract in (expected,actual):
        for kind in contract.type_map.values():
            kind.description=None
            for field in getattr(kind,'fields',{}).values():
                field.description=None
    assert print_schema(lexicographic_sort_schema(actual))==print_schema(lexicographic_sort_schema(expected))
    assert Path('schema.graphql').read_text(encoding='utf-8').strip()==schema.as_str().strip()
