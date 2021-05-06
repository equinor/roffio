Roff IO
==========

A (lazy) parser and writer for the Roxar Open File Format (ROFF) (binary and ascii).


Usage
-----

ROFF files contains values stored in tag keys that are grouped by tags. These
can be read by:

```
import roffio

contents = roffio.read("my/file.roff")
value = contents["tagname"]["keyname"]
```

Similarly, files are written through a dictionary of tags and tagkeys:

```
import roffio

contents = {
 "tagname": {
    "keyname": 1.0
  }
}

roffio.write("my/file.roff", contents)
```

Additionally, the contents of a file can be read lazily, avoiding unneccessary
disk operations and memory useage:


```
import roffio

result = None
with roffio.lazyread("my/file.roff") as contents:
    for tagname, tagkeys in contents:
        for keyname, value in tagkeys:
            if tagname = "mytag" and keyname = "mykey":
                result = value
                break
        if result is not None:
           break

```

### Same name tags and tag-keys

The simple read/write functions works best for tags and tagkeys with unique
names, however, if the file has multiple tags with the same name, a list will
be returned:


```
import roffio

contents = [
 ("tagname", ("keyname", 1.0)),
 ("tagname", ("keyname", 2.0)),
]

roffio.write("my/file.roff", contents)

values = roffio.read("my/file.roff")
```

Then `values["tagname"]` will be the list `[{"keyname": 1.0}, {"keyname": 2.0}]`.


## building

    pip install .

## testing

    pytest

The ROFF ascii format
---------------------

The roff ascii format is a file format that consists of a list of tags.  Each
tag contains tag keys.

A simple valid example looks like this:

```
roff-asc
tag tagname
int keyname 1
endtag
eof
```

A ascii roff file starts with the header token `"roff-asc"` and ends with the
`"eof"` token. Between the header token and the eof token, is a list of tags,
each delimited by the tokens `"tag"` and `"endtag"`, imidiately after the tag
token is the name of the tag.

Comments can be added between `#` characters.


### Tag keys

Each tag contains a list of tag keys defining a key name and value. There
are single value tag keys and array tag keys.

#### Single value tag keys

Single value keys consists of three tokens:
```
type name value
```

where type is one of

* char
* bool
* byte
* int
* float
* double

e.g.

```
roff-asc
#comment#
tag exampletag
int x 80
float y 3.0
bool flag 0
byte mask 4
char str_name "a string"
endtag
eof
```


#### Array tag keys

Array tag keys contain the following tokens: array, name, type, length and
value, where type is a single value tag key type. The value is not
zero-terminated but the size is given by the number of bytes in the type times
the length of the array, ie.  `array int arr_name 1 255` (an array of one int
value, the length of the array being 1 and the one int value being `255`). Similary,
char arrays contain any number of strings:

```
array char char_array 3
   "hello"
   "hello again"
   "hello world"
```


The ROFF binary format
----------------------

The binary format is very similar to the ascii format. The header is changed to
`roff-bin` to indicate binary format. Each token is delimited by the zero character
instead of whitespace. int, float, byte, bool, and double are fixed-size byte-encoded
values. String values are zero terminated instead of surrounded by quotes.

Comments can also be added to binary files but are terminated by zero character
in addition to delimited by `'#'`.

A simple valid example looks like this:

```
b"roff-bin\0tag\0tagname\0int\0varname\0\x00\x00\x00\x01endtag\0eof\0"
```

char tag keys no longer have quotes but are simply zero character delimited:

`char\0str_name\0some_string\0`.

Tag keys of type int, float, double, bool and byte are all fixed size tag keys,
meaning they consist of three consecutive tokens: type, name, and value. The
name is any zero delimited string of bytes giving the name of the tag keys and
value is a fixed length of bytes. For byte, bool and char it is 1 byte, for
float and int it is 4 bytes and for double it is 8 bytes. i.e `int\0x\0\x00\x00\x00\x01`

If the type of an array is char then the size denotes the number of zero
terminated strings in the array:
`array char str_arr \x00\x00\x00\x02\0hello world\0hello again\0`.


### Endianess and filedata tag

There is no fixed endianess defined for the roff format. Instead, a filedata
tag is added as the first tag in the file. In addition to metadata about
creation date and filetype, the `byteswaptest` record key is added which
should be set to `1` in whatever endianess the file is intended to be read in.

```
tag filedata
 int byteswaptest 1
 char filetype "grid"
 char creationDate "01/03/1999 10:00:48"
endtag
```

### Version tag

Another tag keeps track of the file format version, currently 2.0:

```
tag version
 int major 2
 int minor 0
endtag
```

### End of file tag

Its a common convention to have the last tag in a roff file be
an empty tag with name eof:

```
tag eof
endtag
```

### Mapping of python types to roff types

Reading and writing maps roff types to python types, usually as expected.
For more control use numpy dtypes, ie. numpy.array(dtype="float32") will
be written as a tag key as with roff type "array float". Reading always
results in numpy arrays and dtypes for performance reasons, that is,
except for bytes.

#### Special case of bytes:

writing of python `bytes` results in roff keys with types of either `array bytes`
or `byte` depending on length. If the length is `1` then you get a non-array
tag key:

```python
roffio.write("my/file.roff", { "t": { "key": b'\x00' }})
```

results in a roff file containing

```
tag t
bytes key 0
endtag
```

while

```python
roffio.write("my/file.roff", { "t": { "key": b'\x00\x01' }})
```

results in a roff file containing

```
tag t
array bytes key 2 0 1
endtag
```
