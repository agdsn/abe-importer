import logging

import click

from abe_importer.importer import do_import
from abe_importer.session import create_session


@click.command()
@click.option('--abe-uri-file', default=".abe_uri")
@click.option('-v', '--verbose', is_flag=True,
              help="Will raise the loglevel to DEBUG.")
def main(abe_uri_file: str, verbose: True):
    abe_session = create_session(read_uri(uri_file=abe_uri_file))
    logger = logging.getLogger('abe-importer')
    log_format = "[%(levelname).4s] %(name)s:%(funcName)s:%(message)s"
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format=log_format)
    do_import(abe_session, logger)


def read_uri(uri_file: str) -> str:
    with open(uri_file) as f:
        return f.read()

