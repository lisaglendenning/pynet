# @copyright
# @license

# Paver project
# http://paver.github.com/

# Paver works a bit like Make or Rake. 
# To use Paver, you run paver <taskname> and the paver command 
# will look for a pavement.py file in the current directory

import sys, os

import paver.easy
import paver.setuputils

NAME = 'pynet'

def configure():
    cwd = os.getcwd()
    sys.path.insert(0, os.path.join(cwd, 'source'))
    package = __import__(NAME)
    del sys.path[0]
    setup = dict(
                 version=package.__version__,
                 url=package.__url__,
                 author=package.__author__,
                 author_email=package.__author_email__,
                 license=package.__license__,
                 keywords=', '.join([repr(k) for k in package.__keywords__]),
                 install_requires=package.__requires__,
                 extras_require=package.__extras__,
                )
    return setup

paver.setuputils.setup(
        name=NAME,
        packages=paver.setuputils.find_packages('source'),
        package_dir = {'':'source'},
        **configure())

@paver.easy.task
@paver.easy.needs('paver.misctasks.generate_setup',
       'paver.misctasks.minilib',)
def sdist():
    """Overrides sdist to make sure that our setup.py is generated."""
    
    # Create distribution manifest
    includes = ['setup.py', 'paver-minilib.zip']
    lines = ['include %s' % ' '.join(includes),
             'recursive-include source *.py',]
    with open('MANIFEST.in', 'w') as f:
        f.write('\n'.join(lines))
        f.write('\n')

    paver.easy.call_task('setuptools.command.sdist')
    
