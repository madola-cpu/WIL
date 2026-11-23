// Call Phase 4 from a Node backend, two ways:
//   1. runPipelineCli  - runs the Python package directly (no server needed)
//   2. runPipelineHttp - calls the HTTP service started with `python -m phase4 serve`
// Both return the PipelineResult described in contracts/phase4.d.ts.
//
// Demo:  node examples/node/phase4_client.mjs
import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const PHASE4_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

/**
 * Phase 3 output in, everything Phase 5 needs out, via the Python CLI.
 * @param {unknown} phase3 what steps 7 and 8 produced
 * @param {{profile?: string, expected?: string, python?: string, cwd?: string}} [opts]
 * @returns {Promise<import("../../contracts/phase4").PipelineResult>}
 */
export function runPipelineCli(phase3, opts = {}) {
  const { profile = "veloran", expected, python = process.env.PYTHON || "python3", cwd = PHASE4_DIR } = opts;
  const args = ["-m", "phase4", "pipeline", "-", "--json"];
  if (profile) args.push("--profile", profile);
  if (expected) args.push("--expected", expected);
  return new Promise((resolve, reject) => {
    const child = spawn(python, args, { cwd });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(JSON.parse(out));
      else reject(new Error(err.trim() || `phase4 exited with code ${code}`));
    });
    child.stdin.end(JSON.stringify(phase3));
  });
}

/**
 * Same result through the HTTP service.
 * @param {unknown} phase3
 * @param {{profile?: string, expected?: string, baseUrl?: string}} [opts]
 * @returns {Promise<import("../../contracts/phase4").PipelineResult>}
 */
export async function runPipelineHttp(phase3, opts = {}) {
  const { profile = "veloran", expected, baseUrl = "http://127.0.0.1:8040" } = opts;
  const res = await fetch(`${baseUrl}/phase4/pipeline`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phase3, profile, expected }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error((body.errors || [body.error]).join("\n"));
  return body;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const phase3 = JSON.parse(await readFile(path.join(PHASE4_DIR, "examples/phase3/veloran_step7_8.json"), "utf8"));
  const result = await runPipelineCli(phase3, { profile: "veloran", expected: "veloran" });
  const h = result.manager_view.headline;
  console.log(`${h.annual_savings.display} a year for ${h.year_one_cost.display}, payback ${h.payback.display}`);
  console.log(`Scorecard: ${result.scorecard?.matched} of ${result.scorecard?.checks} numbers match the reference`);
}
