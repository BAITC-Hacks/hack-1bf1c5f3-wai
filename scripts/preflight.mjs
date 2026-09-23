import { existsSync } from "node:fs";
import { execFileSync } from "node:child_process";

const checks = [
  ["Node.js 20+", () => Number(process.versions.node.split(".")[0]) >= 20],
  ["package.json", () => existsSync("package.json")],
  [".env.local (optional; enables live AI)", () => existsSync(".env.local")],
];

for (const [name, test] of checks) console.log(`${test() ? "PASS" : "WARN"}  ${name}`);
try { console.log(`PASS  ${execFileSync("git", ["--version"]).toString().trim()}`); }
catch { console.log("WARN  Git is not available"); }
console.log("\nDemo mode works without OPENAI_API_KEY. Do not paste keys into chat, source files, or Git.");

