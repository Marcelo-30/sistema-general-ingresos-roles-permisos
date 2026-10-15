"""Empaqueta solo archivos de entrega y verifica integridad y exclusión de secretos."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'entrega'
PREFIX = 'UnidadII_Actividad4_Configuracion_Permisos'


def main():
    files = [ROOT / name for name in (
        'ENTREGA.md', 'README.md', 'requirements.txt', 'schema.graphql',
        '.env.example', '.env.docker.example', '.gitignore', '.dockerignore', 'Dockerfile', 'compose.yaml', 'pytest.ini')]
    for directory in ('app', 'tests', 'scripts', 'docs'):
        files.extend(path for path in (ROOT / directory).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts
                     and path.suffix in {'.py', '.md', '.graphql', '.json', '.txt', '.xml', '.jpg', '.png', '.sql'})
    files = sorted(set(files))
    # Se comparan los secretos locales sin imprimirlos ni incorporarlos al manifiesto.
    secrets = []
    for configuration in (ROOT / '.env', ROOT / '.env.docker'):
        if not configuration.exists():
            continue
        for line in configuration.read_text(encoding='utf-8-sig').splitlines():
            key, _, value = line.partition('=')
            if key.strip() in {'JWT_SECRET', 'BOOTSTRAP_KEY', 'MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD'} and value.strip():
                secrets.append(value.strip().strip('\"\'').encode())
    credentials = ROOT / '.demo-credentials.json'
    if credentials.exists():
        secrets.append(json.loads(credentials.read_text(encoding='utf-8'))['password'].encode())

    roles_credentials = ROOT / '.roles-demo.json'
    if roles_credentials.exists():
        secrets.extend(value.encode() for value in json.loads(roles_credentials.read_text(encoding='utf-8')).values())

    activity4_credentials = ROOT / '.actividad4-credentials.json'
    if activity4_credentials.exists():
        secrets.extend(value.encode() for value in json.loads(activity4_credentials.read_text(encoding='utf-8')).values())

    payloads = {}
    for path in files:
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            raise RuntimeError(f'Secreto local detectado en {path.relative_to(ROOT)}; no se empaquetó.')
        payloads[f'{PREFIX}/{path.relative_to(ROOT).as_posix()}'] = data
    OUTPUT.mkdir(exist_ok=True)
    archive = OUTPUT / f'{PREFIX}.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED) as zipped:
        for name, data in payloads.items():
            zipped.writestr(name, data)
    with ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert set(zipped.namelist()) == set(payloads)
        for name, expected in payloads.items():
            assert zipped.read(name) == expected
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUTPUT / f'{PREFIX}.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    print(f'ZIP verificado: {archive}')
    print(f'Archivos: {len(files)}. Tamaño: {archive.stat().st_size} bytes.')
    print('Sin secretos locales, bases de datos, entornos virtuales ni cachés.')


if __name__ == '__main__':
    main()
