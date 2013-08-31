import binascii
import datetime
import smtplib
import string
import syslog
from dbf import Date, Time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.Encoders import encode_base64

try:
    next
except NameError:
    from dbf import next

String = str, unicode
Integer = int, long

one_day = datetime.timedelta(1)

spelled_out_numbers = set(['ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE','TEN'])

def all_equal(iterator, test=None):
    '''if `test is None` do a straight equality test'''
    it = iter(iterator)
    try:
        if test is None:
            target = next(it)
        else:
            target = test(next(it))
    except StopIteration:
        return True
    if test is None:
        test = lambda x: x == target
    for item in it:
        if test(item) != target:
            return False
    return True

def bb_text_to_date(text):
    mm, dd, yy = map(int, (text[:2], text[2:4], text[4:]))
    if any([i == 0 for i in (mm, dd, yy)]):
        Date()
    yyyy = yy + 2000
    return Date(yyyy, mm, dd)

building_subs = set([
    '#','APARTMENT','APT','BLDG','BUILDING','CONDO','FL','FLR','FLOOR','LOT','LOWER','NO','NUM','NUMBER',
    'RM','ROOM','SLIP','SLP','SPACE','SP','SPC','STE','SUITE','TRLR','UNIT','UPPER',
    ])
caps_okay = set(['UCLA', 'OHSU', 'IBM', 'LLC', 'USA', 'NASA'])
lower_okay = set(['dba', 'c/o', 'attn'])

def translator(frm='', to='', delete='', keep=None):
    if len(to) == 1:
        to = to * len(frm)
    bytes_trans = string.maketrans(frm, to)
    if keep is not None:
        allchars = string.maketrans('', '')
        delete = allchars.translate(allchars, keep.translate(allchars, delete)+frm)
    uni_table = {}
    for src, dst in zip(frm, to):
        uni_table[ord(src)] = ord(dst)
    for chr in delete:
        uni_table[ord(chr)] = None
    def translate(s):
        if isinstance(s, unicode):
            s = s.translate(uni_table)
            if keep is not None:
                for chr in set(s) - set(keep):
                    uni_table[ord(chr)] = None
                s = s.translate(uni_table)
            return s
        else:
            return s.translate(bytes_trans, delete)
    return translate

alpha_num = translator(delete='.,:_#')
non_alpha_num = translator(delete="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,-")
any_digits = translator(keep='0123456789')
has_digits = any_digits
name_chars = translator(to=' ', keep="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' /")
name_chars_punc = translator(keep="' /")
grad_year = translator(keep="'0123456789")
vowels = translator(keep='aeiouyAEIOUY')
no_vowels = translator(delete='aeiouyAEIOUY')
has_lower = translator(keep="abcdefghijklmnopqrstuvwxyz")
has_upper = translator(keep="ABCDEFGHIJKLMNOPQRSTUVWXYZ")
has_alpha = translator(keep="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
phone = translator(delete=' -().')

mixed_case_names = {
    'aj'        : 'AJ',
    'bj'        : 'BJ',
    'cj'        : 'CJ',
    'deangelis' : 'DeAngelis',
    'decarlo'   : 'DeCarlo',
    'decosta'   : 'DeCosta',
    'decristoforo' : 'DeCristoforo',
    'deferrari' : 'DeFerrari',
    'degrandpre': 'DeGrandpre',
    'degroat'   : 'DeGroat',
    'delucia'   : 'DeLucia',
    'denardis'  : 'DeNardis',
    'denorch'   : 'DeNorch',
    'depaola'   : 'DePaola',
    'deprez'    : 'DePrez',
    'deshields' : 'DeShields',
    'deshon'    : 'DeShon',
    'desousa'   : 'deSousa',
    'devet'     : 'DeVet',
    'devida'    : 'DeVida',
    'devore'    : 'DeVore',
    'difrederico':'DiFrederico',
    'diponziano': 'DiPonziano',
    'jd'        : 'JD',
    'jj'        : 'JJ',
    'joann'     : 'JoAnn',
    'joanne'    : 'JoAnne',
    'jodee'     : 'JoDee',
    'jp'        : 'JP',
    'jumaal'    : 'JuMaal',
    'delany'    : 'DeLany',
    'demerritt' : 'DeMerritt',
    'dewaal'    : 'DeWaal',
    'lamon'     : 'LaMon',
    'lebarron'  : 'LeBarron',
    'leeanne'   : 'LeeAnne',
    'maryjo'    : 'MaryJo',
    'tachelle'  : 'TaChelle',
    'tj'        : 'TJ',
    }

us_ca_state_abbr = {
    'AB' : 'ALBERTA' ,
    'AK' : 'ALASKA' ,
    'AL' : 'ALABAMA' ,
    'AR' : 'ARKANSAS' ,
    'AS' : 'AMERICAN SAMOA' ,
    'AZ' : 'ARIZONA' ,
    'BC' : 'BRITISH COLUMBIA' ,
    'CA' : 'CALIFORNIA' ,
    'CO' : 'COLORADO' ,
    'CT' : 'CONNECTICUT' ,
    'DC' : 'DISTRICT OF COLUMBIA' ,
    'DE' : 'DELAWARE' ,
    'FL' : 'FLORIDA' ,
    'FM' : 'FEDERATED STATES OF MICRONESIA' ,
    'GA' : 'GEORGIA' ,
    'GU' : 'GUAM' ,
    'HI' : 'HAWAII' ,
    'IA' : 'IOWA' ,
    'ID' : 'IDAHO' ,
    'IL' : 'ILLINOIS' ,
    'IN' : 'INDIANA' ,
    'KS' : 'KANSAS' ,
    'KY' : 'KENTUCKY' ,
    'LA' : 'LOUISIANA' ,
    'MA' : 'MASSACHUSETTS' ,
    'MB' : 'MANITOBA' ,
    'MD' : 'MARYLAND' ,
    'ME' : 'MAINE' ,
    'MH' : 'MARSHALL ISLANDS' ,
    'MI' : 'MICHIGAN' ,
    'MN' : 'MINNESOTA' ,
    'MO' : 'MISSOURI' ,
    'MP' : 'NORTHERN MARIANA ISLANDS' ,
    'MS' : 'MISSISSIPPI' ,
    'MT' : 'MONTANA' ,
    'NB' : 'NEW BRUNSWICK' ,
    'NC' : 'NORTH CAROLINA' ,
    'ND' : 'NORTH DAKOTA' ,
    'NE' : 'NEBRASKA' ,
    'NH' : 'NEW HAMPSHIRE' ,
    'NJ' : 'NEW JERSEY' ,
    'NL' : 'NEWFOUNDLAND' ,
    'NM' : 'NEW MEXICO' ,
    'NS' : 'NOVA SCOTIA' ,
    'NT' : 'NORTHWEST TERRITORY' ,
    'NU' : 'NUNAVUT' ,
    'NV' : 'NEVADA' ,
    'NY' : 'NEW YORK' ,
    'OH' : 'OHIO' ,
    'OK' : 'OKLAHOMA' ,
    'ON' : 'ONTARIO' ,
    'OR' : 'OREGON' ,
    'PA' : 'PENNSYLVANIA' ,
    'PE' : 'PRINCE EDWARD ISLAND' ,
    'PR' : 'PUERTO RICO' ,
    'PW' : 'PALAU' ,
    'QC' : 'QUEBEC' ,
    'RI' : 'RHODE ISLAND' ,
    'SC' : 'SOUTH CAROLINA' ,
    'SD' : 'SOUTH DAKOTA' ,
    'SK' : 'SASKATCHEWAN' ,
    'TN' : 'TENNESSEE' ,
    'TX' : 'TEXAS' ,
    'UT' : 'UTAH' ,
    'VA' : 'VIRGINIA' ,
    'VI' : 'VIRGIN ISLANDS' ,
    'VT' : 'VERMONT' ,
    'WA' : 'WASHINGTON' ,
    'WI' : 'WISCONSIN' ,
    'WV' : 'WEST VIRGINIA' ,
    'WY' : 'WYOMING' ,
    'YT' : 'YUKON' ,
    }
us_ca_state_name = dict([(v, k) for k, v in us_ca_state_abbr.items()])

ca_province_abbr = {
    'AB' : 'ALBERTA' ,
    'BC' : 'BRITISH COLUMBIA' ,
    'MB' : 'MANITOBA' ,
    'NB' : 'NEW BRUNSWICK' ,
    'NL' : 'NEWFOUNDLAND' ,
    'NS' : 'NOVA SCOTIA' ,
    'NT' : 'NORTHWEST TERRITORY' ,
    'NU' : 'NUNAVUT' ,
    'ON' : 'ONTARIO' ,
    'PE' : 'PRINCE EDWARD ISLAND' ,
    'QC' : 'QUEBEC' ,
    'SK' : 'SASKATCHEWAN' ,
    'YT' : 'YUKON' ,
    }
ca_province_name = dict([(v, k) for k, v in ca_province_abbr.items()])

addr_abbr = {
        'rd.'       : 'road',
        'rd'        : 'road',
        'st.'       : 'street',
        'st'        : 'street',
        'ste'       : 'suite',
        'ste.'      : 'suite',
        'ave.'      : 'avenue',
        'blvd.'     : 'boulevard',
        'blvd'      : 'boulevard',
        'e.'        : 'e',
        'east'      : 'e',
        'w.'        : 'w',
        'west'      : 'w',
        'n.'        : 'n',
        'north'     : 'n',
        's.'        : 's',
        'south'     : 's',
        'ne.'       : 'ne',
        'northeast' : 'ne',
        'se.'       : 'se',
        'southeast' : 'se',
        'nw.'       : 'nw',
        'northwest' : 'nw',
        'sw.'       : 'sw',
        'southwest' : 'sw',
        'so.'       : 's',
        'highway'   : 'hwy',
        'hwy.'      : 'hwy',
        'building'  : 'bldg',
        'bldg.'     : 'bldg',
        'ln.'       : 'lane',
        'apt.'      : 'apt',
        'apartment' : 'apt',
        'p.o.'      : 'po',
        'p.o'       : 'po',
        'po.'       : 'po',
        'p.o.box'   : 'po box',
        'po.box'    : 'po box',
        'pob'       : 'po box',
        }

bsns_abbr = {
        'inc.'      : 'incorporated',
        'inc'       : 'incorporated',
        'co.'       : 'company',
        'co'        : 'company',
        'corp.'     : 'corporation',
        'corp'      : 'corporation',
        'dept.'     : 'department',
        'dept'      : 'department',
        'ltd.'      : 'limited',
        'ltd'       : 'limited',
        }

country_abbr = {
    "AF":  "AFGHANISTAN",
    "AX":  "ALAND ISLANDS",
    "AL":  "ALBANIA",
    "DZ":  "ALGERIA",
    "AS":  "AMERICAN SAMOA",
    "AD":  "ANDORRA",
    "AO":  "ANGOLA",
    "AI":  "ANGUILLA",
    "AQ":  "ANTARCTICA",
    "AG":  "ANTIGUA AND BARBUDA",
    "AR":  "ARGENTINA",
    "AM":  "ARMENIA",
    "AW":  "ARUBA",
    "AU":  "AUSTRALIA",
    "AT":  "AUSTRIA",
    "AZ":  "AZERBAIJAN",
    "BS":  "BAHAMAS",
    "BH":  "BAHRAIN",
    "BD":  "BANGLADESH",
    "BB":  "BARBADOS",
    "BY":  "BELARUS",
    "BE":  "BELGIUM",
    "BZ":  "BELIZE",
    "BJ":  "BENIN",
    "BM":  "BERMUDA",
    "BT":  "BHUTAN",
    "BO":  "BOLIVIA, PLURINATIONAL STATE OF",
    "BQ":  "BONAIRE, SINT EUSTATIUS AND SABA",
    "BA":  "BOSNIA AND HERZEGOVINA",
    "BW":  "BOTSWANA",
    "BV":  "BOUVET ISLAND",
    "BR":  "BRAZIL",
    "IO":  "BRITISH INDIAN OCEAN TERRITORY",
    "BN":  "BRUNEI DARUSSALAM",
    "BG":  "BULGARIA",
    "BF":  "BURKINA FASO",
    "BI":  "BURUNDI",
    "KH":  "CAMBODIA",
    "CM":  "CAMEROON",
    "CA":  "CANADA",
    "CV":  "CAPE VERDE",
    "KY":  "CAYMAN ISLANDS",
    "CF":  "CENTRAL AFRICAN REPUBLIC",
    "TD":  "CHAD",
    "CL":  "CHILE",
    "CN":  "CHINA",
    "CX":  "CHRISTMAS ISLAND",
    "CC":  "COCOS (KEELING) ISLANDS",
    "CO":  "COLOMBIA",
    "KM":  "COMOROS",
    "CG":  "CONGO",
    "CD":  "CONGO, THE DEMOCRATIC REPUBLIC OF THE",
    "CK":  "COOK ISLANDS",
    "CR":  "COSTA RICA",
    "CI":  "IVORY COAST",
    "HR":  "CROATIA",
    "CU":  "CUBA",
    "CW":  "CURACAO",
    "CY":  "CYPRUS",
    "CZ":  "CZECH REPUBLIC",
    "DK":  "DENMARK",
    "DJ":  "DJIBOUTI",
    "DM":  "DOMINICA",
    "DO":  "DOMINICAN REPUBLIC",
    "EC":  "ECUADOR",
    "EG":  "EGYPT",
    "SV":  "EL SALVADOR",
    "GQ":  "EQUATORIAL GUINEA",
    "ER":  "ERITREA",
    "EE":  "ESTONIA",
    "ET":  "ETHIOPIA",
    "FK":  "FALKLAND ISLANDS (MALVINAS)",
    "FO":  "FAROE ISLANDS",
    "FJ":  "FIJI",
    "FI":  "FINLAND",
    "FR":  "FRANCE",
    "GF":  "FRENCH GUIANA",
    "PF":  "FRENCH POLYNESIA",
    "TF":  "FRENCH SOUTHERN TERRITORIES",
    "GA":  "GABON",
    "GM":  "GAMBIA",
    "GE":  "GEORGIA",
    "DE":  "GERMANY",
    "GH":  "GHANA",
    "GI":  "GIBRALTAR",
    "GR":  "GREECE",
    "GL":  "GREENLAND",
    "GD":  "GRENADA",
    "GP":  "GUADELOUPE",
    "GU":  "GUAM",
    "GT":  "GUATEMALA",
    "GG":  "GUERNSEY",
    "GN":  "GUINEA",
    "GW":  "GUINEA-BISSAU",
    "GY":  "GUYANA",
    "HT":  "HAITI",
    "HM":  "HEARD ISLAND AND MCDONALD ISLANDS",
    "VA":  "HOLY SEE (VATICAN CITY STATE)",
    "HN":  "HONDURAS",
    "HK":  "HONG KONG",
    "HU":  "HUNGARY",
    "IS":  "ICELAND",
    "IN":  "INDIA",
    "ID":  "INDONESIA",
    "IR":  "IRAN, ISLAMIC REPUBLIC OF",
    "IQ":  "IRAQ",
    "IE":  "IRELAND",
    "IM":  "ISLE OF MAN",
    "IL":  "ISRAEL",
    "IT":  "ITALY",
    "JM":  "JAMAICA",
    "JP":  "JAPAN",
    "JE":  "JERSEY",
    "JO":  "JORDAN",
    "KZ":  "KAZAKHSTAN",
    "KE":  "KENYA",
    "KI":  "KIRIBATI",
    "KP":  "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    "KR":  "KOREA, REPUBLIC OF",
    "KW":  "KUWAIT",
    "KG":  "KYRGYZSTAN",
    "LA":  "LAO PEOPLE'S DEMOCRATIC REPUBLIC",
    "LV":  "LATVIA",
    "LB":  "LEBANON",
    "LS":  "LESOTHO",
    "LR":  "LIBERIA",
    "LY":  "LIBYA",
    "LI":  "LIECHTENSTEIN",
    "LT":  "LITHUANIA",
    "LU":  "LUXEMBOURG",
    "MO":  "MACAO",
    "MK":  "MACEDONIA, THE FORMER YUGOSLAV REPUBLIC OF",
    "MG":  "MADAGASCAR",
    "MW":  "MALAWI",
    "MY":  "MALAYSIA",
    "MV":  "MALDIVES",
    "ML":  "MALI",
    "MT":  "MALTA",
    "MH":  "MARSHALL ISLANDS",
    "MQ":  "MARTINIQUE",
    "MR":  "MAURITANIA",
    "MU":  "MAURITIUS",
    "YT":  "MAYOTTE",
    "MX":  "MEXICO",
    "FM":  "MICRONESIA, FEDERATED STATES OF",
    "MD":  "MOLDOVA, REPUBLIC OF",
    "MC":  "MONACO",
    "MN":  "MONGOLIA",
    "ME":  "MONTENEGRO",
    "MS":  "MONTSERRAT",
    "MA":  "MOROCCO",
    "MZ":  "MOZAMBIQUE",
    "MM":  "MYANMAR",
    "NA":  "NAMIBIA",
    "NR":  "NAURU",
    "NP":  "NEPAL",
    "NL":  "NETHERLANDS",
    "NC":  "NEW CALEDONIA",
    "NZ":  "NEW ZEALAND",
    "NI":  "NICARAGUA",
    "NE":  "NIGER",
    "NG":  "NIGERIA",
    "NU":  "NIUE",
    "NF":  "NORFOLK ISLAND",
    "MP":  "NORTHERN MARIANA ISLANDS",
    "NO":  "NORWAY",
    "OM":  "OMAN",
    "PK":  "PAKISTAN",
    "PW":  "PALAU",
    "PS":  "PALESTINE, STATE OF",
    "PA":  "PANAMA",
    "PG":  "PAPUA NEW GUINEA",
    "PY":  "PARAGUAY",
    "PE":  "PERU",
    "PH":  "PHILIPPINES",
    "PN":  "PITCAIRN",
    "PL":  "POLAND",
    "PT":  "PORTUGAL",
    "PR":  "PUERTO RICO",
    "QA":  "QATAR",
    "RE":  "REUNION",
    "RO":  "ROMANIA",
    "RU":  "RUSSIAN FEDERATION",
    "RW":  "RWANDA",
    "BL":  "SAINT BARTHELEMY",
    "SH":  "SAINT HELENA, ASCENSION AND TRISTAN DA CUNHA",
    "KN":  "SAINT KITTS AND NEVIS",
    "LC":  "SAINT LUCIA",
    "MF":  "SAINT MARTIN (FRENCH PART)",
    "PM":  "SAINT PIERRE AND MIQUELON",
    "VC":  "SAINT VINCENT AND THE GRENADINES",
    "WS":  "SAMOA",
    "SM":  "SAN MARINO",
    "ST":  "SAO TOME AND PRINCIPE",
    "SA":  "SAUDI ARABIA",
    "SN":  "SENEGAL",
    "RS":  "SERBIA",
    "SC":  "SEYCHELLES",
    "SL":  "SIERRA LEONE",
    "SG":  "SINGAPORE",
    "SX":  "SINT MAARTEN (DUTCH PART)",
    "SK":  "SLOVAKIA",
    "SI":  "SLOVENIA",
    "SB":  "SOLOMON ISLANDS",
    "SO":  "SOMALIA",
    "ZA":  "SOUTH AFRICA",
    "GS":  "SOUTH GEORGIA AND THE SOUTH SANDWICH ISLANDS",
    "SS":  "SOUTH SUDAN",
    "ES":  "SPAIN",
    "LK":  "SRI LANKA",
    "SD":  "SUDAN",
    "SR":  "SURINAME",
    "SJ":  "SVALBARD AND JAN MAYEN",
    "SZ":  "SWAZILAND",
    "SE":  "SWEDEN",
    "CH":  "SWITZERLAND",
    "SY":  "SYRIAN ARAB REPUBLIC",
    "TW":  "TAIWAN, PROVINCE OF CHINA",
    "TJ":  "TAJIKISTAN",
    "TZ":  "TANZANIA, UNITED REPUBLIC OF",
    "TH":  "THAILAND",
    "TL":  "TIMOR-LESTE",
    "TG":  "TOGO",
    "TK":  "TOKELAU",
    "TO":  "TONGA",
    "TT":  "TRINIDAD AND TOBAGO",
    "TN":  "TUNISIA",
    "TR":  "TURKEY",
    "TM":  "TURKMENISTAN",
    "TC":  "TURKS AND CAICOS ISLANDS",
    "TV":  "TUVALU",
    "UG":  "UGANDA",
    "UA":  "UKRAINE",
    "AE":  "UNITED ARAB EMIRATES",
    "UK":  "UNITED KINGDOM",
    "GB":  "UNITED KINGDOM",
    "US":  "UNITED STATES",
    "UM":  "UNITED STATES MINOR OUTLYING ISLANDS",
    "UY":  "URUGUAY",
    "UZ":  "UZBEKISTAN",
    "VU":  "VANUATU",
    "VE":  "VENEZUELA, BOLIVARIAN REPUBLIC OF",
    "VN":  "VIET NAM",
    "VG":  "VIRGIN ISLANDS, BRITISH",
    "VI":  "VIRGIN ISLANDS, U.S.",
    "WF":  "WALLIS AND FUTUNA",
    "EH":  "WESTERN SAHARA",
    "YE":  "YEMEN",
    "ZM":  "ZAMBIA",
    "ZW":  "ZIMBABWE",
    }
country_name = dict([(v, k) for k, v in country_abbr.items()])

def cszk(line1, line2):
    """
    parses two lines of text into blah, city, state, zip, country

    supported formats:
      line1: city (state)
      line2: zip zip country

      line1: ...
      line2: city state zip zip country

      line1: city state zip zip
      line2: country

      line1: ...
      line2: city, state zip zip

      returns street, city, state, zip, country; but state is only
      populated if country is US or CA
    """
    street = city = state = postal = country = ''
    try:
        pieces, line2 = line2.split(), ''
        k = kountry = ''
        while pieces:
            new_k = pieces.pop().upper()
            if has_digits(new_k):
                city = k.strip(', ')
                pieces.append(new_k)
                break
            k = (new_k + ' ' + k).strip()
            if k in country_abbr:
                k, kountry = country_abbr[k], k
            if k in country_name:
                country = k
                if pieces and pieces[-1].upper() == 'THE':
                    pieces.pop()
                break
            else:
                # check for a state
                if k.replace('.','') in us_ca_state_abbr:
                    k = us_ca_state_abbr[k.replace('.','')]
                if k in us_ca_state_name:
                    state = k
                    break
        else:
            pieces = k.split()
        if pieces and pieces[-1] == ',':
            pieces.pop()
        if not pieces:
            pieces, line1 = line1.split(), ''
        if pieces and pieces[-1] == ',':
            pieces.pop()
        if has_digits(pieces[-1]) or len(pieces[-1]) == 3:  # zip code!
            if len(pieces) > 1 and (has_digits(pieces[-2]) or len(pieces[-2]) == 3):
                postal = PostalCode(' '.join(pieces[-2:]), country=country)
                pieces.pop(); pieces.pop()
            else:
                postal = PostalCode(pieces.pop(), country=country)
        if not pieces:
            pieces, line1 = line1.split(), ''
        s = pieces.pop()  # now looking for a state
        if s[-1] == ')':
            if s[0] == '(':
                s = s[1:-1]
            elif len(pieces) > 1 and pieces[-2][0] == '(':
                s = pieces.pop()[1:] + ' ' + s[:-1]
        else: # parens not found, scan for comma
            for i, p in enumerate(pieces[::-1]):
                if p.endswith(','):
                    break
                s = (p + ' ' + s).strip()
                pieces.pop()
        if s.replace('.','') in us_ca_state_abbr:
            s = us_ca_state_abbr[s.replace('.','')]
        if s in us_ca_state_name:
            state = s
        else:
            city = (s + ' ' + city).strip(', ')
        # see if state is canadian
        if state in ca_province_name and not country:
            country = 'CANADA'
        # if state is empty but we have a country, check that country abbreviation is not a state
        if country and not state:
            if kountry in us_ca_state_abbr:
                state = us_ca_state_abbr[kountry]
                country = ''
        if pieces:
            city = (' '.join(pieces) + ' ' + city).strip(', ')
            pieces[:] = []
        if city : # early bail
            street, line1 = line1, ''
            return street, city, state, postal, country
        else:
            city, line1 = line1.strip(', '), ''
            return street, city, state, postal, country
    except IndexError:
        if line1 or line2 or pieces:
            raise
        return street, city, state, postal, country



def crc32(binary_data):
    "wrapper around binascii.crc32 that is consistent across python versions"
    return binascii.crc32(binary_data) & 0xffffffff

def unabbreviate(text, abbr):
    """
    returns line lower-cased with standardized abbreviations
    text: text to work with
    abbr: dictionary of abbreviations to use
    """
    text = text.lower().replace(u'\uffa6', ' ')
    words = text.split()
    final = []
    for word in words:
        final.append(abbr.get(word, word))
    return ' '.join(final)

class BiDict(object):
    """
    key <=> value (value must also be hashable)
    """
    def __init__(yo, *args, **kwargs):
        _dict = yo._dict = dict()
        original_keys = yo._primary_keys = list()
        for k, v in args:
            if k not in original_keys:
                original_keys.append(k)
            _dict[k] = v
            if v != k and v in _dict:
                raise ValueError("%s:%s violates one-to-one mapping" % (k, v))
            _dict[v] = k
        for key, value in kwargs.items():
            if key not in original_keys:
                original_keys.append(key)
            _dict[key] = value
            if value != key and value in _dict:
                raise ValueError("%s:%s violates one-to-one mapping" % (key, value))
            _dict[value] = key
    def __contains__(yo, key):
        return key in yo._dict
    def __delitem__(yo, key):
        _dict = yo._dict
        value = _dict[key]
        del _dict[value]
        if key != value:
            del _dict[key]
        target = (key, value)[value in yo._primary_keys]
        yo._primary_keys.pop(yo._primary_keys.index(target))
    #def __getattr__(yo, key):
    #    return getattr(yo._dict, key)
    def __getitem__(yo, key):
        return yo._dict.__getitem__(key)
    def __iter__(yo):
        return iter(yo._primary_keys)
    def __len__(yo):
        return len(yo._primary_keys)
    def __setitem__(yo, key, value):
        _dict = yo._dict
        original_keys = yo._primary_keys
        if key in _dict:
            mapping = key, _dict[key]
        else:
            mapping = ()
        if value in _dict and value not in mapping:
            raise ValueError("%s:%s violates one-to-one mapping" % (key, value))
        if mapping:
            k, v = mapping
            del _dict[k]
            if k != v:
                del _dict[v]
            target = (k, v)[v in original_keys]
            original_keys.pop(original_keys.index(target))
        _dict[key] = value
        _dict[value] = key
        original_keys.append(key)
    def __repr__(yo):
        result = []
        for key in yo._primary_keys:
            result.append(repr((key, yo._dict[key])))
        return "BiDict(%s)" % ', '.join(result)
    def keys(yo):
        return yo._primary_keys[:]
    def items(yo):
        return [(k, yo._dict[k]) for k in yo._primary_keys]
    def values(yo):
        return [yo._dict[key] for key in yo._primary_keys]

class PropertyDict(object):
    """
    allows dictionary lookup using . notation
    allows a default similar to defaultdict
    """
    _internal = ['_illegal', '_values', '_default', '_order']
    _default = None
    def __init__(yo, *args, **kwargs):
        if 'default' in kwargs:
            yo._default = kwargs.pop('default')
        yo._values = _values = kwargs.copy()
        yo._order = _order = []
        yo._illegal = _illegal = tuple([attr for attr in dir(_values) if attr[0] != '_'])
        args = list(args)
        if len(args) == 1 and isinstance(args[0], tuple) and isinstance(args[0][0], tuple) and len(args[0][0]) == 2:
            for k, v in args[0]:
                if k in _illegal:
                    raise ValueError("%s is a reserved word" % k)
                _values[k] = v
                _order.append(k)
        else:
            for attr in args:
                if attr in _illegal:
                    raise ValueError("%s is a reserved word" % attr)
                elif isinstance(attr, dict):
                    attr.update(kwargs)
                    kwargs = attr
                    continue
                value = False
                _values[attr] = value
                _order.append(attr)
        for attr, value in sorted(kwargs.items()):
            if attr in _illegal:
                raise ValueError("%s is a reserved word" % attr)
            _values[attr] = value
            _order.append(attr)
    def __contains__(yo, key):
        return key in yo._values
    def __delitem__(yo, name):
        if name[0] == '_':
            raise KeyError("illegal key name: %s" % name)
        if name not in yo._values:
            raise KeyError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))
    def __delattr__(yo, name):
        if name[0] == '_':
            raise AttributeError("illegal key name: %s" % name)
        if name not in yo._values:
            raise AttributeError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))
    def __getitem__(yo, name):
        if name in yo._values:
            return yo._values[name]
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise KeyError("object has no key %s" % name)
    def __getattr__(yo, name):
        if name in yo._values:
            return yo._values[name]
        attr = getattr(yo._values, name, None)
        if attr is not None:
            return attr
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise AttributeError("object has no attribute %s" % name)
    def __iter__(yo):
        return iter(yo._order)
    def __len__(yo):
        return len(yo._values)
    def __setitem__(yo, name, value):
        if name in yo._internal:
            object.__setattr__(yo, name, value)
        elif name[0] == '_':
            raise KeyError("illegal attribute name: %s" % name)
        else:
            if name not in yo._values:
                yo._order.append(name)
            yo._values[name] = value
    def __setattr__(yo, name, value):
        if name in yo._internal:
            object.__setattr__(yo, name, value)
        elif name[0] == '_' or name in yo._illegal:
            raise AttributeError("illegal attribute name: %s" % name)
        else:
            if name not in yo._values:
                yo._order.append(name)
            yo._values[name] = value
    def __repr__(yo):
        return "PropertyDict((%s,))" % ', '.join(["(%r, %r)" % (x, yo._values[x]) for x in yo._order])
    def __str__(yo):
        return '\n'.join(["%r=%r" % (x, yo._values[x]) for x in yo._order])
    def keys(yo):
        return yo._order[:]
    def pop(yo, name):
        yo._order.pop(yo._order.index(name))
        return yo._values.pop(name)

class Sentinel(object):
    def __init__(yo, text):
        yo.text = text
    def __str__(yo):
        return "Sentinel: <%s>" % yo.text


def tuples(func):
    def wrapper(*args):
        if len(args) == 1 and not isinstance(args[0], String):
            args = args[0]
        result = tuple(func(*args))
        if len(result) == 1:
            result = result[0]
        return result
    #wrapper.__name__ = func.__name___
    wrapper.__doc__ = func.__doc__
    return wrapper


@tuples
def NameCase(*names):
    '''names should already be stripped of whitespace'''
    if not any(names):
        return names
    final = []
    for name in names:
        pieces = name.lower().split()
        result = []
        for i, piece in enumerate(pieces):
            if '-' in piece:
                piece = ' '.join(piece.replace('-',' ').split())
                piece = '-'.join(NameCase(piece).split())
            elif alpha_num(piece) in ('i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x'):
                piece = piece.upper()
            elif piece in ('and', 'de', 'del', 'der', 'el', 'la', 'van', 'of'):
                pass
            elif piece[:2] == 'mc':
                piece = 'Mc' + piece[2:].title()
            else:
                possible = mixed_case_names.get(piece, None)
                if possible is not None:
                    piece = possible
                else:
                    piece = piece.title()
                    if piece[-2:].startswith("'"):
                        piece = piece[:-1] + piece[-1].lower()
            result.append(piece)
        if result[0] == result[0].lower():
            result[0] = result[0].title()
        if result[-1] == result[-1].lower():
            result[-1] = result[-1].title()
        final.append(' '.join(result))
    return final


@tuples
def AddrCase(*fields):
    if not any(fields):
        return fields
    final = []
    for field in fields:
        result = []
        for word in field.split():
            uppered = word.upper()
            if uppered in ('N','NW','W','SW','S','SE','E','NE','PO','PMB','US'):
                result.append(uppered)
            elif word[:-2].isdigit() and word[-2:].lower() in ('st','nd','rd','th'):
                result.append(word.lower())
            elif has_alpha(word) and has_digits(word) or non_alpha_num(word):
                result.append(word)
            elif uppered[:2] == 'MC':
                result.append('Mc' + uppered[2:].title())
            else:
                result.append(word.title())
        final.append(' '.join(result))
    return final


@tuples
def BsnsCase(*fields):
    if not any(fields):
        return fields
    final = []
    for name in fields:
        pieces = name.split()
        #if len(pieces) <= 1:
        #    final.append(name)
        #    continue
        mixed = []
        last_piece = ''
        for piece in pieces:
            #if has_lower(piece):
            #    return name
            lowered = piece.lower()
            if piece in caps_okay:
                mixed.append(piece)
            elif lowered in lower_okay:
                piece = lowered
                mixed.append(piece)
            elif lowered in ('a','an','and','of','the','at') and last_piece not in ('&','and'):
                mixed.append(lowered)
            elif lowered[:2] == 'mc':
                mixed.append('Mc' + lowered[2:].title())
            elif len(piece) == 2 and not vowels(piece):
                mixed.append(piece)
            else:
                number, suffix = lowered[:-2], lowered[-2:]
                if number.isdigit() and suffix in ('st','nd','rd','th'):
                    piece = piece[:-2].title() + suffix
                else:
                    piece = piece.title()
                    if piece[-2:].startswith("'"):
                        piece = piece[:-1] + piece[-1].lower()
                mixed.append(piece)
            last_piece = piece
        if mixed[0].lower() == mixed[0] and (mixed[0] not in lower_okay and mixed[0][-2:] not in ('st','nd','rd','th')):
            mixed[0] = mixed[0].title()
        final.append(' '.join(mixed))
    return final


def BusinessOrAddress(suspect):
    ususpect = suspect.upper().strip()
    company = address = ''
    m = Memory()
    if ususpect and \
       ((ususpect == 'GENERAL DELIVERY') or
        (ususpect.split()[0] in spelled_out_numbers or ususpect.split()[0] in building_subs) or
        (ususpect[:3] == 'PMB' and ususpect[3:4] in ('# 0123456789')) or
        (ususpect[:3] == 'MC:' or ususpect[:8] == 'MAILCODE') or 
        (ususpect[:4] == 'BOX ' and len(m.set(ususpect.split())) == 2 
            and (m.cell[1] in spelled_out_numbers or m.cell[1].isdigit() or len(m.cell[1]) < 2)) or
        ('BOX ' in ususpect and ususpect[:ususpect.index('BOX ')+4].replace('.','').replace(' ','')[:5] == 'POBOX') or
        ('DRAWER ' in ususpect and ususpect[:ususpect.index('DRAWER ')+7].replace('.','').replace(' ','')[:8] == 'PODRAWER') or
        ususpect.startswith('DRAWER ')):
           address = suspect
    else:
        for char in suspect:
            if char.isdigit():
                address = suspect
                break
        else:
            company = suspect
    return company, address


@tuples
def Rise(*fields):
    #fields = _fields(args)
    data = []
    empty = []
    for possible in fields:
        if possible:
            data.append(possible)
        else:
            empty.append(possible)
    results = data + empty
    return results


def Salute(name):
    pieces = name.split()
    for piece in pieces:
        if not piece.upper() in prefixi:
            return piece


@tuples
def Sift(*fields):
    #fields = _fields(args)
    data = []
    empty = []
    for possible in fields:
        if possible:
            data.append(possible)
        else:
            empty.append(possible)
    results = empty + data
    return results


_memory_sentinel = Sentinel("amnesiac")


class Memory(object):
    """
    allows attribute and item lookup
    allows a default similar to defaultdict
    remembers insertion order (alphabetic if not possible)
    """
    _default = None
    def __init__(yo, cell=_memory_sentinel, **kwargs):
        if 'default' in kwargs:
            yo._default = kwargs.pop('default')
        if cell is not _memory_sentinel:
            yo._order.append('cell')
            yo._values['cell'] = cell
        yo._values = _values = kwargs.copy()
        yo._order = _order = sorted(_values.keys())
        for attr, value in sorted(kwargs.items()):
            _values[attr] = value
            _order.append(attr)
    def __contains__(yo, key):
        return key in yo._values
    def __delitem__(yo, name):
        if name not in yo._values:
            raise KeyError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))
    def __delattr__(yo, name):
        if name not in yo._values:
            raise AttributeError("%s: no such key" % name)
        yo._values.pop(name)
        yo._order.pop(yo._order.index(name))
    def __getitem__(yo, name):
        if name in yo._values:
            return yo._values[name]
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise KeyError("object has no key %s" % name)
    def __getattr__(yo, name):
        if name in yo._values:
            return yo._values[name]
        elif yo._default:
            yo._order.append(name)
            result = yo._values[name] = yo._default()
            return result
        raise AttributeError("object has no attribute %s" % name)
    def __iter__(yo):
        return iter(yo._order)
    def __len__(yo):
        return len(yo._values)
    def __setitem__(yo, name, value):
        if name not in yo._values:
            yo._order.append(name)
        yo._values[name] = value
    def __setattr__(yo, name, value):
        if name in ('_values','_order'):
            object.__setattr__(yo, name, value)
        else:
            if name not in yo._values:
                yo._order.append(name)
            yo._values[name] = value
    def __repr__(yo):
        return "Memory(%s)" % ', '.join(["%r=%r" % (x, yo._values[x]) for x in yo._order])
    def __str__(yo):
        return "I am remembering...\n" + '\n\t'.join(["%r=%r" % (x, yo._values[x]) for x in yo._order])
    def keys(yo):
        return yo._order[:]
    def set(yo, cell=_memory_sentinel, **kwargs):
        _values = yo._values
        _order = yo._order
        if cell is not _memory_sentinel:
            if 'cell' not in _values:
                _order.append('cell')
            _values['cell'] = cell
            return cell
        for attr, value in sorted(kwargs.items()):
            _order.append(attr)
            _values[attr] = value
            return value


class PostalCode(object):
    """
    primarily for US and Canadian postal codes (ignores US +4)
    """

    def __init__(yo, postal, country=None):
        alpha2num = {
                'I' : '1',
                'O' : '0',
                'S' : '5',
                }
        num2alpha = {
                '1'   : 'I',
                '0'   : 'O',
                '5'   : 'S',
                }
        postal = postal.strip('-,')
        if len(postal.replace('-', '')) in (5, 9):
            yo.code = postal[:5]
        elif postal[:5].isdigit():
            yo.code = postal[:5]
        elif (has_alpha(postal) and len(postal.replace(' ', '')) == 6
        and   (not country or country == 'CANADA')):
            # alpha-num-alpha num-alpha-num
            postal = list(postal.replace(' ', '').upper())
            for i in (0, 2, 4):
                postal[i] = num2alpha.get(postal[i], postal[i])
            for i in (1, 3, 5):
                postal[i] = alpha2num.get(postal[i], postal[i])
            yo.code = "%s %s" % (''.join(postal[:3]), ''.join(postal[3:]))
        else:
            yo.code = postal

    def __eq__(yo, other):
        if not isinstance(other, (str, unicode, yo.__class__)):
            return NotImplemented
        if isinstance(other, yo.__class__):
            other = other.code
        return yo.code == other
    def __ne__(yo, other):
        return not yo.__eq__(other)
    def __repr__(yo):
        return repr(yo.code)
    def __str__(yo):
        return yo.code


def fix_phone(text):
    text = text.strip()
    data = phone(text)
    if len(data) not in (7, 10, 11):
        return text
    if len(data) == 11:
        if data[0] != '1':
            return text
        data = data[1:]
    if len(data) == 7:
        return '%s.%s' % (data[:3], data[3:])
    return '%s.%s.%s' % (data[:3], data[3:6], data[6:])


def fix_date(text):
    '''takes mmddyy (with yy in hex (A0 = 2000)) and returns a Date'''
    text = text.strip()
    if len(text) != 6:
        return None
    yyyy, mm, dd = int(text[4:], 16)-160+2000, int(text[:2]), int(text[2:4])
    return Date(yyyy, mm, dd)

def text_to_date(text, format='ymd'):
    '''(yy)yymmdd'''
    if not text.strip():
        return None
    dd = mm = yyyy = None
    if len(text) == 6:
        if format == 'ymd':
            yyyy, mm, dd = int(text[:2])+2000, int(text[2:4]), int(text[4:])
        elif format == 'mdy':
            mm, dd, yyyy = int(text[:2]), int(text[2:4]), int(text[4:])+2000
    elif len(text) == 8:
        if format == 'ymd':
            yyyy, mm, dd = int(text[:4]), int(text[4:6]), int(text[6:])
        elif format == 'mdy':
            mm, dd, yyyy = int(text[:2]), int(text[2:4]), int(text[4:])
    if dd is None:
        raise ValueError("don't know how to convert %r using %r" % (text, format))
    return Date(yyyy, mm, dd)

def text_to_time(text):
    if not text.strip():
        return None
    return Time(int(text[:2]), int(text[2:]))

def simplegeneric(func):
    """Make a trivial single-dispatch generic function (from Python3.4 functools)"""
    registry = {}
    def wrapper(*args, **kw):
        ob = args[0]
        try:
            cls = ob.__class__
        except AttributeError:
            cls = type(ob)
        try:
            mro = cls.__mro__
        except AttributeError:
            try:
                class cls(cls, object):
                    pass
                mro = cls.__mro__[1:]
            except TypeError:
                mro = object,   # must be an ExtensionClass or some such  :(
        for t in mro:
            if t in registry:
                return registry[t](*args, **kw)
        else:
            return func(*args, **kw)
    try:
        wrapper.__name__ = func.__name__
    except (TypeError, AttributeError):
        pass    # Python 2.3 doesn't allow functions to be renamed

    def register(typ, func=None):
        if func is None:
            return lambda f: register(typ, f)
        registry[typ] = func
        return func

    wrapper.__dict__ = func.__dict__
    wrapper.__doc__ = func.__doc__
    wrapper.register = register
    return wrapper

def mail(server, port, sender, receiver, message):
    """sends email.message to server:port

    receiver is a list of addresses
    """
    msg = MIMEText(message.get_payload())
    for address in receiver:
        msg['To'] = address
    msg['From'] = sender
    for header, value in message.items():
        if header in ('To','From'):
            continue
        msg[header] = value
    smtp = smtplib.SMTP(server, port)
    try:
        send_errs = smtp.sendmail(msg['From'], receiver, msg.as_string())
    except smtplib.SMTPRecipientsRefused, exc:
        send_errs = exc.recipients
    smtp.quit()
    errs = {}
    if send_errs:
        for user in send_errs:
            server = 'mail.' + user.split('@')[1]
            smtp = smtplib.SMTP(server, 25)
            try:
                smtp.sendmail(msg['From'], [user], msg.as_string())
            except smtplib.SMTPRecipientsRefused, exc:
                errs[user] = [send_errs[user], exc.recipients[user]]
            smtp.quit()
    for user, errors in errs.items():
        for code, response in errors:
            syslog.syslog('%s --> %s: %s' % (user, code, response))
