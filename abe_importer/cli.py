import click
import colorama
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from abe_importer.importer import do_import
from abe_importer.importer.operational import ldap_view_too_old, refresh_ldap_view
from abe_importer.importer.translations import ImportException
from abe_importer.logging import setup_logger
from abe_importer.session import create_session, create_scoped_session

from pycroft.model import session as pyc_session


@click.command()
@click.option('--abe-uri-file', default=".abe_uri")
@click.option('--pycroft-uri-file', default=".pycroft_uri")
@click.option('--refresh/--no-refresh', default=True,
              help="Don't force a refresh of the LDAP view")
@click.option('-n', '--dry-run', is_flag=True,
              help="Don't write to the pycroft database")
@click.option('-v', '--verbose', is_flag=True,
              help="Will raise the loglevel to DEBUG.")
def main(abe_uri_file: str, pycroft_uri_file: str, dry_run: bool, refresh: bool, verbose: bool):
    colorama.init()
    abe_session = create_session(read_uri(uri_file=abe_uri_file))
    _pyc_scoped_session = create_scoped_session(read_uri(pycroft_uri_file))
    pyc_session.set_scoped_session(_pyc_scoped_session)
    pycroft_session = pyc_session.session

    logger_name = 'abe-importer'
    logger = setup_logger(logger_name, verbose)

    check_connections(abe_session, pycroft_session, logger=logger)

    view_too_old = ldap_view_too_old(abe_session)
    if refresh:
        logger.info("Refreshing LDAP view due to CLI parameters…")
        logger.info("HINT: You can disable this with --no-refresh")
    if view_too_old:
        logger.warning("LDAP view is older than one day, forcing refresh…")
    if refresh or view_too_old:
        refresh_ldap_view(abe_session)
        logger.info("…Done.")
    else:
        logger.info("Skipping LDAP refresh.  Use --refresh to force it.")

    try:
        objs = do_import(abe_session, pycroft_session, logger)
    except ImportException:
        exit(1)
        return  # Don't judge me, this keeps pycharm silent

    if dry_run:
        exit(0)
        return

    if click.confirm(f'Do you want to add {len(objs)} new entries to the pycroft repository?',
                     abort=True):
        pycroft_session.add_all(objs)
        pycroft_session.commit()
    else:
        pycroft_session.rollback()


def check_connections(*sessions: Session, logger):
    try:
        for s in sessions:
            s.execute("select 1")
    except OperationalError:
        # noinspection PyUnboundLocalVariable
        logger.critical("Unable to connect to %s", s.get_bind())
        exit(1)


def read_uri(uri_file: str) -> str:
    with open(uri_file) as f:
        return f.read()

