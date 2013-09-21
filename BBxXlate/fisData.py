#!/usr/local/bin/python
import sys, getpass, shlex, subprocess, re, os
from bbxfile import BBxFile
from fnx.path import Path

execfile('/etc/openerp/fnx.fis.conf')

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
    iolist = None    
    contents = open(source).readlines()
    TABLES = {}
    skip_table = False
    for line in contents:
        line = line.rstrip()
        if not line:
            continue
        if skip_table and line[:1] == ' ':
            continue
        elif line[:1] == 'F' and line[1:2] != 'C':
            skip_table = True
            continue
        elif line[:15].strip() == '':
            continue    # skip commenting lines
        elif line.startswith(PROBLEM_TABLES):
            skip_table = True
        elif line.startswith('FC'):
            skip_table = False
            name = line[2:9].strip()
            parts = line[9:].rsplit(" (", 1)
            desc = parts[0].strip()
            if parts[1].startswith('at '):
                if name in TABLES:
                    # skip duplicate tables
                    skip_table = True
                    continue
                fields = TABLES.setdefault(name, {'name':name, 'desc':desc, 'filenum':None, 'fields':[], 'iolist':[], 'key':None})['fields']
                iolist = TABLES[name]['iolist']
                table_id = name
                filenum = ''
            else:
                filenum = int(parts[1].split()[0])
                fields = TABLES.setdefault(filenum, {'name':name, 'desc':desc, 'filenum':filenum, 'fields':[], 'iolist':[], 'key':None})['fields']
                
                if name in TABLES:
                    del TABLES[name]    # only allow names if there aren't any duplicates
                else:
                    TABLES[name] = TABLES[filenum]
                iolist = TABLES[filenum]['iolist']
                table_id = filenum
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
                    if rest and (table_id, rest[0].lower()) in NUMERICAL_FIELDS_AS_TEXT:
                        fieldmask = ''
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
            fieldvar = fieldvar.title()
            if "$" in fieldvar:
                basevar = fieldvar.split("(")[0]
            else:
                basevar = fieldvar
            basevar = basevar
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
                # or TABLES[name] . . .
                TABLES[table_id]['key'] = token, start, stop
    return TABLES


DATACACHE = {}

def fisData (table, keymatch=None, subset=None, filter=None):
    table_id = tables[table]['filenum']
    if table_id is None:
        table_id = tables[table]['name']
    tablename = tables[table_id]['name']
    key = table_id, keymatch, subset, filter
    datafile = DATA/CID+tablename[:4]
    mtime = os.stat(datafile).st_mtime
    if key in DATACACHE:
        table, old_mtime = DATACACHE[key]
        if old_mtime == mtime:
            return table
    description = tables[table_id]['desc']
    datamap = tables[table_id]['iolist']
    fieldlist = tables[table_id]['fields']
    rectype = tables[table_id]['key']
    table = BBxFile(datafile, datamap, keymatch=keymatch, subset=subset, filter=filter, rectype=rectype, fieldlist=fieldlist, name=tablename, desc=description)
    DATACACHE[key] = table, mtime
    return table

tables = parse_FIS_Schema(SCHEMA)

#tables['NVTY1']['fields'][77]

#NVTY = fisData(135,keymatch="%s101000    101**")

#vendors = fisData(65,keymatch='10%s')
#vendors['000099']['Gn$']
