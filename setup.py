from setuptools import setup, find_packages

setup(
    name='HelioIndex',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'pandas',
        'requests',
        'BeautifulSoup4'
    ],
    author='Balaji Kannan',
    description='A Python Package for Reproducible Construction of Machine-Learning Datasets from Solar Observations and Event Catalogs')
