from setuptools import setup, find_packages

setup(
    name='cloudify-docker-plugin2',
    packages=find_packages(),
    install_requires=['docker==2.4.2']
)
