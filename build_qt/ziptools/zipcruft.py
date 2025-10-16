from fnmatch import fnmatchcase    # non-case-mapping version


#===============================================================================



# Cruft patterns: used by scripts, and callers that import it


# skip all files and folders matching these
cruft_skip = [
    '.*',                # Unix hidden files, Mac junk files
    '[dD]esktop.ini',    # Windows appearance
    'Thumbs.db',         # Windows caches
    '~*',                # Office temp files
    '$Recycle.bin',      # Windows recycle bin (in full, [1.3])
    '*.py[co]',          # Python bytecode files
    '__pycache__'        # Python 3.2+ bytecode folder [1.3]
    ]


# never skip any matching these, even if they match a skip pattern (=mergeall [1.3])
cruft_keep = [
    '.htaccess*',        # Apache website config files
    '.login',            # Unix login settings, but unlikely in an archive?
    '.bash*',            # Ditto, but for the bash shell (linux, mac)
    '.profile',          # Various uses
    '.svn',              # Source control system storage, unlikely in archive?
    '.nomedia'           # Android media-scan blocker, in content root
    ]


# pass the pair as a dict to ziptools.createzipfile() if desired 
cruft_skip_keep = {'skip': cruft_skip,
                   'keep': cruft_keep}



#===============================================================================



def isCruft(filename, cruftpatts=cruft_skip_keep):
    return (cruftpatts
            and
            any(fnmatchcase(filename, patt) for patt in cruftpatts['skip'])
            and not
            any(fnmatchcase(filename, patt) for patt in cruftpatts['keep']))

