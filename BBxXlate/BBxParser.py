import os
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
