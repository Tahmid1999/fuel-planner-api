const nextJest = require("next/jest");

module.exports = nextJest({ dir: "./" })({
  testEnvironment: "jsdom",
  // antd forms in jsdom are slow on a cold run
  testTimeout: 30000,
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/$1" },
});
