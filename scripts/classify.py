"""Classify every register code by network type, with a confidence tier.

Tiers, strongest first:
  stated    the ITU text or a national registry says it (e.g. 'Government use', '(MVNO)',
            'used for private network', OFCA's MVNO remark, CNAC 'Experimental Purposes')
  name      the holder's name itself says it (a power company, a railway, a university)
  inferred  from knowledge of who the holder is (Ericsson is an equipment vendor)
Anything else is left 'unclassified'.

Usage: python3 -I classify.py <register_json> <registries_json> <out_json>
"""
import json, re, sys, unicodedata
from collections import Counter

TYPES = {
    "mno": "Mobile network operator",
    "mvno": "Virtual operator (MVNO)",
    "operator": "Public operator, type unclear",
    "iot": "IoT and M2M connectivity",
    "satellite": "Satellite",
    "maritime_aviation": "Maritime and in-flight",
    "messaging": "Messaging and SMS",
    "carrier_services": "Roaming hub, wholesale or carrier services",
    "utility": "Utility and energy",
    "transport": "Transport and infrastructure",
    "public_safety": "Public safety",
    "government": "Government and defence",
    "research": "Research and education",
    "vendor_test": "Equipment vendor or test",
    "private": "Private or enterprise network",
    "community": "Tribal and community",
    "trial": "Trial of a new service",
    "reserved": "Reserved",
    "unclassified": "Unclassified",
}


def fold(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def rx(*words):
    return re.compile(r"(?<![a-z0-9])(" + "|".join(words) + r")(?![a-z0-9])")


# ---- stated: wording in the ITU entry itself
STATED = [
    ("reserved", rx(r"reserved for public safety", r"not available for assignment", r"reclaimed \d+[/\d]*", r"spare")),
    ("government", rx(r"government use")),
    ("vendor_test", rx(r"test imsi", r"test use only", r"test network", r"testing", r"^test$", r"test bed", r"testbed", r"test purposes?", r"experimental")),
    ("mvno", rx(r"mvno", r"mvne", r"virtual network operator", r"full mvno")),
    ("public_safety", rx(r"ppdr", r"public safety")),
    ("private", rx(r"private network", r"used for private", r"privat(es)? netz", r"campus ?netz", r"private lte", r"private 5g", r"enterprise network")),
]

# ---- name: the holder's own name states its line of business
NAME = [
    ("satellite", rx(r"satellite\w*", r"satelital", r"sat", r"satcom", r"satcomms", r"space", r"orbital", r"ntn")),
    ("maritime_aviation", rx(r"maritime", r"marine", r"aeronautic\w*", r"aerospace", r"aviation", r"airline\w*", r"in-?flight", r"avionics", r"cruise", r"shipping", r"seanet", r"offshore")),
    ("iot", rx(r"iot", r"m2m\w*", r"machine", r"telematics", r"things", r"connected car", r"lpwa\w*", r"nb-?iot", r"smart metering", r"esim")),
    ("messaging", rx(r"sms", r"messaging", r"message\w*", r"a2p", r"mass response", r"paging", r"beeper")),
    ("utility", rx(r"power", r"energy", r"energie", r"energia", r"energetica", r"electric\w*", r"electri\w*", r"elektri\w*", r"electricite", r"hydro\w*",
                   r"gas", r"water", r"wasser", r"eletri\w*", r"edison", r"nethys", r"endesa", r"e-redes", r"national grid", r"utilit\w*", r"netbeheer", r"stromnetz", r"stadtwerke", r"edf", r"enedis", r"iberdrola",
                   r"vattenfall", r"fortum", r"tennet", r"amprion", r"nuclear", r"river authority", r"cooperativa de electrificacion\w*", r"light, gas")),
    ("transport", rx(r"rail\w*", r"ferrovi\w*", r"ferrocarril\w*", r"metro", r"transit", r"transport\w*", r"airport", r"port authority", r"harbour", r"harbor",
                     r"terminals?", r"traffic", r"department of transportation", r"highways? (agency|authority)", r"motorway\w*", r"liikenne\w*", r"kaupunkiliikenne", r"trafikverket", r"infrabel",
                     r"prorail", r"zeleznic\w*", r"zelezni\w*", r"jernbane\w*", r"banedanmark", r"bundesbahn", r"sbb", r"obb", r"mav infrastructure", r"nmbs", r"rff", r"infraestruturas de portugal", r"portuari\w*", r"db netz", r"db infrago", r"sncf", r"adif", r"mtr corporation", r"bahn", r"tramway\w*", r"metropolitano")),
    ("public_safety", rx(r"police", r"policia", r"polizei", r"fire", r"emergency", r"rescue", r"ambulance", r"bdbos", r"firstnet", r"civil contingencies",
                         r"civil protection", r"beredskab\w*", r"samhallsskydd", r"erillisverkot", r"airwave", r"rakel", r"virve", r"astrid", r"safety")),
    ("research", rx(r"universit\w*", r"universidad", r"universite", r"universitat", r"universidade", r"college", r"institut\w*", r"instituto", r"research",
                    r"laborator\w*", r"lab", r"labs", r"academ\w*", r"school", r"korkeakoulu\w*", r"ammattikorkeakoulu", r"saatio", r"vtt", r"fraunhofer",
                    r"teknologian tutkimuskeskus", r"5g ep", r"office of education", r"public schools", r"school district", r"education")),
    ("government", rx(r"ministry", r"ministerio", r"ministere", r"ministerium", r"government", r"gobierno", r"gouvernement", r"governo", r"bundesamt",
                      r"bundeswehr", r"defen[cs]e", r"army", r"armed forces", r"military", r"navy", r"home office", r"department", r"departamento",
                      r"county", r"city of", r"municipal\w*", r"state of", r"commonwealth", r"council", r"authority", r"agency", r"administration",
                      r"regionen", r"region", r"kommune", r"gemeente", r"cyber security", r"liaison office", r"correctional", r"immigration", r"customs",
                      r"radiation", r"defensie", r"syndicat\w*", r"numerique", r"departement", r"special state protection", r"royal court", r"free zone organi[sz]ation", r"saeteilyturvakeskus", r"saeteily\w*", r"sateilyturvakeskus")),
    ("community", rx(r"tribal", r"(?<!tribe mobile )tribe(?! mobile)", r"nation(?!al)", r"band of", r"indian", r"tlingit", r"haida", r"navajo", r"keewaytinook", r"first nations", r"rural",
                     r"cooperative", r"co-op")),
]

# ---- inferred: known companies
KNOWN = [
    ("satellite", [r"iridium", r"inmarsat", r"thuraya", r"globalstar", r"skylo", r"lynk", r"ast ?& ?science", r"space exploration technologies", r"spacex",
                   r"starlink", r"sateliot", r"satelio", r"oq technology", r"omnispace", r"viasat", r"eutelsat", r"oneweb", r"echostar", r"ligado",
                   r"kepler", r"myriota", r"e-space", r"hughes", r"intelsat", r"ses", r"astrocast", r"sateliot", r"fossa", r"orbcomm", r"swarm",
                   r"tampnet", r"galaxy broadband"]),
    ("maritime_aviation", [r"onair", r"sita", r"aeromobile", r"maritime communications partner", r"mcp", r"telenor maritime", r"wireless maritime",
                           r"panasonic avionics", r"smartsky", r"gogo", r"anuvu", r"global eagle", r"marlink", r"kvh", r"carnival", r"royal caribbean"]),
    ("iot", [r"numerex", r"globetouch", r"cobira", r"teleena", r"gigsky", r"oxio", r"m2mconnect", r"cubic ag", r"telit", r"1nce", r"hologram", r"emnify", r"wireless logic", r"cubic telecom", r"kore", r"eseye", r"webbing", r"soracom", r"monogoto",
             r"onomondo", r"flolive", r"pod group", r"podsystem", r"giesecke", r"thales dis", r"gemalto", r"kigen", r"tismi", r"globalmatix", r"jasper", r"arkessa",
             r"aeris", r"telenor connexion", r"stream ?technologies", r"simbase", r"teal communications",
             r"hanhaa", r"particle", r"conexa", r"airlinq", r"zte iot", r"bics", r"sierra wireless", r"semtech", r"u-blox", r"quectel", r"nordic semi",
             r"mobileum", r"telna", r"things mobile", r"tata communications move", r"workz",
             r"ipass", r"telefonica ?iot", r"vodafone ?iot"]),
    ("messaging", [r"bird\.com", r"telesign", r"link mobility", r"messagebird", r"bird b\.?v", r"sinch", r"infobip", r"twilio", r"vonage", r"mitto", r"clx",
                   r"tyntec", r"hsl messaging", r"textmagic", r"esendex", r"routee", r"bulksms"]),
    ("carrier_services", [r"comfone", r"mobileum", r"syniverse", r"mediafon carrier", r"mi carrier services", r"carrier services", r"rgtn", r"wholesale", r"ip directions", r"erate", r"viatel", r"interconnect", r"peeringhub", r"tata communications", r"bics", r"ibasis", r"comfone", r"globalcell", r"mobiweb", r"yateco", r"tychron"]),
    ("vendor_test", [r"japan radio", r"ericsson", r"nokia", r"huawei", r"zte", r"samsung", r"qualcomm", r"keysight", r"rohde", r"exfo", r"mavenir", r"amarisoft",
                     r"core network dynamics", r"athonet", r"siemens", r"motorola solutions", r"cisco", r"intel", r"anritsu", r"spirent", r"viavi",
                     r"parallel wireless", r"airspan", r"baicells", r"casa systems", r"druid", r"mediatek", r"thales communications", r"ofinno",
                     r"telecoms lab", r"uktl", r"telet research", r"bittium", r"ntt advanced", r"fujitsu", r"nec", r"kyocera"]),
    ("utility", [r"national grid", r"pacific gas", r"exelon", r"oncor", r"southern linc", r"ameren", r"duke energy", r"xcel", r"dominion", r"entergy",
                 r"evergy", r"cps energy", r"lcra", r"lower colorado river", r"alliant", r"enexis", r"liander", r"stedin", r"alliander", r"450connect",
                 r"anterix", r"digita", r"hydro quebec", r"altalink", r"bc hydro", r"powertech", r"clp power", r"hongkong electric", r"butachimie"]),
    ("transport", [r"network rail", r"mtr corporation", r"db netz", r"modern terminals", r"hong kong international terminals", r"airport authority",
                   r"utah dot", r"pinpoint"]),
    ("public_safety", [r"home office", r"esn", r"suomen erillisverkot", r"halton regional police"]),
    ("research", [r"strathclyde", r"aalto", r"tty-saatio", r"virginia tech", r"northeastern", r"purdue", r"nist"]),
    ("mvno", [r"internet initiative japan", r"sakura internet", r"closip", r"grape one", r"bb backbone", r"wicom", r"vroove", r"aurens", r"mitsui knowledge", r"starcat", r"i-tec solutions", r"textnow", r"freedompop", r"financiera para el bienestar", r"maskyoo", r"annatel", r"paycall", r"simpracy", r"ziggo", r"telenet", r"upc", r"virgin media", r"cogeco", r"mediacom", r"execulink", r"fibernetics", r"iristel", r"xplore", r"windstream", r"bredband2", r"luxembourg online", r"join experience", r"speakup", r"lemontel", r"gmobile", r"mobilive", r"monty uk", r"spirius", r"phonero", r"ice danmark", r"com4", r"teletopia", r"nexphone", r"iway", r"netplus", r"bebbicell", r"upc cablecom", r"sumamovil", r"g9telecom", r"digi portugal", r"free caraibe", r"ultravision", r"television internacional", r"alestra", r"vinoc", r"telenabler", r"netmore", r"karrier one", r"xnet", r"imsi\.ai", r"lycamobile", r"lebara", r"vectone", r"giffgaff", r"virgin mobile", r"tesco mobile", r"sky uk", r"talktalk", r"carphone warehouse",
              r"tracfone", r"boost", r"dish", r"mint mobile", r"ting", r"google fi", r"consumer cellular", r"spectrum", r"charter", r"comcast",
              r"cox", r"altice", r"lyca", r"ortel", r"vectone", r"simyo", r"ay yildiz", r"aldi", r"lidl", r"fonic", r"congstar",
              r"spusu", r"sipgate", r"simsalasim", r"telcovillage", r"mtel", r"drillisch", r"1&1", r"united internet", r"freenet", r"lowi",
              r"digi", r"digi$", r"free mobile", r"iliad", r"nrj", r"coriolis", r"prixtel", r"transatel", r"lefrenchmobile", r"mobiquithings",
              r"euroinformation", r"cic", r"credit mutuel", r"la poste", r"rami levi", r"golan", r"xphone", r"telzar", r"merkaziya", r"wecom",
              r"widly", r"voicenter", r"012", r"019", r"018", r"truphone", r"1global", r"tp global", r"transatel", r"voye global", r"globalsim", r"redtea", r"sim ?local", r"airalo", r"ubigi",
              r"public mobile", r"fido", r"koodo", r"chatr", r"lucky mobile", r"virgin plus", r"freedom mobile", r"ecotel", r"data on tap",
              r"cape", r"private tech", r"minute wireless", r"mobi", r"puloli", r"popcorn labs", r"helium", r"nova labs", r"limitless mobile",
              r"enreach", r"voiceworks", r"intovoice", r"steam-connect", r"w-tone", r"l-mobi", r"victor mobile", r"airgsm", r"sona business",
              r"cleverenable", r"koning & hartman", r"wholesale operator", r"private mobility", r"ultraband", r"olamo", r"venus movil",
              r"chadeva", r"alta tecnologia", r"xfera", r"simyo", r"pepephone", r"lowi", r"jazztel", r"citic telecom", r"china-hongkong",
              r"china unicom \(hong kong\)", r"china mobile international", r"sun mobile", r"jet connectivity", r"gamma telecom", r"telewaregroup",
              r"teleware", r"marathon telecom", r"shyam telecom uk", r"tango networks", r"synectiv", r"stour marine", r"spitfire", r"wave mobile",
              r"compatel", r"telavox", r"nettia", r"kuiri", r"ukkoverkot", r"boldyn", r"voxbone", r"bandwidth", r"telnyx",
              r"plintron", r"ztar", r"lycamobile", r"kddi.*mvno"]),
    ("mno", [r"pelephone", r"hot mobile", r"cellcom israel", r"partner communications", r"jt \(jersey\)", r"jersey telecom", r"aero 2", r"aero2", r"shyam telelink", r"teliasonera", r"sure", r"uzdunrobita", r"coscom", r"buztel", r"uzmacom", r"somoncom", r"indigo tajikistan", r"kyrgyztelecom", r"vietnamobile", r"cadcomms", r"starcell", r"mfone", r"hello", r"smart", r"etl company", r"gramenphone", r"aktel", r"dhimobile", r"centennialdominicana", r"aircell", r"tplus", r"reddi", r"ntt east", r"optage", r"vocus", r"inquam", r"airdata", r"gibfibre", r"icecell", r"inu:it", r"kalimat", r"itisaluna", r"fanoos", r"oteglobe", r"tdc", r"eircom", r"bezeq", r"nos comunicacoes", r"meo", r"etecsa", r"setar", r"tricom", r"comcel", r"post luxembourg", r"a1 slovenija", r"t-2", r"mobiltel", r"globul", r"omnitel", r"cosmofon", r"eurotel", r"aycell", r"aria", r"wind", r"blu", r"microcell", r"vipnet", r"essar", r"aircel", r"fascel", r"tata teleservices", r"radiomovil dipsa", r"telcel", r"altan redes", r"albtelecom", r"moldtelecom", r"ukrtelecom", r"romtelecom", r"euskaltel", r"cyfrowy polsat", r"centernet", r"mobyland", r"sferia", r"netia", r"ice norge", r"hi3g", r"tbaytel", r"ssi micro", r"nsight", r"smith bagley", r"cellularone", r"new mexico rsa", r"azerfon", r"catel", r"nakhtel", r"mobicom", r"fastlink", r"xpress", r"mobilecom", r"cmpak", r"areeba", r"iraqtel", r"itpc", r"spacetel", r"gibtel", r"mobiland", r"gsmbih", r"mdc velcom", r"belcel", r"televorgu", r"rigatta", r"omnitel pronto", r"globaltel", r"novatel", r"nov operator", r"wti macedonia", r"logic", r"ozone", r"deltronics", r"fkb net", r"rectel", r"laqtel", r"weblinks", r"newco2015", r"qatarnet", r"myanmar economic corporation", r"global technology co", r"vodafone", r"orange", r"telefonica", r"movistar", r"o2", r"t-mobile", r"deutsche telekom", r"telekom", r"verizon", r"at&t", r"sprint",
             r"u\.s\. cellular", r"us cellular", r"united states cellular", r"bell mobility", r"rogers", r"telus", r"sasktel", r"videotron", r"eastlink",
             r"telstra", r"optus", r"tpg", r"mtn", r"airtel", r"bharti", r"jio", r"reliance", r"vodafone idea", r"idea cellular", r"bsnl", r"mtnl",
             r"etisalat", r"e&", r"ooredoo", r"zain", r"stc", r"saudi telecom", r"mobily", r"du", r"emirates integrated", r"batelco", r"omantel",
             r"omani qatari", r"turkcell", r"turk telekom", r"avea", r"megafon", r"mts", r"mobile telesystems", r"beeline", r"vimpelcom", r"tele2",
             r"t2", r"telia", r"telenor", r"elisa", r"dna oy", r"kpn", r"proximus", r"swisscom", r"sunrise", r"salt mobile", r"a1", r"a1 telekom",
             r"magenta", r"hutchison", r"three", r"h3g", r"drei", r"bouygues", r"radiotelephone", r"sfr", r"windtre", r"wind tre", r"wind hellas",
             r"telecom italia", r"tim", r"tim$", r"fastweb", r"p4", r"play", r"polkomtel", r"plus", r"cosmote", r"ote", r"ote$", r"nova m\.a\.e",
             r"vivo", r"claro", r"america movil", r"oi", r"tigo", r"millicom", r"digicel", r"flow", r"cable & wireless", r"liberty", r"entel",
             r"wom", r"personal", r"telecom argentina", r"ntt docomo", r"docomo", r"kddi", r"softbank", r"rakuten mobile", r"sk telecom", r"kt corp",
             r"lg u", r"china mobile", r"china unicom", r"china telecom", r"hong kong telecommunications", r"hkt", r"csl", r"smartone", r"ctm",
             r"chunghwa", r"taiwan mobile", r"far eastone", r"singtel", r"singapore telecom", r"starhub", r"m1", r"maxis", r"celcom", r"digi telecom",
             r"u mobile", r"telkomsel", r"indosat", r"xl axiata", r"smartfren", r"globe telecom", r"smart communications", r"dito", r"advanced info",
             r"ais", r"dtac", r"true move", r"viettel", r"vinaphone", r"mobifone", r"grameenphone", r"robi", r"banglalink", r"teletalk", r"jazz",
             r"mobilink", r"zong", r"ufone", r"dialog", r"mobitel", r"ncell", r"nepal telecom", r"roshan", r"awcc", r"afghan wireless", r"celtel",
             r"safaricom", r"vodacom", r"cell c", r"telkom sa", r"telkom kenya", r"glo mobile", r"globacom", r"9mobile", r"moov", r"maroc telecom", r"itissalat",
             r"inwi", r"wana", r"djezzy", r"mobilis", r"sudatel", r"ethio telecom", r"libancell", r"cellis", r"alfa", r"touch", r"yettel",
             r"one hungary", r"magyar telekom", r"telemach", r"bh telecom", r"eronet", r"moldcell", r"kyivstar", r"lifecell", r"vf ukraine",
             r"geocell", r"silknet", r"magti", r"ucom", r"viva", r"azercell", r"bakcell", r"nar mobile", r"kcell", r"altel", r"megacom",
             r"tcell", r"babilon", r"ucell", r"uzmobile", r"mobiuz", r"mytel", r"atom", r"myanmar posts", r"unitel", r"lao telecom", r"cellcard",
             r"smart axiata", r"metfone", r"telesur", r"lime", r"bmobile", r"tstt", r"cellone", r"paradise mobile", r"spark", r"2degrees",
             r"one new zealand", r"telikom", r"vodafone fiji", r"airtel", r"bharat", r"telenor", r"oteglobe", r"cyta", r"epic", r"primetel",
             r"go mobile", r"melita", r"siminn", r"nova ehf", r"og fjarskipti", r"faroese telecom", r"kall", r"tusass", r"tele greenland",
             r"lmt", r"bite", r"tele2", r"telia", r"elisa eesti", r"mobile telephone networks", r"cellular one", r"appalachian wireless",
             r"east kentucky network", r"cellcom", r"nex-tech", r"union telephone", r"carolina west", r"inland cellular", r"pioneer cellular",
             r"viaero", r"gci", r"alaska communications", r"bluegrass cellular", r"cellular south", r"c spire", r"sprint", r"nntc", r"northwest missouri",
             r"chariton valley", r"illinois valley", r"commnet", r"choice wireless", r"docomo pacific", r"it&e", r"pti pacifica", r"gta teleguam",
             r"liberty latin", r"puerto rico telephone", r"claro puerto rico", r"open mobile", r"hutchison 3g", r"ee limited", r"bt", r"british telecom",
             r"jersey airtel", r"sure \(", r"manx telecom", r"jt", r"swisscom", r"salt", r"telecel", r"econet", r"net one", r"zamtel", r"airtel",
             r"tnm", r"expresso", r"sotelma", r"malitel", r"orange", r"sonatel", r"moov", r"libyana", r"al madar", r"asiacell", r"korek", r"zain iraq",
             r"mci", r"irancell", r"rightel", r"mtce", r"hamrah", r"taliya", r"sabafon", r"yemen mobile", r"mtc", r"aircel", r"tata docomo",
             r"vodafone qatar", r"stc kuwait", r"viva kuwait", r"wataniya", r"jawwal", r"wataniya palestine", r"zain jordan", r"umniah",
             r"syriatel", r"mtn syria", r"asia pacific telecom", r"gt&t", r"telecom namibia", r"mtc namibia", r"btc", r"mascom", r"botswana telecom",
             r"lesotho", r"econet", r"swazi mtn", r"tigo", r"halotel", r"vodacom", r"telkom kenya", r"airtel", r"uganda telecom", r"lyca", r"mtn"]),
]
KNOWN_RX = [(t, re.compile(r"(?<![a-z0-9])(" + "|".join(p) + r")(?![a-z0-9])")) for t, p in KNOWN]
# specific holders whose names would otherwise trip a keyword rule
OVERRIDES = [(t, re.compile(r"(?<![a-z0-9])(" + "|".join(p) + r")(?![a-z0-9])")) for t, p in [
    ("satellite", [r"ast ?& ?science", r"ast spacemobile", r"airbus defence and space", r"terrestar"]),
    ("mno", [r"metro ?pcs", r"american samoa telecommunications authority", r"tribe mobile"]),
    ("mvno", [r"nova labs", r"popcorn labs", r"helium"]),
    ("private", [r"bhp", r"pilbara iron", r"santos", r"yancoal", r"rio tinto", r"fortescue", r"woodside", r"chudenko", r"jtower", r"coeur", r"newmont", r"chevron", r"jci us", r"johnson controls", r"skoda auto", r"geoverse", r"extenet", r"broadpoint", r"petrocom", r"celblox", r"townes 5g", r"wi-das", r"aetheros", r"orcid", r"open ran center", r"halys", r"hub one", r"airmob", r"netwo", r"nomotech", r"citymesh", r"smartspace", r"teracom", r"net4mobility", r"gotalandsnatet", r"systemnet", r"highway9", r"celona", r"betacom", r"federated wireless", r"boldyn", r"ukkoverkot", r"edzcom", r"druid"]),
    ("utility", [r"utility connect"]),
    ("vendor_test", [r"mitsubishi electric", r"telecoms lab", r"telet research"]),
    ("government", [r"tkuv", r"ukrspetszvyazok", r"viestintavirasto", r"gujocity", r"royal court", r"imod", r"ministerie van defensie", r"civil aviation authority", r"communications authority", r"regulatory authority", r"etsi", r"european telecommunications standards"]),
    ("community", [r"telephone cooperative", r"telephone association", r"telephone coop", r"naskapi", r"keewatinook", r"cheyenne and arapaho"]),
    ("utility", [r"lower colorado river authority"]),
]]
GENERIC_OPERATOR = rx(r"cable", r"cable television", r"catv", r"ertebatat", r"\w*svyaz\w*", r"\w*telesot", r"mobile", r"mobil", r"movil", r"movel", r"cellular", r"celular", r"cellulaire", r"wireless", r"telecom\w*", r"telekom\w*",
                      r"telecomunica\w*", r"telecommunica\w*", r"communications?", r"comunicaciones", r"pcs", r"gsm", r"cdma", r"networks?",
                      r"telephone", r"telefon\w*", r"phone", r"cell", r"tel", r"mobility", r"connect\w*", r"broadband", r"telco")


def classify(rec, nat_hint):
    name = rec["network"] or ""
    f = fold(name)
    if rec["mcc"] == "991":
        return "trial", "stated", "MCC 991 is the ITU's range for trials of proposed new international services"
    if nat_hint:
        return nat_hint
    for t, r in STATED:
        if r.search(f):
            return t, "stated", f"register text: “{name}”"
    for t, r in OVERRIDES:
        m = r.search(f)
        if m:
            return t, "inferred", f"known holder: {m.group(0)}"
    for t, r in KNOWN_RX:
        if t == "mno":
            continue
        m = r.search(f)
        if m:
            return t, "inferred", f"known holder: {m.group(0)}"
    for t, r in NAME:
        m = r.search(f)
        if m:
            return t, "name", f"holder name contains “{m.group(0)}”"
    for t, r in KNOWN_RX:
        if t != "mno":
            continue
        m = r.search(f)
        if m:
            return t, "inferred", f"known holder: {m.group(0)}"
    if GENERIC_OPERATOR.search(f):
        return "operator", "name", "holder name describes a public telecoms operator; MNO or MVNO not determined"
    return "unclassified", None, None


def main(rp, natp, outp):
    reg = json.load(open(rp))
    nat = json.load(open(natp))
    # national registry hints that state a type outright
    hints = {}
    for x in nat["records"]:
        rem = fold(x.get("remark") or "")
        k = (x["mcc"], x["mnc"])
        if x["registry"] == "hk_ofca" and x["status"] == "assigned":
            if "mvno" in rem:
                hints[k] = ("mvno", "stated", "OFCA lists it as an MVNO")
            elif "public mobile networks" in rem:
                hints[k] = ("mno", "stated", "OFCA lists it as a public mobile network without an MVNO remark")
        if x["registry"] == "ca_cnac" and "experimental" in rem:
            hints[k] = ("vendor_test", "stated", "CNAC lists it for experimental purposes")
        if x["registry"] == "us_imsi" and x["status"] == "reserved":
            hints[k] = ("reserved", "stated", "US administrator: reserved for public safety")
    out, cnt, tiers = [], Counter(), Counter()
    for r in reg:
        h = hints.get((r["mcc"], r["mnc"])) if r["scope"] == "geographic" else None
        # a hint keyed only by code must belong to the same country's registry
        if h and r["country"] not in ("Hong Kong, China", "Canada", "United States"):
            h = None
        t, tier, why = classify(r, h)
        r2 = dict(r, type=t, type_tier=tier, type_basis=why)
        out.append(r2)
        if r["status"] == "active":
            cnt[t] += 1; tiers[tier] += 1
    json.dump({"types": TYPES, "register": out}, open(outp, "w"), ensure_ascii=False, indent=1)
    tot = sum(cnt.values())
    print("active codes:", tot)
    for t, n in cnt.most_common():
        print(f"  {t:18s} {n:5d}  {n/tot:5.1%}")
    print("tiers:", dict(tiers))


if __name__ == "__main__":
    main(*sys.argv[1:4])
