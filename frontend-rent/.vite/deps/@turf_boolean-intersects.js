import {
  booleanDisjoint
} from "./chunk-2UO76BCB.js";
import "./chunk-QPRHBWFJ.js";
import "./chunk-GH4D7NQT.js";
import "./chunk-EGSHJPUB.js";
import "./chunk-4MBMRILA.js";

// node_modules/@turf/boolean-intersects/dist/esm/index.js
function booleanIntersects(feature1, feature2, {
  ignoreSelfIntersections = true
} = {}) {
  return !booleanDisjoint(feature1, feature2, { ignoreSelfIntersections });
}
var index_default = booleanIntersects;
export {
  booleanIntersects,
  index_default as default
};
//# sourceMappingURL=@turf_boolean-intersects.js.map
