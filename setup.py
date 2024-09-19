from setuptools import setup

setup (name='gitc',
       version=1.0,
       packages=['gitc'],
       entry_points = {
           'console_scripts' : [
               'gitc = gitc.cli:main'
           ]
       })