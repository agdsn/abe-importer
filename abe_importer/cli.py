import click
import colorama

from abe_importer.importer import do_import
from abe_importer.importer.translations import ImportException
from abe_importer.logging import setup_logger
from abe_importer.session import create_session


@click.command()
@click.option('--abe-uri-file', default=".abe_uri")
@click.option('-v', '--verbose', is_flag=True,
              help="Will raise the loglevel to DEBUG.")
def main(abe_uri_file: str, verbose: bool):
    colorama.init()
    abe_session = create_session(read_uri(uri_file=abe_uri_file))

    logger_name = 'abe-importer'
    logger = setup_logger(logger_name, verbose)

    try:
        do_import(abe_session, logger)
    except ImportException:
        exit(1)


def read_uri(uri_file: str) -> str:
    with open(uri_file) as f:
        return f.read()

