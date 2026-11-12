import {
  booleanPointInPolygon,
  getGeom
} from "./chunk-QPRHBWFJ.js";
import {
  flattenEach
} from "./chunk-GH4D7NQT.js";
import {
  feature,
  featureCollection,
  lineString,
  multiLineString,
  point
} from "./chunk-EGSHJPUB.js";

// node_modules/tinyqueue/index.js
var TinyQueue = class {
  constructor(data = [], compare = defaultCompare) {
    this.data = data;
    this.length = this.data.length;
    this.compare = compare;
    if (this.length > 0) {
      for (let i = (this.length >> 1) - 1; i >= 0; i--) this._down(i);
    }
  }
  push(item) {
    this.data.push(item);
    this.length++;
    this._up(this.length - 1);
  }
  pop() {
    if (this.length === 0) return void 0;
    const top = this.data[0];
    const bottom = this.data.pop();
    this.length--;
    if (this.length > 0) {
      this.data[0] = bottom;
      this._down(0);
    }
    return top;
  }
  peek() {
    return this.data[0];
  }
  _up(pos) {
    const { data, compare } = this;
    const item = data[pos];
    while (pos > 0) {
      const parent = pos - 1 >> 1;
      const current = data[parent];
      if (compare(item, current) >= 0) break;
      data[pos] = current;
      pos = parent;
    }
    data[pos] = item;
  }
  _down(pos) {
    const { data, compare } = this;
    const halfLength = this.length >> 1;
    const item = data[pos];
    while (pos < halfLength) {
      let left = (pos << 1) + 1;
      let best = data[left];
      const right = left + 1;
      if (right < this.length && compare(data[right], best) < 0) {
        left = right;
        best = data[right];
      }
      if (compare(best, item) >= 0) break;
      data[pos] = best;
      pos = left;
    }
    data[pos] = item;
  }
};
function defaultCompare(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// node_modules/robust-predicates/esm/util.js
var epsilon = 11102230246251565e-32;
var splitter = 134217729;
var resulterrbound = (3 + 8 * epsilon) * epsilon;
function sum(elen, e, flen, f, h) {
  let Q, Qnew, hh, bvirt;
  let enow = e[0];
  let fnow = f[0];
  let eindex = 0;
  let findex = 0;
  if (fnow > enow === fnow > -enow) {
    Q = enow;
    enow = e[++eindex];
  } else {
    Q = fnow;
    fnow = f[++findex];
  }
  let hindex = 0;
  if (eindex < elen && findex < flen) {
    if (fnow > enow === fnow > -enow) {
      Qnew = enow + Q;
      hh = Q - (Qnew - enow);
      enow = e[++eindex];
    } else {
      Qnew = fnow + Q;
      hh = Q - (Qnew - fnow);
      fnow = f[++findex];
    }
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
    while (eindex < elen && findex < flen) {
      if (fnow > enow === fnow > -enow) {
        Qnew = Q + enow;
        bvirt = Qnew - Q;
        hh = Q - (Qnew - bvirt) + (enow - bvirt);
        enow = e[++eindex];
      } else {
        Qnew = Q + fnow;
        bvirt = Qnew - Q;
        hh = Q - (Qnew - bvirt) + (fnow - bvirt);
        fnow = f[++findex];
      }
      Q = Qnew;
      if (hh !== 0) {
        h[hindex++] = hh;
      }
    }
  }
  while (eindex < elen) {
    Qnew = Q + enow;
    bvirt = Qnew - Q;
    hh = Q - (Qnew - bvirt) + (enow - bvirt);
    enow = e[++eindex];
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
  }
  while (findex < flen) {
    Qnew = Q + fnow;
    bvirt = Qnew - Q;
    hh = Q - (Qnew - bvirt) + (fnow - bvirt);
    fnow = f[++findex];
    Q = Qnew;
    if (hh !== 0) {
      h[hindex++] = hh;
    }
  }
  if (Q !== 0 || hindex === 0) {
    h[hindex++] = Q;
  }
  return hindex;
}
function estimate(elen, e) {
  let Q = e[0];
  for (let i = 1; i < elen; i++) Q += e[i];
  return Q;
}
function vec(n) {
  return new Float64Array(n);
}

// node_modules/robust-predicates/esm/orient2d.js
var ccwerrboundA = (3 + 16 * epsilon) * epsilon;
var ccwerrboundB = (2 + 12 * epsilon) * epsilon;
var ccwerrboundC = (9 + 64 * epsilon) * epsilon * epsilon;
var B = vec(4);
var C1 = vec(8);
var C2 = vec(12);
var D = vec(16);
var u = vec(4);
function orient2dadapt(ax, ay, bx, by, cx, cy, detsum) {
  let acxtail, acytail, bcxtail, bcytail;
  let bvirt, c, ahi, alo, bhi, blo, _i, _j, _0, s1, s0, t1, t0, u32;
  const acx = ax - cx;
  const bcx = bx - cx;
  const acy = ay - cy;
  const bcy = by - cy;
  s1 = acx * bcy;
  c = splitter * acx;
  ahi = c - (c - acx);
  alo = acx - ahi;
  c = splitter * bcy;
  bhi = c - (c - bcy);
  blo = bcy - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t1 = acy * bcx;
  c = splitter * acy;
  ahi = c - (c - acy);
  alo = acy - ahi;
  c = splitter * bcx;
  bhi = c - (c - bcx);
  blo = bcx - bhi;
  t0 = alo * blo - (t1 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t0;
  bvirt = s0 - _i;
  B[0] = s0 - (_i + bvirt) + (bvirt - t0);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t1;
  bvirt = _0 - _i;
  B[1] = _0 - (_i + bvirt) + (bvirt - t1);
  u32 = _j + _i;
  bvirt = u32 - _j;
  B[2] = _j - (u32 - bvirt) + (_i - bvirt);
  B[3] = u32;
  let det = estimate(4, B);
  let errbound = ccwerrboundB * detsum;
  if (det >= errbound || -det >= errbound) {
    return det;
  }
  bvirt = ax - acx;
  acxtail = ax - (acx + bvirt) + (bvirt - cx);
  bvirt = bx - bcx;
  bcxtail = bx - (bcx + bvirt) + (bvirt - cx);
  bvirt = ay - acy;
  acytail = ay - (acy + bvirt) + (bvirt - cy);
  bvirt = by - bcy;
  bcytail = by - (bcy + bvirt) + (bvirt - cy);
  if (acxtail === 0 && acytail === 0 && bcxtail === 0 && bcytail === 0) {
    return det;
  }
  errbound = ccwerrboundC * detsum + resulterrbound * Math.abs(det);
  det += acx * bcytail + bcy * acxtail - (acy * bcxtail + bcx * acytail);
  if (det >= errbound || -det >= errbound) return det;
  s1 = acxtail * bcy;
  c = splitter * acxtail;
  ahi = c - (c - acxtail);
  alo = acxtail - ahi;
  c = splitter * bcy;
  bhi = c - (c - bcy);
  blo = bcy - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t1 = acytail * bcx;
  c = splitter * acytail;
  ahi = c - (c - acytail);
  alo = acytail - ahi;
  c = splitter * bcx;
  bhi = c - (c - bcx);
  blo = bcx - bhi;
  t0 = alo * blo - (t1 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t0;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t0);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t1;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t1);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const C1len = sum(4, B, 4, u, C1);
  s1 = acx * bcytail;
  c = splitter * acx;
  ahi = c - (c - acx);
  alo = acx - ahi;
  c = splitter * bcytail;
  bhi = c - (c - bcytail);
  blo = bcytail - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t1 = acy * bcxtail;
  c = splitter * acy;
  ahi = c - (c - acy);
  alo = acy - ahi;
  c = splitter * bcxtail;
  bhi = c - (c - bcxtail);
  blo = bcxtail - bhi;
  t0 = alo * blo - (t1 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t0;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t0);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t1;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t1);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const C2len = sum(C1len, C1, 4, u, C2);
  s1 = acxtail * bcytail;
  c = splitter * acxtail;
  ahi = c - (c - acxtail);
  alo = acxtail - ahi;
  c = splitter * bcytail;
  bhi = c - (c - bcytail);
  blo = bcytail - bhi;
  s0 = alo * blo - (s1 - ahi * bhi - alo * bhi - ahi * blo);
  t1 = acytail * bcxtail;
  c = splitter * acytail;
  ahi = c - (c - acytail);
  alo = acytail - ahi;
  c = splitter * bcxtail;
  bhi = c - (c - bcxtail);
  blo = bcxtail - bhi;
  t0 = alo * blo - (t1 - ahi * bhi - alo * bhi - ahi * blo);
  _i = s0 - t0;
  bvirt = s0 - _i;
  u[0] = s0 - (_i + bvirt) + (bvirt - t0);
  _j = s1 + _i;
  bvirt = _j - s1;
  _0 = s1 - (_j - bvirt) + (_i - bvirt);
  _i = _0 - t1;
  bvirt = _0 - _i;
  u[1] = _0 - (_i + bvirt) + (bvirt - t1);
  u32 = _j + _i;
  bvirt = u32 - _j;
  u[2] = _j - (u32 - bvirt) + (_i - bvirt);
  u[3] = u32;
  const Dlen = sum(C2len, C2, 4, u, D);
  return D[Dlen - 1];
}
function orient2d(ax, ay, bx, by, cx, cy) {
  const detleft = (ay - cy) * (bx - cx);
  const detright = (ax - cx) * (by - cy);
  const det = detleft - detright;
  if (detleft === 0 || detright === 0 || detleft > 0 !== detright > 0) return det;
  const detsum = Math.abs(detleft + detright);
  if (Math.abs(det) >= ccwerrboundA * detsum) return det;
  return -orient2dadapt(ax, ay, bx, by, cx, cy, detsum);
}

// node_modules/robust-predicates/esm/orient3d.js
var o3derrboundA = (7 + 56 * epsilon) * epsilon;
var o3derrboundB = (3 + 28 * epsilon) * epsilon;
var o3derrboundC = (26 + 288 * epsilon) * epsilon * epsilon;
var bc = vec(4);
var ca = vec(4);
var ab = vec(4);
var at_b = vec(4);
var at_c = vec(4);
var bt_c = vec(4);
var bt_a = vec(4);
var ct_a = vec(4);
var ct_b = vec(4);
var bct = vec(8);
var cat = vec(8);
var abt = vec(8);
var u2 = vec(4);
var _8 = vec(8);
var _8b = vec(8);
var _16 = vec(8);
var _12 = vec(12);
var fin = vec(192);
var fin2 = vec(192);

// node_modules/robust-predicates/esm/incircle.js
var iccerrboundA = (10 + 96 * epsilon) * epsilon;
var iccerrboundB = (4 + 48 * epsilon) * epsilon;
var iccerrboundC = (44 + 576 * epsilon) * epsilon * epsilon;
var bc2 = vec(4);
var ca2 = vec(4);
var ab2 = vec(4);
var aa = vec(4);
var bb = vec(4);
var cc = vec(4);
var u3 = vec(4);
var v = vec(4);
var axtbc = vec(8);
var aytbc = vec(8);
var bxtca = vec(8);
var bytca = vec(8);
var cxtab = vec(8);
var cytab = vec(8);
var abt2 = vec(8);
var bct2 = vec(8);
var cat2 = vec(8);
var abtt = vec(4);
var bctt = vec(4);
var catt = vec(4);
var _82 = vec(8);
var _162 = vec(16);
var _16b = vec(16);
var _16c = vec(16);
var _32 = vec(32);
var _32b = vec(32);
var _48 = vec(48);
var _64 = vec(64);
var fin3 = vec(1152);
var fin22 = vec(1152);

// node_modules/robust-predicates/esm/insphere.js
var isperrboundA = (16 + 224 * epsilon) * epsilon;
var isperrboundB = (5 + 72 * epsilon) * epsilon;
var isperrboundC = (71 + 1408 * epsilon) * epsilon * epsilon;
var ab3 = vec(4);
var bc3 = vec(4);
var cd = vec(4);
var de = vec(4);
var ea = vec(4);
var ac = vec(4);
var bd = vec(4);
var ce = vec(4);
var da = vec(4);
var eb = vec(4);
var abc = vec(24);
var bcd = vec(24);
var cde = vec(24);
var dea = vec(24);
var eab = vec(24);
var abd = vec(24);
var bce = vec(24);
var cda = vec(24);
var deb = vec(24);
var eac = vec(24);
var adet = vec(1152);
var bdet = vec(1152);
var cdet = vec(1152);
var ddet = vec(1152);
var edet = vec(1152);
var abdet = vec(2304);
var cddet = vec(2304);
var cdedet = vec(3456);
var deter = vec(5760);
var _83 = vec(8);
var _8b2 = vec(8);
var _8c = vec(8);
var _163 = vec(16);
var _24 = vec(24);
var _482 = vec(48);
var _48b = vec(48);
var _96 = vec(96);
var _192 = vec(192);
var _384x = vec(384);
var _384y = vec(384);
var _384z = vec(384);
var _768 = vec(768);
var xdet = vec(96);
var ydet = vec(96);
var zdet = vec(96);
var fin4 = vec(1152);

// node_modules/@turf/line-intersect/dist/esm/index.js
function sweeplineIntersections(geojson, ignoreSelfIntersections) {
  const eventQueue = new TinyQueue([], checkWhichEventIsLeft);
  fillEventQueue(geojson, eventQueue);
  return runCheck(eventQueue, ignoreSelfIntersections);
}
function checkWhichEventIsLeft(e1, e2) {
  if (e1.p.x > e2.p.x) return 1;
  if (e1.p.x < e2.p.x) return -1;
  if (e1.p.x === e2.p.x && (e1.featureId !== e2.featureId || e1.ringId !== e2.ringId)) {
    if (e1.isLeftEndpoint && !e2.isLeftEndpoint) return -1;
  }
  if (e1.p.y !== e2.p.y) return e1.p.y > e2.p.y ? 1 : -1;
  return 1;
}
function checkWhichSegmentHasRightEndpointFirst(seg1, seg2) {
  if (seg1.rightSweepEvent.p.x > seg2.rightSweepEvent.p.x) return 1;
  if (seg1.rightSweepEvent.p.x < seg2.rightSweepEvent.p.x) return -1;
  if (seg1.rightSweepEvent.p.y !== seg2.rightSweepEvent.p.y) {
    return seg1.rightSweepEvent.p.y < seg2.rightSweepEvent.p.y ? 1 : -1;
  }
  return 1;
}
function fillEventQueue(geojson, eventQueue) {
  if (geojson.type === "FeatureCollection") {
    const features = geojson.features;
    for (let i = 0; i < features.length; i++) {
      processFeature(features[i], eventQueue);
    }
  } else {
    processFeature(geojson, eventQueue);
  }
}
var featureId = 0;
var ringId = 0;
var eventId = 0;
function processFeature(featureOrGeometry, eventQueue) {
  const geom = featureOrGeometry.type === "Feature" ? featureOrGeometry.geometry : featureOrGeometry;
  let coords = geom.coordinates;
  if (geom.type === "Polygon" || geom.type === "MultiLineString")
    coords = [coords];
  if (geom.type === "LineString") coords = [[coords]];
  for (let i = 0; i < coords.length; i++) {
    for (let ii = 0; ii < coords[i].length; ii++) {
      let currentP = coords[i][ii][0];
      let nextP = null;
      ringId = ringId + 1;
      for (let iii = 0; iii < coords[i][ii].length - 1; iii++) {
        nextP = coords[i][ii][iii + 1];
        const e1 = new Event(currentP, featureId, ringId, eventId);
        const e2 = new Event(nextP, featureId, ringId, eventId + 1);
        e1.otherEvent = e2;
        e2.otherEvent = e1;
        if (checkWhichEventIsLeft(e1, e2) > 0) {
          e2.isLeftEndpoint = true;
          e1.isLeftEndpoint = false;
        } else {
          e1.isLeftEndpoint = true;
          e2.isLeftEndpoint = false;
        }
        eventQueue.push(e1);
        eventQueue.push(e2);
        currentP = nextP;
        eventId = eventId + 1;
      }
    }
  }
  featureId = featureId + 1;
}
var Event = class {
  constructor(p, featureId2, ringId2, eventId2) {
    this.p = {
      x: p[0],
      y: p[1]
    };
    this.featureId = featureId2;
    this.ringId = ringId2;
    this.eventId = eventId2;
    this.otherEvent = null;
    this.isLeftEndpoint = null;
  }
  isSamePoint(eventToCheck) {
    return this.p.x === eventToCheck.p.x && this.p.y === eventToCheck.p.y;
  }
  asNewXY() {
    return [this.p.x, this.p.y];
  }
};
function runCheck(eventQueue, ignoreSelfIntersections = false) {
  const intersectionPoints = [];
  const outQueue = new TinyQueue([], checkWhichSegmentHasRightEndpointFirst);
  while (eventQueue.length) {
    const event = eventQueue.pop();
    if (event.isLeftEndpoint) {
      const segment = new Segment(event);
      for (let i = 0; i < outQueue.data.length; i++) {
        const otherSeg = outQueue.data[i];
        if (ignoreSelfIntersections) {
          if (otherSeg.leftSweepEvent.featureId === event.featureId) continue;
        }
        const intersection = testSegmentIntersect(segment, otherSeg);
        if (intersection !== false) intersectionPoints.push(intersection);
      }
      outQueue.push(segment);
    } else if (event.isLeftEndpoint === false) {
      outQueue.pop();
    }
  }
  return intersectionPoints;
}
var Segment = class {
  /** @param event must have otherEvent non-null */
  constructor(event) {
    this.leftSweepEvent = event;
    this.rightSweepEvent = event.otherEvent;
  }
};
function testSegmentIntersect(seg1, seg2) {
  if (seg1 === null || seg2 === null) return false;
  const x1 = seg1.leftSweepEvent.p.x;
  const y1 = seg1.leftSweepEvent.p.y;
  const x2 = seg1.rightSweepEvent.p.x;
  const y2 = seg1.rightSweepEvent.p.y;
  const x3 = seg2.leftSweepEvent.p.x;
  const y3 = seg2.leftSweepEvent.p.y;
  const x4 = seg2.rightSweepEvent.p.x;
  const y4 = seg2.rightSweepEvent.p.y;
  const score1 = orient2d(x1, y1, x2, y2, x3, y3);
  const score2 = orient2d(x1, y1, x2, y2, x4, y4);
  if (score1 > 0 && score2 > 0) return false;
  else if (score1 < 0 && score2 < 0) return false;
  if (seg1.leftSweepEvent.ringId === seg2.leftSweepEvent.ringId) {
    if (seg1.rightSweepEvent.isSamePoint(seg2.leftSweepEvent) || seg1.rightSweepEvent.isSamePoint(seg2.rightSweepEvent) || seg1.leftSweepEvent.isSamePoint(seg2.leftSweepEvent) || seg1.leftSweepEvent.isSamePoint(seg2.rightSweepEvent))
      return false;
  } else {
    if (seg1.rightSweepEvent.isSamePoint(seg2.leftSweepEvent))
      return seg2.leftSweepEvent.asNewXY();
    if (seg1.rightSweepEvent.isSamePoint(seg2.rightSweepEvent))
      return seg2.rightSweepEvent.asNewXY();
    if (seg1.leftSweepEvent.isSamePoint(seg2.leftSweepEvent))
      return seg2.leftSweepEvent.asNewXY();
    if (seg1.leftSweepEvent.isSamePoint(seg2.rightSweepEvent))
      return seg2.rightSweepEvent.asNewXY();
  }
  const denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1);
  const numeA = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3);
  const numeB = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3);
  if (denom === 0) {
    if (numeA === 0 && numeB === 0) return false;
    return false;
  }
  const uA = numeA / denom;
  const uB = numeB / denom;
  if (uA >= 0 && uA <= 1 && uB >= 0 && uB <= 1) {
    const x = x1 + uA * (x2 - x1);
    const y = y1 + uA * (y2 - y1);
    return [x, y];
  }
  return false;
}
function lineIntersect(line1, line2, options = {}) {
  const { removeDuplicates = true, ignoreSelfIntersections = true } = options;
  let features = [];
  if (line1.type === "FeatureCollection")
    features = features.concat(line1.features);
  else if (line1.type === "Feature") features.push(line1);
  else if (line1.type === "LineString" || line1.type === "Polygon" || line1.type === "MultiLineString" || line1.type === "MultiPolygon") {
    features.push(feature(line1));
  }
  if (line2.type === "FeatureCollection")
    features = features.concat(line2.features);
  else if (line2.type === "Feature") features.push(line2);
  else if (line2.type === "LineString" || line2.type === "Polygon" || line2.type === "MultiLineString" || line2.type === "MultiPolygon") {
    features.push(feature(line2));
  }
  const intersections = sweeplineIntersections(
    featureCollection(features),
    ignoreSelfIntersections
  );
  let results = [];
  if (removeDuplicates) {
    const unique = {};
    intersections.forEach((intersection) => {
      const key = intersection.join(",");
      if (!unique[key]) {
        unique[key] = true;
        results.push(intersection);
      }
    });
  } else {
    results = intersections;
  }
  return featureCollection(results.map((r) => point(r)));
}

// node_modules/@turf/polygon-to-line/dist/esm/index.js
function polygonToLine(poly, options = {}) {
  const geom = getGeom(poly);
  if (!options.properties && poly.type === "Feature") {
    options.properties = poly.properties;
  }
  switch (geom.type) {
    case "Polygon":
      return singlePolygonToLine(geom, options);
    case "MultiPolygon":
      return multiPolygonToLine(geom, options);
    default:
      throw new Error("invalid poly");
  }
}
function singlePolygonToLine(poly, options = {}) {
  const geom = getGeom(poly);
  const coords = geom.coordinates;
  const properties = options.properties ? options.properties : poly.type === "Feature" ? poly.properties : {};
  return coordsToLine(coords, properties);
}
function multiPolygonToLine(multiPoly, options = {}) {
  const geom = getGeom(multiPoly);
  const coords = geom.coordinates;
  const properties = options.properties ? options.properties : multiPoly.type === "Feature" ? multiPoly.properties : {};
  const lines = [];
  coords.forEach((coord) => {
    lines.push(coordsToLine(coord, properties));
  });
  return featureCollection(lines);
}
function coordsToLine(coords, properties) {
  if (coords.length > 1) {
    return multiLineString(coords, properties);
  }
  return lineString(coords[0], properties);
}

// node_modules/@turf/boolean-disjoint/dist/esm/index.js
function booleanDisjoint(feature1, feature2, {
  ignoreSelfIntersections = true
} = { ignoreSelfIntersections: true }) {
  let bool = true;
  flattenEach(feature1, (flatten1) => {
    flattenEach(feature2, (flatten2) => {
      if (bool === false) {
        return false;
      }
      bool = disjoint(
        flatten1.geometry,
        flatten2.geometry,
        ignoreSelfIntersections
      );
    });
  });
  return bool;
}
function disjoint(geom1, geom2, ignoreSelfIntersections) {
  switch (geom1.type) {
    case "Point":
      switch (geom2.type) {
        case "Point":
          return !compareCoords(geom1.coordinates, geom2.coordinates);
        case "LineString":
          return !isPointOnLine(geom2, geom1);
        case "Polygon":
          return !booleanPointInPolygon(geom1, geom2);
      }
      break;
    case "LineString":
      switch (geom2.type) {
        case "Point":
          return !isPointOnLine(geom1, geom2);
        case "LineString":
          return !isLineOnLine(geom1, geom2, ignoreSelfIntersections);
        case "Polygon":
          return !isLineInPoly(geom2, geom1, ignoreSelfIntersections);
      }
      break;
    case "Polygon":
      switch (geom2.type) {
        case "Point":
          return !booleanPointInPolygon(geom2, geom1);
        case "LineString":
          return !isLineInPoly(geom1, geom2, ignoreSelfIntersections);
        case "Polygon":
          return !isPolyInPoly(geom2, geom1, ignoreSelfIntersections);
      }
  }
  return false;
}
function isPointOnLine(lineString2, pt) {
  for (let i = 0; i < lineString2.coordinates.length - 1; i++) {
    if (isPointOnLineSegment(
      lineString2.coordinates[i],
      lineString2.coordinates[i + 1],
      pt.coordinates
    )) {
      return true;
    }
  }
  return false;
}
function isLineOnLine(lineString1, lineString2, ignoreSelfIntersections) {
  const doLinesIntersect = lineIntersect(lineString1, lineString2, {
    ignoreSelfIntersections
  });
  if (doLinesIntersect.features.length > 0) {
    return true;
  }
  for (const coords of lineString1.coordinates) {
    if (isPointOnLine(lineString2, { type: "Point", coordinates: coords })) {
      return true;
    }
  }
  for (const coords of lineString2.coordinates) {
    if (isPointOnLine(lineString1, { type: "Point", coordinates: coords })) {
      return true;
    }
  }
  return false;
}
function isLineInPoly(polygon, lineString2, ignoreSelfIntersections) {
  for (const coord of lineString2.coordinates) {
    if (booleanPointInPolygon(coord, polygon)) {
      return true;
    }
  }
  const doLinesIntersect = lineIntersect(lineString2, polygonToLine(polygon), {
    ignoreSelfIntersections
  });
  if (doLinesIntersect.features.length > 0) {
    return true;
  }
  return false;
}
function isPolyInPoly(feature1, feature2, ignoreSelfIntersections) {
  for (const coord1 of feature1.coordinates[0]) {
    if (booleanPointInPolygon(coord1, feature2)) {
      return true;
    }
  }
  for (const coord2 of feature2.coordinates[0]) {
    if (booleanPointInPolygon(coord2, feature1)) {
      return true;
    }
  }
  const doLinesIntersect = lineIntersect(
    polygonToLine(feature1),
    polygonToLine(feature2),
    { ignoreSelfIntersections }
  );
  if (doLinesIntersect.features.length > 0) {
    return true;
  }
  return false;
}
function isPointOnLineSegment(lineSegmentStart, lineSegmentEnd, pt) {
  const dxc = pt[0] - lineSegmentStart[0];
  const dyc = pt[1] - lineSegmentStart[1];
  const dxl = lineSegmentEnd[0] - lineSegmentStart[0];
  const dyl = lineSegmentEnd[1] - lineSegmentStart[1];
  const cross = dxc * dyl - dyc * dxl;
  if (cross !== 0) {
    return false;
  }
  if (Math.abs(dxl) >= Math.abs(dyl)) {
    if (dxl > 0) {
      return lineSegmentStart[0] <= pt[0] && pt[0] <= lineSegmentEnd[0];
    } else {
      return lineSegmentEnd[0] <= pt[0] && pt[0] <= lineSegmentStart[0];
    }
  } else if (dyl > 0) {
    return lineSegmentStart[1] <= pt[1] && pt[1] <= lineSegmentEnd[1];
  } else {
    return lineSegmentEnd[1] <= pt[1] && pt[1] <= lineSegmentStart[1];
  }
}
function compareCoords(pair1, pair2) {
  return pair1[0] === pair2[0] && pair1[1] === pair2[1];
}
var index_default = booleanDisjoint;

export {
  booleanDisjoint,
  index_default
};
//# sourceMappingURL=chunk-2UO76BCB.js.map
