BBxXlate/bbxfile.py                                                                                 0000664 0001750 0001750 00000026633 12125165312 013506  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  """
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
            ref = [self.fieldlist[ref]]
            single = True
        elif isinstance(ref, slice):
            ref = self.fieldlist[slice]
            single = False
        else:
            ref = [ref]
            single = True
        result = []
        for r in ref:
            if r in self.datamap:
                var, sub = r, ''
            else:
                var, sub = (r+"(").split("(")[:2]
            varidx = self.datamap.find(var)
            if varidx == -1:
                raise ValueError('%s is not a valid field' % var)
            else:
                val = self.rec[varidx]
            if sub:
                sub = sub[:-1]
                first,last = [ int(x) for x in sub.split(",") ]
                val = val[first-1:first+last-1]
            result.append(val)
        if single:
            return result[0]
        return result

    def __setitem__(self, ref, newval):
        if isinstance(ref, (int, long)):
            ref = self.fieldlist[ref]
        if ref in self.datamap:
            var, sub = ref, ''
        else:
            var, sub = (ref+"(").split("(")[:2]
        varidx = self.datamap.find(var)
        if varidx == -1:
            raise ValueError('%s is not a valid field' % var)
        else:
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

    def __init__(self, srcefile, datamap, fieldlist, keymatch=None, subset=None, section=None, rectype=None):
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
            or  len(rec) != len(fieldlengths)
            or  any(len(field) != length for field, length, name in
                    zip(rec, fieldlengths, datamap) if name in fixedLengthFields)
            or  rectype and ky[start:stop] != token):
                continue    # record is not a match for this table
            if section is None or ky.startswith(section):
                if trailer is None or ky.endswith(trailer):
                    records[ky] = BBxRec(rec, datamap, fieldlist)
        self.records = records
        self.datamap = datamap
        self.fieldlist = fieldlist
        self.keymatch  = keymatch
        self.subset  = subset
        self.section = section
        self.rectype = rectype

    def get_item_or_single(self, ky):
        if self.records.has_key(ky):
            return self.records[ky]
        elif self.keymatch:
            if self.records.has_key(self.keymatch % ky):
                return self.records[self.keymatch % ky]

    def __getitem__(self, ky):
        rv = self.get_item_or_single(ky)
        if rv:
            return rv
        elif self.subset:
            match = self.subset % ky
            rv = [ (xky,xrec) for (xky,xrec) in self.records.items() if xky.startswith(match) ]
            rv.sort()
            return rv

    def __contains__(self, ky):
        return self.get_item_or_single(ky)

    def __len__(self):
        return len(self.records)

    def keys(self):
        return self.records.keys()

    def items(self):
        return self.records.items()

    def has_key(self, ky):
        #print 'testing for %s ' % ky
        return not not self[ky]

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
                        if keychainrec[0] == '': keychainrec[0] = keychainkey
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
                if keychainrec[0] == '': keychainrec[0] = keychainkey
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
    
                                                                                                     BBxXlate/BBxFuncs.py                                                                                0000664 0001750 0001750 00000034040 07202016360 013532  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  def _A900(stmt, vartbl, ptr, retval):
	retval.append("")
	ptr += 1
	return ptr

def _A901(stmt, vartbl, ptr, retval):
	retval.append("AND(")
	ptr += 1
	return ptr

def _A902(stmt, vartbl, ptr, retval):
	retval.append("ARGV")
	ptr += 1
	return ptr

def _A903(stmt, vartbl, ptr, retval):
	retval.append("ATH(")
	ptr += 1
	return ptr

def _A904(stmt, vartbl, ptr, retval):
	retval.append("BIN(")
	ptr += 1
	return ptr

def _A905(stmt, vartbl, ptr, retval):
	retval.append("CHR(")
	ptr += 1
	return ptr

def _A906(stmt, vartbl, ptr, retval):
	retval.append("CPL(")
	ptr += 1
	return ptr

def _A907(stmt, vartbl, ptr, retval):
	retval.append("CRC(")
	ptr += 1
	return ptr

def _A908(stmt, vartbl, ptr, retval):
	retval.append("CVS(")
	ptr += 1
	return ptr

def _A909(stmt, vartbl, ptr, retval):
	retval.append("DATE")
	ptr += 1
	return ptr

def _A90A(stmt, vartbl, ptr, retval):
	retval.append(" DAY")
	ptr += 1
	return ptr

def _A90B(stmt, vartbl, ptr, retval):
	retval.append("DIR")
	ptr += 1
	return ptr

def _A90C(stmt, vartbl, ptr, retval):
	retval.append("DSK")
	ptr += 1
	return ptr

def _A90D(stmt, vartbl, ptr, retval):
	retval.append("FATTR")
	ptr += 1
	return ptr

def _A90E(stmt, vartbl, ptr, retval):
	retval.append("FBIN")
	ptr += 1
	return ptr

def _A90F(stmt, vartbl, ptr, retval):
	retval.append("FID(")
	ptr += 1
	return ptr

def _A910(stmt, vartbl, ptr, retval):
	retval.append("FIELD")
	ptr += 1
	return ptr

def _A911(stmt, vartbl, ptr, retval):
	retval.append("FILL")
	ptr += 1
	return ptr

def _A912(stmt, vartbl, ptr, retval):
	retval.append("FIN(")
	ptr += 1
	return ptr

def _A913(stmt, vartbl, ptr, retval):
	retval.append("GAP( ")
	ptr += 1
	return ptr

def _A914(stmt, vartbl, ptr, retval):
	retval.append("HSH(")
	ptr += 1
	return ptr

def _A915(stmt, vartbl, ptr, retval):
	retval.append("HTA(")
	ptr += 1
	return ptr

def _A916(stmt, vartbl, ptr, retval):
	retval.append("INFO")
	ptr += 1
	return ptr

def _A917(stmt, vartbl, ptr, retval):
	retval.append("IOR(")
	ptr += 1
	return ptr

def _A918(stmt, vartbl, ptr, retval):
	retval.append("KEY(")
	ptr += 1
	return ptr

def _A919(stmt, vartbl, ptr, retval):
	retval.append("KEYF(")
	ptr += 1
	return ptr

def _A91A(stmt, vartbl, ptr, retval):
	retval.append("KEYL(")
	ptr += 1
	return ptr

def _A91B(stmt, vartbl, ptr, retval):
	retval.append("KEYN(")
	ptr += 1
	return ptr

def _A91C(stmt, vartbl, ptr, retval):
	retval.append("KEYP(")
	ptr += 1
	return ptr

def _A91D(stmt, vartbl, ptr, retval):
	retval.append(" LRC(")
	ptr += 1
	return ptr

def _A91E(stmt, vartbl, ptr, retval):
	retval.append("LST(")
	ptr += 1
	return ptr

def _A91F(stmt, vartbl, ptr, retval):
	retval.append("NOT")
	ptr += 1
	return ptr

def _A920(stmt, vartbl, ptr, retval):
	retval.append("OPTS")
	ptr += 1
	return ptr

def _A921(stmt, vartbl, ptr, retval):
	retval.append("PCK")
	ptr += 1
	return ptr

def _A922(stmt, vartbl, ptr, retval):
	retval.append("PFX")
	ptr += 1
	return ptr

def _A923(stmt, vartbl, ptr, retval):
	retval.append("PGM(")
	ptr += 1
	return ptr

def _A924(stmt, vartbl, ptr, retval):
	retval.append("PUB")
	ptr += 1
	return ptr

def _A925(stmt, vartbl, ptr, retval):
	retval.append("REV")
	ptr += 1
	return ptr

def _A926(stmt, vartbl, ptr, retval):
	retval.append("SSN")
	ptr += 1
	return ptr

def _A927(stmt, vartbl, ptr, retval):
	retval.append("S TBL")
	ptr += 1
	return ptr

def _A928(stmt, vartbl, ptr, retval):
	retval.append("STR(")
	ptr += 1
	return ptr

def _A929(stmt, vartbl, ptr, retval):
	retval.append("SWAP")
	ptr += 1
	return ptr

def _A92A(stmt, vartbl, ptr, retval):
	retval.append("SYS")
	ptr += 1
	return ptr

def _A92B(stmt, vartbl, ptr, retval):
	retval.append("TBL")
	ptr += 1
	return ptr

def _A92C(stmt, vartbl, ptr, retval):
	retval.append("TSK(")
	ptr += 1
	return ptr

def _A92D(stmt, vartbl, ptr, retval):
	retval.append("XOR")
	ptr += 1
	return ptr

def _A92E(stmt, vartbl, ptr, retval):
	retval.append("CHN")
	ptr += 1
	return ptr

def _A92F(stmt, vartbl, ptr, retval):
	retval.append("KGEN")
	ptr += 1
	return ptr

def _A930(stmt, vartbl, ptr, retval):
	retval.append("SSORT")
	ptr += 1
	return ptr

def _A931(stmt, vartbl, ptr, retval):
	retval.append("ADJN")
	ptr += 1
	return ptr

def _A932(stmt, vartbl, ptr, retval):
	retval.append("SQLLIST")
	ptr += 1
	return ptr

def _A933(stmt, vartbl, ptr, retval):
	retval.append("SQLTABLES")
	ptr += 1
	return ptr

def _A934(stmt, vartbl, ptr, retval):
	retval.append("SQLTMPL")
	ptr += 1
	return ptr

def _A935(stmt, vartbl, ptr, retval):
	retval.append("SQLERR")
	ptr += 1
	return ptr

def _A936(stmt, vartbl, ptr, retval):
	retval.append("SQLFETCH")
	ptr += 1
	return ptr

def _A937(stmt, vartbl, ptr, retval):
	retval.append("FILEOPT")
	ptr += 1
	return ptr

def _A938(stmt, vartbl, ptr, retval):
	retval.append("CHANOPT")
	ptr += 1
	return ptr

def _A939(stmt, vartbl, ptr, retval):
	retval.append("SEVAL")
	ptr += 1
	return ptr

def _A800(stmt, vartbl, ptr, retval):
	retval.append("")
	ptr += 1
	return ptr

def _A801(stmt, vartbl, ptr, retval):
	retval.append("ABS(")
	ptr += 1
	return ptr

def _A802(stmt, vartbl, ptr, retval):
	retval.append("ARGC")
	ptr += 1
	return ptr

def _A803(stmt, vartbl, ptr, retval):
	retval.append("ASC(")
	ptr += 1
	return ptr

def _A804(stmt, vartbl, ptr, retval):
	retval.append("ATN")
	ptr += 1
	return ptr

def _A805(stmt, vartbl, ptr, retval):
	retval.append("BSZ")
	ptr += 1
	return ptr

def _A806(stmt, vartbl, ptr, retval):
	retval.append("COS")
	ptr += 1
	return ptr

def _A807(stmt, vartbl, ptr, retval):
	retval.append("CTL")
	ptr += 1
	return ptr

def _A808(stmt, vartbl, ptr, retval):
	retval.append("DEC(")
	ptr += 1
	return ptr

def _A809(stmt, vartbl, ptr, retval):
	retval.append("DSZ")
	ptr += 1
	return ptr

def _A80A(stmt, vartbl, ptr, retval):
	retval.append("EPT")
	ptr += 1
	return ptr

def _A80B(stmt, vartbl, ptr, retval):
	retval.append("ERR")
	ptr += 1
	return ptr

def _A80C(stmt, vartbl, ptr, retval):
	retval.append("FDEC")
	ptr += 1
	return ptr

def _A80D(stmt, vartbl, ptr, retval):
	retval.append("FPT(")
	ptr += 1
	return ptr

def _A80E(stmt, vartbl, ptr, retval):
	retval.append("HSA")
	ptr += 1
	return ptr

def _A80F(stmt, vartbl, ptr, retval):
	retval.append("IND(")
	ptr += 1
	return ptr

def _A810(stmt, vartbl, ptr, retval):
	retval.append("INT(")
	ptr += 1
	return ptr

def _A811(stmt, vartbl, ptr, retval):
	retval.append("JUL")
	ptr += 1
	return ptr

def _A812(stmt, vartbl, ptr, retval):
	retval.append("LEN(")
	ptr += 1
	return ptr

def _A813(stmt, vartbl, ptr, retval):
	retval.append("LOG")
	ptr += 1
	return ptr

def _A814(stmt, vartbl, ptr, retval):
	retval.append("MASK")
	ptr += 1
	return ptr

def _A815(stmt, vartbl, ptr, retval):
	retval.append("MAX(")
	ptr += 1
	return ptr

def _A816(stmt, vartbl, ptr, retval):
	retval.append("MIN(")
	ptr += 1
	return ptr

def _A817(stmt, vartbl, ptr, retval):
	retval.append("MOD(")
	ptr += 1
	return ptr

def _A818(stmt, vartbl, ptr, retval):
	retval.append("NFIELD")
	ptr += 1
	return ptr

def _A819(stmt, vartbl, ptr, retval):
	retval.append("NUM(")
	ptr += 1
	return ptr

def _A81A(stmt, vartbl, ptr, retval):
	retval.append("POS(")
	ptr += 1
	return ptr

def _A81B(stmt, vartbl, ptr, retval):
	retval.append("PSZ")
	ptr += 1
	return ptr

def _A81C(stmt, vartbl, ptr, retval):
	retval.append("RND(")
	ptr += 1
	return ptr

def _A81D(stmt, vartbl, ptr, retval):
	retval.append("SCALL(")
	ptr += 1
	return ptr

def _A81E(stmt, vartbl, ptr, retval):
	retval.append("SGN(")
	ptr += 1
	return ptr

def _A81F(stmt, vartbl, ptr, retval):
	retval.append("SIN")
	ptr += 1
	return ptr

def _A820(stmt, vartbl, ptr, retval):
	retval.append("SQR")
	ptr += 1
	return ptr

def _A821(stmt, vartbl, ptr, retval):
	retval.append("SSZ")
	ptr += 1
	return ptr

def _A822(stmt, vartbl, ptr, retval):
	retval.append("TCB(")
	ptr += 1
	return ptr

def _A823(stmt, vartbl, ptr, retval):
	retval.append("TIM")
	ptr += 1
	return ptr

def _A824(stmt, vartbl, ptr, retval):
	retval.append("UNT")
	ptr += 1
	return ptr

def _A825(stmt, vartbl, ptr, retval):
	retval.append("UPK")
	ptr += 1
	return ptr

def _A826(stmt, vartbl, ptr, retval):
	retval.append("ROUND")
	ptr += 1
	return ptr

def _A827(stmt, vartbl, ptr, retval):
	retval.append("NEVAL")
	ptr += 1
	return ptr

def _A828(stmt, vartbl, ptr, retval):
	retval.append("!")
	ptr += 1
	return ptr

def _A829(stmt, vartbl, ptr, retval):
	retval.append("SQLUNT")
	ptr += 1
	return ptr

def _A82A(stmt, vartbl, ptr, retval):
	retval.append("RESOPEN")
	ptr += 1
	return ptr

def _A82B(stmt, vartbl, ptr, retval):
	retval.append("MSGBOX")
	ptr += 1
	return ptr

def _A82C(stmt, vartbl, ptr, retval):
	retval.append("CLIPISFORMAT")
	ptr += 1
	return ptr

def _A82D(stmt, vartbl, ptr, retval):
	retval.append("CLIPREGFORMAT")
	ptr += 1
	return ptr

def _A82E(stmt, vartbl, ptr, retval):
	retval.append("CVT")
	ptr += 1
	return ptr

def _A82F(stmt, vartbl, ptr, retval):
	retval.append("WINFIRST")
	ptr += 1
	return ptr

def _A830(stmt, vartbl, ptr, retval):
	retval.append("WINNEXT")
	ptr += 1
	return ptr

def _A835(stmt, vartbl, ptr, retval):
	retval.append("AND")
	ptr += 1
	return ptr

def _A836(stmt, vartbl, ptr, retval):
	retval.append("ARGV")
	ptr += 1
	return ptr

def _A837(stmt, vartbl, ptr, retval):
	retval.append("ATH(")
	ptr += 1
	return ptr

def _A838(stmt, vartbl, ptr, retval):
	retval.append("BIN(")
	ptr += 1
	return ptr

def _A839(stmt, vartbl, ptr, retval):
	retval.append("CHR(")
	ptr += 1
	return ptr

def _A83A(stmt, vartbl, ptr, retval):
	retval.append("CPL(")
	ptr += 1
	return ptr

def _A83B(stmt, vartbl, ptr, retval):
	retval.append("CRC(")
	ptr += 1
	return ptr

def _A83C(stmt, vartbl, ptr, retval):
	retval.append("CVS(")
	ptr += 1
	return ptr

def _A83D(stmt, vartbl, ptr, retval):
	retval.append("DATE")
	ptr += 1
	return ptr

def _A83E(stmt, vartbl, ptr, retval):
	retval.append("DAY")
	ptr += 1
	return ptr

def _A83F(stmt, vartbl, ptr, retval):
	retval.append("DIR")
	ptr += 1
	return ptr

def _A840(stmt, vartbl, ptr, retval):
	retval.append("DSK")
	ptr += 1
	return ptr

def _A841(stmt, vartbl, ptr, retval):
	retval.append("FATTR")
	ptr += 1
	return ptr

def _A842(stmt, vartbl, ptr, retval):
	retval.append("FBIN")
	ptr += 1
	return ptr

def _A843(stmt, vartbl, ptr, retval):
	retval.append("FID(")
	ptr += 1
	return ptr

def _A844(stmt, vartbl, ptr, retval):
	retval.append("FIELD")
	ptr += 1
	return ptr

def _A845(stmt, vartbl, ptr, retval):
	retval.append("FILL")
	ptr += 1
	return ptr

def _A846(stmt, vartbl, ptr, retval):
	retval.append("FIN(")
	ptr += 1
	return ptr

def _A847(stmt, vartbl, ptr, retval):
	retval.append("GAP(")
	ptr += 1
	return ptr

def _A848(stmt, vartbl, ptr, retval):
	retval.append("HSH(")
	ptr += 1
	return ptr

def _A849(stmt, vartbl, ptr, retval):
	retval.append("HTA(")
	ptr += 1
	return ptr

def _A84A(stmt, vartbl, ptr, retval):
	retval.append("INFO")
	ptr += 1
	return ptr

def _A84B(stmt, vartbl, ptr, retval):
	retval.append("IOR")
	ptr += 1
	return ptr

def _A84C(stmt, vartbl, ptr, retval):
	retval.append("KEY(")
	ptr += 1
	return ptr

def _A84D(stmt, vartbl, ptr, retval):
	retval.append("KEYF(")
	ptr += 1
	return ptr

def _A84E(stmt, vartbl, ptr, retval):
	retval.append("KEYL(")
	ptr += 1
	return ptr

def _A84F(stmt, vartbl, ptr, retval):
	retval.append("KEYN(")
	ptr += 1
	return ptr

def _A850(stmt, vartbl, ptr, retval):
	retval.append("KEYP(")
	ptr += 1
	return ptr

def _A851(stmt, vartbl, ptr, retval):
	retval.append("LRC(")
	ptr += 1
	return ptr

def _A852(stmt, vartbl, ptr, retval):
	retval.append("LST(")
	ptr += 1
	return ptr

def _A853(stmt, vartbl, ptr, retval):
	retval.append("NOT")
	ptr += 1
	return ptr

def _A854(stmt, vartbl, ptr, retval):
	retval.append("OPTS")
	ptr += 1
	return ptr

def _A855(stmt, vartbl, ptr, retval):
	retval.append("PCK")
	ptr += 1
	return ptr

def _A856(stmt, vartbl, ptr, retval):
	retval.append("PFX")
	ptr += 1
	return ptr

def _A857(stmt, vartbl, ptr, retval):
	retval.append("PGM(")
	ptr += 1
	return ptr

def _A858(stmt, vartbl, ptr, retval):
	retval.append("PUB")
	ptr += 1
	return ptr

def _A859(stmt, vartbl, ptr, retval):
	retval.append("REV")
	ptr += 1
	return ptr

def _A85A(stmt, vartbl, ptr, retval):
	retval.append("SSN")
	ptr += 1
	return ptr

def _A85B(stmt, vartbl, ptr, retval):
	retval.append("STBL")
	ptr += 1
	return ptr

def _A85C(stmt, vartbl, ptr, retval):
	retval.append("STR(")
	ptr += 1
	return ptr

def _A85D(stmt, vartbl, ptr, retval):
	retval.append("SWAP")
	ptr += 1
	return ptr

def _A85E(stmt, vartbl, ptr, retval):
	retval.append("SYS")
	ptr += 1
	return ptr

def _A85F(stmt, vartbl, ptr, retval):
	retval.append("TBL")
	ptr += 1
	return ptr

def _A860(stmt, vartbl, ptr, retval):
	retval.append("TSK(")
	ptr += 1
	return ptr

def _A861(stmt, vartbl, ptr, retval):
	retval.append("XOR")
	ptr += 1
	return ptr

def _A862(stmt, vartbl, ptr, retval):
	retval.append("CHN")
	ptr += 1
	return ptr

def _A863(stmt, vartbl, ptr, retval):
	retval.append("KGEN")
	ptr += 1
	return ptr

def _A864(stmt, vartbl, ptr, retval):
	retval.append("SSORT")
	ptr += 1
	return ptr

def _A865(stmt, vartbl, ptr, retval):
	retval.append("ADJN")
	ptr += 1
	return ptr

def _A866(stmt, vartbl, ptr, retval):
	retval.append("SQLLIST")
	ptr += 1
	return ptr

def _A867(stmt, vartbl, ptr, retval):
	retval.append("SQLTABLES")
	ptr += 1
	return ptr

def _A868(stmt, vartbl, ptr, retval):
	retval.append("SQLTMPL")
	ptr += 1
	return ptr

def _A869(stmt, vartbl, ptr, retval):
	retval.append("SQLERR")
	ptr += 1
	return ptr

def _A86A(stmt, vartbl, ptr, retval):
	retval.append("SQLFETCH")
	ptr += 1
	return ptr

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                BBxXlate/BBxOpCodes.py                                                                              0000664 0001750 0001750 00000023503 07021456372 014024  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  CMD$="$00$1RNN      xxx"
CMD$="$01$1RNN      ADD "
CMD$="$02$1RNN      ADDR "
CMD$="$03$1RNN      BEGIN "
CMD$="$04$1RNN      CALL "
CMD$="$05$1RNN      CHDIR "
CMD$="$06$1RNN      CLEAR "
CMD$="$07$1RNN      CLOSE "
CMD$="$08$1RNN      DEF "
CMD$="$09$1RNN      DELETE "
CMD$="$0A$1RNN      DIM "
CMD$="$0B$1RNN      DIRECT "
CMD$="$0C$1RNN      DISABLE "
CMD$="$0D$1RNN      DROP "
CMD$="$0E$1RNN      EDIT"
CMD$="$0F$1RNN      ENABLE "
CMD$="$10$1RNN      END"
CMD$="$11$1RNN      ENDTRACE"
CMD$="$12$1RNN      ENTER "
CMD$="$13$1RNN      ERASE "
CMD$="$14$1RNN      ERASE "
CMD$="$15$1RNN      ESCAPE"
CMD$="$16$1RNN      EXECUTE "
CMD$="$17$1RNN      EXIT "
CMD$="$18$1RNN      EXITTO "
CMD$="$19$1RNN      EXTRACT "
CMD$="$1A$1RNN      FILE "
CMD$="$1B$1RNN      FIND "
CMD$="$1C$1RNN      FLOATINGPOINT"
CMD$="$1D$1RNN      FOR "
CMD$="$1E$1RNN      GOSUB "
CMD$="$1F$1RNN      GOTO "
CMD$="$20$1RNN      IF "
CMD$="$21$1RNN      INDEXED "
CMD$="$22$1RNN      INPUT "
CMD$="$23$1RNN      IOLIST "
CMD$="$24$1RNN      LET "
CMD$="$25$1RNN      LIST "
CMD$="$26$1RNN      LOAD "
CMD$="$27$1RNN      LOCK "
CMD$="$28$1RNN      MERGE "
CMD$="$29$1RNN      MKDIR "
CMD$="$2A$1RNN      NEXT "
CMD$="$2B$1RNN      ON "
CMD$="$2C$1RNN      OPEN "
CMD$="$2D$1RNN      PRECISION "
CMD$="$2E$1RNN      PREFIX "
CMD$="$2F$1RNN      PRINT "
CMD$="$30$1RNN      PROGRAM "
CMD$="$31$1RNN      READ "
CMD$="$32$1RNN      RELEASE "
CMD$="$33$1RNN      REM "
CMD$="$34$1RNN      REMOVE "
CMD$="$35$1RNN      RENAME "
CMD$="$36$1RNN      RESERVE "
CMD$="$37$1RNN      RESET"
CMD$="$38$1RNN      RETURN "
CMD$="$39$1RNN      RETRY"
CMD$="$3A$1RNN      RMDIR "
CMD$="$3B$1RNN      RUN "
CMD$="$3C$1RNN      SAVE "
CMD$="$3D$1RNN      SERIAL "
CMD$="$3E$1RNN      SETDRIVE "
CMD$="$3F$1RNN      SETDAY "
CMD$="$40$1RNN      SETERR "
CMD$="$41$1RNN      SETESC "
CMD$="$42$1RNN      SETTIME "
CMD$="$43$1RNN      SETTRACE "
CMD$="$44$1RNN      SORT "
CMD$="$45$1RNN      SORT "
CMD$="$46$1RNN      START "
CMD$="$47$1RNN      STOP"
CMD$="$48$1RNN      STRING "
CMD$="$49$1RNN      TABLE "
CMD$="$4A$1RNN      UNLOCK "
CMD$="$4B$1RNN      WAIT "
CMD$="$4C$1RNN      WRITE "
CMD$="$4D$1RNN      SAVEP "
CMD$="$4E$1RNN      SETOPTS "
CMD$="$4F$1RNN      DATA "
CMD$="$50$1RNN      RESTORE "
CMD$="$51$1RNN      DREAD "
CMD$="$52$1RNN      MKEYED "
CMD$="$53$1RNN      WHILE "
CMD$="$54$1RNN      WEND"
CMD$="$55$1RNN      WEND"
CMD$="$56$1RNN      FIELD "
CMD$="$57$1RNN      INPUTE "
CMD$="$58$1RNN      BACKGROUND "
CMD$="$59$1RNN      INITFILE "
CMD$="$5A$1RNN      REPEAT"
CMD$="$5B$1RNN      UNTIL "
CMD$="$5C$1RNN      INPUTN "
CMD$="$5D$1RNN      FNEND"
CMD$="$5E$1RNN      FNERR "
CMD$="$5F$1RNN      SELECT "
CMD$="$60$1RNN      CISAM "
CMD$="$61$1RNN      SQLOPEN "
CMD$="$62$1RNN      SQLCLOSE "
CMD$="$63$1RNN      SQLPREP "
CMD$="$64$1RNN      SQLEXEC "
CMD$="$65$1RNN      SQLSET "
CMD$="$66$1RNN      SWITCH "
CMD$="$67$1RNN      CASE "
CMD$="$68$1RNN      DEFAULT"
CMD$="$69$1RNN      SWEND"
CMD$="$6A$1RNN      BREAK"
CMD$="$6B$1RNN      CONTINUE"
CMD$="$6C$1RNN      FILEOPT "
CMD$="$6D$1RNN      CHANOPT "
CMD$="$6E$1RNN      RESCLOSE "
CMD$="$6F$1RNN      xxx"
CMD$="$70$1RNN      xxx"
CMD$="$71$1RNN      xxx"
CMD$="$72$1RNN      xxx"
CMD$="$73$1RNN      xxx"
CMD$="$74$1RNN      xxx"
CMD$="$75$1RNN      xxx"
CMD$="$76$1RNN      xxx"
CMD$="$77$1RNN      xxx"
CMD$="$78$1RNN      xxx"
CMD$="$79$1RNN      xxx"
CMD$="$7A$1RNN      xxx"
CMD$="$7B$1RNN      xxx"
CMD$="$7C$1RNN      xxx"
CMD$="$7D$1RNN      xxx"
CMD$="$7E$1RNN      xxx"
CMD$="$7F$1RNN      xxx"
CMD$="$80$1RNN      xxx"
CMD$="$81$1RNN      xxx"
CMD$="$82$1RNN      xxx"
CMD$="$83$1RNN      xxx"
CMD$="$84$1RNN      xxx"
CMD$="$85$1RNN      xxx"
CMD$="$86$1RNN      xxx"
CMD$="$87$1RNN      xxx"
CMD$="$88$1RNN      xxx"
CMD$="$89$1RNN      xxx"
CMD$="$8A$1RNN      xxx"
CMD$="$8B$1RNN      xxx"
CMD$="$8C$1RNN      xxx"
CMD$="$8D$1RNN      xxx"
CMD$="$8E$1RNN      xxx"
CMD$="$8F$1RNN      xxx"
CMD$="$90$1RNN      xxx"
CMD$="$91$1RNN      xxx"
CMD$="$92$1RNN      xxx"
CMD$="$93$1RNN      xxx"
CMD$="$94$1RNN      xxx"
CMD$="$95$1RNN      xxx"
CMD$="$96$1RNN      xxx"
CMD$="$97$1RNN      xxx"
CMD$="$98$1RNN      xxx"
CMD$="$99$1RNN      xxx"
CMD$="$9A$1RNN      xxx"
CMD$="$9B$1RNN      xxx"
CMD$="$9C$1RNN      xxx"
CMD$="$9D$1RNN      xxx"
CMD$="$9E$1RNN      xxx"
CMD$="$9F$1RNN      xxx"
CMD$="$A0$1RNN      xxx"
CMD$="$A1$1RNN      xxx"
CMD$="$A2$1RNN      xxx"
CMD$="$A3$1RNN      xxx"
CMD$="$A4$1RNN      FROM "
CMD$="$A5$1RNN      WHERE "
CMD$="$A6$1RNN      SORTBY "
CMD$="$A7$1RNN      LIMIT "
CMD$="$A8$1RNN      LIMIT "
CMD$="$A9$1RNN      LIMIT "
CMD$="$AA$1RNN      LIMIT "
CMD$="$AB$1RNN      LIMIT "
CMD$="$AC$1RNN      xxx"
CMD$="$AD$1RNN      xxx"
CMD$="$AE$1RNN      xxx"
CMD$="$AF$1RNN      ,DOM="
CMD$="$B0$1RNN      ,END="
CMD$="$B1$1RNN      ,ERR="
CMD$="$B2$1RNN      ,IND="
CMD$="$B3$1RNN      IOL="
CMD$="$B4$1RNN      ,ISZ="
CMD$="$B5$1RNN      ,KEY="
CMD$="$B6$1RNN      LEN="
CMD$="$B7$1RNN      ,MODE="
CMD$="$B8$1RNN      ,SIZ="
CMD$="$B9$1RNN      ,TBL="
CMD$="$BA$1RNN      ,TIM="
CMD$="$BB$1RNN      ,LEN="
CMD$="$BC$1RNN      ,KNUM="
CMD$="$BD$1RNN      ,DIR="
CMD$="$BE$1RNN      xxx"
CMD$="$BF$1RNN      xxx"
CMD$="$C0$1RNN      xxx"
CMD$="$C1$1RNN      xxx"
CMD$="$C2$1RNN      xxx"
CMD$="$C3$1RNN      xxx"
CMD$="$C4$1RNN      xxx"
CMD$="$C5$1RNN      xxx"
CMD$="$C6$1RNN      xxx"
CMD$="$C7$1RNN      xxx"
CMD$="$C8$1RNN      xxx"
CMD$="$C9$1RNN      xxx"
CMD$="$CA$1RNN      xxx"
CMD$="$CB$1RNN      xxx"
CMD$="$CC$1RNN      xxx"
CMD$="$CD$1RNN      xxx"
CMD$="$CE$1RNN      xxx"
CMD$="$CF$1RNN      xxx"
CMD$="$D0$1RNN      xxx"
CMD$="$D1$1RNN      xxx"
CMD$="$D2$1RNN      xxx"
CMD$="$D3$1RNN      ("
CMD$="$D4$1RNN      ("
CMD$="$D5$1RNN      @"
CMD$="$D6$1RNN      xxx"
CMD$="$D7$1RNN      xxx"
CMD$="$D8$1RNN      xxx"
CMD$="$D9$1RNN      xxx"
CMD$="$DA$1RNN      -"
CMD$="$DB$1RNN      +"
CMD$="$DC$1RNN      +"
CMD$="$DD$1RNN      -"
CMD$="$DE$1RNN      *"
CMD$="$DF$1RNN      /"
CMD$="$E0$1RNN      ^"
CMD$="$E1$1RNN      ="
CMD$="$E2$1RNN      <>"
CMD$="$E3$1RNN      <"
CMD$="$E4$1RNN      >"
CMD$="$E5$1RNN      <="
CMD$="$E6$1RNN      >="
CMD$="$E7$1RNN      xxx"
CMD$="$E8$1RNN      EXCEPT "
CMD$="$E9$1RNN      FI"
CMD$="$EA$1RNN      FI"
CMD$="$EB$1RNN      AND "
CMD$="$EC$1RNN      OR "
CMD$="$ED$1RNN      ["
CMD$="$EE$1RNN      ]"
CMD$="$EF$1RNN      [ALL]"
CMD$="$F0$1RNN      ="
CMD$="$F1$1RNN      ="
CMD$="$F2$1RNN      ,"
CMD$="$F3$1RNN      ; "
CMD$="$F4$1RNN      ELSE "
CMD$="$F5$1RNN      *"
CMD$="$F6$1RNN      *"
CMD$="$F7$1RNN      :"
CMD$="$F8$1RNN      GOSUB "
CMD$="$F9$1RNN      GOTO "
CMD$="$FA$1RNN      RECORD"
CMD$="$FB$1RNN      )"
CMD$="$FC$1RNN      STEP "
CMD$="$FD$1RNN      THEN "
CMD$="$FE$1RNN      TO "
CMD$="$FF$1RNN      :"
A8$="$00$1RNN      xxx"
A8$="$01$1RNN      ABS"
A8$="$02$1RNN      ARGC"
A8$="$03$1RNN      ASC"
A8$="$04$1RNN      ATN"
A8$="$05$1RNN      BSZ"
A8$="$06$1RNN      COS"
A8$="$07$1RNN      CTL"
A8$="$08$1RNN      DEC"
A8$="$09$1RNN      DSZ"
A8$="$0A$1RNN      EPT"
A8$="$0B$1RNN      ERR"
A8$="$0C$1RNN      FDEC"
A8$="$0D$1RNN      FPT"
A8$="$0E$1RNN      HSA"
A8$="$0F$1RNN      IND"
A8$="$10$1RNN      INT"
A8$="$11$1RNN      JUL"
A8$="$12$1RNN      LEN"
A8$="$13$1RNN      LOG"
A8$="$14$1RNN      MASK"
A8$="$15$1RNN      MAX"
A8$="$16$1RNN      MIN"
A8$="$17$1RNN      MOD"
A8$="$18$1RNN      NFIELD"
A8$="$19$1RNN      NUM"
A8$="$1A$1RNN      POS"
A8$="$1B$1RNN      PSZ"
A8$="$1C$1RNN      RND"
A8$="$1D$1RNN      SCALL"
A8$="$1E$1RNN      SGN"
A8$="$1F$1RNN      SIN"
A8$="$20$1RNN      SQR"
A8$="$21$1RNN      SSZ"
A8$="$22$1RNN      TCB"
A8$="$23$1RNN      TIM"
A8$="$24$1RNN      UNT"
A8$="$25$1RNN      UPK"
A8$="$26$1RNN      ROUND"
A8$="$27$1RNN      NEVAL"
A8$="$28$1RNN      !"
A8$="$29$1RNN      SQLUNT"
A8$="$2A$1RNN      RESOPEN"
A8$="$2B$1RNN      xxx"
A8$="$2C$1RNN      xxx"
A8$="$2D$1RNN      xxx"
A8$="$2E$1RNN      xxx"
A8$="$2F$1RNN      xxx"
A8$="$30$1RNN      xxx"
A8$="$31$1RNN      xxx"
A8$="$32$1RNN      AND"
A8$="$33$1RNN      ARGV"
A8$="$34$1RNN      ATH"
A8$="$35$1RNN      BIN"
A8$="$36$1RNN      CHR"
A8$="$37$1RNN      CPL"
A8$="$38$1RNN      CRC"
A8$="$39$1RNN      CVS"
A8$="$3A$1RNN      DATE"
A8$="$3B$1RNN      DAY"
A8$="$3C$1RNN      DIR"
A8$="$3D$1RNN      DSK"
A8$="$3E$1RNN      FATTR"
A8$="$3F$1RNN      FBIN"
A8$="$40$1RNN      FID"
A8$="$41$1RNN      FIELD"
A8$="$42$1RNN      FILL"
A8$="$43$1RNN      FIN"
A8$="$44$1RNN      GAP"
A8$="$45$1RNN      HSH"
A8$="$46$1RNN      HTA"
A8$="$47$1RNN      INFO"
A8$="$48$1RNN      IOR"
A8$="$49$1RNN      KEY"
A8$="$4A$1RNN      KEYF"
A8$="$4B$1RNN      KEYL"
A8$="$4C$1RNN      KEYN"
A8$="$4D$1RNN      KEYP"
A8$="$4E$1RNN      LRC"
A8$="$4F$1RNN      LST"
A8$="$50$1RNN      NOT"
A8$="$51$1RNN      OPTS"
A8$="$52$1RNN      PCK"
A8$="$53$1RNN      PFX"
A8$="$54$1RNN      PGM"
A8$="$55$1RNN      PUB"
A8$="$56$1RNN      REV"
A8$="$57$1RNN      SSN"
A8$="$58$1RNN      STBL"
A8$="$59$1RNN      STR"
A8$="$5A$1RNN      SWAP"
A8$="$5B$1RNN      SYS"
A8$="$5C$1RNN      TBL"
A8$="$5D$1RNN      TSK"
A8$="$5E$1RNN      XOR"
A8$="$5F$1RNN      CHN"
A8$="$60$1RNN      KGEN"
A8$="$61$1RNN      SSORT"
A8$="$62$1RNN      ADJN"
A8$="$63$1RNN      SQLLIST"
A8$="$64$1RNN      SQLTABLES"
A8$="$65$1RNN      SQLTMPL"
A8$="$66$1RNN      SQLERR"
A8$="$67$1RNN      SQLFETCH"
A8$="$68$1RNN      FILEOPT"
A8$="$69$1RNN      CHANOPT"
A8$="$6A$1RNN      SEVAL"
A8$="$6B$1RNN      FIELDS"
A8$="$6C$1RNN      DIMS"
A8$="$6D$1RNN      CTRL"
A8$="$6E$1RNN      SQLCHN"
A8$="$6F$1RNN      TMPL"
A8$="$70$1RNN      RESGET"
A8$="$71$1RNN      CRC16"
A8$="$72$1RNN      PAD"
A8$="$73$1RNN      xxx"
A8$="$74$1RNN      xxx"

                                                                                                                                                                                             BBxXlate/BBxParser.py                                                                               0000664 0001750 0001750 00000015227 07575716500 013736  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  import os
import md5

import BBxCmds
import BBxFuncs
from fxFNs import hexdump, dec, hta

problemPgms = []
dupPgms = {}

class Holder: pass

ttls = Holder()

ttls.PgmCount = 0
ttls.LinesParsed = 0

class BBxParser:
    #global ttlPgmCount, ttlLinesParsed
    def __init__(self, args=None, bbxPgmFQN = None):
        if args is not None:
            if len(args) == 3:
                dirname, sep, name = args
        elif bbxPgmFQN is not None:
            dirname, name = os.path.split(bbxPgmFQN)
            sep = os.sep
        bbxPgmFQN = ''.join((dirname, sep, name))
        self.bbxpgm = open(bbxPgmFQN,'rb').read()
        if self.bbxpgm[:8] == '<<bbx>>\004':
            print bbxPgmFQN,
            ttls.PgmCount += 1
             
            pgmkey = (name, md5.new(self.bbxpgm).digest())
            if dupPgms.has_key(pgmkey):
                print "**dup**"
            #elif name[-5:] == ".SAVE":
            #   svdpgmkey = (name[:-5], pgmkey[1])
            #   if dupPgms.has_key(pgmkey):
            #       print "**svdup**",
            else:

                dupPgms[pgmkey] = None

                #os.system(r'e:\basis\vpro5\pro5lst.exe -dC:\temp %s' % bbxPgmFQN)
                #self.lstrStmts = open(r'c:\temp\%s' % name,'rb').read().split('\n')
                #os.remove(r'c:\temp\%s' % name)
                self.linecount = 0

                #print hta(self.bbxpgm[:10])
                self.bbxtag = self.bbxpgm[:15]
                self.pgmhdr = self.bbxpgm[15:25]
                self.pgmlen = dec('\000' + self.pgmhdr[4:6]) + 15 
                self.pgm = self.bbxpgm[25:self.pgmlen]
                self.endvarpos = dec ('\000'+self.pgmhdr[0:2]) + 13 
                self.varlen = self.endvarpos - self.pgmlen
                #raw_input('C/R to continue...(%d)(%d)' %(self.endvarpos, self.varlen))
                self.varsrce = ''
                self.vartbl = []
                self.functbl = []
                self.bbxCode = []
                varptr = 0
                varcntr = 0
                funccntr = 0
                if self.endvarpos != 0:
                    self.varsrce=self.bbxpgm[self.pgmlen:self.endvarpos]
                    while varptr < self.varlen:
                        thisvarlen = dec(self.varsrce[varptr])
                        vartype = dec(self.varsrce[varptr+1])
                        # types: 0:string, 1:numeric, 4:numeric_array, -127:integer function, -126:string function
                        varname = self.varsrce[varptr+2:varptr + thisvarlen + 1]
                        self.vartbl.append([vartype,varname,varcntr])
                        if vartype < 0:
                            self.functbl.append([vartype,varname,funccntr])
                            funccntr += 1
                        varptr += thisvarlen + 1
                        varcntr += 1
                    self.vartbl.append(self.functbl)
                    #print self.vartbl
                self.pgmStmts = []
                pgmptr = 0
                #raw_input('C/R111  to continue...')

                while pgmptr < self.pgmlen:
                    thisStmtNo = dec(self.pgm[pgmptr:pgmptr + 2])
                    if thisStmtNo == -1: break
                    if thisStmtNo < 0:
                        thisStmtNo = dec("\000" + self.pgm[pgmptr:pgmptr + 2])
                    #print thisStmtNo,
                    thisStmtLen = dec(self.pgm[pgmptr + 2:pgmptr + 4])
                    thisStmt = self.pgm[pgmptr + 4:pgmptr + 4 + thisStmtLen]
                    debugflag = (thisStmtNo in target[1])
                    if debugflag:
                        print hta(thisStmt)
                    newline = '%05d %s' % (thisStmtNo, self.lst(thisStmtNo, thisStmt, DEBUG=debugflag))
                    if newline[0]=='0':
                        newline=newline[1:]
                    #if newline == self.lstrStmts[self.linecount][:-1] or thisStmt[0] == '\x14':
                    self.pgmStmts.append(newline)
                    if debugflag: print newline
                    pgmptr += thisStmtLen + 4
                    self.linecount += 1
                    ttls.LinesParsed += 1
                    
    def __call__(self, startline, lastline=None):
        startline = '%04d' % startline
        if lastline == None: lastline = startline
        else: lastline = '%04d' % lastline
        ii = 0
        while not self.pgmStmts[ii].startswith(startline): ii+=1
        while ii < len(self.pgmStmts):
            if self.pgmStmts[ii][:len(lastline)] <= lastline:
                print self.pgmStmts[ii]
                ii+=1
            else:
                break
                
    def lst(self, stmtNo, pgmStmt, DEBUG=0):
        ptr = 0
        retval = []
        stmnt = []
        #raw_input('C/R113  to continue...')
        while ptr < len(pgmStmt):
            startptr = ptr
            bbxOp = '%02X' % ord(pgmStmt[ptr])
            if bbxOp in ('A8','A9'):
                ptr = ptr + 1
                bbxOp = bbxOp + '%02X' % ord(pgmStmt[ptr])
            op = eval('BBxCmds._%s' % bbxOp)
            retval = []
            ptr = op(pgmStmt, self.vartbl, ptr, retval)
            self.bbxCode.append([bbxOp, retval, stmtNo, startptr])
            stmnt.extend(retval)
            #if DEBUG:
            #   print "".join(stmnt)
        return "".join(stmnt)

target = (r'',[]) # range(50,90))

if target[0]:
    bbx = BBxParser(target[0])
    raise "Breaking..."

def func(arg, dirname, names):
    #print '%s:%s:%d' % (dirname, dirname[-2:], dirname[-2:] == 'GM')
    if dirname[-2:] == 'GM':
        for name in names[:4]:
            FQN = ''.join((dirname, os.sep, name))
            if os.path.isfile(FQN) and name.find(' ') == -1:
                print FQN
                bbx = BBxParser((dirname, os.sep, name))
                """try:
                    bbx = BBxParser((dirname, os.sep, name))
                except:
                    problemPgms.append(FQN)
                    break
                #"""
            #"""
                #print dir(bbx)
                for i in bbx.bbxCode:
                    print i
                raise "Breaking..."
            #"""
if __name__ == '__main__':
    os.path.walk(r'E:\Fenx\Apps\VSDS\SourceCopies', func, ('',))
    #os.path.walk(r'E:\Fenx\Apps\VSDS\SourceCopies\lnxfc\fclt_backup\Fenx\FxPro\SnS\Pgms\GM', func, ('',))

    print "\n\n----Problem Programs----\n"
    for i in problemPgms:
        print i

    print "\n\n----Totals (Pgms, Unique, UniqueLines)----\n"
    print ttls.PgmCount, len(dupPgms.keys()), ttls.LinesParsed

    raise "Breaking..."
                                                                                                                                                                                                                                                                                                                                                                         BBxXlate/fisData.py                                                                                 0000664 0001750 0001750 00000011411 12125137341 013433  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  #!/usr/local/bin/python
import sys, getpass, shlex, subprocess, re, os
from bbxfile import BBxFile

FIS_SCHEMAS = "/FIS/Falcon_FIS_SCHEMA"
FIS_DATA = "/FIS/data"

# enable for text file output to compare against original output
textfiles = False

def sizefrom(mask):
    if not(mask): return ""
    fieldlen = len(mask)
    postdec = 0
    if "." in mask: postdec = len(mask.split(".")[-1])
    return "(%s,%s)" % (fieldlen,postdec)

def slicendice(line, *nums):
    results = []
    start = None
    nums += (None, )
    for num in nums:
        results.append(line[start:num].strip())
        start = num
    return tuple(results)

def parse_FIS_Schema(source):
    if textfiles:
        file_fields = open('fields.txt.latest', 'w')
        file_iolist = open('iolist.txt.latest', 'w')
        file_tables = open('tables.txt.latest', 'w')
    iolist = None    
    contents = open(source).readlines()
    FIS_TABLES = {}
    for line in contents:
        line = line.rstrip()
        if not line:
            continue
        if line.startswith("FC"):
            if textfiles and iolist is not None:
               file_iolist.write(str(iolist) + '\n')            
            name = line[2:9].strip()
            parts = line[9:].split(" ( ")
            desc = parts[0].strip()
            filenum = int(parts[1].split()[0])
            fields = FIS_TABLES.setdefault(filenum, {'name':name, 'desc':desc, 'filenum':filenum, 'fields':[], 'iolist':[], 'key':None})['fields']
            if name in FIS_TABLES:
                del FIS_TABLES[name]    # only allow names if there aren't any duplicates
            else:
                FIS_TABLES[name] = FIS_TABLES[filenum]
            iolist = FIS_TABLES[filenum]['iolist']
        else:   # should start with a field number...
            fieldnum, fielddesc, fieldsize, rest = slicendice(line, 10, 50, 56)
            rest = rest.split()
            if not rest:
                fieldmask, fieldvar = '', 'None'
                if fielddesc.strip('()').lower() != 'open':
                    fieldvar = 'Fld%02d' % int(fieldnum)
            else:
                if '#' in rest[-1]:
                    fieldmask = rest.pop()
                    if not rest:
                        rest.append('Fld%02d' % int(fieldnum))
                else:
                    fieldmask = ''
                if len(rest) == 2:
                    fieldvar, maybe = rest
                    if '(' in maybe:
                        fieldvar = maybe
                else:
                    fieldvar = rest[0]
            if "(" in fieldvar and not fieldvar.endswith(")"):
                fieldvar+=")"                    
            if "$" in fieldvar:
                basevar = fieldvar.split("(")[0]
            else:
                basevar = fieldvar
            basevar = basevar.title()
            if not basevar in iolist:
                iolist.append(basevar)
            fieldsize = int(fieldsize) if fieldsize else 0
            fields.append(["f%s_%s" % (filenum,fieldnum), fielddesc, fieldsize, fieldvar, sizefrom(fieldmask)])
            desc = fielddesc.replace(' ','').replace('-','=').lower()
            if (fieldvar.startswith(iolist[0])
            and desc.startswith(('key','keygroup','keytyp','rectype','recordtype'))
            and desc.count('=') == 1):
                token = fielddesc.replace('-','=').split('=')[1].strip().strip('\'"')
                start, length = fieldvar.split('(')[1].strip(')').split(',')
                start, length = int(start) - 1, int(length)
                if len(token) < length:
                    length = len(token)
                stop = start + length
                FIS_TABLES[filenum]['key'] = token, start, stop
            if textfiles:
                file_fields.write(str(fields[-1]) + '\n')            
    if textfiles:
        file_iolist.write(str(iolist) + '\n')
        for key, value in sorted(FIS_TABLES.items(), key=lambda kv: kv[1]['filenum']):
            file_tables.write("%-10s %5s - %-10s  %s\n" % (key, value['filenum'], value['name'], value['desc']))            
    return FIS_TABLES


DATACACHE = {}

def fisData (table, keymatch=None, section=None):
    filenum = tables[table]['filenum']
    key = filenum, keymatch, section
    if key in DATACACHE:
        return DATACACHE[key]
    tablename = tables[filenum]['name']
    datamap = tables[filenum]['iolist']
    fieldlist = tables[filenum]['fields']
    rectype = tables[filenum]['key']
    datafile = os.sep.join([FIS_DATA,"O"+tablename[:4]])
    table = DATACACHE[key] = BBxFile(datafile, datamap, keymatch=keymatch, section=section, rectype=rectype, fieldlist=fieldlist)
    return table

tables = parse_FIS_Schema(FIS_SCHEMAS)

#tables['NVTY1']['fields'][77]

#NVTY = fisData(135,keymatch="%s101000    101**")

#vendors = fisData(65,keymatch='10%s')
#vendors['000099']['Gn$']
                                                                                                                                                                                                                                                       BBxXlate/fxFNs.py                                                                                   0000664 0001750 0001750 00000007447 07372051574 013135  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  #!
#fxFNs.py
""" Varied functions like hta, ath, etc """
test = 0
def hta(s, padlen=1):
    """ hta(string) returns a hex repr of string"""
    if not s:
        return ""
    elif type(s)<>type("string"):
        raise "argument should be of type string"
    elif len(s)<padlen:
        while len(s)<padlen:
            s = '\000' + s
    h = ""
    for c in s:
        h = h + '%02X' % ord(c)
    return h

def hexify(s):
    " contributed by Guido "
    return "%02X"*len(s) % tuple(map(ord, s))

def ath(s):
    """ ath(string) returns a binary string from a hex repr"""
    import string
    if not s:
        return ""
    elif type(s)<>type("string"):
        raise "argument should be of type string"
    if len(s) % 2 == 1:
        s = "0"+s
    a = ""
    for i in range(0,len(s)-1,2):
        if s[i:i+1] in string.hexdigits and s[i+1:i+2] in string.hexdigits:
            a = a + chr(eval('0x'+s[i:i+2]))
        else:
            raise "argument contains: '%s' invalid hex characters" % s[i:i+2]
    if test:
        if a == ascstring:
            a = "Passed..."
        else:
            a = "Failed...("+a+")"
    return a

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

def dec(strval):
    if ord(strval[0]) >= 128:
        try:
            return asc(strval)-256**len(strval)
        except:
            return asc(strval)-256L**len(strval)
    else:
        return asc(strval)

def bin(number):
    if number > 255:
        return chr(int(number / 256))+bin(number % 256)
    else:
        return chr(number)

def hexdump(data, testlines = None, linelength = 32):
    if testlines == None:
        testlines = len(data) / 32 + 1
    print '\n'
    blknum = 0
    hdr = ''
    for i in range(linelength):
        hdr = hdr + hta(chr(i))
    for blkpos in range(0, len(data), testlines*linelength):
        # if blknum > 255 : raise "Breaking..."
        print '\n       %s' % ('-'*2*linelength)
        print '\n%6s %s' % (hta(bin(blknum)),hdr)
        print '\n       %s' % ('-'*2*linelength)
        blknum = blknum + 1
        strvar = data[blkpos:blkpos+testlines*linelength]
        for step in range(0,testlines*linelength,linelength):
            line = strvar[step:step+linelength]
            out = '\n%6s %s\n' % (hta(bin(step)), hta(line))
            print out
            print '       ',
            for char in line:
                out = char
                if 32 > ord(out):
                    out = "."
                print out,
            print '\n'



def n_asc(strval):                    ##USED in bbxfile
    from struct import unpack
    print '\n\n',len(strval)
    for argtype in ('x','c','b','B','h','H','i','I','l','L','f','d'):
        try:
            print '%s : %s' % (argtype, unpack(argtype, s))
        except:
            pass



"""
 x: pad byte (no data); c:char; b:signed byte; B:unsigned byte;
 h:short; H:unsigned short; i:int; I:unsigned int;
 l:long; L:unsigned long; f:float; d:double.

>>> struct.unpack('d','aaaaaaaa')
(1.2217638442043777e+161,)
>>> struct.unpack('l','aaaa')
(1633771873,)"""



if __name__ == '__main__':
    #t = 64345
    #print "%s  :  %s  :  %s " % (t, hta(bin(t)), asc(ath(hta(bin(t)))))

    for s in ['a','aa','aaa','aaaa']:
        print '\n\n',asc(s), n_asc(s)




    #funcs = dir()
    #test = 1
    #hexstring = "3132334142436162635a7a"
    #ascstring = "123ABCabcZz"
    #
    #for func in funcs:
    #       if func[0] <> '_':
    #               print "Function: ",func,"()", eval('%s("")' % func)
                                                                                                                                                                                                                         BBxXlate/__init__.py                                                                                0000664 0001750 0001750 00000000350 10141743342 013617  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  #
# fenx utilities
# $Id: __init__.py,v 1.2 2004/11/02 17:41:54 emile Exp $
#
# package placeholder
#
# Copyright (c) 1999 by Secret Labs AB.
#
# See the README file for information on usage and redistribution.
#

# ;-)
                                                                                                                                                                                                                                                                                        BBxXlate/test.py                                                                                    0000664 0001750 0001750 00000004760 07404023302 013043  0                                                                                                    ustar   ethan                           ethan                                                                                                                                                                                                                  #!/usr/bin/python

class Integers:
    def __init__(self, step=None, auto=0):
        self.lb = None   #Lower bound (inclusive)
        self.ub = None   #Upper bound (inclusive)
        self.up = None   #Flag: Are we counting up (a<i<c) or down (a>i>c)?
        self.step = step #Stepping increment
        self.auto = auto #Automatically return an iterator when we have 2
                         # bounds?

    def __gt__(self, n):
        self.lb = n+1
        if self.ub == None: self.up = 1
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __lt__(self, n):
        self.ub = n-1
        if self.lb == None: self.up = 0
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __ge__(self, n):
        self.lb=n
        if self.ub == None: self.up = 1
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __le__(self, n):
        self.ub=n
        if self.lb == None: self.up = 0
        if self.auto and self.ub != None and self.lb != None:
            return iter(self)
        else:
            return self

    def __nonzero__(self):
        return 1

    def __iter__(self):
        if self.step == None:
            self.step = (-1, 1)[self.up]
        else:
            assert self.step != 0 and self.up == (self.step > 0)

        if self.up:
            return iter(xrange(self.lb, self.ub+1, self.step))
        else:
            return iter(xrange(self.ub, self.lb-1, self.step))

ints = Integers(step=1, auto=1)

if __name__=='__main__':

    assert [i for i in 1 <= Integers() <= 10] == range(1,11)
    assert [i for i in 10 >= Integers() >= 1] == range(10,0,-1)

    assert [i for i in 1 < Integers() < 10] == range(2,10)
    assert [i for i in 10 > Integers() > 1] == range(9,1,-1)

    assert [i for i in 1 < Integers() <= 10] == range(2,11)
    assert [i for i in 10 > Integers() >= 1] == range(9,0,-1)

    assert [i for i in 1 <= Integers() < 10] == range(1,10)
    assert [i for i in 10 >= Integers() > 1] == range(10,1,-1)

    assert [i for i in 2 <= Integers(step=2) < 99] == range(2,99,2)

    n = 0
    for i in 1 <= ints <= 10:
        for j in 1 <= ints <= 10:
            n += 1
    assert n == 100

    assert zip(1 <= ints <= 3, 1 <= ints <= 3) == zip((1,2,3), (1,2,3))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                