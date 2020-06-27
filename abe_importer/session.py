from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, scoped_session


# URL might be "postgres://postgres:password@172.22.0.2/abe?search_path=abe,public"

def create_session(url):
    return Session(bind=(create_engine(url, connect_args={'connect_timeout': 10})))


def create_scoped_session(url):
    return scoped_session(sessionmaker(bind=(create_engine(url, connect_args={'connect_timeout': 10}))))
