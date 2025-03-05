from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram Token
    TOKEN: str

    # Database
    DB_USER_NAME: str
    DB_HOST: str
    DB_NAME: str
    DB_USER_PASSWORD: str
    DB_PORT: int

    class Config:
        env_file = '.env'


settings = Settings()  # type: ignore
