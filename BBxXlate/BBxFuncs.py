def _A900(stmt, vartbl, ptr, retval):
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

