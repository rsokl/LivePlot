import tempfile
import os
import pytest


@pytest.fixture()
def cleandir() -> str:
    """ This fixture will use the stdlib `tempfile` module to
    move the current working directory to a tmp-dir for the
    duration of the test.

    Afterwards, the session returns to its previous working
    directory, and the temporary directory and its contents
    are removed.

    Yields
    ------
    str
        The name of the temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdirname:
        old_dir = os.getcwd()
        os.chdir(tmpdirname)
        yield tmpdirname
        os.chdir(old_dir)