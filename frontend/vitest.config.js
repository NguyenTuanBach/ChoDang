import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Test giao diện: `npm test`. jsdom + React Testing Library; API được mock trong từng test (không cần backend).
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    include: ["src/**/*.test.{js,jsx}"],
  },
});
