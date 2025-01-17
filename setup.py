# from distutils.core import setup, Extension
from setuptools import setup, Extension, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

ljpeg92 = Extension('ljpegCompress', sources=[
                    "src/diypidng/bitunpack.c", "src/diypidng/liblj92/lj92.c"],  extra_compile_args=['-std=gnu99'], extra_link_args=[])

setup(
    name="diypidng",
    include_package_data=True,
    version="5.2",
    author="Bastian Kiefer",
    description="Python utility for creating Adobe DNG files from RAW image data.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BlackF0rest/DIYPiDNG",
    install_requires=[
        'numpy',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        "Topic :: Multimedia :: Graphics :: Capture :: Digital Camera",
        "Topic :: Multimedia :: Graphics :: Graphics Conversion",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
    ],
    ext_modules=[ljpeg92],
    package_dir={"": "src"},
    packages=find_packages(where="C:\Projects\DIYPiDNG\src"),
    python_requires='>=3.6',
)