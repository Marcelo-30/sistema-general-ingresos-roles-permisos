"""Genera configuración privada para Docker sin alterar el .env anterior."""
import secrets
from pathlib import Path


if __name__ == '__main__':
    password = secrets.token_hex(24)
    with Path('.env.docker').open('x', encoding='utf-8') as file:
        file.write('MYSQL_DATABASE=ingresos\nMYSQL_USER=ingresos\nMYSQL_PORT=3307\nAPI_PORT=8007\n'
                   f'MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={secrets.token_hex(32)}\n'
                   f'DATABASE_URL=mysql+pymysql://ingresos:{password}@127.0.0.1:3307/ingresos?charset=utf8mb4\n'
                   f'JWT_SECRET={secrets.token_urlsafe(48)}\nBOOTSTRAP_KEY={secrets.token_urlsafe(48)}\n'
                   'JWT_EXPIRE_MINUTES=30\n')
    print('.env.docker creado. No se alteró .env ni se imprimieron secretos.')
