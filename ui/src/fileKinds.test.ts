import { describe, expect, it } from "vitest";
import { kindOf, parseCsv, prettyJson } from "./fileKinds";

describe("file kinds", () => {
  it("is decided by the extension, in any case; unknown ones are other", () => {
    expect(["a.PDF", "b.jpeg", "c.CSV", "d.json", "e.md", "f.zip", "noext"].map(kindOf)).toEqual(["pdf", "image", "csv", "json", "text", "other", "other"]);
  });

  it("reads quoted cells, doubled quotes, line breaks inside quotes and Windows line ends", () => {
    expect(parseCsv('name,note\r\n"Smith, J","said ""hi""\nthere"\r\nplain,\r\n')).toEqual([["name", "note"], ["Smith, J", 'said "hi"\nthere'], ["plain", ""]]);
  });

  it("handles tab-separated files and a missing final newline, and drops blank lines", () => {
    expect(parseCsv("a\tb\n1\t2\n\n3\t4", "\t")).toEqual([["a", "b"], ["1", "2"], ["3", "4"]]);
  });

  it("pretty prints JSON and leaves broken JSON alone", () => {
    expect(prettyJson('{"a":[1,2]}')).toBe('{\n  "a": [\n    1,\n    2\n  ]\n}');
    expect(prettyJson('{"a": ')).toBe('{"a": ');
  });
});
