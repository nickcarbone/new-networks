// Pre-project the world map for the atlas page.
// Writes geo.json: { width, height, land, borders, countries: {num: path}, points: {A3: [x, y]} }
// Usage: node build_geo.mjs <country_iso_json> <out_json>
import fs from "node:fs";
import { feature, mesh } from "topojson-client";
import { geoEqualEarth, geoPath, geoCentroid, geoArea } from "d3-geo";

const [, , isoPath, outPath] = process.argv;
const iso = JSON.parse(fs.readFileSync(isoPath, "utf8"));
const w110 = JSON.parse(fs.readFileSync("node_modules/world-atlas/countries-110m.json", "utf8"));
const w50 = JSON.parse(fs.readFileSync("node_modules/world-atlas/countries-50m.json", "utf8"));

const W = 1000, H = 520;
const land = feature(w110, w110.objects.land);
const projection = geoEqualEarth().fitExtent([[8, 8], [W - 8, H - 8]], { type: "Sphere" });
const path = geoPath(projection).digits(1);

const countries110 = feature(w110, w110.objects.countries).features;
const countries50 = feature(w50, w50.objects.countries).features;
const byNum = new Map();
for (const f of countries50) if (f.id) byNum.set(String(f.id).padStart(3, "0"), f);

// Hand-placed points for codes whose territory is missing or too small in the 50m data.
// [lon, lat]
const MANUAL = {
  XKX: [20.9, 42.6], GIB: [-5.35, 36.14], MCO: [7.42, 43.74], SMR: [12.46, 43.94], VAT: [12.45, 41.9],
  LIE: [9.55, 47.16], AND: [1.52, 42.51], MLT: [14.4, 35.9], HKG: [114.17, 22.32], MAC: [113.55, 22.19],
  SGP: [103.82, 1.35], BHR: [50.56, 26.07], MDV: [73.5, 4.2], IOT: [72.4, -7.3], GUF: [-53.1, 3.9],
  GLP: [-61.55, 16.25], MTQ: [-61.0, 14.64], REU: [55.53, -21.12], CUW: [-68.99, 12.17], SXM: [-63.06, 18.04],
  BES: [-68.26, 12.18], ABW: [-69.97, 12.52], BMU: [-64.75, 32.31], CYM: [-81.25, 19.31], TCA: [-71.8, 21.8],
  VGB: [-64.6, 18.42], VIR: [-64.9, 18.34], AIA: [-63.06, 18.22], MSR: [-62.19, 16.74], KNA: [-62.75, 17.3],
  LCA: [-60.98, 13.9], VCT: [-61.2, 13.25], GRD: [-61.68, 12.12], BRB: [-59.55, 13.17], ATG: [-61.8, 17.08],
  DMA: [-61.37, 15.42], TTO: [-61.25, 10.5], SPM: [-56.3, 46.9], COK: [-159.78, -21.24], NIU: [-169.87, -19.05],
  TKL: [-171.85, -9.2], WLF: [-176.2, -13.3], TUV: [179.2, -8.5], NRU: [166.93, -0.53], KIR: [173.0, 1.4],
  MHL: [171.2, 7.1], PLW: [134.58, 7.5], FSM: [158.2, 6.9], ASM: [-170.7, -14.3], GUM: [144.79, 13.44],
  MNP: [145.75, 15.2], TON: [-175.2, -21.2], WSM: [-172.1, -13.76], SHN: [-5.7, -15.95], STP: [6.6, 0.3],
  COM: [43.3, -11.7], SYC: [55.45, -4.6], MUS: [57.55, -20.25], CPV: [-23.6, 15.1], FRO: [-6.9, 62.0],
  NFK: [167.95, -29.04], CXR: [105.69, -10.45], PYF: [-149.4, -17.6], NCL: [165.6, -21.3], BRN: [114.7, 4.5],
  LUX: [6.13, 49.81], PSE: [35.2, 31.9], QAT: [51.2, 25.3], FLK: [-59.5, -51.7], GMB: [-15.4, 13.45], TLS: [125.7, -8.8],
};

const points = {};
const missing = [];
for (const [name, v] of Object.entries(iso)) {
  let lonlat = MANUAL[v.a3];
  if (!lonlat) {
    const f = v.num ? byNum.get(v.num) : null;
    if (f) {
      // use the centroid of the largest polygon, so overseas territories don't drag the point into the sea
      let g = f.geometry;
      if (g.type === "MultiPolygon") {
        let best = null, bestA = -1;
        for (const poly of g.coordinates) {
          const pf = { type: "Polygon", coordinates: poly };
          const a = geoArea(pf);
          if (a > bestA) { bestA = a; best = pf; }
        }
        g = best;
      }
      lonlat = geoCentroid({ type: "Feature", geometry: g });
    }
  }
  if (!lonlat) { missing.push(`${name} (${v.a3})`); continue; }
  const p = projection(lonlat);
  points[v.a3] = [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
}

const countryPaths = {};
for (const f of countries110) if (f.id) countryPaths[String(f.id).padStart(3, "0")] = path(f);

const out = {
  width: W, height: H,
  sphere: path({ type: "Sphere" }),
  graticule: null,
  land: path(land),
  borders: path(mesh(w110, w110.objects.countries, (a, b) => a !== b)),
  countries: countryPaths,
  points,
};
fs.writeFileSync(outPath, JSON.stringify(out));
console.log("points:", Object.keys(points).length, "| missing:", missing, "| size KB:", Math.round(JSON.stringify(out).length / 1024));
