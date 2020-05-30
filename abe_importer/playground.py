import colorama
from sqlalchemy import select

from . import model as abe_model
from .cli import read_uri, check_connections
from .importer.context import Context
from .importer.membership import MEMBERSHIP_FEE_PATTERN, get_latest_month
from .logging import setup_logger
from .session import create_session


def main():
    colorama.init()
    abe_session = create_session(read_uri(uri_file='.abe_uri'))
    pycroft_session = create_session(read_uri(uri_file='.pycroft_uri'))
    logger_name = 'abe-importer'
    logger = setup_logger(logger_name, verbose=True)

    check_connections(abe_session, pycroft_session, logger=logger)

    ctx = Context(abe_session, pycroft_session, logger=logger)
    descs = [d[0] for d in ctx.abe_session.execute(
        select((abe_model.FeeInfo.description,))
        .where(abe_model.FeeInfo.description.like(MEMBERSHIP_FEE_PATTERN))
        .select_from(abe_model.FeeInfo)
    )]

    ctx.logger.info("Current descriptions:")
    for desc in descs:
        ctx.logger.info(desc)
    ctx.logger.info("Latest month: %s", get_latest_month(descs))


if __name__ == '__main__':
    main()
