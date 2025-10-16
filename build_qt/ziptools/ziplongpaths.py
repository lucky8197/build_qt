from __future__ import print_function   # py 2.x
import sys, os


TracePaths = False             # show expanded paths? (here or arg)

FileLimit  = 260 - 1           # 259 in Py, including 3 for drive, N for UNC
DirLimit   = FileLimit - 12    # 247 in Py, after reserving 12 for 8.3 name

# only need to care here
RunningOnWindows  = sys.platform.startswith('win')



def fixLongWindowsPath(pathname, force=False, limit=DirLimit, trace=TracePaths):
    if not RunningOnWindows:
        # Mac, Linux, etc.: no worries
        return pathname
    else:
        abspathname = os.path.abspath(pathname)       # use abs len (see above)
        if len(abspathname) <= limit and not force:   # rel path len is moot
            # Windows path within limits: ok
            return pathname
        else:
            # Windows path too long: fix it
            pathname = abspathname                    # to absolute, and / => \
            extralenprefix = '\\\\?\\'                # i.e., \\?\ (or r'\\?'+'\\')
            if not pathname.startswith('\\\\'):       # i.e., \\   (or r'\\')
                # local drives: C:\
                pathname = extralenprefix + pathname  # C:\dir => \\?\C:\dir
            else:
                # network drives: \\...               # \\dev  => \\?\UNC\dev
                pathname = extralenprefix + 'UNC' + pathname[1:]
            if trace: print('Extended path =>', pathname[:60])
            return pathname



def unfixLongWindowsPath(pathname):
    if not pathname.startswith('\\\\?\\'):      # never will on Mac, Linux
        return pathname                         # may or may not on Windows
    else:
        if pathname.startswith('\\\\?\\UNC'):
            return '\\' + pathname[7:]          # network: drop \\?\UNC, add \
        else:
            return pathname[4:]                 # local: drop \\?\ only



#---------------------------------------------------------------------
# Shorter synonyms for coding convenience
# FWP stands for "Fix Windows Paths" (officially...)
#---------------------------------------------------------------------

FWP      = fixLongWindowsPath      # generic: use most-inclusive limit (dirs)
FWP_dir  = FWP                     # or force dir-path or file/other limits
FWP_file = lambda *pargs, **kargs: FWP(*pargs, limit=FileLimit, **kargs)
UFWP     = unfixLongWindowsPath

