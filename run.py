# -*- coding: utf-8 -*-
"""
Created on Thu Jan  8 09:56:32 2026

@author: NBoyd1
"""

import os
import sys
from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))


from decouple import config
from config import DevelopmentConfig, DevServerConfig
from app import create_app
from seed import seed


app = Flask(__name__,
    static_folder='src/web',
    static_url_path='')

env = config('FLASK_ENV', default='development')

if env == "development":
    app.config.from_object(DevelopmentConfig)
elif env == "dev_server":
    app.config.from_object(DevServerConfig)
    
connection_string = app.config['CONNECTION_STRING']

engine = create_engine(connection_string, echo=True)
Session = sessionmaker(bind=engine)

connect_src = app.config['CONNECT_SRC']

if __name__ == "__main__":
    # Seed database on first run
    # db_path = "app.db"
    # if os.getenv("DATABASE_URL", "").startswith("sqlite:///"):
    #     db_path = os.getenv("DATABASE_URL").replace("sqlite:///", "")

    # if not os.path.exists(db_path):
    #     seed(os.getenv("DATABASE_URL", "sqlite:///app.db"))

    app = create_app()
    app.run(debug=True)

