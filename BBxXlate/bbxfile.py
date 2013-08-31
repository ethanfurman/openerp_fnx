"""
Bbx File utilities.
"""

import os, string

def asc(strval):                    ##USED in bbxfile
    if len(strval) == 0:
        return 0
    elif len(strval) == 1:
        try:
            return ord(strval)
        except:
            return long(ord(strval))
    else:
        return 256L*(asc(strval[:-1]))+ord(strval[-1])


def applyfieldmap(record, fieldmap):
    if fieldmap == None:
        return record
    elif type(fieldmap) != type({}):
        raise FieldMapTypeError("FieldMap must be a dictionary of fieldindex[.startpos.endpos]:fieldname")
    retval = {}
    fieldmapkeys = fieldmap.keys()
    fieldmapkeys.sort()
    for item in fieldmapkeys:
        fieldparams = string.split(item,".")
        field = int(fieldparams[0])
        startpos = endpos = ''
        if len(fieldparams) > 1:
            startpos = fieldparams[1]
        if len(fieldparams) == 3:
            endpos = fieldparams[2]
        fieldeval = `record[field]` + '['+startpos+":"+endpos+']'
        retval[fieldmap[item]] = eval(fieldeval)
    return retval


class BBxRec(object):
    # define datamap as per the iolist in the subclasses
    datamap = "iolist here".split(",")

    def __init__(self, rec, datamap, fieldlist):
        self.rec = rec
        self.datamap = [ xx.strip() for xx in datamap ]
        if fieldlist is None:
            fieldlist = []
            for fieldvar in datamap:
                fieldlist.append(None, '', None, fieldvar, None)
        self.fieldlist = fieldlist

    def __getitem__(self, ref):
        if isinstance(ref, (int, long)):
            ref, mask = self.fieldlist[ref][3:5]
            ref = [ref]
            if mask and ',0)' not in mask:
                masks = ["%%%s.%sf" % tuple(mask[1:-1].split(','))]
            else:
                masks = ['%s']
            single = True
        elif isinstance(ref, slice):
            ref = [r[3] for r in self.fieldlist[ref]]
            masks = [r[4] for r in self.fieldlist[ref]]
            for i, mask in enumerate(masks):
                if mask and ',0)' not in mask:
                    masks[i] = ["%%%s.%sf" % tuple(mask[1:-1].split(','))]
                else:
                    masks[i] = ['%s']
            single = False
        else:
            ref = ref.title()
            for fld in self.fieldlist:
                if fld[3] == ref:
                    mask = fld[4]
                    break
            else:
                raise ValueError('%s is not a valid field' % ref)
            ref = [ref]
            if mask and ',0)' not in mask:
                masks = ["%%%s.%sf" % tuple(mask[1:-1].split(','))]
            else:
                masks = ['%s']
            single = True
        result = []
        for r, m in zip(ref, masks):
            if r in self.datamap:
                var, sub = r, ''
            else:
                var, sub = (r+"(").split("(")[:2]
            try:
                varidx = self.datamap.index(var)
            except ValueError, err:
                raise ValueError('%s is not a valid field' % var)
            val = self.rec[varidx]
            if sub:
                sub = sub[:-1]
                first,last = [ int(x) for x in sub.split(",") ]
                val = val[first-1:first+last-1]
            if 'f' in m:
                try:
                    val = float(val)
                except ValueError:
                    m = '<%s>'
            result.append((m % val).strip())
        if single:
            return result[0]
        return result

    def __setitem__(self, ref, newval):
        if isinstance(ref, (int, long)):
            ref = self.fieldlist[ref][3]
        if ref in self.datamap:
            var, sub = ref, ''
        else:
            var, sub = (ref+"(").split("(")[:2]
        try:
            varidx = self.datamap.index(var)
        except ValueError, err:
            raise ValueError('%s is not a valid field' % var)
        val = self.rec[varidx]
        if sub:
            sub = sub[:-1]
            first,last = [ int(x) for x in sub.split(",") ]
            val = val[first-1:first+last-1]
            self.rec[varidx][first-1:first+last-1] = newval
        else:
            self.rec[varidx] = newval

    def __repr__(self):
        return repr(self.rec)

    def __str__(self):
        lines = []
        for i, row in enumerate(self.fieldlist):
            if '$' in row[3]:
                lines.append('%5d | %-12s | %-35s | %s' % (i, row[3], self[row[3]], row[1]))
            else:
                lines.append('%5d | %-12s | %35s | %s' % (i, row[3], self[row[3]], row[1]))
        return '\n'.join(lines)


def getSubset(itemslist, pattern):
    # returns a sorted itemslist where keys match pattern
    import sre
    if pattern:
        itemslist = [ (xky,xrec) for (xky,xrec) in itemslist if sre.search(pattern, xky) ]
    itemslist.sort()
    return itemslist

def BBVarLength(datamap, fieldlist):
    dm_iter = iter(datamap)
    current_var = next(dm_iter)
    length = 0
    result = []
    for field in fieldlist:
        if not field[3].startswith(current_var):
            result.append(length)
            try:
                current_var = next(dm_iter)
            except StopIteration:
                return result
            length = 0
        length += field[2]
    result.append(length)
    return result

class BBxFile(object):

    def __init__(self, srcefile, datamap, fieldlist, keymatch=None, subset=None, filter=None, rectype=None, name=None, desc=None):
        records = {}
        datamap = [xx.strip() for xx in datamap]
        leader = trailer = None
        if rectype:
            token, start, stop = rectype
        if keymatch:
            first_ps = keymatch.find('%s')
            last_ps = keymatch.rfind('%s')
            if first_ps != -1:
                leader = keymatch[:first_ps]
            if last_ps != -1:
                trailer = keymatch[last_ps+2:]     # skip the %s ;)
        fieldlengths = BBVarLength(datamap, fieldlist)
        fixedLengthFields = set([fld for fld in fieldlist if '$' in fld and field[-1] != '$'])
        for ky, rec in getfile(srcefile).items():
            if (len(ky) != fieldlengths[0]
            or  len(rec) < len(fieldlengths)
            or  any(len(field) != length for field, length, name in
                    zip(rec, fieldlengths, datamap) if name in fixedLengthFields)
            or  rectype and ky[start:stop] != token):
                continue    # record is not a match for this table
            rec = BBxRec(rec, datamap, fieldlist)
            if filter:
                if filter(rec):
                    records[ky] = rec
            elif leader is None or ky.startswith(leader):
                if trailer is None or ky.endswith(trailer):
                    records[ky] = rec
        self.records = records
        self.datamap = datamap
        self.fieldlist = fieldlist
        self.keymatch  = keymatch
        self.subset  = subset
        self.rectype = rectype
        self.name = name
        self.desc= desc

    def __contains__(self, ky):
        return self[ky] is not None

    def __getitem__(self, ky):
        if self.records.has_key(ky):
            return self.records[ky]
        elif self.keymatch:
            if self.records.has_key(self.keymatch % ky):
                return self.records[self.keymatch % ky]
        raise KeyError(ky)

    def __iter__(self):
        """
        iterates through the records (all records kept during __init__, ignores subsequent keymatch settings, etc.)
        """
        return iter(self.records.values())

    def __len__(self):
        return len(self.records)

    def __repr__(self):
        pieces = []
        for attr in ('name desc keymatch subset rectype'.split()):
            value = getattr(self, attr)
            if value is not None:
                if attr is 'rectype':
                    value = value[0]
                pieces.append("%s=%r" % (attr, value))
        return "BBxFile(%s)" % (', '.join(pieces) + "[%d records]" % len(self.records))

    def get_subset(self, ky):
        if not self.subset:
            raise ValueError('subset not defined')
        match = self.subset % ky
        rv = [(key,rec) for key,rec in self.records.items() if key.startswith(match)]
        rv.sort()
        return rv

    def keys(self):
        return self.records.keys()

    def items(self):
        return self.records.items()

    def has_key(self, ky):
        #print 'testing for %s ' % ky
        return not not self[ky]

    def values(self):
        return self.records.values()

    def iterpattern(self, pattern=None):
        xx = getSubset(self.items(), pattern)
        return iter(xx)


def getfile(filename=None, fieldmap=None):
    """
Read BBx Mkeyed, Direct or Indexed file and return it as a dictionary.

Format: target = getfile([src_dir]filename [,fieldmap = {0:'field 0 name',3:'field 3 name'})
Notes:  The entire file is read into memory.
        Returns None on error opening file.
    """
    default_file = r'C:\Zope\v2.4\Extensions\WSGSourceData\ICCXF0'

    default_srce_loc, default_filename = os.path.split(default_file)
    if filename:
        srce_loc, filename = os.path.split(filename)
        if srce_loc == '': srce_loc = default_srce_loc
    else:
        srce_loc, filename = os.path.split(default_file)

    try:
        data = open(filename,'rb').read()
    except:
        try:
            data = open(srce_loc + os.sep + filename,'rb').read()
        except:
            print "(srce_loc, filename)", (srce_loc, filename)
            raise Exception("File not found or read/permission error. (%s: %s)" % (filename, srce_loc))

    #hexdump(data)
    #raise "Breaking..."

    blocksize = 512
    reclen = int(asc(data[13:15]))
    reccount = int(asc(data[9:13]))
    keylen = ord(data[8])
    filetype = ord(data[7])
    keychainkeycount = 0
    keychainkeys = {}
    if filetype == 6:           # MKEYED
        blockingfactor = ord(data[116])
        for fblock in range(0,len(data),blocksize):         # sniff out a key block...
            if data[fblock] != '\0' \
              and data[fblock+1] == '\0' \
              and data[fblock+5] != '\0':
                keysinthiskeyblock = ord(data[fblock])      # ... then parse and follow the links to the records
                keychainkeycount = keychainkeycount + keysinthiskeyblock
                for thiskey in range(fblock+5,fblock+5+keysinthiskeyblock*(keylen+8),keylen+8):
                    keychainkey =  string.split(data[thiskey:thiskey+keylen],'\0',1)[0]
                    keychainrecblkptr = int(asc(data[thiskey+keylen:thiskey+keylen+3]) / 2)
                    keychainrecbyteptr = int(256*(asc(data[thiskey+keylen:thiskey+keylen+3]) % 2) + ord(data[thiskey+keylen+3]))
                    keychainrec = string.split(data[keychainrecblkptr*512+keychainrecbyteptr:keychainrecblkptr*512+keychainrecbyteptr+reclen],'\n')[:-1]
                    # Note:  The trailing [:-1] on the preceeding line is to chop off trailing nulls.  This could lose data in a packed record
                    if keychainrec:
                        keychainrec[0] = keychainkey
                        keychainrec = applyfieldmap(keychainrec, fieldmap)
                        keychainkeys[keychainkey] = keychainrec
    elif filetype == 2:         # DIRECT
        keysperblock = ord(data[62])
        #x#keyareaoffset = ord(data[50])+1
        keyareaoffset = int(asc(data[49:51]))+1
        keyptrsize = ord(data[56])
        nextkeyptr = int(asc(data[24:27]))
        netkeylen = keylen
        keylen = netkeylen + 3*keyptrsize
        dataareaoffset = keyareaoffset + reccount / keysperblock + 1
        while nextkeyptr > 0:
            lastkeyinblock = not(nextkeyptr % keysperblock)
            thiskeyptr = (keyareaoffset + (nextkeyptr/keysperblock) - lastkeyinblock)*blocksize + (((nextkeyptr % keysperblock)+(lastkeyinblock*keysperblock))-1)*keylen
            keychainkey = string.split(data[thiskeyptr:thiskeyptr+netkeylen],'\0',1)[0]
            thisdataptr = dataareaoffset*blocksize + (nextkeyptr-1)*reclen
            keychainrec = string.split(data[thisdataptr:thisdataptr+reclen],'\n')[:-1]
            # Note:  The trailing [:-1] on the preceeding line is to chop off trailing nulls.  This could lose data in a packed record
            if keychainrec:
                keychainrec[0] = keychainkey
                keychainrec = applyfieldmap(keychainrec, fieldmap)
                keychainkeys[keychainkey] = keychainrec
            nextkeyptr = int(asc(data[thiskeyptr+netkeylen:thiskeyptr+netkeylen+keyptrsize]))
            keychainkeycount = keychainkeycount + 1
    elif filetype == 0:         # INDEXED
        for i in range(15, reccount*reclen, reclen):
            keychainrec = string.split(data[i:i+reclen],'\n')[:-1]
            keychainrec = applyfieldmap(keychainrec, fieldmap)
            keychainkeys[keychainkeycount] = keychainrec
            keychainkeycount = keychainkeycount + 1
    else:
        #hexdump(data)
        raise Exception("UnknownFileTypeError: %s" % (filetype))
    return keychainkeys

if __name__ == '__main__':
    import time
    #print "Starting..."
    #for fn in ("ICIMF0","GMCMF0","GMAFF0","GMCFF0"):   # "ICCXF0",
    #    start = time.time()
    #    print fn, len(getfile(fn)), time.time()-start
    #start = time.time()
    #print "ICCXXF", len(open(r'C:\Zope\v2.4\Extensions\WSGSourceData\ICCXXF', 'rb').read()), time.time()-start
    
