#!
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
