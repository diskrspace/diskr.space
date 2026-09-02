from setuptools import setup, find_packages

NAME = "diskr.space"
DESCRIPTION = "A disk space management tool"
AUTHOR = "raptor"
AUTHOR_EMAIL = "raptor.zh@gmail.com"
URL = "http://diskr.space/"
VERSION = __import__("web").__version__
REQUIRES = ['fastapi', 'uvicorn', 'sqlalchemy', 'pyyaml', 'python-dotenv']

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    license="Apache",
    url=URL,
    install_requires=REQUIRES,
    packages=find_packages(),
    zip_safe=False,
)
