import {
  booleanPointInPolygon,
  getCoord,
  getCoords,
  getGeom
} from "./chunk-QPRHBWFJ.js";
import "./chunk-EGSHJPUB.js";
import "./chunk-4MBMRILA.js";

// node_modules/@turf/boolean-point-on-line/dist/esm/index.js
function booleanPointOnLine(pt, line, options = {}) {
  const ptCoords = getCoord(pt);
  const lineCoords = getCoords(line);
  for (let i = 0; i < lineCoords.length - 1; i++) {
    let ignoreBoundary = false;
    if (options.ignoreEndVertices) {
      if (i === 0) {
        ignoreBoundary = "start";
      }
      if (i === lineCoords.length - 2) {
        ignoreBoundary = "end";
      }
      if (i === 0 && i + 1 === lineCoords.length - 1) {
        ignoreBoundary = "both";
      }
    }
    if (isPointOnLineSegment(
      lineCoords[i],
      lineCoords[i + 1],
      ptCoords,
      ignoreBoundary,
      typeof options.epsilon === "undefined" ? null : options.epsilon
    )) {
      return true;
    }
  }
  return false;
}
function isPointOnLineSegment(lineSegmentStart, lineSegmentEnd, pt, excludeBoundary, epsilon) {
  const x = pt[0];
  const y = pt[1];
  const x1 = lineSegmentStart[0];
  const y1 = lineSegmentStart[1];
  const x2 = lineSegmentEnd[0];
  const y2 = lineSegmentEnd[1];
  const dxc = pt[0] - x1;
  const dyc = pt[1] - y1;
  const dxl = x2 - x1;
  const dyl = y2 - y1;
  const cross = dxc * dyl - dyc * dxl;
  if (epsilon !== null) {
    if (Math.abs(cross) > epsilon) {
      return false;
    }
  } else if (cross !== 0) {
    return false;
  }
  if (Math.abs(dxl) === Math.abs(dyl) && Math.abs(dxl) === 0) {
    if (excludeBoundary) {
      return false;
    }
    if (pt[0] === lineSegmentStart[0] && pt[1] === lineSegmentStart[1]) {
      return true;
    } else {
      return false;
    }
  }
  if (!excludeBoundary) {
    if (Math.abs(dxl) >= Math.abs(dyl)) {
      return dxl > 0 ? x1 <= x && x <= x2 : x2 <= x && x <= x1;
    }
    return dyl > 0 ? y1 <= y && y <= y2 : y2 <= y && y <= y1;
  } else if (excludeBoundary === "start") {
    if (Math.abs(dxl) >= Math.abs(dyl)) {
      return dxl > 0 ? x1 < x && x <= x2 : x2 <= x && x < x1;
    }
    return dyl > 0 ? y1 < y && y <= y2 : y2 <= y && y < y1;
  } else if (excludeBoundary === "end") {
    if (Math.abs(dxl) >= Math.abs(dyl)) {
      return dxl > 0 ? x1 <= x && x < x2 : x2 < x && x <= x1;
    }
    return dyl > 0 ? y1 <= y && y < y2 : y2 < y && y <= y1;
  } else if (excludeBoundary === "both") {
    if (Math.abs(dxl) >= Math.abs(dyl)) {
      return dxl > 0 ? x1 < x && x < x2 : x2 < x && x < x1;
    }
    return dyl > 0 ? y1 < y && y < y2 : y2 < y && y < y1;
  }
  return false;
}

// node_modules/@turf/boolean-touches/dist/esm/index.js
function booleanTouches(feature1, feature2) {
  var geom1 = getGeom(feature1);
  var geom2 = getGeom(feature2);
  var type1 = geom1.type;
  var type2 = geom2.type;
  switch (type1) {
    case "Point":
      switch (type2) {
        case "LineString":
          return isPointOnLineEnd(geom1, geom2);
        case "MultiLineString":
          var foundTouchingPoint = false;
          for (var ii = 0; ii < geom2.coordinates.length; ii++) {
            if (isPointOnLineEnd(geom1, {
              type: "LineString",
              coordinates: geom2.coordinates[ii]
            }))
              foundTouchingPoint = true;
          }
          return foundTouchingPoint;
        case "Polygon":
          for (var i = 0; i < geom2.coordinates.length; i++) {
            if (booleanPointOnLine(geom1, {
              type: "LineString",
              coordinates: geom2.coordinates[i]
            }))
              return true;
          }
          return false;
        case "MultiPolygon":
          for (var i = 0; i < geom2.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates[i].length; ii++) {
              if (booleanPointOnLine(geom1, {
                type: "LineString",
                coordinates: geom2.coordinates[i][ii]
              }))
                return true;
            }
          }
          return false;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    case "MultiPoint":
      switch (type2) {
        case "LineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (isPointOnLineEnd(
                { type: "Point", coordinates: geom1.coordinates[i] },
                geom2
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointOnLine(
              { type: "Point", coordinates: geom1.coordinates[i] },
              geom2,
              { ignoreEndVertices: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "MultiLineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (isPointOnLineEnd(
                  { type: "Point", coordinates: geom1.coordinates[i] },
                  { type: "LineString", coordinates: geom2.coordinates[ii] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom1.coordinates[i] },
                { type: "LineString", coordinates: geom2.coordinates[ii] },
                { ignoreEndVertices: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "Polygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom1.coordinates[i] },
                { type: "LineString", coordinates: geom2.coordinates[0] }
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom1.coordinates[i] },
              geom2,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "MultiPolygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[i] },
                  {
                    type: "LineString",
                    coordinates: geom2.coordinates[ii][0]
                  }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom1.coordinates[i] },
                { type: "Polygon", coordinates: geom2.coordinates[ii] },
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    case "LineString":
      switch (type2) {
        case "Point":
          return isPointOnLineEnd(geom2, geom1);
        case "MultiPoint":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (isPointOnLineEnd(
                { type: "Point", coordinates: geom2.coordinates[i] },
                geom1
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointOnLine(
              { type: "Point", coordinates: geom2.coordinates[i] },
              geom1,
              { ignoreEndVertices: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "LineString":
          var endMatch = false;
          if (isPointOnLineEnd(
            { type: "Point", coordinates: geom1.coordinates[0] },
            geom2
          ))
            endMatch = true;
          if (isPointOnLineEnd(
            {
              type: "Point",
              coordinates: geom1.coordinates[geom1.coordinates.length - 1]
            },
            geom2
          ))
            endMatch = true;
          if (endMatch === false) return false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (booleanPointOnLine(
              { type: "Point", coordinates: geom1.coordinates[i] },
              geom2,
              { ignoreEndVertices: true }
            ))
              return false;
          }
          return endMatch;
        case "MultiLineString":
          var endMatch = false;
          for (var i = 0; i < geom2.coordinates.length; i++) {
            if (isPointOnLineEnd(
              { type: "Point", coordinates: geom1.coordinates[0] },
              { type: "LineString", coordinates: geom2.coordinates[i] }
            ))
              endMatch = true;
            if (isPointOnLineEnd(
              {
                type: "Point",
                coordinates: geom1.coordinates[geom1.coordinates.length - 1]
              },
              { type: "LineString", coordinates: geom2.coordinates[i] }
            ))
              endMatch = true;
            for (var ii = 0; ii < geom1.coordinates[i].length; ii++) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom1.coordinates[ii] },
                { type: "LineString", coordinates: geom2.coordinates[i] },
                { ignoreEndVertices: true }
              ))
                return false;
            }
          }
          return endMatch;
        case "Polygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom1.coordinates[i] },
                { type: "LineString", coordinates: geom2.coordinates[0] }
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom1.coordinates[i] },
              geom2,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "MultiPolygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[i] },
                  {
                    type: "LineString",
                    coordinates: geom2.coordinates[ii][0]
                  }
                ))
                  foundTouchingPoint = true;
              }
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom1.coordinates[i] },
              geom2,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    case "MultiLineString":
      switch (type2) {
        case "Point":
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (isPointOnLineEnd(geom2, {
              type: "LineString",
              coordinates: geom1.coordinates[i]
            }))
              return true;
          }
          return false;
        case "MultiPoint":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (isPointOnLineEnd(
                  { type: "Point", coordinates: geom2.coordinates[ii] },
                  { type: "LineString", coordinates: geom1.coordinates[ii] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom2.coordinates[ii] },
                { type: "LineString", coordinates: geom1.coordinates[ii] },
                { ignoreEndVertices: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "LineString":
          var endMatch = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (isPointOnLineEnd(
              { type: "Point", coordinates: geom1.coordinates[i][0] },
              geom2
            ))
              endMatch = true;
            if (isPointOnLineEnd(
              {
                type: "Point",
                coordinates: geom1.coordinates[i][geom1.coordinates[i].length - 1]
              },
              geom2
            ))
              endMatch = true;
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom2.coordinates[ii] },
                { type: "LineString", coordinates: geom1.coordinates[i] },
                { ignoreEndVertices: true }
              ))
                return false;
            }
          }
          return endMatch;
        case "MultiLineString":
          var endMatch = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (isPointOnLineEnd(
                { type: "Point", coordinates: geom1.coordinates[i][0] },
                { type: "LineString", coordinates: geom2.coordinates[ii] }
              ))
                endMatch = true;
              if (isPointOnLineEnd(
                {
                  type: "Point",
                  coordinates: geom1.coordinates[i][geom1.coordinates[i].length - 1]
                },
                { type: "LineString", coordinates: geom2.coordinates[ii] }
              ))
                endMatch = true;
              for (var iii = 0; iii < geom1.coordinates[i].length; iii++) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[i][iii] },
                  { type: "LineString", coordinates: geom2.coordinates[ii] },
                  { ignoreEndVertices: true }
                ))
                  return false;
              }
            }
          }
          return endMatch;
        case "Polygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom1.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[i][ii] },
                  { type: "LineString", coordinates: geom2.coordinates[0] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom1.coordinates[i][ii] },
                geom2,
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "MultiPolygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom1.coordinates.length; ii++) {
              for (var iii = 0; iii < geom1.coordinates[ii].length; iii++) {
                if (!foundTouchingPoint) {
                  if (booleanPointOnLine(
                    {
                      type: "Point",
                      coordinates: geom1.coordinates[ii][iii]
                    },
                    {
                      type: "LineString",
                      coordinates: geom2.coordinates[0][i]
                    }
                  ))
                    foundTouchingPoint = true;
                }
                if (booleanPointInPolygon(
                  { type: "Point", coordinates: geom1.coordinates[ii][iii] },
                  { type: "Polygon", coordinates: [geom2.coordinates[0][i]] },
                  { ignoreBoundary: true }
                ))
                  return false;
              }
            }
          }
          return foundTouchingPoint;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    case "Polygon":
      switch (type2) {
        case "Point":
          for (var i = 0; i < geom1.coordinates.length; i++) {
            if (booleanPointOnLine(geom2, {
              type: "LineString",
              coordinates: geom1.coordinates[i]
            }))
              return true;
          }
          return false;
        case "MultiPoint":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom2.coordinates[i] },
                { type: "LineString", coordinates: geom1.coordinates[0] }
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom2.coordinates[i] },
              geom1,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "LineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates.length; i++) {
            if (!foundTouchingPoint) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom2.coordinates[i] },
                { type: "LineString", coordinates: geom1.coordinates[0] }
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom2.coordinates[i] },
              geom1,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "MultiLineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates[i].length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom2.coordinates[i][ii] },
                  { type: "LineString", coordinates: geom1.coordinates[0] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom2.coordinates[i][ii] },
                geom1,
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "Polygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            if (!foundTouchingPoint) {
              if (booleanPointOnLine(
                { type: "Point", coordinates: geom1.coordinates[0][i] },
                { type: "LineString", coordinates: geom2.coordinates[0] }
              ))
                foundTouchingPoint = true;
            }
            if (booleanPointInPolygon(
              { type: "Point", coordinates: geom1.coordinates[0][i] },
              geom2,
              { ignoreBoundary: true }
            ))
              return false;
          }
          return foundTouchingPoint;
        case "MultiPolygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom2.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom1.coordinates[0].length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[0][ii] },
                  { type: "LineString", coordinates: geom2.coordinates[0][i] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom1.coordinates[0][ii] },
                { type: "Polygon", coordinates: geom2.coordinates[0][i] },
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    case "MultiPolygon":
      switch (type2) {
        case "Point":
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            if (booleanPointOnLine(geom2, {
              type: "LineString",
              coordinates: geom1.coordinates[0][i]
            }))
              return true;
          }
          return false;
        case "MultiPoint":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom2.coordinates[ii] },
                  { type: "LineString", coordinates: geom1.coordinates[0][i] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom2.coordinates[ii] },
                { type: "Polygon", coordinates: geom1.coordinates[0][i] },
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "LineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom2.coordinates[ii] },
                  { type: "LineString", coordinates: geom1.coordinates[0][i] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom2.coordinates[ii] },
                { type: "Polygon", coordinates: geom1.coordinates[0][i] },
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "MultiLineString":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates.length; i++) {
            for (var ii = 0; ii < geom2.coordinates.length; ii++) {
              for (var iii = 0; iii < geom2.coordinates[ii].length; iii++) {
                if (!foundTouchingPoint) {
                  if (booleanPointOnLine(
                    {
                      type: "Point",
                      coordinates: geom2.coordinates[ii][iii]
                    },
                    {
                      type: "LineString",
                      coordinates: geom1.coordinates[i][0]
                    }
                  ))
                    foundTouchingPoint = true;
                }
                if (booleanPointInPolygon(
                  { type: "Point", coordinates: geom2.coordinates[ii][iii] },
                  { type: "Polygon", coordinates: [geom1.coordinates[i][0]] },
                  { ignoreBoundary: true }
                ))
                  return false;
              }
            }
          }
          return foundTouchingPoint;
        case "Polygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom1.coordinates[0][i].length; ii++) {
              if (!foundTouchingPoint) {
                if (booleanPointOnLine(
                  { type: "Point", coordinates: geom1.coordinates[0][i][ii] },
                  { type: "LineString", coordinates: geom2.coordinates[0] }
                ))
                  foundTouchingPoint = true;
              }
              if (booleanPointInPolygon(
                { type: "Point", coordinates: geom1.coordinates[0][i][ii] },
                geom2,
                { ignoreBoundary: true }
              ))
                return false;
            }
          }
          return foundTouchingPoint;
        case "MultiPolygon":
          var foundTouchingPoint = false;
          for (var i = 0; i < geom1.coordinates[0].length; i++) {
            for (var ii = 0; ii < geom2.coordinates[0].length; ii++) {
              for (var iii = 0; iii < geom1.coordinates[0].length; iii++) {
                if (!foundTouchingPoint) {
                  if (booleanPointOnLine(
                    {
                      type: "Point",
                      coordinates: geom1.coordinates[0][i][iii]
                    },
                    {
                      type: "LineString",
                      coordinates: geom2.coordinates[0][ii]
                    }
                  ))
                    foundTouchingPoint = true;
                }
                if (booleanPointInPolygon(
                  {
                    type: "Point",
                    coordinates: geom1.coordinates[0][i][iii]
                  },
                  { type: "Polygon", coordinates: geom2.coordinates[0][ii] },
                  { ignoreBoundary: true }
                ))
                  return false;
              }
            }
          }
          return foundTouchingPoint;
        default:
          throw new Error("feature2 " + type2 + " geometry not supported");
      }
    default:
      throw new Error("feature1 " + type1 + " geometry not supported");
  }
}
function isPointOnLineEnd(point, line) {
  if (compareCoords(line.coordinates[0], point.coordinates)) return true;
  if (compareCoords(
    line.coordinates[line.coordinates.length - 1],
    point.coordinates
  ))
    return true;
  return false;
}
function compareCoords(pair1, pair2) {
  return pair1[0] === pair2[0] && pair1[1] === pair2[1];
}
var index_default = booleanTouches;
export {
  booleanTouches,
  index_default as default
};
//# sourceMappingURL=@turf_boolean-touches.js.map
