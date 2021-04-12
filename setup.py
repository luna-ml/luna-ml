import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="luna-ml",
    version="v0.1.9",
    license='Apache License 2.0',
    author="Staroid",
    author_email="moon@staroid.com",
    description="Luna ML client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/luna-ml/luna-ml",
    packages=setuptools.find_packages(),
    include_package_data=True, # include template dir
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        # Indicate who your project is intended for
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Specify the Python versions you support here. In particular, ensure
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',

        # Pick your license as you wish (should match "license" above)
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
    ],
    scripts=[
        'bin/luna-ml'
    ]
)
