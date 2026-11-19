import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import RentPendingNotice, { PENDING_NOTICE } from "../../src/components/RentPendingNotice";

test("보류 건수가 있으면 확인 문구를 보이고, 없으면 비운다", () => {
  const shown = renderToStaticMarkup(<RentPendingNotice pendingN={2} />);
  assert.ok(shown.includes(PENDING_NOTICE));
  assert.equal(PENDING_NOTICE, "확인되지 않은 거래 포함");
  assert.equal(renderToStaticMarkup(<RentPendingNotice pendingN={0} />), "");
  assert.equal(renderToStaticMarkup(<RentPendingNotice />), "");
});
