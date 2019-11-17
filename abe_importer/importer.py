from logging import Logger

from sqlalchemy.orm import Session


def do_import(abe_session: Session, logger: Logger):
    logger.info("Starting (dummy) import")
