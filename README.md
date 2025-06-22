# Karai's Priston Tale Asset Tool

## Build Instructions

This application is written in Python and dependencies are managed with Poetry. You will need both of these tools to run this application.

```sh
poetry install
```

## Usage Instructions

By default, if you run this application it will not produce results. You need to apply command line options to patch, decode, and encode data.

```sh
-i, --input          Input directory
-o, --output         Output directory
-t, --texture        Patch textures
-a, --audio          Patch audio
-m, --model          Decode models
-s, --server         Decode server data
-p, --png            Encode textures as PNG
-j, --json           Encode models as JSON
-g, --gltf           Encode models as GLTF
```

```sh
poetry run python -u -m app.main -i "~/Games/Priston Tale" -o ~/Games/PT_decoded -mtpg
```

## Features

### Client

* Patch BMP textures
* Patch TGA textures
* Patch WAV / BGM audio
* Decode INX model configurations
* Decode SMD / SMB model files
* Encode textures as PNG
* Encode models as JSON (internal data structure)
* Encode models as GLTF / GLB

### Server

* Decode SPM monster spawn configuration
* Decode SPP spawn point files
* Decode SPC NPC spawn point files
* Encode spawn data as JSON

## Work in Progress

### Application

* CLI
* `--godot` switch for Godot quirks
	* Godot's X axis is backwards (important for spawn point data)
	* Godot has name hints for animations and other things

### Client

* Texture link list for multi-texture materials
* Stage lights
* INX animation information for faces / etc.
* Encode models as ASE

### Server

* Decode INF monster configurations (bin/Server/GameServer/Monster)
* Decode NPC npc configurations (bin/Server/GameServer/NPC)
* Decode TXT item configurations (bin/Server/GameServer/OpenItem)
* Encode monsters as JSON
* Encode npcs as JSON
* Encode items as JSON
* get list of monster names (korean, english) from inf files
	* maybe we need a monster data structure that has all data from inf, srm, etc. should have 3 names: key (raw bytes), name (english), name_k (korean re-encoding of key)

## File Structures

### SMD Model Files and SMB Bone Files

#### SMD Stage data Ver 0.72

* `smDFILE_HEADER`
* `smSTAGE3D`
* `smMATERIAL_GROUP`
* `Materials` * smDFILE_HEADER.MatCounter
	* `smMATERIAL`
	* `uint32` (length of texture paths block)
	* `uint8` * length of texture paths block
* `smSTAGE_VERTEX` * smSTAGE3D.nVertex
* `smSTAGE_FACE` * smSTAGE3D.nFace
* `smTEXLINK` * smSTAGE3D.nTexLink
* `smLIGHT3D` * smSTAGE3D.nLight
* more?

##### References

* `smStage3d.cpp::smSTAGE3D::LoadFile`
* `smTexture.cpp::smMATERIAL_GROUP::LoadFile`

#### SMD Model data Ver 0.62

* `smDFILE_HEADER`
* `smDFILE_OBJINFO` * smDFILE_HEADER.ObjCounter
* `smMATERIAL_GROUP`
* `Materials` * smDFILE_HEADER.MatCounter
	* `smMATERIAL`
	* `uint32` (length of texture paths block)
	* `uint8` * length of texture paths block
* `Objects` * smDFILE_HEADER.ObjCounter
	* `smOBJ3D`
	* `smVERTEX` * smOBJ3D.nVertex
	* `smFACE` * smOBJ3D.nFace
	* `smTEXLINK` * smOBJ3D.nTexLink
	* `smTM_ROT` * smOBJ3D.TmRotCnt
	* `smTM_POS` * smOBJ3D.TmPosCnt
	* `smTM_SCALE` * smOBJ3D.TmScaleCnt
	* `smFMATRIX` * smOBJ3D.TmRotCnt
	* `uint8` * 32 (optional, physique bone name)

##### References

* `smObj3d.cpp::smPAT3D::LoadFile`
* `smObj3d.cpp::smOBJ3D::LoadFile`
* `smTexture.cpp::smMATERIAL_GROUP::LoadFile`

### SPP Server Stage Spawn Point Files

### SPM Server Stage Spawn Monster Files

#### Compiling a List of Monster Names

To compile a list of monster names, we need to parse all of the SRM files for monster names. In the SRM files, there are lines that indicare which monsters can spawn in a given stage. We want to extract the names out of these lines. This seems like a simple, if tedious task, however it is a bit more complicated than expected.

The SRM files, like all files in the Priston Tale source, are encoded in CP949, not UTF-8. When opening an SRM file in a text editor, you may see lines that look like this:

	*�⿬�� "ȣ��" 35

Instead of like this:

	*출연자 "호피" 35

At first glance it may seem sensible to re-encode the files as UTF-8 so that they "look" right, however that would cause the underlying byte data to change and that is a problem. We need those bytes to remain so that they match up with the source code. More specifically, it needs to match the name in the INF monster definition files:

	*�̸� "ȣ��"

Re-encoded:

	*이름 "호피"

Here is how I compiled a list of monster names so that I could convert their data to JSON:

1. Open an SRM file in a hex editor
1. Select all of the bytes and copy them to a text file
1. Compress all of the bytes down to a single line if they span across multiple lines
1. Multi-select the byte sequence `2A C3 E2 BF AC C0 DA` (reformat as needed) and press `Enter` to put each name on a new line
1. Multi-select on byte `22` (quotation mark) and press `Enter` to isolate the name bytes
1. Copy isolated name bytes to a list
1. Deduplicate list at the end

##### References

* `fileread.h::rsSTG_MONSTER`
* `smPacket.h::smCHAR_MONSTER_INFO`
