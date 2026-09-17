/** Xóa can thiệp do E2E tạo ra (nội dung bắt đầu bằng "[e2e]") để không để lại dữ liệu rác. */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

export default function globalTeardown() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
  const result = spawnSync(process.env.E2E_PYTHON ?? "python", ["scripts/e2e_cleanup.py"], { cwd: root, encoding: "utf-8" });
  if (result.status !== 0) console.warn(`[e2e] Không dọn được dữ liệu test: ${result.stderr || result.error}`);
  else process.stdout.write(result.stdout);
}
