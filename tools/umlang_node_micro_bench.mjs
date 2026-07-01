import { performance } from "node:perf_hooks";

const lines = Number.parseInt(process.argv[2] ?? "100000", 10);
const iterations = Number.parseInt(process.argv[3] ?? "7", 10);

function microSource(lineCount) {
  const rows = ["어떻게", "엄.....", "어엄..."];
  for (let i = 0; i < lineCount; i += 1) {
    const slot = 2 + (i % 31);
    rows.push(`${"어".repeat(slot)}엄어... 어어,`);
  }
  rows.push("이 사람이름이냐ㅋㅋ");
  return rows.join("\n");
}

function parseExprTerm(term) {
  let loadCount = 0;
  let offset = 0;
  for (const ch of term) {
    if (ch === "어") {
      loadCount += 1;
    } else if (ch === ".") {
      offset += 1;
    } else if (ch === ",") {
      offset -= 1;
    }
  }
  return { loadVar: loadCount > 0 ? loadCount : 0, offset };
}

function parseExpr(expr) {
  const terms = [];
  for (const term of expr.split(" ")) {
    if (term.length > 0) {
      terms.push(parseExprTerm(term));
    }
  }
  return terms;
}

function parseStatement(code) {
  const splitIndex = code.indexOf("엄");
  if (splitIndex < 0) {
    throw new Error(`unknown statement: ${code}`);
  }
  const left = code.slice(0, splitIndex);
  const right = code.slice(splitIndex + 1);
  return {
    op: "assign",
    index: [...left].filter((ch) => ch === "어").length + 1,
    expr: parseExpr(right),
  };
}

function parse(source) {
  const raw = source.replaceAll("\r\n", "\n").replaceAll("\r", "\n").split("\n");
  if (raw[0].trim() !== "어떻게") {
    throw new Error("program must start with 어떻게");
  }
  const instructions = [];
  for (let i = 1; i < raw.length; i += 1) {
    const line = raw[i].trim();
    if (line === "이 사람이름이냐ㅋㅋ") {
      break;
    }
    instructions.push(line.length === 0 ? { op: "noop" } : line);
  }
  return instructions;
}

function evalExpr(vars, expr) {
  if (expr.length === 0) {
    return 0;
  }
  let result = 1;
  for (const term of expr) {
    const loaded = term.loadVar > 0 ? vars[term.loadVar] ?? 0 : 0;
    result = Math.imul(result, loaded + term.offset);
  }
  return result | 0;
}

function run(instructions) {
  const vars = new Int32Array(4096);
  for (let pc = 0; pc < instructions.length; pc += 1) {
    let instruction = instructions[pc];
    if (typeof instruction === "string") {
      instruction = parseStatement(instruction);
      instructions[pc] = instruction;
    }
    if (instruction.op === "assign") {
      vars[instruction.index] = evalExpr(vars, instruction.expr);
    }
  }
}

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const mean = sorted.reduce((sum, value) => sum + value, 0) / sorted.length;
  return {
    mean,
    median: sorted[Math.floor(sorted.length / 2)],
    min: sorted[0],
    max: sorted[sorted.length - 1],
  };
}

const source = microSource(lines);
const parseTimes = [];
const runTimes = [];
const totalTimes = [];

for (let i = 0; i < iterations; i += 1) {
  const start = performance.now();
  const instructions = parse(source);
  const parsed = performance.now();
  run(instructions);
  const ended = performance.now();
  parseTimes.push(parsed - start);
  runTimes.push(ended - parsed);
  totalTimes.push(ended - start);
}

const parseStats = stats(parseTimes);
const runStats = stats(runTimes);
const totalStats = stats(totalTimes);
const throughput = lines / (runStats.mean / 1000);

console.log(
  "runtime,workload,iterations,units,parse_mean_ms,run_mean_ms,total_mean_ms,total_median_ms,throughput_units_per_s,total_min_ms,total_max_ms",
);
console.log(
  [
    "node",
    "micro_assign_expr",
    iterations,
    lines,
    parseStats.mean.toFixed(3),
    runStats.mean.toFixed(3),
    totalStats.mean.toFixed(3),
    totalStats.median.toFixed(3),
    throughput.toFixed(0),
    totalStats.min.toFixed(3),
    totalStats.max.toFixed(3),
  ].join(","),
);
