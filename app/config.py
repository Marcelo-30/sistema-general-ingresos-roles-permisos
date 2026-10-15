import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    bootstrap_key: str
    jwt_expire_minutes: int = 30

    def __post_init__(self):
        if len(self.jwt_secret) < 32 or len(self.bootstrap_key) < 32:
            raise ValueError('JWT_SECRET y BOOTSTRAP_KEY requieren al menos 32 caracteres.')
        if self.jwt_secret == self.bootstrap_key:
            raise ValueError('Las claves deben ser independientes.')
        if self.jwt_expire_minutes <= 0:
            raise ValueError('JWT_EXPIRE_MINUTES debe ser positivo.')

    @classmethod
    def from_env(cls):
        load_dotenv(os.getenv('SETTINGS_FILE', '.env'))
        return cls(os.getenv('DATABASE_URL', 'sqlite:///./app.db'),
                   os.getenv('JWT_SECRET', ''), os.getenv('BOOTSTRAP_KEY', ''),
                   int(os.getenv('JWT_EXPIRE_MINUTES', '30')))
