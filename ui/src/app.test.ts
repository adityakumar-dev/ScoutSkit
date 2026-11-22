import { describe, expect, it } from "vitest";
import { hashFor, runFromHash } from "./App";

describe("run addresses", () => {
  it("reads a run id from the address, and only a real one", () => {
    expect(runFromHash("#/run/20261122-223830")).toBe("20261122-223830");
    expect(runFromHash("#/run/20261122-223830-2")).toBe("20261122-223830-2");
    for (const bad of ["", "#/", "#/run/", "#/run/../../etc", "#/run/20261122-223830/extra", "#/run/abc"]) expect(runFromHash(bad)).toBeNull();
  });

  it("writes the address for a run, or the start page", () => {
    expect(hashFor("20261122-223830")).toBe("#/run/20261122-223830");
    expect(hashFor(null)).toBe("#/");
    expect(runFromHash(hashFor("20261122-223830-3"))).toBe("20261122-223830-3");
  });
});
