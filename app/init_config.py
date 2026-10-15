"""Genera secretos locales sin imprimirlos ni sobrescribir configuración."""
import secrets
from pathlib import Path

if __name__ == '__main__':
    with Path('.env').open('x', encoding='utf-8') as file:
        file.write('DATABASE_URL=sqlite:///./app.db\n'
                   f'JWT_SECRET={secrets.token_urlsafe(48)}\n'
                   f'BOOTSTRAP_KEY={secrets.token_urlsafe(48)}\n'
                   'JWT_EXPIRE_MINUTES=30\n')
    print('.env creado. Guarda sus claves en privado.')
