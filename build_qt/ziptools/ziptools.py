#!/usr/bin/env python3
# -*- coding: utf8 -*-
r"""jun25 (else py3.14? makes \? escapes errors)
================================================================================
ziptools.py - the main library module of the ziptools system.
See ziptools' ../_README.html for license, attribution, and other logistics.

Tools to create and extract zipfiles containing a set of files, folders, and
symbolic links.  All functions here are callable, but the main top-level entry
points are these two (see ahead for more on their arguments):

   createzipfile(zipname, [addnames],
           storedirs=True, cruftpatts={}, 
           atlinks=False,  trace=print, 
           zipat=None,     nocompress=False)
                     
   extractzipfile(zipname, pathto='.',
           nofixlinks=False,  trace=print, 
           permissions=False, nomangle=False)

Pass "trace=lambda *p, **k: None" to silence most messages from these calls.
See also scripts zip-create.py and zip-extract.py for command-line clients,
and zipcruft.cruft_skip_keep for a default "cruftpatts" cruft-file definition. 
All of these have additional documentation omitted here.

This ziptools package mostly extends Python's zipfile module with top-level
convenience tools that add some important missing features:

   * For folders, adds the folder's entire tree to the zipfile automatically
   * For zipfile creates, filters out cruft (hidden metadata) files on request
   * For zipfile extracts, retains original modtimes for files, folders, links
   * For symlinks, adds/recreates the link itself to/from zipfiles, by default
   * For Windows, supports long pathnames by lifting the normal length limit
   * For zipfile extracts, optionally retains access permissions for all items
   * For all items, adds UTC-timestamp modtimes immune to DST and timezone
================================================================================
"""


from __future__ import print_function           # py 2.X compatibility

import os, sys, shutil
from zipfile import ZipFile                     # stdlib base support
from zipfile import ZIP_DEFLATED, ZIP_STORED    # compressed, or not

# nested package so same if used as main script or package in py3.X

# default cruft-file patterns, import here for importers ({}=don't skip)
from .zipcruft import cruft_skip_keep, isCruft    # [1.1] isCruft moved

# major workaround to support links: split this narly code off to a module...
from .zipsymlinks import addSymlink, isSymlink, extractSymlink

# also major: fix any too-long Windows paths on archive adds and extracts
from .ziplongpaths import FWP, UFWP

# UTC timestamp zip/unzip [1.2]
from .zipmodtimeutc import addModtimeUTC, getModtimeUTCorLocal

# interoperability nits [1.1]
RunningOnPython2 = sys.version.startswith('2')
RunningOnMacOS   = sys.platform.startswith('darwin')
RunningOnWindows = sys.platform.startswith('win')



#===============================================================================

_builtinprint = print

#===============================================================================



def tryrmtree(folder, trace=print):

    if os.path.exists(FWP(folder)):
        trace('Removing', folder)
        try:
            if os.path.islink(FWP(folder)):
                os.remove(FWP(folder))
            else:
                shutil.rmtree(FWP(folder, force=True))    # recurs: always \\?\
        except Exception as why:
            print('shutil.rmtree (or os.remove) failed:', why)
            input('Try running again, and press Enter to exit.')
            sys.exit(1)



#===============================================================================



def isRecursiveLink(dirpath):

    trace = lambda *args: None                  # or print to watch

    # called iff atlinks: following links
    if (not os.path.islink(FWP(dirpath)) or     # dir item not a link?
        os.stat(os.getcwd()).st_ino == 0):      # platform has no inodes?
        return False                            # moot, or hope for best 
    else:
        # collect inode ids for each path extension except last
        inodes = []
        path = []
        parts = dirpath.split(os.sep)[:-1]      # all but link at end
        while parts:
            trace(path, parts)
            path    += [parts[0]]               # add next path part
            parts    = parts[1:]                # expand, fetch inode
            thisext  = os.sep.join(path)
            thispath = os.path.abspath(thisext)
            inodes.append(os.stat(FWP(thispath)).st_ino)

        # recursive if points to item with same inode as any item in path               
        linkpath = os.path.abspath(dirpath)
        trace(inodes, os.stat(FWP(linkpath)).st_ino)
        return os.stat(FWP(linkpath)).st_ino in inodes



#===============================================================================



def isRecursiveLink0(dirpath, visited):

    # called iff atlinks: following links
    if not os.path.islink(dirpath):
        # skip non-links
        return False                                      # don't note path
    else:
        # check links history
        realpath = os.path.realpath(dirpath)              # dereference, abs
        #print('\t', dirpath, '\n\t', realpath, sep='')
        if (realpath in visited and
            any(dirpath.startswith(prior) for prior in visited[realpath])):
            return True          
        else:
            # record this link's visit
            visited[realpath] = visited.get(realpath, []) # add first or next
            visited[realpath].append(dirpath)
            return False



#===============================================================================



class CreateStats:
    """
    -----------------------------------------------------------------------
    Helper for recursive create (zip) stats counters [1.1].
    May also pass same mutable instance instead of using +=.
    -----------------------------------------------------------------------
    """
    attrs = 'files', 'folders', 'symlinks', 'unknowns', 'crufts'

    def __init__(self):
        for attr in self.attrs:
            setattr(self, attr, 0)       # or exec() strs

    def __iadd__(self, other):           # += all attrs in place
        for attr in self.attrs:
            setattr(self, attr, getattr(self, attr) + getattr(other, attr))
        return self

    def __repr__(self, format='%s=%%d'):
        display = ', '.join(format % attr for attr in self.attrs)
        return display % tuple(getattr(self, attr) for attr in self.attrs) 



class ExtractStats(CreateStats):
    """
    -----------------------------------------------------------------------
    Extract (unzip) stats: unknowns unlikely, no crufts or recursion.
    [1.3] Add mangled and skipped, but don't display unless nonzero.
    -----------------------------------------------------------------------
    """
    attrs = ['files', 'folders', 'symlinks', 'unknowns', 'mangled', 'skipped']

    def __repr__(self, format='%s=%%d'):
        """
        Don't show mangled or skipped if 0: rare and too much info
        """
        self.attrs = ExtractStats.attrs[:]      # .copy(), but work in py 2.X 
        for attr in ['mangled', 'skipped']:
              if getattr(self, attr) == 0: self.attrs.remove(attr)
        return CreateStats.__repr__(self, format)



def _testCreateStats():
    x = CreateStats()
    print(x)  # files=0, folders=0, symlinks=0, unknowns=0, crufts=0

    x.files += 1; x.folders += 2;  x.symlinks += 3
    print(x)  # files=1, folders=2, symlinks=3, unknowns=0, crufts=0

    y = CreateStats()
    y.folders += 10; y.unknowns += 20
    x += y
    print(x)  # files=1, folders=12, symlinks=3, unknowns=20, crufts=0



#===============================================================================



def addEntireDir(thisdirpath,      # pathname of directory to add (rel or abs)
                 zipfile,          # open zipfile.Zipfile object to add to 
                 stats,            # counters instance, same at all levels [1.1]
                 thiszipatpath,    # modified pathname if zipat/zip@ used [1.2]
                 storedirs=True,   # record dirs explicitly in zipfile?
                 cruftpatts={},    # cruft files skip/keep, or {}=do not skip
                 atlinks=False,    # zip items referenced instead of links?
                 trace=print):     # trace message router (or lambda *p, **k: None)

    # 
    # handle this dir
    #
    if storedirs and thisdirpath != '.':
        # add folders too
        stats.folders += 1
        trace2('Adding folder', thisdirpath, thiszipatpath, trace)  
        zipfile.write(filename=FWP(thisdirpath),             # fwp for file tools
                      arcname=thiszipatpath)                 # not \\?\ + abs, -zip@?
        addModtimeUTC(zipfile, FWP(thisdirpath))             # UTC modtimes [1.2]

    # 
    # handle items here
    #
    for itemname in os.listdir(FWP(thisdirpath)):            # list (fixed windows) path
        itempath  = os.path.join(thisdirpath, itemname)      # extend real provided path
        zipatpath = os.path.join(thiszipatpath, itemname)    # possibly munged path [1.2]
        
        # 
        # handle subdirs (and links to them)
        #
        if os.path.isdir(FWP(itempath)):
            if isCruft(itemname, cruftpatts):                # match name, not path
                # skip cruft dirs
                stats.crufts += 1
                trace('--Skipped cruft dir', itempath)

            elif atlinks:
                # following links: follow? + add
                if isRecursiveLink(itempath):
                    # links to a parent: copy dir link instead
                    stats.symlinks += 1
                    trace('Recursive link copied', itempath)
                    addSymlink(FWP(itempath), zipatpath, zipfile, trace)
                else:
                    # recur into dir or link
                    addEntireDir(itempath, zipfile,     
                                 stats, zipatpath, 
                                 storedirs, cruftpatts, atlinks, trace)

            else:
                # not following links
                if os.path.islink(FWP(itempath)):
                    # copy dir link
                    stats.symlinks += 1 
                    trace2('Adding  link  ~folder', itempath, zipatpath, trace) 
                    addSymlink(FWP(itempath), zipatpath, zipfile, trace)               
                else:
                    # recur into dir
                    addEntireDir(itempath, zipfile, 
                                 stats, zipatpath,
                                 storedirs, cruftpatts, atlinks, trace)

        # 
        # handle files (and links to them)
        # 
        elif os.path.isfile(FWP(itempath)):
            if isCruft(itemname, cruftpatts):
                # skip cruft files
                stats.crufts += 1
                trace('--Skipped cruft file', itempath)

            elif atlinks:
                # following links: follow? + add
                stats.files += 1
                trace2('Adding  file ', itempath, zipatpath, trace)
                zipfile.write(filename=FWP(itempath),         # fwp for file tools
                              arcname=zipatpath)              # not \\?\ + abs, -zip@?
                addModtimeUTC(zipfile, FWP(itempath))         # UTC modtimes [1.2]

            else:
                # not following links
                if os.path.islink(FWP(itempath)):
                    # copy file link
                    stats.symlinks += 1  
                    trace2('Adding  link  ~file', itempath, zipatpath, trace)
                    addSymlink(FWP(itempath), zipatpath, zipfile, trace)
                else:
                    # add simple file
                    stats.files += 1
                    trace2('Adding  file ', itempath, zipatpath, trace)
                    zipfile.write(filename=FWP(itempath),     # fwp for file tools
                                  arcname=zipatpath)          # name in archive, -zip@?
                    addModtimeUTC(zipfile, FWP(itempath))     # UTC modtimes [1.2]

        #
        # handle non-file/dir links (to nonexistents or oddities)
        #
        elif os.path.islink(FWP(itempath)):
            if isCruft(itemname, cruftpatts):
                # skip cruft non-file/dir links
                stats.crufts += 1
                trace('--Skipped cruft link', itempath)

            else:
                # copy link to other: atlinks or not
                stats.symlinks += 1   
                trace2('Adding  link  ~unknown', itempath, zipatpath, trace)
                addSymlink(FWP(itempath), zipatpath, zipfile, trace)

        #
        # handle oddities (not links to them)
        #
        else:
            # ignore cruft: not adding this
            stats.unknowns += 1
            trace('--Skipped unknown type:', itempath)       # skip fifos, etc.

        # goto next item in this folder



#===============================================================================



def zipatmunge(sourcepath, zipat):
    
    if zipat is None:
        return sourcepath    # zip@ not used, or zipat not passed

    assert isinstance(zipat, str)
    zipat = zipat.rstrip(os.sep)                               # drops trailing slash
    sourceroot, sourceitem = os.path.split(sourcepath)         # ditto, but implicit

    if sourceroot == '':                                       # source has no path:
        return os.path.join(zipat, sourcepath)                 #   concat zipat, if any
    elif zipat in ['.', '']:                                   # zipat is '.' or '': 
        return sourceitem                                      #   rm root path, if any
    else:                                                      # else replace root path
        return sourcepath.replace(sourceroot, zipat, 1)        # but just at the front



#===============================================================================



def trace2(message, filepath, zipatpath, trace):

    # mimic what zipfile will do
    arcname = os.path.splitdrive(zipatpath)[1]
    arcname = os.path.normpath(arcname)
    arcname = arcname.lstrip(os.sep + (os.altsep or ''))

    # but not this: filepath still has '\' on Windows!
    # arcname = arcname.replace(os.sep, "/")

    trace(message, filepath)
    if arcname != filepath:
        trace('\t\t=> %s' % arcname)    # sans leading '/\', '.', most '..', '\', 'c:'



#===============================================================================
    
    

def createzipfile(zipname,            # pathname of new zipfile to create
                  addnames,           # sequence of pathnames of items to add
                  storedirs=True,     # record dirs explicitly in zipfile?
                  cruftpatts={},      # cruft files skip/keep, or {}=do not skip
                  atlinks=False,      # zip items referenced instead of links?
                  trace=print,        # trace message router (or lambda *p, **k: None)
                  zipat=None,         # alternate root zip path for all items [1.2]
                  nocompress=False):  # store uncompressed in zipfile for speed [1.3]

    trace('Zipping', addnames, 'to', zipname)
    if cruftpatts:
        trace('Cruft patterns:', cruftpatts)
    stats = CreateStats()    # counts [1.1]
 
    #
    # handle top-level items
    #
    compress = ZIP_STORED if nocompress else ZIP_DEFLATED
    zipfile = ZipFile(zipname, mode='w', compression=compress, allowZip64=True)
    for addname in addnames:
 
        # force Unicode in Python 2.X so non-ASCII interoperable [1.1]
        if RunningOnPython2:
            try:
                addname = addname.decode(encoding='UTF-8')    # same as unicode()
            except:
                trace('**Cannot decode "%s": skipped' % addname)
                continue

        # change zipped paths for top-level sources if -zip@/zipat [1.2]
        zipatpath = zipatmunge(addname, zipat)

        if (addname not in ['.', '..'] and
            isCruft(os.path.basename(addname), cruftpatts)):
            stats.crufts += 1
            trace('--Skipped cruft item', addname)

        elif os.path.islink(FWP(addname)) and not atlinks:
            stats.symlinks += 1
            trace2('Adding  link  ~item', addname, zipatpath, trace)
            addSymlink(FWP(addname), zipatpath, zipfile, trace)

        elif os.path.isfile(FWP(addname)):
            stats.files += 1
            trace2('Adding  file ', addname, zipatpath, trace)
            zipfile.write(filename=FWP(addname), arcname=zipatpath)
            addModtimeUTC(zipfile, FWP(addname))    # UTC modtimes [1.2]

        elif os.path.isdir(FWP(addname)):
            addEntireDir(addname, zipfile,
                         stats, zipatpath,
                         storedirs, cruftpatts, atlinks, trace)

        else: # fifo, etc.
            stats.unknowns += 1
            trace('--Skipped unknown type:', addname)

    zipfile.close()
    return stats       # [1.1] printed at shell



#===============================================================================



def showpath(pathto, pathtoWasRelative):

    if RunningOnWindows:
        pathto = UFWP(pathto)                       # strip \\?\
        if pathtoWasRelative:
            try:
                pathto = os.path.relpath(pathto)    # relative to '.'
            except:
                pass                                # abondon ship [1.3]
    return pathto



#===============================================================================



def trace3(zippath, unzippath, trace):

    # folders: drop trailing slash in zipfile to compare
    zippathX = zippath.rstrip('/\\')    # or r'\/'

    # Windows: match Unix slashes in zipfile to compare
    if RunningOnWindows and '/' in zippath:
        unzippathX = unzippath.replace('\\', '/')
    else:
        unzippathX = unzippath

    if zippathX == unzippathX:
        # new lite format
        trace('Extracted %s' % zippath)
    else:
        # original format
        trace('Extracted %s\n\t\t=> %s' % (zippath, unzippath))



#===============================================================================



# Disable zipfile's auto-mangle on Windows.  There is no good way to 
# customize its private _sanitize method, so do this bad way instead.
# A class with __getitem__ that raises LookupError is likely slower.

ZipFile._windows_illegal_name_trans_table = {None: None}



def trymangle(zipinfo, pathto, nomangle=False, trace=print):
 
    if not RunningOnWindows:
        # only mangle on Windows: Android shared storage botches folders
        return False

    elif nomangle:
        # no changes if disabled in ziptools command or call
        return False

    else:
        # split and consume path separators 
        zippath0 = zipinfo.filename                     # unzip path recorded in zipfile
        zippath1 = zippath0.replace('/', os.path.sep)   # unix+android no-op, windows /=>\
        zippath2 = os.path.splitdrive(zippath1)[1]      # drop a c: on windows else :=>_
        zipparts = zippath2.split(os.path.sep)          # unix+android on /, windows on \
        
        # illegal chars
        nonportables = ' \x00 / \\ | < > ? * : " '      # for filesystems, not platforms
        nonportables = nonportables.replace(' ', '')    # drop space used for readability

        if not any(c in part for part in zipparts for c in nonportables):
            # none found: mangling won't help
            return False

        else:
            # mangle the entire path
            replacements = {ord(c): '_' for c in nonportables}
            mangledparts = [part.translate(replacements) for part in zipparts]

            # join with zip / even on windows: trailing / means dir in zipfile
            mangledpath  = '/'.join(mangledparts)

            # replace in zipfile structure: required by zipfile.extract()
            zipinfo.filename = mangledpath
            message = '--Name mangled:\n    from... %s\n    to..... %s'
            trace(message % (zippath0, mangledpath))
            return True

#===============================================================================

def extractzipfile(zipname,               # pathname of zipfile to extract from
                   pathto='.',            # pathname of folder to extract to
                   nofixlinks=False,      # do not translate symlink separators? 
                   trace=print,           # trace router (or lambda *p, **k: None)
                   permissions=False,     # propagate saved permisssions? [1.1]
                   nomangle=False):       # don't mod bad filename chars to '_' on errors?
    if trace is None:
        trace = lambda *args, **kwargs: None
    trace('Unzipping from', zipname, 'to', pathto)
    dirmodtimes = []
    stats = ExtractStats()

    # always prefix with \\?\ on Windows: joined-path lengths are unknown;
    # hence, on Windows 'savepath' result is also \\?\-prefixed and absolute;

    pathtoWasRelative = not os.path.isabs(pathto)   # user gave relative?
    pathto = FWP(pathto, force=True)                # add \\?\, make abs
    
    #
    # extract all items in zip
    #
    zipfile = ZipFile(zipname, mode='r', allowZip64=True)
    for zipinfo in zipfile.infolist():              # for all items in zip
        origname = zipinfo.filename                 # before trymangle mods

        # 
        # extract one item
        #
        try:
            if isSymlink(zipinfo):
                # read/save link path: stubs on non-mangle failures
                trace('(Link)', end=' ')
                try:
                    savepath = extractSymlink(
                           zipinfo, pathto, zipfile, nofixlinks, trace)
                except:
                    # retry with mangled name? [1.3]
                    if trymangle(zipinfo, pathto, nomangle, trace):
                        savepath = extractSymlink(
                               zipinfo, pathto, zipfile, nofixlinks, trace, origname)
                        stats.mangled += 1
                    else:
                        raise  # reraise

            else:
                # create file or dir: skip on all failures
                try:
                    savepath = zipfile.extract(zipinfo, pathto) 
                except:
                    # retry with mangled name? [1.3]
                    if trymangle(zipinfo, pathto, nomangle, trace):
                        savepath = zipfile.extract(zipinfo, pathto) 
                        stats.mangled += 1
                    else:
                        raise  # reraise

        except Exception as E:
            # continue with rest on any item failure post mangle retry [1.3]
            stats.skipped += 1
            trace('**SKIP - item failed and skipped:', zipinfo.filename)
            trace('Python exception: %s, %s' % (E.__class__.__name__, E))
            continue  # next zipinfo in for loop
                
        # show both from+to paths iff they differ
        filename = zipinfo.filename                          # item's path in zip 
        showname = showpath(savepath, pathtoWasRelative)     # undo fwp on windows           
        trace3(filename, showname, trace)                    # show 1 or 2 lines [1.3]

        # 
        # propagate permissions from/to Unix for all, iff enabled [1.1]
        #
        if permissions:
            try:                                          # create saved perms
                perms = zipinfo.external_attr >> 16       # to lower 16 bits
                if perms != 0:

                    if os.path.islink(savepath):
                        # mod link itself, where supported
                        # not on Windows, Py3.2 and earlier
                        # Mac OS bug moot: no-op on exFAT
 
                        if (hasattr(os, 'supports_follow_symlinks') and
                            os.chmod in os.supports_follow_symlinks):
                            os.chmod(savepath, perms, follow_symlinks=False)

                        # Unix Py 2.X and 3.2- have lchmod, but not f_s
                        elif hasattr(os, 'lchmod'):
                            os.lchmod(savepath, perms)

                    else:
                        # mod file or dir, where supported (exFAT=no-op)
                        os.chmod(savepath, perms) 
            except:
                trace('--Error setting permissions')         # e.g., pre-Oreo Android

        # 
        # propagate modtime to files, links (and dirs on some platforms)
        #
        zipinfo.filename = origname                          # lookup premangle [1.3]
        datetime = getModtimeUTCorLocal(zipinfo, zipfile)    # UTC if present [1.2]

        if os.path.islink(savepath):
            # reset modtime of link itself where supported
            # but not on Windows or Py3.2-: keep now time
            # and call _twice_ on Mac for exFAT drives bug  

            stats.symlinks += 1
            if (hasattr(os, 'supports_follow_symlinks') and  # iff utime does links
                os.utime in os.supports_follow_symlinks):
                try:
                    os.utime(savepath, (datetime, datetime), follow_symlinks=False)
                except:
                    trace('--Error setting link modtime')    # pre-Oreo Android [1.2]
                else:
                    # go again for Mac OS exFAT bug
                    if RunningOnMacOS:
                        os.utime(savepath, (datetime, datetime), follow_symlinks=False)

        elif os.path.isfile(savepath):
            # reset (non-link) file modtime now              # no Mac OS exFAT bug 
            stats.files += 1
            try:
                os.utime(savepath, (datetime, datetime))     # dest time = src time 
            except:
                trace('--Error setting file modtime')        # pre-Oreo Android [1.2]

        elif os.path.isdir(savepath):
            # defer (non-link) dir till after add files
            stats.folders += 1
            dirmodtimes.append((savepath, datetime))         # where supported

        else:
            # bad type in zipfile
            stats.unknowns += 1
            assert False, 'Unknown type extracted'           # should never happen

    # 
    # reset (non-link) dir modtimes now, post file adds
    #
    for (savepath, datetime) in dirmodtimes:
        try:
            os.utime(savepath, (datetime, datetime))         # reset dir mtime now
        except:                                              # pre-Oreo Android [1.2]
            trace('--Error settting folder modtime')
        else:                                                # but ok on Windows/Unix
            # go again for Mac OS exFAT bug [1.1]
            if RunningOnMacOS:
                os.utime(savepath, (datetime, datetime))

    zipfile.close()
    return stats       # to be printed at shell [1.1]



#===============================================================================

# see ../selftest.py for former __main__ code cut here for new pkg structure
