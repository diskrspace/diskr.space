from setuptools import setup, find_packages

PACKAGE = "diskr.space"
NAME = "diskr.space"
DESCRIPTION = "A disk space management tool"
AUTHOR = "raptor"
AUTHOR_EMAIL = "raptor.zh@gmail.com"
URL = "http://raptorz.github.com/"
VERSION = __import__(PACKAGE).__version__
REQUIRES = ['bottle', 'sqlalchemy', 'mako', 'beaker', 'bottle-sqlalchemy']

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="Apache",
    url=URL,
    requires=REQUIRES,
    packages=find_packages(),
    zip_safe=False,
)
