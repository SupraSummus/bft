from setuptools import setup


setup(
    name="bft",
    version="0.0.0",
    packages=['bft'],
    tests_require=[
        'flake8',
    ],
    install_requires=[
        'reedsolo==1.4.0',
    ],
    dependency_links=[
        'git+https://github.com/lrq3000/reedsolomon.git@7583ed3fb624dc012c363a120222941f221994f9#egg=reedsolo-1.4.0',
    ],
)
