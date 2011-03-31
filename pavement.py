# @copyright
# @license

# Paver project
# http://paver.github.com/

# Paver works a bit like Make or Rake. 
# To use Paver, you run paver <taskname> and the paver command 
# will look for a pavement.py file in the current directory

import sys, os

import paver.easy
import paver.doctools
import paver.setuputils


def configure():
    cwd = os.getcwd()
    sys.path.insert(0, cwd)
    package = __import__('source')
    del sys.path[0]
    setup = dict(
                 version=package.__version__,
                 url=package.__url__,
                 author=package.__author__,
                 author_email=package.__author_email__,
                 license=package.__license__,
                 keywords=', '.join([repr(k) for k in package.__keywords__]),
                 install_requires=', '.join([repr(k) for k in package.__requires__]),
                )
    return setup

paver.setuputils.setup(
        name='io',
        packages=['io'],
        package_dir = {'':'source'},
        **configure())

@paver.easy.task
@paver.easy.needs('generate_setup', 'minilib',)
def sdist():
    """Overrides sdist to make sure that our setup.py is generated."""
    
    # Create distribution manifest
    includes = ['pavement.py', 'setup.py', 'paver-minilib.zip']
    lines = ['include %s' % ' '.join(includes),]
    with open('MANIFEST.in', 'w') as f:
        f.write('\n'.join(lines))
        f.write('\n')

    paver.easy.call_task('setuptools.command.sdist')
    
