import json
import secrets
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.factory import create_app

records = []
reports = {}


def pytest_runtest_logreport(report):
    if report.when == "call" or report.failed:
        reports[report.nodeid.split("::")[-1]] = report.outcome



def redact(obj):
    if isinstance(obj, dict):
        return {key: ('<oculto>' if key in {'password', 'token', 'passwordHash'} else redact(val))
                for key, val in obj.items()}
    if isinstance(obj, list):
        return [redact(val) for val in obj]
    return obj


@pytest.fixture
def api(tmp_path, request):
    settings = Settings('sqlite:///' + (tmp_path / 'test.db').as_posix(),
                        secrets.token_urlsafe(48), secrets.token_urlsafe(48))
    app = create_app(settings)
    with TestClient(app) as client:
        class API:
            bootstrap = {'X-Bootstrap-Key': settings.bootstrap_key}

            def call(self, query, variables=None, headers=None, code=None):
                response = client.post('/graphql', json={'query': query, 'variables': variables or {}},
                                       headers=headers or {})
                result = response.json()
                records.append({'caso': request.node.name, 'operacion': query,
                                'variables': redact(variables or {}),
                                'cabeceras': list((headers or {}).keys()),
                                'esperado': code or 'Sin errores GraphQL', 'http': response.status_code,
                                'real': redact(result)})
                assert response.status_code == 200
                if code == 'GRAPHQL_VALIDATION':
                    assert result.get('errors'), result
                elif code:
                    assert result['errors'][0]['extensions']['code'] == code, result
                else:
                    assert 'errors' not in result, result
                return result.get('data')

        api = API()
        api.app, api.client, api.settings = app, client, settings
        yield api
    app.state.engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    directory = Path('docs/evidencias')
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'graphql.json').write_text(json.dumps(
        {'exitstatus': exitstatus, 'pruebas': reports, 'casos': [{**r, 'estado': reports.get(r['caso'], 'no registrado')} for r in records]}, ensure_ascii=False, indent=2), encoding='utf-8')
