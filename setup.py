import setuptools
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, "README.md"), encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="oem2orm",
    version="0.3.0",
    author="henhuy, jh-RLI",
    author_email="Hendrik.Huyskens@rl-institut.de",
    description="SQLAlchemy module to generate ORM, read from data model (oedatamodel) in open-energy-metadata(oem-v1.4.0) JSON format",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/OpenEnergyPlatform/oem2orm",
    packages=setuptools.find_packages(),
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=['sqlalchemy==1.3.14', 'oedialect', 'requests', 'jmespath', 'omi', 'click'],  # Optional
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/OpenEnergyPlatform/oem2orm/issues',
        'Source': 'https://github.com/OpenEnergyPlatform/oem2orm/tree/develop/oem2orm',
    },
    entry_points={
        'console_scripts': ['oem2orm=oem2orm.main:cli'],
    }
)
