"""Map ITU E.212 country names in the register to ISO 3166-1 codes.

Usage: python3 -I country_iso.py <register_typed_json> <out_json>
"""
import json, sys
import pycountry

OVERRIDES = {
    "Bolivia (Plurinational State of)": "BOL", "Bosnia and Herzegovina": "BIH", "Cabo Verde": "CPV",
    "Central African Rep.": "CAF", "Congo (Rep. of the)": "COG", "Dem. Rep. of the Congo": "COD",
    "Czech Rep.": "CZE", "Dominican Rep.": "DOM", "Dem. People's Rep. of Korea": "PRK", "Korea (Rep. of)": "KOR",
    "Hong Kong, China": "HKG", "Macao, China": "MAC", "Iran (Islamic Republic of)": "IRN", "Lao P.D.R.": "LAO",
    "Micronesia": "FSM", "Moldova (Republic of)": "MDA", "Russian Federation": "RUS", "Syrian Arab Republic": "SYR",
    "Tanzania": "TZA", "Venezuela (Bolivarian Republic of)": "VEN", "Viet Nam": "VNM", "Kyrgyzstan": "KGZ",
    "Slovak Republic": "SVK", "Türkiye": "TUR", "Turkey": "TUR", "Côte d'Ivoire": "CIV", "Taiwan, China": "TWN",
    "Vatican": "VAT", "Palestine": "PSE", "Kosovo*": "XKX", "Kosovo": "XKX", "North Macedonia": "MKD",
    "The Former Yugoslav Republic of Macedonia": "MKD", "Gambia": "GMB", "Bahamas": "BHS", "Brunei Darussalam": "BRN",
    "Curaçao": "CUW", "Sint Maarten": "SXM", "Bonaire, Sint Eustatius and Saba": "BES", "Falkland Islands (Malvinas)": "FLK",
    "French Departments and Territories in the Indian Ocean": "REU", "French Guiana": "GUF", "Guadeloupe (French Department of)": "GLP",
    "Martinique (French Department of)": "MTQ", "French Polynesia": "PYF", "New Caledonia": "NCL", "Wallis and Futuna": "WLF",
    "Saint Pierre and Miquelon": "SPM", "Saint Pierre and Miquelon (Collectivité territoriale de la République française)": "SPM",
    "Netherlands Antilles": "CUW", "Aruba": "ABW", "Cayman Islands": "CYM", "Turks and Caicos Islands": "TCA",
    "British Virgin Islands": "VGB", "United States Virgin Islands": "VIR", "Puerto Rico": "PRI", "Guam": "GUM",
    "Northern Mariana Islands": "MNP", "American Samoa": "ASM", "Greenland (Denmark)": "GRL", "Greenland": "GRL",
    "Faroe Islands": "FRO", "Gibraltar": "GIB", "Montserrat": "MSR", "Anguilla": "AIA", "Bermuda": "BMU",
    "Saint Helena, Ascension and Tristan da Cunha": "SHN", "Saint Kitts and Nevis": "KNA", "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT", "Swaziland": "SWZ", "Eswatini": "SWZ", "Timor-Leste": "TLS",
    "Cook Islands": "COK", "Niue": "NIU", "Tokelau": "TKL", "Diego Garcia": "IOT", "Norfolk Island": "NFK",
    "Christmas Island": "CXR", "Libya": "LBY", "Moldova": "MDA", "Iraq": "IRQ", "Yemen": "YEM", "Myanmar": "MMR",
    "Guinea-Bissau": "GNB", "Equatorial Guinea": "GNQ", "Sao Tome and Principe": "STP", "Comoros": "COM",
    "Marshall Islands": "MHL", "Palau": "PLW", "Kiribati": "KIR", "Tuvalu": "TUV", "Nauru": "NRU",
    "South Sudan": "SSD", "Sudan": "SDN", "Montenegro": "MNE", "Serbia": "SRB", "Kazakhstan": "KAZ",
    "Mauritania": "MRT", "Andorra": "AND", "Monaco": "MCO", "San Marino": "SMR", "Liechtenstein": "LIE",
}


def main(rp, outp):
    reg = json.load(open(rp))["register"]
    names = sorted({r["country"] for r in reg if r["scope"] == "geographic"})
    out, miss = {}, []
    for n in names:
        a3 = OVERRIDES.get(n)
        if not a3:
            c = pycountry.countries.get(name=n) or pycountry.countries.get(common_name=n) or pycountry.countries.get(official_name=n)
            if not c:
                try:
                    c = pycountry.countries.search_fuzzy(n)[0]
                except LookupError:
                    c = None
            a3 = c.alpha_3 if c else None
        if not a3:
            miss.append(n); continue
        c = pycountry.countries.get(alpha_3=a3)
        out[n] = {"a3": a3, "num": c.numeric if c else None, "iso_name": c.name if c else n}
    json.dump(out, open(outp, "w"), ensure_ascii=False, indent=1)
    print("countries:", len(names), "| mapped:", len(out), "| unmapped:", miss)
    # show fuzzy matches that are not exact, for eye-check
    for n, v in out.items():
        if n not in OVERRIDES and v["iso_name"] != n:
            print(f"  {n!r} -> {v['a3']} {v['iso_name']!r}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
