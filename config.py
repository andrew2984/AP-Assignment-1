from decouple import config

class Config:
    CONNECTION_STRING = config('CONNECTION_STRING')
    CONNECT_SRC = config('CONNECT_SRC')
    API_URL = config('API_URL')

class DevelopmentConfig(Config):
    DEBUG = config('DEBUG', cast=bool)
    
class DevServerConfig(Config):
    DEBUG = config('DEBUG', cast=bool)