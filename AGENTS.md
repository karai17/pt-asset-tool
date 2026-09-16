# Agent Instructions

This project is a data format converter. It takes input of files in old, proprietary formats and outputs the data to files in modern, open source formats.

Read:

- `src/pt/cdef.py` - C structs that represent the old data formats
- `src/pt/pdef.py` - Python data classes that represent an in-app intermediary format
- `README.md` - information about the project, including the structure of the 3D model files

Read on demand:

- `docs/*` - technical documentation about the game engine
- `src/pt/decode/*` - various decoders from the old formats
- `src/pt/encode/*` - various encoders to the new formats
- `src/pt/patch/*` - various patchers that fix malformed files to the same format
- `.local/PTClassic/src/smLib3d/*` - original source code for smLib3d which handles:
	- loading `ase` 3D Studio Max text model files
	- loading and saving `smd` model files
	- loading and saving `smb` bone files
	- much more

## File Access

- You will find the original files at `.local/input` in their original context. This directory is **READ ONLY** and must never be modified.
- You will find the original C++ code base at `.local/PTClassic` in its original context. This directory is **READ ONLY** and must never be modified.
- When running the app, `.local/input/*` should be used for the input and `.local/output/*` should be used for the output.

## Goal

The goal of this project is to extract meaningful data from the old, proprietary formats and preserve them accurately in modern, open formats that have better tooling.

### 3D Models

The old 3D model format contains 3 primary files:

- `.inx` - metadata about the model
- `.smd` - the model data
- `.smb` - the model bones

There are two types of models: actors and fields. Actors will generally contain all 3 files whereas fields will only have data. When using the app, `src/pt/decode/inx.py` is the main gateway for decoding actors. It processes the metadata before handing off to the `smd` and `smb` decoder, `src/pt/decode/smd.py`. There is a GLTF encoder that can be used to export the decoded data.

### Textures

Textures are encoded as `bmp` and `tga` files. The original files in `.local/input` have their headers scrambled as a simple way to "encrypt" them. There are already patchers in `src/pt/patch` to patch these. There is also a `png` encoder that can export the textures as `png` files instead.

### Audio

Audio files (music and sound effects) are encoded as `wav` files. Like the textures, their headers are scrambled and a patcher is already available. There is currently no additional exporter as `wav` is a well known format with extensive tooling, so patching the files is enough.

### Server Data

There are additional text and binary files with loose formats that contain server data such as enemy spawn points, loot drops, etc. These are being decoded to an intermediary format and then encoded to `json`.

## Tools

There is a `src/pt/buffer.py` file with a `BufferReader` class. This class is used to mimic C's buffer reading, where the pointer moves along the buffer as it is read. If you are modifying code that uses C data or is reading binary data, use the `BufferReader`.

## Coding Style

- Use idiomatic Python conventions when writing Python code
- Do not add comments
- If a comment is absolutely necessary to explain something that the code itself cannot explain, make sure it's as minimal as possible
- Do not use object oriented programming conventions, this code base is procedural and functional
