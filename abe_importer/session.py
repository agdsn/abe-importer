from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# URL might be "postgres://postgres:password@172.22.0.2/abe?search_path=abe,public"

def create_session(url):
    return Session(bind=create_engine(url))
