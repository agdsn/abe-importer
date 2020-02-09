import click
import colorama

from abe_importer.importer import do_import
from abe_importer.importer.operational import ldap_view_too_old, refresh_ldap_view
from abe_importer.importer.translations import ImportException
from abe_importer.logging import setup_logger
from abe_importer.session import create_session


@click.command()
@click.option('--abe-uri-file', default=".abe_uri")
@click.option('--refresh/--no-refresh', default=True,
              help="Don't force a refresh of the LDAP view")
@click.option('-v', '--verbose', is_flag=True,
              help="Will raise the loglevel to DEBUG.")
def main(abe_uri_file: str, refresh: bool, verbose: bool):
    colorama.init()
    abe_session = create_session(read_uri(uri_file=abe_uri_file))

    logger_name = 'abe-importer'
    logger = setup_logger(logger_name, verbose)

    if refresh or ldap_view_too_old(abe_session):
        logger.warning("Ldap view is older than one day, refreshing…")
        logger.info("HINT: You can disable this with --no-refresh")
        refresh_ldap_view(abe_session)
        logger.info("…Done.")
    else:
        logger.info("Skipping LDAP refresh.  Use --refresh to force it.")

    try:
        do_import(abe_session, logger)
    except ImportException:
        exit(1)


def read_uri(uri_file: str) -> str:
    with open(uri_file) as f:
        return f.read()

