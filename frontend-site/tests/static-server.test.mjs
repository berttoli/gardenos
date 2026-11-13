import assert from "node:assert/strict";
import test from "node:test";
import { serve } from "../serve.mjs";

async function request(url, method = "GET") {
  const result = { status: 0, headers: {}, body: undefined };
  await serve(
    { method, url },
    {
      writeHead(status, headers = {}) {
        result.status = status;
        result.headers = headers;
      },
      end(body) {
        result.body = body;
      },
    },
  );
  return result;
}

test("static server serves the built app and supports HEAD", async () => {
  const page = await request("/");
  assert.equal(page.status, 200);
  assert.match(page.headers["Content-Type"], /^text\/html/);
  assert.match(page.body.toString(), /id="root"/);

  const head = await request("/", "HEAD");
  assert.equal(head.status, 200);
  assert.equal(head.body, undefined);
});

test("static server rejects writes and malformed or escaping paths", async () => {
  assert.equal((await request("/", "POST")).status, 405);
  assert.equal((await request("/%ZZ")).status, 400);
  assert.equal((await request("/..%2fpackage.json")).status, 403);
  assert.equal((await request("/missing-script.js")).status, 404);
});
