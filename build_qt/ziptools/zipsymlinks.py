from __future__ import print_function    # python2.X compatibility
import os, sys, time
import zipfile as zipfilemodule          # versus the passed zipfile object

# UTC timestamp zip [1.2]
from .zipmodtimeutc import addModtimeUTC

# portability exceptions
RunningOnWindows = sys.platform.startswith('win')



#===============================================================================


"""
ABOUT THE "MAGIC" BITMASK

Magic = type + permission + DOS is-dir flag?
    >>> code = 0xA1ED0000
    >>> code
    2716663808
    >>> bin(code)
    '0b10100001111011010000000000000000'

Type = symlink (0o12/0xA=symlink 0o10/0x8=file, 0o04/0x4=dir) [=stat() bits]
    >>> bin(code & 0xF0000000)
    '0b10100000000000000000000000000000'
    >>> bin(code >> 28)
    '0b1010'
    >>> hex(code >> 28)
    '0xa'
    >>> oct(code >> 28)
    '0o12'

Permission = 0o755 [rwx + r-x + r-x]
    >>> bin((code & 0b00000001111111110000000000000000) >> 16)
    '0b111101101'
    >>> bin((code >> 16) & 0o777)
    '0b111101101'

DOS (Windows) is-dir bit
    >>> code |= 0x10 
    >>> bin(code)
    '0b10100001111011010000000000010000'
    >>> code & 0x10
    16
    >>> code = 0xA1ED0000
    >>> code & 0x10
    0

Full format:
    TTTTsstrwxrwxrwx0000000000ADVSHR
    ^^^^____________________________ file type, per sys/stat.h (BSD)
        ^^^_________________________ setuid, setgid, sticky
           ^^^^^^^^^________________ permissions, per unix style
                    ^^^^^^^^________ Unused (apparently)
                            ^^^^^^^^ DOS attribute bits: bit 0x10 = is-dir

Discussion:
    http://unix.stackexchange.com/questions/14705/
        the-zip-formats-external-file-attribute
    http://stackoverflow.com/questions/434641/  
        how-do-i-set-permissions-attributes-
        on-a-file-in-a-zip-file-using-pythons-zip/6297838#6297838
"""


SYMLINK_TYPE  = 0xA
SYMLINK_PERM  = 0o755    # no longer used
SYMLINK_ISDIR = 0x10
SYMLINK_MAGIC = (SYMLINK_TYPE << 28) | (SYMLINK_PERM << 16)

assert SYMLINK_MAGIC == 0xA1ED0000, 'Bit math is askew'    


# [1.1] ziptools now saves permission bits from the link itself instead of 
# always using 0o755, because 1.1 "-permissions" extracts now propagate all
# permissions.  Custom link permissions may be rare, but are supported here
# on platforms that support them too (Windows doesn't, in Python's builtins).
# Nit: could just set this to type alone, but retaining the coding history.

SYMLINK_MAGIC &= 0b11111110000000001111111111111111   # mask off permission bits



#===============================================================================



def addSymlink(filepath, zippath, zipfile, trace=print):
    assert os.path.islink(filepath)
    if hasattr(os, 'readlink'):
        try:
            linkpath = os.readlink(filepath)        # str of link itself
        except:
            trace('--Symlink not supported')        # any other issues [1.1]
            linkpath = 'symlink-not-supported'      # forge a link-to path 
    else:
        trace('--Symlink not supported')            # python2.X on Windows? [1.1]
        linkpath = 'symlink-not-supported'          # forge a link-to path 
    
    # 0 is windows, 3 is unix (e.g., mac, linux) [and 1 is Amiga!]
    createsystem = 0 if RunningOnWindows else 3 

    # else time defaults in zipfile to Jan 1, 1980
    linkstat = os.lstat(filepath)                   # stat of link itself
    origtime = linkstat.st_mtime                    # mtime of link itself
    ziptime  = time.localtime(origtime)[0:6]        # first 6 tuple items

    # zip mandates '/' separators in the zipfile
    allseps = os.sep + (os.altsep or '')            # +leading '/' on win [1.2]
    if not zippath:                                 # pass None to equate
        zippath = filepath
    zippath = os.path.splitdrive(zippath)[1]        # drop Windows drive, unc
    zippath = os.path.normpath(zippath)             # drop '.', double slash...
    zippath = zippath.lstrip(allseps)               # drop leading slash(es)
    zippath = zippath.replace(os.sep, '/')          # no-op if unix or simple
   
    newinfo = zipfilemodule.ZipInfo()               # new zip entry's info
    newinfo.filename      = zippath
    newinfo.date_time     = ziptime
    newinfo.create_system = createsystem            # woefully undocumented
    newinfo.compress_type = zipfile.compression     # use the file's default
    newinfo.external_attr = SYMLINK_MAGIC           # type plus dflt permissions

    if os.path.isdir(filepath):                     # symlink to dir?
        newinfo.external_attr |= SYMLINK_ISDIR      # DOS directory-link flag

    # [1.1] set this link's permission bits
    linkperms = (linkstat[0] & 0xFFFF) << 16        # zero-filled, both ends
    newinfo.external_attr |= linkperms              # set bits from file 

    zipfile.writestr(newinfo, linkpath)             # add to the new zipfile

    # record link's UTC timestamp [1.2]
    addModtimeUTC(zipfile, utcmodtime=origtime)     # to be written on zip close()



#===============================================================================



def isSymlink(zipinfo):
    """
    ----------------------------------------------------------------------------
    Extract: check the entry's type bits for symlink code.
    This is the upper 4 bits, and matches os.stat() codes.
    ----------------------------------------------------------------------------
    """
    return (zipinfo.external_attr >> 28) == SYMLINK_TYPE



def symlinkStubFile(destpath, linkpath, trace):
    """
    ----------------------------------------------------------------------------
    Extract: simulate an unsupported symlink with a dummy file [1.1].
    The is subpar, but it's better than killing the rest of the unzip.
    No stub is made for symlink filenames with non-portable characters.
    Must encode, else non-ASCII Unicode bombs on py2.X for 'w' text 
    files, and Unicode text-file interfaces differ in py2.X and 3.X.
    Update: zips don't stop on errors anymore, but stubs still useful.
    ----------------------------------------------------------------------------
    """
    try:
        linkpath = linkpath.encode('utf8')    # finesse 3.X/2.X unicode diffs [1.2]
        bogus = open(destpath, 'wb')          # record linkpath in plain text file
        bogus.write(linkpath)                 # though linkpath forged in Win+2.X
        bogus.close()
    except:
        # may fail for access perms, etc. (but not illegal filname chars)
        trace('--Could not make stub file for', destpath)



#===============================================================================



def extractSymlink(zipinfo, pathto, zipfile, 
                   nofixlinks=False, trace=print, origname=None):

    assert zipinfo.external_attr >> 28 == SYMLINK_TYPE
    
    zippath  = zipinfo.filename                         # path in zip, mangled on retry
    linkpath = zipfile.read(origname or zippath)        # original link's path str
    try:
        linkpath = linkpath.decode('utf8')              # must match types ahead
    except UnicodeDecodeError:                          # don't die if !utf8 [1.2]
        trace('--Symlink not decodable: link forged')
        linkpath = u'symlink-not-decodable'             # ensure unicode in 2.X

    # undo zip-mandated '/' separators on Windows
    zippath  = zippath.replace('/', os.sep)             # no-op if unix or simple

    # drop Win drive + unc, leading slashes, '.' and '..'
    zippath  = os.path.splitdrive(zippath)[1]
    zippath  = zippath.lstrip(os.sep)                   # if other program's zip
    allparts = zippath.split(os.sep)
    okparts  = [p for p in allparts if p not in ('.', '..')]
    zippath  = os.sep.join(okparts)

    # where to store link now (assume chars portable)
    destpath = os.path.join(pathto, zippath)            # hosting machine path
    destpath = os.path.normpath(destpath)               # perhaps moot, but...

    # make leading dirs if needed
    upperdirs = os.path.dirname(destpath)               # skip if './link' => '' [1.1]
    if upperdirs and not os.path.exists(upperdirs):     # will fail if '' or exists;
        os.makedirs(upperdirs)                          # exists_ok in py 3.2+ only

    # force exc now if makedirs didn't and basename must be mangled [1.3]
    if not origname:
        open(destpath + '.ziptools_probe', 'w').close() # hacky, but too rare to care
        os.remove(destpath + '.ziptools_probe')         # caveat: assumes name unique

    # adjust link separators for the local platform
    if not nofixlinks:
        linkpath = linkpath.replace(u'/', os.sep).replace(u'\\', os.sep)

    # test+remove link, not target
    if os.path.lexists(destpath):                       # else symlink() fails
        os.remove(destpath)

    # windows dir-link arg
    isdir = zipinfo.external_attr & SYMLINK_ISDIR
    if (isdir and                                       # not suported in py 2.X
        RunningOnWindows and                            # ignored on unix in 3.3+
        int(sys.version[0]) >= 3):                      # never required on unix 
        dirarg = dict(target_is_directory=True)
    else:
        dirarg ={}

    # make the link in dest
    if hasattr(os, 'symlink'):
        try:
            os.symlink(linkpath, destpath, **dirarg)          # store new link in dest
        except:
            # including non-admin Windows
            trace('--Symlink not supported: stub file made')  # any python on Android [1.1]
            symlinkStubFile(destpath, linkpath, trace)        # make dummy file?, go on
    else:
        trace('--Symlink not supported: stub file made')      # python2.X on Windows [1.1]
        symlinkStubFile(destpath, linkpath, trace)            # make dummy file, go on

    return destpath                                           # savepath as made here

    # and caller sets link's modtime and permissions where supported
