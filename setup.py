import setuptools

from midiprocessor.version import __version__

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name="midiprocessor",  # Replace with your own username
    version=__version__,
    author="Botao Yu",
    author_email="btyu@foxmail.com",
    description="A tool for processing MIDI files.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    package_data={'midiprocessor': ['legacy_tools/tools/midi_model/*', 'key_profile.pickle']},
    entry_points={
        'console_scripts': [
            'mp-batch-encoding = midiprocessor.batch_encoding:main'
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
